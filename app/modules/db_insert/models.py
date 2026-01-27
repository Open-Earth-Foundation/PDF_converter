"""Data structures for db insert loading."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Type

from pydantic import BaseModel

MAX_ERROR_DETAILS = 50


class StopProcessing(Exception):
    """Stop processing due to error policy."""


@dataclass(frozen=True)
class TableSpec:
    name: str
    filename: str
    schema: Type[BaseModel]
    model: Type[Any]
    pk_field: str | None
    pk_alias: str | None


@dataclass
class TableCounts:
    loaded: int = 0
    validated: int = 0
    inserted: int = 0
    failed: int = 0


@dataclass
class LoadReport:
    mode: str
    dry_run: bool
    atomic: bool
    on_error: str
    input_dir: str
    report_path: str
    validation_skipped: bool
    tables: Dict[str, TableCounts]
    missing_fields: Dict[str, int] = field(default_factory=dict)
    error_count_total: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)

    def record_error(self, entry: dict[str, Any]) -> None:
        self.error_count_total += 1
        if len(self.errors) < MAX_ERROR_DETAILS:
            self.errors.append(entry)

    def record_missing_field(self, field_name: str) -> None:
        self.missing_fields[field_name] = self.missing_fields.get(field_name, 0) + 1


@dataclass(frozen=True)
class SchemaInfo:
    schema: Type[BaseModel]
    alias_to_field: dict[str, str]
    field_to_alias: dict[str, str]
    alias_to_type: dict[str, Any]
