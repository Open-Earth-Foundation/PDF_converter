"""Data transformation and validation utilities."""

import inspect
import json
import logging
from typing import List, Sequence, Set, Type, get_args, get_origin

from openai.types.responses import (
    Response,
    ResponseFunctionToolCall,
    ResponseOutputMessage,
)
from pydantic import BaseModel, ValidationError
from uuid import UUID, uuid5

LOGGER = logging.getLogger(__name__)

IGNORE_CLASS_NAMES = {"PossiblyTEF"}


def escape_braces(text: str) -> str:
    """Escape braces in text for template formatting."""
    return text.replace("{", "{{").replace("}", "}}")


def contains_uuid_type(annotation: object) -> bool:
    """Check if a type annotation contains UUID type."""
    if annotation is UUID:
        return True
    origin = get_origin(annotation)
    if origin is None:
        return False
    return any(contains_uuid_type(arg) for arg in get_args(annotation))


def auto_fill_missing_ids(raw: dict, model_cls: Type[BaseModel]) -> dict:
    """Fill missing UUID fields with deterministic placeholders for validation."""
    filled = dict(raw)
    for name, field in model_cls.model_fields.items():
        alias = field.alias or name
        if alias in filled and filled[alias]:
            continue
        if contains_uuid_type(field.annotation):
            placeholder = str(
                uuid5(
                    uuid5(UUID(int=0), model_cls.__name__),
                    json.dumps(raw, sort_keys=True, ensure_ascii=False) + alias,
                )
            )
            filled[alias] = placeholder
    return filled


def extract_model_classes(models_module) -> list[Type[BaseModel]]:
    """Extract all BaseDBModel subclasses from a module."""
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


def to_json_ready(model_obj: BaseModel) -> dict:
    """Convert Pydantic model to JSON-serialisable dict using field aliases."""
    return model_obj.model_dump(mode="json", by_alias=True)


def summarise_instances(instances: Sequence[dict], max_items: int = 3) -> str:
    """Create a preview summary of instances."""
    if not instances:
        return "None yet."
    preview = [
        json.dumps(entry, ensure_ascii=False) for entry in list(instances)[:max_items]
    ]
    if len(instances) > max_items:
        preview.append(f"... ({len(instances) - max_items} more)")
    return "\n".join(preview)


def extract_text(output_message: ResponseOutputMessage) -> str:
    """Extract text from OpenAI response message."""
    from openai.types.responses.response_output_text import ResponseOutputText

    parts: list[str] = []
    for content in output_message.content:
        if isinstance(content, ResponseOutputText):
            parts.append(content.text)
    return "\n".join(parts)


def make_tool_output(call_id: str, payload: dict) -> dict:
    """Create a tool output response."""
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": json.dumps(payload),
    }


def parse_record_instances(
    call: ResponseFunctionToolCall,
    model_cls: Type[BaseModel],
    seen_hashes: Set[str],
    stored: List[dict],
) -> tuple[dict, bool]:
    """
    Parse and validate a `record_instances` tool call.

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
            error_msg = f"Item {idx} is not an object; received {type(raw).__name__}."
            errors.append(error_msg)
            LOGGER.debug("[%s] Validation error: %s", model_cls.__name__, error_msg)
            continue
        try:
            normalized_raw = auto_fill_missing_ids(raw, model_cls)
            parsed = model_cls.model_validate(normalized_raw)
            normalised = to_json_ready(parsed)
        except ValidationError as exc:
            # Provide more helpful error messages for common missing fields
            missing_fields = []
            for error in exc.errors():
                if error.get("type") == "missing":
                    missing_fields.append(error.get("loc", ("unknown",))[0])

            if missing_fields:
                error_msg = f"Item {idx} missing required field(s): {', '.join(str(f) for f in missing_fields)}. Raw data: {list(raw.keys())}"
            else:
                error_msg = f"Item {idx} failed validation: {exc}"

            errors.append(error_msg)
            LOGGER.warning(
                "[%s] Validation failed for item %d: %s",
                model_cls.__name__,
                idx,
                error_msg,
            )
            continue

        key = json.dumps(normalised, sort_keys=True, ensure_ascii=False)
        if key in seen_hashes:
            error_msg = f"Item {idx} duplicates an existing entry; skipped."
            errors.append(error_msg)
            LOGGER.debug("[%s] Duplicate detected: %s", model_cls.__name__, error_msg)
            continue

        seen_hashes.add(key)
        stored.append(normalised)
        accepted.append(normalised)
        LOGGER.debug("[%s] Successfully accepted item %d", model_cls.__name__, idx)

    notes = args.get("source_notes")
    result = {
        "status": "ok" if not errors else "partial",
        "accepted": len(accepted),
        "errors": errors,
        "total_stored": len(stored),
    }
    if notes:
        result["source_notes"] = notes

    if errors:
        LOGGER.info(
            "[%s] record_instances: %d accepted, %d errors. Details: %s",
            model_cls.__name__,
            len(accepted),
            len(errors),
            " | ".join(errors[:3]) + (" ..." if len(errors) > 3 else ""),
        )

    return result, bool(accepted)


def handle_response_output(
    response: Response,
) -> tuple[list[ResponseFunctionToolCall], list[str]]:
    """Parse response output and extract tool calls and text."""
    tool_calls: list[ResponseFunctionToolCall] = []
    assistant_texts: list[str] = []
    for item in response.output or []:
        if isinstance(item, ResponseFunctionToolCall):
            tool_calls.append(item)
        elif isinstance(item, ResponseOutputMessage):
            assistant_texts.append(extract_text(item))
        # Skip ResponseReasoningItem and other non-output items
    return tool_calls, assistant_texts
