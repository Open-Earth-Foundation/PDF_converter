"""
Extraction engine for parsing Pydantic model instances from Markdown.

Usage:
    python -m extraction.scripts.extract --markdown path/to/combined_markdown.md [--output-dir extraction/output]

Flags:
- --markdown: path to combined_markdown.md (required)
- --output-dir: directory for extracted JSON (default: extraction/output)
- --model/--max-rounds/--class-names/--log-level: overrides for runtime settings
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
from pathlib import Path
from typing import Type

from dotenv import load_dotenv
from openai import OpenAI, APIStatusError
import tiktoken
from pydantic import BaseModel

from utils import load_llm_config
from extraction.utils import (
    load_config,
    load_prompt,
    load_class_context,
    clean_debug_logs,
    load_markdown,
    load_existing,
    persist_instances,
    escape_braces,
    extract_model_classes,
    to_json_ready,
    summarise_instances,
    parse_record_instances,
    truncate,
    log_full_response,
)
from extraction.tools import get_all_tools

LOGGER = logging.getLogger(__name__)

# Load tool definitions from tools module
TOOLS = get_all_tools()


def run_class_extraction(
    *,
    client: OpenAI,
    model_name: str,
    system_prompt: str,
    user_template: str,
    markdown_text: str,
    model_cls: Type[BaseModel],
    output_dir: Path,
    max_rounds: int,
    config: dict | None = None,
) -> None:
    """
    Run extraction for a single Pydantic model class using chat.completions with tools.

    Args mirror the CLI entry point.
    """
    output_path = output_dir / f"{model_cls.__name__}.json"
    stored_instances = load_existing(output_path)
    seen_hashes = {json.dumps(entry, sort_keys=True, ensure_ascii=False) for entry in stored_instances}

    class_context = escape_braces(load_class_context(model_cls.__name__))
    user_prompt = user_template.format(
        class_name=model_cls.__name__,
        class_context=class_context,
        json_schema=escape_braces(json.dumps(model_cls.model_json_schema(by_alias=True), indent=2)),
        existing_summary=escape_braces(summarise_instances(stored_instances)),
        markdown=escape_braces(markdown_text),
    )

    LOGGER.info("Starting extraction for %s (existing %d records).", model_cls.__name__, len(stored_instances))
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for round_idx in range(1, max_rounds + 1):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=TOOLS,
                tool_choice="required",
            )
        except APIStatusError as exc:
            if getattr(exc, "status_code", None) == 404 and "tool_choice" in str(exc).lower():
                LOGGER.warning(
                    "tool_choice='required' not supported by model %s; retrying with tool_choice='auto'.",
                    model_name,
                )
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                )
            else:
                raise

        if not getattr(response, "choices", None):
            LOGGER.warning(
                "No choices returned for %s (round %d); aborting extraction.",
                model_cls.__name__,
                round_idx,
            )
            break

        # Persist full raw response for debugging (works for chat.completions too)
        log_full_response(model_cls.__name__, response, round_idx, config)

        choice = response.choices[0].message
        tool_calls = choice.tool_calls or []
        if not tool_calls:
            preview_text = truncate(choice.content or "", 160) if choice.content else "(no text)"
            LOGGER.warning(
                "No tool calls returned for %s (round %d). Assistant said: %s",
                model_cls.__name__,
                round_idx,
                preview_text,
            )
            break

        # Keep conversation history by adding the assistant turn with tool calls
        messages.append(
            {
                "role": "assistant",
                "content": choice.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        extracted_complete = False
        tool_messages: list[dict] = []

        for tc in tool_calls:
            name = tc.function.name
            args = tc.function.arguments or "{}"
            fake_call = type("ToolCall", (), {"name": name, "arguments": args, "call_id": tc.id})

            if name == "record_instances":
                payload, added = parse_record_instances(fake_call, model_cls, seen_hashes, stored_instances)
                if added:
                    persist_instances(output_path, stored_instances)
                    LOGGER.info(
                        "[%s] Stored %d total after record_instances.",
                        model_cls.__name__,
                        len(stored_instances),
                    )
            elif name == "all_extracted":
                extracted_complete = True
                try:
                    reason = json.loads(args or "{}").get("reason", "completed")
                except json.JSONDecodeError:
                    reason = "completed"
                payload = {"status": "done", "stored": len(stored_instances), "reason": reason}
            else:
                payload = {"status": "error", "message": f"Unknown tool {name}"}

            tool_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(payload),
                }
            )

        if not tool_messages:
            LOGGER.warning("No tool outputs generated for %s; aborting loop.", model_cls.__name__)
            break

        messages.extend(tool_messages)

        if extracted_complete:
            LOGGER.info("Model signalled completion for %s.", model_cls.__name__)
            break
    else:
        LOGGER.warning("Reached max rounds (%d) for %s.", max_rounds, model_cls.__name__)

    persist_instances(output_path, stored_instances)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Extract Pydantic model instances from Markdown using OpenAI agents.")
    parser.add_argument("--markdown", required=True, type=Path, help="Path to the Markdown file to parse.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write extracted JSON (default: extraction/output).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI model to use for extraction (overrides config.yaml if set).",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Maximum tool-calling rounds per class before stopping (overrides config.yaml if set).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Request timeout in seconds (default: 180).",
    )
    parser.add_argument(
        "--class-names",
        nargs="*",
        help="Optional subset of class names to extract (defaults to all BaseDBModel subclasses).",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level (DEBUG, INFO, WARNING, ERROR).",
    )
    return parser.parse_args()


def main() -> None:
    """Main entry point for the extraction engine."""
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or OPENROUTER_API_KEY must be set.")

    config = load_config()
    llm_cfg = load_llm_config().get("extraction", {})
    
    # Clean debug logs at startup if configured
    clean_logs_on_start = config.get("clean_debug_logs_on_start", True)
    if clean_logs_on_start:
        clean_debug_logs()
    
    model_name = args.model or llm_cfg.get("model") or config.get("model")
    if not model_name:
        raise RuntimeError("Model must be specified in llm_config.yml, config.yaml, or via --model CLI argument.")
    
    # Get token limit from config
    token_limit = config.get("token_limit", 900000)
    
    # Get max rounds from config or CLI override
    max_rounds = args.max_rounds or config.get("max_rounds", 12)
    
    # Output directory (CLI override)
    output_dir = args.output_dir or Path(__file__).resolve().parent / "output"
    
    LOGGER.info("Using model: %s (token_limit: %d, max_rounds: %d)", model_name, token_limit, max_rounds)
    
    # Check for stray environment variables
    vision_model_env = os.getenv("VISION_MODEL")
    if vision_model_env:
        LOGGER.warning("VISION_MODEL environment variable is set to: %s (but not being used)", vision_model_env)

    markdown_text = load_markdown(args.markdown)

    # Check token count
    enc = tiktoken.get_encoding("cl100k_base")
    token_count = len(enc.encode(markdown_text))
    if token_count > token_limit:
        LOGGER.error("File too large: %d tokens (limit: %d)", token_count, token_limit)
        return
    
    LOGGER.info("File size OK: %d tokens (limit: %d)", token_count, token_limit)

    system_prompt = load_prompt("system.md")
    user_template = load_prompt("class_prompt.md")

    # Get base_url from config, environment, or default to OpenRouter
    base_url = config.get("base_url") or os.getenv("OPENAI_BASE_URL")
    if not base_url and os.getenv("OPENROUTER_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"

    client = OpenAI(
        api_key=api_key,
        base_url=base_url or None,
        timeout=args.timeout,
    )

    models_module = importlib.import_module("database.models")
    model_classes = extract_model_classes(models_module)
    if args.class_names:
        wanted = set(args.class_names)
        model_classes = [cls for cls in model_classes if cls.__name__ in wanted]
        missing = wanted - {cls.__name__ for cls in model_classes}
        if missing:
            LOGGER.warning("Requested class names not found: %s", ", ".join(sorted(missing)))

    if not model_classes:
        LOGGER.warning("No classes to process.")
        return

    for model_cls in model_classes:
        run_class_extraction(
            client=client,
            model_name=model_name,
            system_prompt=system_prompt,
            user_template=user_template,
            markdown_text=markdown_text,
            model_cls=model_cls,
            output_dir=output_dir,
            max_rounds=max_rounds,
            config=config,
        )


if __name__ == "__main__":
    main()
