"""
Extraction engine for parsing Pydantic model instances from Markdown documents.

Uses OpenAI's Responses API with agentic tool-calling patterns to extract
structured data from Markdown converted from PDFs, mapping to domain models.
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Type

from dotenv import load_dotenv
from openai import OpenAI
import tiktoken
from pydantic import BaseModel

# Ensure the project root is on the import path when executed as a script
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from app.extraction.utils import (
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
    make_tool_output,
    parse_record_instances,
    handle_response_output,
    truncate,
    log_response_preview,
    log_full_response,
)

LOGGER = logging.getLogger(__name__)

# Tool definitions for OpenAI API
RECORD_TOOL = {
    "type": "function",
    "name": "record_instances",
    "description": (
        "Store one or more instances for the current Pydantic class. "
        "Use the schema field names (aliases) as keys."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "description": (
                    "List of objects for the current class, using alias field names."
                ),
                "items": {
                    "type": "object",
                    "description": "A single instance matching the current class schema.",
                },
                "minItems": 1,
            },
            "source_notes": {
                "type": "string",
                "description": (
                    "Optional short note about how the values were derived or any uncertainty."
                ),
            },
        },
        "required": ["items"],
        "additionalProperties": False,
    },
    "strict": True,
}

ALL_EXTRACTED_TOOL = {
    "type": "function",
    "name": "all_extracted",
    "description": (
        "Signal that every instance for the current class has been extracted "
        "(call even if zero instances exist)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "Why extraction is finished or why no instances were found.",
            }
        },
        "required": ["reason"],
        "additionalProperties": False,
    },
    "strict": True,
}

TOOLS = [RECORD_TOOL, ALL_EXTRACTED_TOOL]


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
) -> None:
    """
    Run extraction for a single Pydantic model class.
    
    Args:
        client: OpenAI API client
        model_name: LLM model to use
        system_prompt: System instruction prompt
        user_template: User message template
        markdown_text: Markdown content to extract from
        model_cls: Target Pydantic model class
        output_dir: Directory for output JSON files
        max_rounds: Maximum extraction rounds
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
    response = client.responses.create(  # type: ignore
        model=model_name,
        input=[{"role": "user", "content": user_prompt}],  # type: ignore
        instructions=system_prompt,
        tools=TOOLS,  # type: ignore
        tool_choice="required",
        parallel_tool_calls=True,
    )

    for round_idx in range(1, max_rounds + 1):
        tool_calls, assistant_messages = handle_response_output(response)
        log_response_preview(model_cls.__name__, assistant_messages, tool_calls)

        if not tool_calls:
            # Log full response for debugging when no tool calls returned
            log_full_response(model_cls.__name__, response, round_idx)
            LOGGER.warning(
                "No tool calls returned for %s (round %d). Assistant said: %s",
                model_cls.__name__,
                round_idx,
                " | ".join(assistant_messages) if assistant_messages else "(no text)"
            )
            break
        else:
            # Also log successful responses for comparison
            log_full_response(model_cls.__name__, response, round_idx)

        tool_outputs: list[dict] = []
        extracted_complete = False

        for call in tool_calls:
            if call.name == "record_instances":
                payload, added = parse_record_instances(call, model_cls, seen_hashes, stored_instances)
                tool_outputs.append(make_tool_output(call.call_id, payload))
                if added:
                    persist_instances(output_path, stored_instances)
                    LOGGER.info(
                        "[%s] Stored %d total after record_instances.",
                        model_cls.__name__,
                        len(stored_instances),
                    )
            elif call.name == "all_extracted":
                extracted_complete = True
                try:
                    reason = json.loads(call.arguments or "{}").get("reason", "completed")
                except json.JSONDecodeError:
                    reason = "completed"
                payload = {
                    "status": "done",
                    "stored": len(stored_instances),
                    "reason": reason,
                }
                tool_outputs.append(make_tool_output(call.call_id, payload))
            else:
                tool_outputs.append(
                    make_tool_output(call.call_id, {"status": "error", "message": f"Unknown tool {call.name}"})
                )

        if not tool_outputs:
            LOGGER.warning("No tool outputs generated for %s; aborting loop.", model_cls.__name__)
            break

        response = client.responses.create(  # type: ignore
            model=model_name,
            previous_response_id=response.id,
            input=tool_outputs,  # type: ignore
            instructions=system_prompt,
            tools=TOOLS,  # type: ignore
            tool_choice="required",
            parallel_tool_calls=True,
        )

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
        "--model",
        default=None,
        help="OpenAI model to use for extraction (overrides config.yaml if set).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to store JSON outputs (default: app/extraction/output).",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Maximum tool-calling rounds per class before stopping (overrides config.yaml if set).",
    )
    parser.add_argument(
        "--token-limit",
        type=int,
        default=None,
        help="Maximum token limit for markdown file (overrides config.yaml if set).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Request timeout in seconds (default: 180).",
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("OPENAI_BASE_URL"),
        help="Optional OpenAI-compatible base URL (defaults to env OPENAI_BASE_URL).",
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
    
    # Clean debug logs at startup if configured
    clean_logs_on_start = config.get("clean_debug_logs_on_start", True)
    if clean_logs_on_start:
        clean_debug_logs()
    
    model_name = args.model or config.get("model")
    if not model_name:
        raise RuntimeError("Model must be specified in config.yaml or via --model CLI argument.")
    
    # Get token limit from config or CLI override
    token_limit = args.token_limit or config.get("token_limit", 900000)
    
    # Get max rounds from config or CLI override
    max_rounds = args.max_rounds or config.get("max_rounds", 12)
    
    # Get output directory with proper default
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
        print(f"file too large: {token_count} tokens exceeds limit of {token_limit}")
        return
    
    LOGGER.info("File size OK: %d tokens (limit: %d)", token_count, token_limit)

    system_prompt = load_prompt("system.md")
    user_template = load_prompt("class_prompt.md")

    # Default to OpenRouter endpoint when using OPENROUTER_API_KEY and no base_url is provided.
    base_url = args.base_url or os.getenv("OPENAI_BASE_URL")
    if not base_url and os.getenv("OPENROUTER_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"

    client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=args.timeout)

    models_module = importlib.import_module("app.database.models")
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
        )


if __name__ == "__main__":
    main()
