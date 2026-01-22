"""
Brief: Run indicator extraction diagnostics on a single markdown file.

Inputs:
- --markdown: path to combined_markdown.md (required)
- --output-dir: directory for diagnostic JSON outputs (optional)
- --model: override extraction model (optional)
- --max-rounds: override max rounds per class (optional)
- --timeout: request timeout in seconds (optional)
- --modes: subset of {indicator, indicator_value, indicator_with_values} (optional)
- Env: OPENAI_API_KEY or OPENROUTER_API_KEY; optional OPENAI_BASE_URL

Outputs:
- Indicator.json, IndicatorValue.json, IndicatorWithValues.json under --output-dir
- Debug logs under extraction/debug_logs (unless cleaned)

Usage (from project root):
- python -m extraction.scripts.indicator_diagnostics --markdown output/pdf2markdown/<run>/combined_markdown.md
"""

from __future__ import annotations

import argparse
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from openai import OpenAI
import tiktoken

from utils import load_llm_config, setup_logger
from extraction.utils import (
    clean_debug_logs,
    load_config,
    load_markdown,
    load_prompt,
    select_provider,
)
from extraction.extract import run_class_extraction

LOGGER = logging.getLogger(__name__)

MODES = ("indicator", "indicator_value", "indicator_with_values")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Run indicator extraction diagnostics.")
    parser.add_argument(
        "--markdown",
        required=True,
        type=Path,
        help="Path to combined_markdown.md.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write diagnostic outputs (default: output/indicator_diagnostics/<timestamp>_<stem>).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override extraction model (defaults to llm_config.yml extraction.model).",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Maximum tool rounds per class (defaults to extraction config).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Request timeout in seconds (default: 180).",
    )
    parser.add_argument(
        "--modes",
        nargs="*",
        choices=MODES,
        default=list(MODES),
        help="Subset of extractions to run.",
    )
    parser.add_argument(
        "--no-clean-logs",
        action="store_true",
        help="Do not clean extraction/debug_logs before running.",
    )
    return parser.parse_args()


def resolve_output_dir(markdown_path: Path, output_dir: Path | None) -> Path:
    """Resolve the output directory for diagnostics."""
    if output_dir:
        return output_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path("output") / "indicator_diagnostics" / f"{timestamp}_{markdown_path.stem}"


def run_modes(
    *,
    modes: Iterable[str],
    client: OpenAI,
    model_name: str,
    extra_body: dict | None,
    system_prompt: str,
    user_template: str,
    markdown_text: str,
    output_dir: Path,
    max_rounds: int,
    config: dict,
) -> None:
    """Run indicator extraction modes."""
    from database.schemas import Indicator
    from extraction.schemas_verified import VerifiedIndicatorValue, IndicatorWithValues

    for mode in modes:
        if mode == "indicator":
            run_class_extraction(
                client=client,
                model_name=model_name,
                extra_body=extra_body,
                system_prompt=system_prompt,
                user_template=user_template,
                markdown_text=markdown_text,
                model_cls=Indicator,
                db_model_name="Indicator",
                output_dir=output_dir,
                max_rounds=max_rounds,
                config=config,
            )
        elif mode == "indicator_value":
            run_class_extraction(
                client=client,
                model_name=model_name,
                extra_body=extra_body,
                system_prompt=system_prompt,
                user_template=user_template,
                markdown_text=markdown_text,
                model_cls=VerifiedIndicatorValue,
                db_model_name="IndicatorValue",
                output_dir=output_dir,
                max_rounds=max_rounds,
                config=config,
            )
        elif mode == "indicator_with_values":
            run_class_extraction(
                client=client,
                model_name=model_name,
                extra_body=extra_body,
                system_prompt=system_prompt,
                user_template=user_template,
                markdown_text=markdown_text,
                model_cls=IndicatorWithValues,
                db_model_name="IndicatorWithValues",
                output_dir=output_dir,
                max_rounds=max_rounds,
                config=config,
            )


def main() -> int:
    """Script entry point."""
    args = parse_args()
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or OPENROUTER_API_KEY must be set.")

    config = load_config()
    llm_cfg = load_llm_config().get("extraction", {})

    if not args.no_clean_logs:
        clean_debug_logs()

    model_name = args.model or llm_cfg.get("model") or config.get("model")
    if not model_name:
        raise RuntimeError(
            "Model must be specified in llm_config.yml (extraction.model) or via --model."
        )

    provider = select_provider(llm_cfg, config, env_prefix="EXTRACTION")
    extra_body = {"provider": provider} if provider else None

    token_limit = config.get("token_limit", 900000)
    max_rounds = args.max_rounds or config.get("max_rounds", 12)

    markdown_text = load_markdown(args.markdown)
    enc = tiktoken.get_encoding("cl100k_base")
    token_count = len(enc.encode(markdown_text))
    if token_count > token_limit:
        LOGGER.error("File too large: %d tokens (limit: %d)", token_count, token_limit)
        return 1

    system_prompt = load_prompt("system.md")
    user_template = load_prompt("class_prompt.md")

    base_url = config.get("base_url") or os.getenv("OPENAI_BASE_URL")
    if not base_url and os.getenv("OPENROUTER_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"

    output_dir = resolve_output_dir(args.markdown, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    LOGGER.info("Diagnostics output dir: %s", output_dir)
    LOGGER.info("Modes: %s", ", ".join(args.modes))

    client = OpenAI(
        api_key=api_key,
        base_url=base_url or None,
        timeout=args.timeout,
    )

    run_modes(
        modes=args.modes,
        client=client,
        model_name=model_name,
        extra_body=extra_body,
        system_prompt=system_prompt,
        user_template=user_template,
        markdown_text=markdown_text,
        output_dir=output_dir,
        max_rounds=max_rounds,
        config=config,
    )

    LOGGER.info("Diagnostics completed.")
    return 0


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
