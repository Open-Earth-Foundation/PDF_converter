"""
Extraction engine for parsing Pydantic model instances from Markdown.

Usage:
    python -m extraction.scripts.extract --markdown path/to/combined_markdown.md [--output-dir extraction/output]

Flags:
- --markdown: path to combined_markdown.md (required)
- --output-dir: directory for extracted JSON (default: extraction/output)
- --model/--max-rounds/--class-names/--log-level: overrides for runtime settings
- --overwrite: clear existing JSON output before extraction
- --extra-guidance: append extra guidance to class prompts
- --chunking/--chunk-size-tokens/--chunk-overlap-tokens/--chunk-auto-threshold-tokens: chunking controls
"""

from __future__ import annotations

import argparse
import importlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Sequence, Type

from dotenv import load_dotenv
from openai import OpenAI, APIStatusError
import tiktoken
from pydantic import BaseModel

from utils import load_llm_config
from extraction.utils import (
    chunk_markdown,
    load_config,
    load_prompt,
    load_class_context,
    clean_debug_logs,
    load_markdown,
    load_existing,
    persist_instances,
    escape_braces,
    extract_model_classes,
    summarise_instances,
    parse_record_instances,
    truncate,
    log_full_response,
    select_provider,
    apply_default_provider,
    load_table_context,
    write_table_context,
    parse_table_signature,
    extract_tables,
    Chunk,
    TableInfo,
)
from extraction.tools import get_all_tools

LOGGER = logging.getLogger(__name__)

# Load tool definitions from tools module
TOOLS = get_all_tools()


def _make_doc_id(markdown_path: Path) -> str:
    """Derive a stable document id for chunk context storage."""
    if markdown_path.parent and markdown_path.parent.name:
        return markdown_path.parent.name
    return markdown_path.stem


def _format_table_context(
    tables: Sequence[TableInfo],
    table_items: dict[str, list[dict]],
    *,
    max_items: int,
) -> str:
    if max_items <= 0 or not tables or not table_items:
        return "None."

    lines: list[str] = []
    for table in tables:
        items = table_items.get(table.signature)
        if not items:
            continue
        summary_limit = max_items if max_items > 0 else len(items)
        lines.append(f"- table_signature={table.signature}")
        lines.append(f"  heading: {table.heading_path or 'None'}")
        lines.append(f"  header: {table.header}")
        lines.append("  items:")
        summary = summarise_instances(items, max_items=summary_limit)
        lines.extend(_indent_text(summary, "    ").splitlines())

    return "\n".join(lines) if lines else "None."


def _indent_text(text: str, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _merge_table_items(
    target: dict[str, list[dict]],
    signature: str,
    items: Sequence[dict],
) -> None:
    existing = target.setdefault(signature, [])
    seen = {json.dumps(entry, sort_keys=True, ensure_ascii=False) for entry in existing}
    for item in items:
        key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key in seen:
            continue
        seen.add(key)
        existing.append(item)


def _coerce_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def run_class_extraction(
    *,
    client: OpenAI,
    model_name: str,
    extra_body: dict | None,
    system_prompt: str,
    user_template: str,
    markdown_text: str,
    model_cls: Type[BaseModel],
    db_model_name: str,
    output_dir: Path,
    max_rounds: int,
    table_context: str | None = None,
    table_signatures: Sequence[str] | None = None,
    table_context_collector: dict[str, list[dict]] | None = None,
    config: dict | None = None,
    overwrite: bool = False,
    extra_guidance: str | None = None,
) -> None:
    """
    Run extraction for a single Pydantic model class using chat.completions with tools.

    Args mirror the CLI entry point.
    table_context is an optional chunk-aware prompt section.

    Args:
        db_model_name: The database model name (for output file naming and context loading).
                       Used when extraction uses a different schema (e.g., VerifiedCityTarget).
    """
    output_path = output_dir / f"{db_model_name}.json"
    if overwrite and output_path.exists():
        output_path.unlink()
        LOGGER.info("Cleared existing output for %s.", db_model_name)
    stored_instances = load_existing(output_path)
    seen_hashes = {
        json.dumps(entry, sort_keys=True, ensure_ascii=False)
        for entry in stored_instances
    }
    base_extra_body = dict(extra_body or {})
    table_signatures = list(table_signatures or [])

    class_context_raw = load_class_context(db_model_name)
    if extra_guidance:
        class_context_raw = f"{class_context_raw}\n\nAdditional guidance:\n{extra_guidance.strip()}"
    class_context = escape_braces(class_context_raw)

    # Generate compact JSON schema: only include properties and required fields
    # This avoids sending large definitions and examples that bloat the context
    full_schema = model_cls.model_json_schema(by_alias=True)
    compact_schema = {
        "title": full_schema.get("title"),
        "type": "object",
        "properties": full_schema.get("properties", {}),
        "required": full_schema.get("required", []),
    }

    table_context_text = table_context or "None."

    user_prompt = user_template.format(
        class_name=model_cls.__name__,
        class_context=class_context,
        json_schema=escape_braces(json.dumps(compact_schema, indent=2)),
        existing_summary=escape_braces(summarise_instances(stored_instances)),
        table_context=escape_braces(table_context_text),
        markdown=escape_braces(markdown_text),
    )

    # Calculate and log prompt size
    enc = tiktoken.get_encoding("cl100k_base")
    system_tokens = len(enc.encode(system_prompt))
    user_tokens = len(enc.encode(user_prompt))
    total_prompt_tokens = system_tokens + user_tokens

    LOGGER.info(
        "Starting extraction for %s (existing %d records).",
        db_model_name,
        len(stored_instances),
    )
    LOGGER.debug(
        "Prompt composition for %s: system=%d tokens, user=%d tokens, total=%d tokens",
        db_model_name,
        system_tokens,
        user_tokens,
        total_prompt_tokens,
    )
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
                extra_body=base_extra_body or None,
            )
        except APIStatusError as exc:
            err_text = str(exc).lower()
            is_404 = getattr(exc, "status_code", None) == 404
            supports_tool_msg = "support tool use" in err_text
            tool_choice_msg = "tool_choice" in err_text

            if is_404 and (supports_tool_msg or tool_choice_msg):
                fallback_body = apply_default_provider(model_name, base_extra_body)
                added_provider = fallback_body.get("provider") != (
                    base_extra_body.get("provider") if base_extra_body else None
                )
                fallback_choice = "auto" if tool_choice_msg else "required"
                LOGGER.warning(
                    "Received 404 for tool use on %s; retrying with tool_choice='%s'%s.",
                    model_name,
                    fallback_choice,
                    (
                        f" and provider={fallback_body.get('provider')}"
                        if added_provider
                        else ""
                    ),
                )
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice=fallback_choice,
                    extra_body=fallback_body or None,
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
            preview_text = (
                truncate(choice.content or "", 160) if choice.content else "(no text)"
            )
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
            source_notes = None
            if table_context_collector is not None:
                try:
                    parsed = json.loads(args or "{}")
                    if isinstance(parsed, dict):
                        source_notes = parsed.get("source_notes")
                except json.JSONDecodeError:
                    source_notes = None
            fake_call = type(
                "ToolCall", (), {"name": name, "arguments": args, "call_id": tc.id}
            )

            if name == "record_instances":
                stored_before = len(stored_instances)
                payload, added = parse_record_instances(
                    fake_call,
                    model_cls,
                    seen_hashes,
                    stored_instances,
                    source_text=markdown_text,
                )
                if added:
                    persist_instances(output_path, stored_instances)
                    LOGGER.info(
                        "[%s] Stored %d total after record_instances.",
                        model_cls.__name__,
                        len(stored_instances),
                    )
                if table_context_collector is not None:
                    table_signature = parse_table_signature(source_notes)
                    if (
                        not table_signature
                        and table_signatures
                        and len(table_signatures) == 1
                    ):
                        table_signature = table_signatures[0]
                    if table_signature and (
                        not table_signatures or table_signature in table_signatures
                    ):
                        new_items = stored_instances[stored_before:]
                        if new_items:
                            _merge_table_items(
                                table_context_collector, table_signature, new_items
                            )
            elif name == "all_extracted":
                extracted_complete = True
                try:
                    reason = json.loads(args or "{}").get("reason", "completed")
                except json.JSONDecodeError:
                    reason = "completed"
                payload = {
                    "status": "done",
                    "stored": len(stored_instances),
                    "reason": reason,
                }
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
            LOGGER.warning(
                "No tool outputs generated for %s; aborting loop.", model_cls.__name__
            )
            break

        messages.extend(tool_messages)

        if extracted_complete:
            LOGGER.info("Model signalled completion for %s.", model_cls.__name__)
            break
    else:
        LOGGER.warning(
            "Reached max rounds (%d) for %s.", max_rounds, model_cls.__name__
        )

    persist_instances(output_path, stored_instances)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Extract Pydantic model instances from Markdown using OpenAI agents."
    )
    parser.add_argument(
        "--markdown",
        required=True,
        type=Path,
        help="Path to the Markdown file to parse.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to write extracted JSON (default: extraction/output).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="OpenAI model to use for extraction (overrides llm_config.yml extraction.model if set).",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=None,
        help="Maximum tool-calling rounds per class before stopping (overrides llm_config.yml if set).",
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
        "--overwrite",
        action="store_true",
        help="Clear existing JSON outputs for selected classes before extraction.",
    )
    parser.add_argument(
        "--extra-guidance",
        default=None,
        help="Append extra guidance to class prompts (useful for targeted re-runs).",
    )
    parser.add_argument(
        "--chunking",
        action="store_true",
        help="Enable chunked extraction regardless of document size.",
    )
    parser.add_argument(
        "--chunk-size-tokens",
        type=int,
        default=None,
        help="Chunk size in tokens (overrides llm_config.yml).",
    )
    parser.add_argument(
        "--chunk-overlap-tokens",
        type=int,
        default=None,
        help="Chunk overlap in tokens (overrides llm_config.yml).",
    )
    parser.add_argument(
        "--chunk-auto-threshold-tokens",
        type=int,
        default=None,
        help="Auto-chunk threshold in tokens (overrides llm_config.yml).",
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
    chunk_cfg = config.get("chunking", {})
    if not isinstance(chunk_cfg, dict):
        LOGGER.warning("Chunking config is not a mapping; using defaults.")
        chunk_cfg = {}

    # Clean debug logs at startup if configured
    clean_logs_on_start = config.get("clean_debug_logs_on_start", True)
    if clean_logs_on_start:
        clean_debug_logs()

    model_name = args.model or llm_cfg.get("model") or config.get("model")
    if not model_name:
        raise RuntimeError(
            "Model must be specified in llm_config.yml (extraction.model) or via --model CLI argument."
        )

    # Optional provider override (useful for OpenRouter when only specific providers support tools)
    provider = select_provider(llm_cfg, config, env_prefix="EXTRACTION")
    if provider and not isinstance(provider, dict):
        LOGGER.warning(
            "Ignoring provider override because it must be a mapping; got %r", provider
        )
        provider = None
    extra_body = {"provider": provider} if provider else None

    # Get token limit from config
    token_limit = config.get("token_limit", 900000)

    boundary_mode = str(chunk_cfg.get("boundary_mode", "paragraph_or_sentence"))
    if boundary_mode != "paragraph_or_sentence":
        LOGGER.warning(
            "Unsupported boundary_mode %s; using paragraph_or_sentence.", boundary_mode
        )
        boundary_mode = "paragraph_or_sentence"
    chunk_size_tokens = _coerce_int(
        args.chunk_size_tokens or chunk_cfg.get("chunk_size_tokens"),
        200000,
    )
    chunk_overlap_tokens = _coerce_int(
        args.chunk_overlap_tokens or chunk_cfg.get("chunk_overlap_tokens"),
        10000,
    )
    auto_threshold_tokens = _coerce_int(
        args.chunk_auto_threshold_tokens or chunk_cfg.get("auto_threshold_tokens"),
        300000,
    )
    chunking_enabled = bool(args.chunking or chunk_cfg.get("enabled", False))
    keep_tables_intact = bool(chunk_cfg.get("keep_tables_intact", True))
    table_context_max_items = _coerce_int(
        chunk_cfg.get("table_context_max_items", 5),
        5,
    )

    # Get max rounds from config or CLI override
    max_rounds = args.max_rounds or config.get("max_rounds", 12)

    # Output directory (CLI override)
    output_dir = args.output_dir or Path(__file__).resolve().parent / "output"

    provider_label = provider or "auto (router)"
    LOGGER.info(
        "Using model: %s (token_limit: %d, max_rounds: %d, provider: %s)",
        model_name,
        token_limit,
        max_rounds,
        provider_label,
    )

    # Check for stray environment variables
    vision_model_env = os.getenv("VISION_MODEL")
    if vision_model_env:
        LOGGER.warning(
            "VISION_MODEL environment variable is set to: %s (but not being used)",
            vision_model_env,
        )

    markdown_text = load_markdown(args.markdown)

    # Check token count
    enc = tiktoken.get_encoding("cl100k_base")
    token_count = len(enc.encode(markdown_text))
    should_chunk = chunking_enabled or token_count > auto_threshold_tokens
    if not should_chunk and token_count > token_limit:
        LOGGER.error("File too large: %d tokens (limit: %d)", token_count, token_limit)
        return

    if should_chunk:
        chunks = chunk_markdown(
            markdown_text,
            chunk_size_tokens=chunk_size_tokens,
            chunk_overlap_tokens=chunk_overlap_tokens,
            boundary_mode=boundary_mode,
            keep_tables_intact=keep_tables_intact,
        )
        LOGGER.info(
            "Chunking enabled: %d chunks (chunk_size=%d, overlap=%d, tokens=%d).",
            len(chunks),
            chunk_size_tokens,
            chunk_overlap_tokens,
            token_count,
        )
    else:
        end_line = markdown_text.count("\n") + 1 if markdown_text else 1
        chunks = [
            Chunk(
                index=0,
                text=markdown_text,
                token_count=token_count,
                start_line=1,
                end_line=end_line,
                tables=extract_tables(markdown_text),
            )
        ]
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

    models_module = importlib.import_module("extraction.schemas_llm")
    model_classes = extract_model_classes(models_module)
    if args.class_names:
        wanted = set(args.class_names)
        model_classes = [cls for cls in model_classes if cls.__name__ in wanted]
        missing = wanted - {cls.__name__ for cls in model_classes}
        if missing:
            LOGGER.warning(
                "Requested class names not found: %s", ", ".join(sorted(missing))
            )

    if not model_classes:
        LOGGER.warning("No classes to process.")
        return

    doc_id = _make_doc_id(args.markdown)
    table_context_root = output_dir / "table_context" / doc_id
    if args.overwrite and table_context_root.exists():
        shutil.rmtree(table_context_root, ignore_errors=True)
        LOGGER.info("Cleared table context directory: %s", table_context_root)

    # Map database schema classes to verified schema classes for extraction
    verified_module = importlib.import_module("extraction.schemas_verified")
    verified_classes_map = {}
    for cls_name in [
        "CityTarget",
        "EmissionRecord",
        "CityBudget",
        "IndicatorValue",
        "BudgetFunding",
        "Initiative",
    ]:
        verified_cls_name = f"Verified{cls_name}"
        try:
            verified_cls = getattr(verified_module, verified_cls_name)
            verified_classes_map[cls_name] = verified_cls
        except AttributeError:
            pass

    for model_cls in model_classes:
        # Special handling: skip standalone IndicatorValue extraction if using combined extraction
        if model_cls.__name__ == "IndicatorValue":
            LOGGER.info(
                "Skipping standalone IndicatorValue extraction (use IndicatorWithValues for combined extraction)"
            )
            continue

        # Use verified schema for extraction if available, otherwise use database schema
        extraction_model_cls = verified_classes_map.get(model_cls.__name__, model_cls)
        if extraction_model_cls != model_cls:
            LOGGER.debug(
                "Using verified schema for %s extraction",
                model_cls.__name__,
            )

        for chunk in chunks:
            table_signatures = [table.signature for table in chunk.tables]
            table_context_items = load_table_context(
                table_context_root,
                class_name=model_cls.__name__,
                chunk_index=chunk.index,
                table_signatures=table_signatures,
                max_items=table_context_max_items,
            )
            table_context = _format_table_context(
                chunk.tables,
                table_context_items,
                max_items=table_context_max_items,
            )
            table_context_collector = {} if should_chunk else None
            run_class_extraction(
                client=client,
                model_name=model_name,
                extra_body=extra_body,
                system_prompt=system_prompt,
                user_template=user_template,
                markdown_text=chunk.text,
                model_cls=extraction_model_cls,
                db_model_name=model_cls.__name__,  # Use DB schema name for output file and context
                output_dir=output_dir,
                max_rounds=max_rounds,
                table_context=table_context,
                table_signatures=table_signatures,
                table_context_collector=table_context_collector,
                config=config,
                overwrite=args.overwrite and chunk.index == 0,
                extra_guidance=args.extra_guidance,
            )
            if table_context_collector:
                write_table_context(
                    table_context_root,
                    class_name=model_cls.__name__,
                    chunk_index=chunk.index,
                    table_items=table_context_collector,
                    max_items=table_context_max_items,
                )

    # Extract combined Indicator + IndicatorValues
    should_run_combined = True
    if args.class_names is not None:
        should_run_combined = "IndicatorWithValues" in args.class_names

    if should_run_combined:
        try:
            indicator_with_values_cls = getattr(verified_module, "IndicatorWithValues")
            LOGGER.info("Extracting combined IndicatorWithValues...")
            for chunk in chunks:
                table_signatures = [table.signature for table in chunk.tables]
                table_context_items = load_table_context(
                    table_context_root,
                    class_name="IndicatorWithValues",
                    chunk_index=chunk.index,
                    table_signatures=table_signatures,
                    max_items=table_context_max_items,
                )
                table_context = _format_table_context(
                    chunk.tables,
                    table_context_items,
                    max_items=table_context_max_items,
                )
                table_context_collector = {} if should_chunk else None
                run_class_extraction(
                    client=client,
                    model_name=model_name,
                    extra_body=extra_body,
                    system_prompt=system_prompt,
                    user_template=user_template,
                    markdown_text=chunk.text,
                    model_cls=indicator_with_values_cls,
                    db_model_name="IndicatorWithValues",
                    output_dir=output_dir,
                    max_rounds=max_rounds,
                    table_context=table_context,
                    table_signatures=table_signatures,
                    table_context_collector=table_context_collector,
                    config=config,
                    overwrite=args.overwrite and chunk.index == 0,
                    extra_guidance=args.extra_guidance,
                )
                if table_context_collector:
                    write_table_context(
                        table_context_root,
                        class_name="IndicatorWithValues",
                        chunk_index=chunk.index,
                        table_items=table_context_collector,
                        max_items=table_context_max_items,
                    )
        except AttributeError:
            LOGGER.debug(
                "IndicatorWithValues schema not available, skipping combined extraction"
            )


if __name__ == "__main__":
    main()
