"""Data transformation and validation utilities."""

import inspect
import json
import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation
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

PLACEHOLDER_UUID_PREFIX = "00000000-0000-0000-0000-"
ID_EXCLUDE_FIELDS = {"misc", "notes"}

PRIMARY_KEY_FIELDS: dict[str, str] = {
    "BudgetFunding": "budgetFundingId",
    "City": "cityId",
    "CityAnnualStats": "statId",
    "CityBudget": "budgetId",
    "CityTarget": "cityTargetId",
    "ClimateCityContract": "climateCityContractId",
    "EmissionRecord": "emissionRecordId",
    "FundingSource": "fundingSourceId",
    "Indicator": "indicatorId",
    "IndicatorValue": "indicatorValueId",
    "Initiative": "initiativeId",
    "InitiativeIndicator": "initiativeIndicatorId",
    "InitiativeStakeholder": "initiativeStakeholderId",
    "InitiativeTef": "initiativeTefId",
    "Sector": "sectorId",
    "Stakeholder": "stakeholderId",
    "TefCategory": "tefId",
}


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


def is_valid_uuid(value: object) -> bool:
    """Return True for well-formed UUID strings."""
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def is_placeholder_uuid(value: object) -> bool:
    """Treat zero-prefixed UUIDs as placeholders that should be replaced."""
    if not isinstance(value, str):
        return False
    return value.strip().lower().startswith(PLACEHOLDER_UUID_PREFIX)


def get_primary_key_alias(model_name: str, model_cls: Type[BaseModel]) -> str | None:
    """Resolve the primary key alias for a model."""
    if model_name in PRIMARY_KEY_FIELDS:
        return PRIMARY_KEY_FIELDS[model_name]
    candidates: list[str] = []
    for name, field in model_cls.model_fields.items():
        alias = field.alias or name
        if contains_uuid_type(field.annotation) and alias.endswith("Id"):
            candidates.append(alias)
    if len(candidates) == 1:
        return candidates[0]
    return None


def _build_id_seed(record: dict, pk_alias: str) -> str:
    """Build a deterministic seed for UUID generation."""
    payload = {
        key: value
        for key, value in record.items()
        if key not in ID_EXCLUDE_FIELDS and key != pk_alias
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def deterministic_uuid_for_record(
    record: dict, model_name: str, pk_alias: str, salt: str | None = None
) -> str:
    """Generate a deterministic UUID for a record using a stable seed."""
    seed = _build_id_seed(record, pk_alias)
    if salt:
        seed = f"{seed}|{salt}"
    namespace = uuid5(UUID(int=0), model_name)
    return str(uuid5(namespace, seed + pk_alias))


def ensure_primary_key(
    record: dict,
    model_name: str,
    model_cls: Type[BaseModel],
    existing_ids: Set[str],
) -> dict:
    """Ensure a deterministic primary key exists and is unique within existing_ids."""
    pk_alias = get_primary_key_alias(model_name, model_cls)
    if not pk_alias:
        return record

    raw_value = record.get(pk_alias)
    needs_new = (
        raw_value is None
        or not is_valid_uuid(raw_value)
        or is_placeholder_uuid(raw_value)
        or raw_value in existing_ids
    )
    if not needs_new:
        return record

    new_id = deterministic_uuid_for_record(record, model_name, pk_alias)
    counter = 1
    while new_id in existing_ids:
        counter += 1
        new_id = deterministic_uuid_for_record(
            record, model_name, pk_alias, salt=str(counter)
        )
    record[pk_alias] = new_id
    return record


def auto_fill_missing_ids(raw: dict, model_cls: Type[BaseModel]) -> dict:
    """Fill missing UUID fields with deterministic placeholders for validation."""
    filled = dict(raw)
    for name, field in model_cls.model_fields.items():
        alias = field.alias or name
        if alias in filled and filled[alias]:
            if not contains_uuid_type(field.annotation):
                continue
            if is_valid_uuid(filled[alias]) and not is_placeholder_uuid(filled[alias]):
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


def _normalize_year(value: object) -> object:
    """Normalize year strings like '2030' to '2030-01-01'."""
    if isinstance(value, str) and value.isdigit() and len(value) == 4:
        return f"{value}-01-01"
    return value


def _normalize_decimal(value: object) -> object:
    """
    Normalize numeric strings with commas/percent/text to a Decimal-friendly string.
    Examples:
      "1,471,000" -> "1471000"
      "4%" -> "4"
      "around 300 MW" -> "300"
    """
    if isinstance(value, (int, float, Decimal)):
        return value
    if not isinstance(value, str):
        return value

    # Find first numeric chunk
    match = re.search(r"-?\d+(?:[.,]\d+)?", value)
    if not match:
        return value
    number = match.group(0)
    # If both comma and dot exist, assume comma is thousand separator
    if "," in number and "." in number:
        number = number.replace(",", "")
    elif "," in number and "." not in number:
        # Treat comma as thousand separator
        number = number.replace(",", "")
    else:
        number = number
    # Convert decimal comma to dot
    number = number.replace(",", ".")
    try:
        return str(Decimal(number))
    except (InvalidOperation, ValueError):
        return value


def normalize_extracted_item(raw: dict, model_cls: Type[BaseModel]) -> dict:
    """
    Coerce common LLM output formats into schema-friendly values for strict Pydantic validation.

    Focuses on date and decimal fields for CityTarget, IndicatorValue, and InitiativeIndicator.
    """
    normalised = dict(raw)
    name = model_cls.__name__

    if name == "CityTarget":
        for field in ("targetYear", "baselineYear"):
            if field in normalised:
                normalised[field] = _normalize_year(normalised[field])
        for field in ("targetValue", "baselineValue"):
            if field in normalised:
                normalised[field] = _normalize_decimal(normalised[field])

    if name == "IndicatorValue":
        if "year" in normalised:
            normalised["year"] = _normalize_year(normalised["year"])
        if "value" in normalised:
            normalised["value"] = _normalize_decimal(normalised["value"])

    if name == "InitiativeIndicator":
        if "expectedChange" in normalised:
            normalised["expectedChange"] = _normalize_decimal(
                normalised["expectedChange"]
            )

    return normalised


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
    source_text: str | None = None,
) -> tuple[dict, bool]:
    """
    Parse and validate a `record_instances` tool call.

    For verified schemas with VerifiedField objects, performs quote validation
    against source text and maps to database format with proof in misc field.

    Args:
        call: The tool call from OpenAI.
        model_cls: The Pydantic model class (verified or standard).
        seen_hashes: Set of seen record hashes to detect duplicates.
        stored: List to accumulate stored records.
        source_text: Optional source markdown text for quote validation.

    Returns:
        Tuple of (result_payload, added_any).
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

    # Check if this is a verified schema (by checking for VerifiedField fields)
    is_verified_schema = _has_verified_fields(model_cls)
    model_name = model_cls.__name__
    if model_name.startswith("Verified"):
        model_name = model_name[len("Verified") :]
    pk_alias = get_primary_key_alias(model_name, model_cls)
    existing_ids: Set[str] = set()
    if pk_alias:
        existing_ids = {
            str(rec.get(pk_alias))
            for rec in stored
            if is_valid_uuid(rec.get(pk_alias))
            and not is_placeholder_uuid(rec.get(pk_alias))
        }

    for idx, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            error_msg = f"Item {idx} is not an object; received {type(raw).__name__}."
            errors.append(error_msg)
            LOGGER.debug("[%s] Validation error: %s", model_cls.__name__, error_msg)
            continue
        try:
            # Validate and parse the verified object
            parsed = model_cls.model_validate(raw)

            # If this is a verified schema and we have source text, perform mapping
            if is_verified_schema and source_text:
                from extraction.utils.verified_utils import map_verified_to_db

                mapped_output, validation_errors = map_verified_to_db(
                    parsed, source_text, None
                )

                if validation_errors:
                    # Reject the record if any quote validation failed
                    error_details = "; ".join(
                        [f"{k}: {v}" for k, v in validation_errors.items()]
                    )
                    error_msg = f"Item {idx} quote validation failed: {error_details}"
                    errors.append(error_msg)
                    LOGGER.warning(
                        "[%s] Quote validation failed for item %d: %s",
                        model_cls.__name__,
                        idx,
                        error_details,
                    )
                    continue

                normalised = mapped_output
            else:
                # Standard schema or no source text: use normal processing
                normalized_raw = normalize_extracted_item(raw, model_cls)
                normalized_raw = auto_fill_missing_ids(normalized_raw, model_cls)
                parsed_standard = model_cls.model_validate(normalized_raw)
                normalised = to_json_ready(parsed_standard)

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

        if pk_alias:
            normalised = ensure_primary_key(
                normalised, model_name, model_cls, existing_ids
            )

        key = json.dumps(normalised, sort_keys=True, ensure_ascii=False)
        if key in seen_hashes:
            error_msg = f"Item {idx} duplicates an existing entry; skipped."
            errors.append(error_msg)
            LOGGER.debug("[%s] Duplicate detected: %s", model_cls.__name__, error_msg)
            continue

        seen_hashes.add(key)
        stored.append(normalised)
        if pk_alias:
            pk_value = normalised.get(pk_alias)
            if is_valid_uuid(pk_value) and not is_placeholder_uuid(pk_value):
                existing_ids.add(str(pk_value))
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


def _has_verified_fields(model_cls: Type[BaseModel]) -> bool:
    """
    Check if a model class contains verified fields (flat structure).

    Detects fields that have corresponding _quote and _confidence fields.

    Args:
        model_cls: The Pydantic model class to check.

    Returns:
        True if the model has verified fields, False otherwise.
    """
    field_names = set(model_cls.model_fields.keys())

    for field_name in field_names:
        # Skip if this is a quote or confidence field itself
        if field_name.endswith("_quote") or field_name.endswith("_confidence"):
            continue

        # Check if this field has corresponding _quote and _confidence fields
        quote_field = f"{field_name}_quote"
        confidence_field = f"{field_name}_confidence"

        if quote_field in field_names and confidence_field in field_names:
            return True

    return False


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
