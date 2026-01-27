"""Schema helpers for db insert loader."""

from __future__ import annotations

from typing import Any, Type

from pydantic import BaseModel

from app.modules.db_insert.models import SchemaInfo

_SCHEMA_CACHE: dict[Type[BaseModel], SchemaInfo] = {}


def get_schema_info(schema: Type[BaseModel]) -> SchemaInfo:
    cached = _SCHEMA_CACHE.get(schema)
    if cached:
        return cached
    alias_to_field: dict[str, str] = {}
    field_to_alias: dict[str, str] = {}
    alias_to_type: dict[str, Any] = {}
    for field_name, field in schema.model_fields.items():
        alias = field.alias or field_name
        alias_to_field[alias] = field_name
        field_to_alias[field_name] = alias
        alias_to_type[alias] = field.annotation
    info = SchemaInfo(
        schema=schema,
        alias_to_field=alias_to_field,
        field_to_alias=field_to_alias,
        alias_to_type=alias_to_type,
    )
    _SCHEMA_CACHE[schema] = info
    return info


def to_model_payload(normalized: dict[str, Any], info: SchemaInfo) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for alias, value in normalized.items():
        field_name = info.alias_to_field.get(alias)
        if field_name is None:
            continue
        payload[field_name] = value
    return payload
