"""Normalization and type coercion for db insert loader."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, get_args, get_origin
from uuid import UUID

from app.modules.db_insert.models import SchemaInfo


def unwrap_optional(annotation: Any) -> Any:
    origin = get_origin(annotation)
    if origin is None:
        return annotation
    args = [arg for arg in get_args(annotation) if arg is not type(None)]
    if len(args) == 1:
        return args[0]
    return annotation


def clean_numeric_string(value: str) -> str:
    return value.replace(",", "").replace("_", "").strip()


def coerce_int(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal):
        try:
            return int(value)
        except Exception:
            return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        cleaned = clean_numeric_string(value)
        if cleaned.isdigit() or (
            cleaned.startswith("-") and cleaned[1:].isdigit()
        ):
            return int(cleaned)
    return value


def coerce_decimal(value: Any) -> Any:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        cleaned = clean_numeric_string(value)
        if cleaned == "":
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return value
    return value


def coerce_date(value: Any) -> Any:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, int) and 1 <= value <= 9999:
        return date(value, 1, 1)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        if text.isdigit() and len(text) == 4:
            return date(int(text), 1, 1)
        text = text.replace("/", "-")
        if "T" in text:
            text = text.split("T")[0]
        if text.endswith("Z"):
            text = text[:-1]
        try:
            return date.fromisoformat(text)
        except ValueError:
            return value
    return value


def coerce_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, int) and 1 <= value <= 9999:
        return datetime(value, 1, 1)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        if text.isdigit() and len(text) == 4:
            return datetime(int(text), 1, 1)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            try:
                parsed = datetime.fromisoformat(text.split("T")[0])
            except ValueError:
                return value
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    return value


def coerce_uuid(value: Any) -> Any:
    if isinstance(value, UUID):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return UUID(text)
        except ValueError:
            return value
    return value


def coerce_value(value: Any, annotation: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return None
    if annotation is None:
        return value
    target = unwrap_optional(annotation)
    if target is str:
        return value
    if target is int:
        return coerce_int(value)
    if target is Decimal:
        return coerce_decimal(value)
    if target is date:
        return coerce_date(value)
    if target is datetime:
        return coerce_datetime(value)
    if target is UUID:
        return coerce_uuid(value)
    return value


def normalize_record(
    record: dict[str, Any],
    info: SchemaInfo,
    *,
    drop_unknown: bool,
) -> tuple[dict[str, Any], list[str]]:
    normalized: dict[str, Any] = {}
    unknown_keys: list[str] = []
    for key, value in record.items():
        if key in info.alias_to_field:
            alias = key
        elif key in info.field_to_alias:
            alias = info.field_to_alias[key]
        else:
            unknown_keys.append(key)
            if not drop_unknown:
                normalized[key] = value
            continue
        normalized[alias] = coerce_value(value, info.alias_to_type.get(alias))
    return normalized, unknown_keys
