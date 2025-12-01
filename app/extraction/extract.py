from __future__ import annotations

import argparse
import importlib
import inspect
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Sequence, Set, Type, get_args, get_origin

from dotenv import load_dotenv
from openai import OpenAI
import yaml
import tiktoken
from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
)
from openai.types.responses.response_output_text import ResponseOutputText
from pydantic import BaseModel, ValidationError
from uuid import UUID, uuid5

# Ensure the project root is on the import path when executed as a script
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

LOGGER = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
DEBUG_LOG_DIR = Path(__file__).resolve().parent / "debug_logs"
LOG_SNIPPET_LEN = 320
IGNORE_CLASS_NAMES = {"PossiblyTEF"}

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


def _load_prompt(name: str) -> str:
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def _escape_braces(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


def _contains_uuid_type(annotation: object) -> bool:
    if annotation is UUID:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    return any(_contains_uuid_type(arg) for arg in get_args(annotation))


def _auto_fill_missing_ids(raw: dict, model_cls: Type[BaseModel]) -> dict:
    """Fill missing UUID fields with deterministic placeholders for validation."""
    filled = dict(raw)
    for name, field in model_cls.model_fields.items():
        alias = field.alias or name
        if alias in filled and filled[alias]:
            continue
        if _contains_uuid_type(field.annotation):
            placeholder = str(
                uuid5(
                    uuid5(UUID(int=0), model_cls.__name__),
                    json.dumps(raw, sort_keys=True, ensure_ascii=False) + alias,
                )
            )
            filled[alias] = placeholder
    return filled


def _load_class_context(class_name: str) -> str:
    path = PROMPTS_DIR / f"{class_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return (
        f"Focus on extracting {class_name} entries related to Climate City Contract "
        "and climate-action programs. If key identifiers are missing, skip that row rather than inventing data."
    )


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file required: {CONFIG_PATH}")
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config file {CONFIG_PATH} is not a mapping.")
        return data
    except Exception as exc:
        raise RuntimeError(f"Failed to load config {CONFIG_PATH}: {exc}")


def _extract_model_classes(models_module) -> list[Type[BaseModel]]:
    base = getattr(models_module, "BaseDBModel", BaseModel)
    classes: list[Type[BaseModel]] = []
    for _, obj in inspect.getmembers(models_module, inspect.isclass):
        if obj is base or not issubclass(obj, base):
            continue
        # Keep only classes defined in this module (skip imports)
        if obj.__module__ != models_module.__name__:
            continue
        if obj.__name__ in IGNORE_CLASS_NAMES:
            continue
        classes.append(obj)
    return sorted(classes, key=lambda cls: cls.__name__)


def _to_json_ready(model_obj: BaseModel) -> dict:
    """Return a JSON-serialisable dict using field aliases."""
    return json.loads(model_obj.model_dump_json(by_alias=True))


def _summarise_instances(instances: Sequence[dict], max_items: int = 3) -> str:
    if not instances:
        return "None yet."
    preview = [json.dumps(entry, ensure_ascii=False) for entry in list(instances)[:max_items]]
    if len(instances) > max_items:
        preview.append(f"... ({len(instances) - max_items} more)")
    return "\n".join(preview)


def _load_markdown(markdown_path: Path) -> str:
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")
    return markdown_path.read_text(encoding="utf-8")


def _load_existing(output_path: Path) -> list[dict]:
    if not output_path.exists():
        return []
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.warning("Existing JSON at %s could not be parsed: %s", output_path, exc)
        return []


def _persist_instances(output_path: Path, instances: Sequence[dict]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(list(instances), indent=2, ensure_ascii=False), encoding="utf-8")


def _extract_text(output_message: ResponseOutputMessage) -> str:
    parts: list[str] = []
    for content in output_message.content:
        if isinstance(content, ResponseOutputText):
            parts.append(content.text)
    return "\n".join(parts)


def _make_tool_output(call_id: str, payload: dict) -> dict:
    return {"type": "function_call_output", "call_id": call_id, "output": json.dumps(payload)}


def _truncate(text: str, limit: int = LOG_SNIPPET_LEN) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _log_response_preview(model_name: str, assistant_messages: list[str], tool_calls: list[ResponseFunctionToolCall]) -> None:
    if assistant_messages:
        preview = _truncate(" | ".join(assistant_messages))
        LOGGER.info("[%s] Assistant preview: %s", model_name, preview)
    if tool_calls:
        names = [call.name for call in tool_calls]
        LOGGER.info("[%s] Tool calls: %s", model_name, ", ".join(names))


def _log_full_response(class_name: str, response: Response, round_idx: int) -> None:
    """Write full response to a debug log file for inspection."""
    DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DEBUG_LOG_DIR / f"{class_name}_round{round_idx}.json"
    
    debug_info = {
        "response_id": response.id,
        "model": getattr(response, "model", None),
        "status": getattr(response, "status", None),
        "has_output_field": hasattr(response, "output"),
        "output_length": len(response.output) if hasattr(response, "output") and response.output else 0,
        "output_items": [],
    }
    
    # Parse each item in response.output
    for idx, item in enumerate(response.output or []):
        if isinstance(item, ResponseFunctionToolCall):
            debug_info["output_items"].append({
                "index": idx,
                "type": "ResponseFunctionToolCall",
                "name": item.name,
                "call_id": item.call_id,
                "arguments": item.arguments,
            })
        elif isinstance(item, ResponseOutputMessage):
            debug_info["output_items"].append({
                "index": idx,
                "type": "ResponseOutputMessage",
                "role": getattr(item, "role", "unknown"),
                "content": _extract_text(item),
            })
        else:
            # For ResponseReasoningItem and other types, just note them
            debug_info["output_items"].append({
                "index": idx,
                "type": type(item).__name__,
                "note": f"Type: {type(item).__name__} (encrypted or non-text content)",
                "has_attributes": list(vars(item).keys()) if hasattr(item, "__dict__") else "no __dict__",
            })
    
    log_file.write_text(json.dumps(debug_info, indent=2, ensure_ascii=False), encoding="utf-8")
    LOGGER.info(
        "[%s] Response logged to %s (round %d, %d items)",
        class_name,
        log_file,
        round_idx,
        debug_info["output_length"]
    )


def _parse_record_instances(
    call: ResponseFunctionToolCall,
    model_cls: Type[BaseModel],
    seen_hashes: Set[str],
    stored: List[dict],
) -> tuple[dict, bool]:
    """
    Apply a `record_instances` call.

    Returns (result_payload, added_any).
    """
    try:
        args = json.loads(call.arguments or "{}")
    except json.JSONDecodeError as exc:
        return {"status": "error", "message": f"Invalid JSON: {exc}"}, False

    raw_items = args.get("items")
    if not isinstance(raw_items, list):
        return {"status": "error", "message": "Argument 'items' must be a list."}, False

    accepted: list[dict] = []
    errors: list[str] = []

    for idx, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            errors.append(f"Item {idx} is not an object; received {type(raw).__name__}.")
            continue
        try:
            normalized_raw = _auto_fill_missing_ids(raw, model_cls)
            parsed = model_cls.model_validate(normalized_raw)
            normalised = _to_json_ready(parsed)
        except ValidationError as exc:
            errors.append(f"Item {idx} failed validation: {exc}")
            continue

        key = json.dumps(normalised, sort_keys=True, ensure_ascii=False)
        if key in seen_hashes:
            errors.append(f"Item {idx} duplicates an existing entry; skipped.")
            continue

        seen_hashes.add(key)
        stored.append(normalised)
        accepted.append(normalised)

    notes = args.get("source_notes")
    result = {
        "status": "ok" if not errors else "partial",
        "accepted": len(accepted),
        "errors": errors,
        "total_stored": len(stored),
    }
    if notes:
        result["source_notes"] = notes
    return result, bool(accepted)


def _handle_response_output(response: Response) -> tuple[list[ResponseFunctionToolCall], list[str]]:
    tool_calls: list[ResponseFunctionToolCall] = []
    assistant_texts: list[str] = []
    for item in response.output or []:
        if isinstance(item, ResponseFunctionToolCall):
            tool_calls.append(item)
        elif isinstance(item, ResponseOutputMessage):
            assistant_texts.append(_extract_text(item))
        # Skip ResponseReasoningItem and other non-output items
    return tool_calls, assistant_texts


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
    output_path = output_dir / f"{model_cls.__name__}.json"
    stored_instances = _load_existing(output_path)
    seen_hashes = {json.dumps(entry, sort_keys=True, ensure_ascii=False) for entry in stored_instances}

    class_context = _escape_braces(_load_class_context(model_cls.__name__))
    user_prompt = user_template.format(
        class_name=model_cls.__name__,
        class_context=class_context,
        json_schema=_escape_braces(json.dumps(model_cls.model_json_schema(by_alias=True), indent=2)),
        existing_summary=_escape_braces(_summarise_instances(stored_instances)),
        markdown=_escape_braces(markdown_text),
    )

    LOGGER.info("Starting extraction for %s (existing %d records).", model_cls.__name__, len(stored_instances))
    response = client.responses.create(
        model=model_name,
        input=[{"role": "user", "content": user_prompt}],
        instructions=system_prompt,
        tools=TOOLS,
        tool_choice="required",
        parallel_tool_calls=True,
    )

    for round_idx in range(1, max_rounds + 1):
        tool_calls, assistant_messages = _handle_response_output(response)
        _log_response_preview(model_cls.__name__, assistant_messages, tool_calls)

        if not tool_calls:
            # Log full response for debugging when no tool calls returned
            _log_full_response(model_cls.__name__, response, round_idx)
            LOGGER.warning(
                "No tool calls returned for %s (round %d). Assistant said: %s",
                model_cls.__name__,
                round_idx,
                " | ".join(assistant_messages) if assistant_messages else "(no text)"
            )
            break
        else:
            # Also log successful responses for comparison
            _log_full_response(model_cls.__name__, response, round_idx)

        tool_outputs: list[dict] = []
        extracted_complete = False

        for call in tool_calls:
            if call.name == "record_instances":
                payload, added = _parse_record_instances(call, model_cls, seen_hashes, stored_instances)
                tool_outputs.append(_make_tool_output(call.call_id, payload))
                if added:
                    _persist_instances(output_path, stored_instances)
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
                tool_outputs.append(_make_tool_output(call.call_id, payload))
            else:
                tool_outputs.append(
                    _make_tool_output(call.call_id, {"status": "error", "message": f"Unknown tool {call.name}"})
                )

        if not tool_outputs:
            LOGGER.warning("No tool outputs generated for %s; aborting loop.", model_cls.__name__)
            break

        response = client.responses.create(
            model=model_name,
            previous_response_id=response.id,
            input=tool_outputs,
            instructions=system_prompt,
            tools=TOOLS,
            tool_choice="required",
            parallel_tool_calls=True,
        )

        if extracted_complete:
            LOGGER.info("Model signalled completion for %s.", model_cls.__name__)
            break
    else:
        LOGGER.warning("Reached max rounds (%d) for %s.", max_rounds, model_cls.__name__)

    _persist_instances(output_path, stored_instances)


def parse_args() -> argparse.Namespace:
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
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to store JSON outputs (default: app/extraction/output).",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=12,
        help="Maximum tool-calling rounds per class before stopping.",
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
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or OPENROUTER_API_KEY must be set.")

    config = _load_config()
    model_name = args.model or config.get("model")
    if not model_name:
        raise RuntimeError(f"Model must be specified in config.yaml at {CONFIG_PATH} (key: 'model')")
    
    LOGGER.info("Using model: %s", model_name)
    
    # Check for stray environment variables
    vision_model_env = os.getenv("VISION_MODEL")
    if vision_model_env:
        LOGGER.warning("VISION_MODEL environment variable is set to: %s (but not being used)", vision_model_env)

    markdown_text = _load_markdown(args.markdown)

    # Check token count
    enc = tiktoken.get_encoding("cl100k_base")
    token_count = len(enc.encode(markdown_text))
    if token_count > 900000:
        LOGGER.error("File too large: %d tokens (limit: 900000)", token_count)
        print("file too large")
        return

    system_prompt = _load_prompt("system.md")
    user_template = _load_prompt("class_prompt.md")

    # Default to OpenRouter endpoint when using OPENROUTER_API_KEY and no base_url is provided.
    base_url = args.base_url or os.getenv("OPENAI_BASE_URL")
    if not base_url and os.getenv("OPENROUTER_API_KEY"):
        base_url = "https://openrouter.ai/api/v1"

    client = OpenAI(api_key=api_key, base_url=base_url or None, timeout=args.timeout)

    models_module = importlib.import_module("app.database.models")
    model_classes = _extract_model_classes(models_module)
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
            output_dir=args.output_dir,
            max_rounds=args.max_rounds,
        )


if __name__ == "__main__":
    main()
