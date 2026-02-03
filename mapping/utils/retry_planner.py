"""
Utilities to build retry feedback for LLM mapping based on FK and uniqueness checks.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from mapping.utils.validate_foreign_keys import build_pk_index, find_fk_issues

UNIQUE_KEY_RULES: dict[str, list[str]] = {
    "CityAnnualStats.json": ["cityId", "year"],
    "EmissionRecord.json": ["cityId", "year", "sectorId", "scope", "ghgType"],
    "InitiativeStakeholder.json": ["initiativeId", "stakeholderId"],
    "InitiativeIndicator.json": ["initiativeId", "indicatorId"],
    "IndicatorValue.json": ["indicatorId", "year"],
    "ClimateCityContract.json": ["cityId"],
    "InitiativeTef.json": ["initiativeId", "tefId"],
}


def find_duplicate_groups(
    records_by_table: dict[str, list[dict]],
    max_groups: int = 50,
) -> list[dict[str, Any]]:
    duplicates: list[dict[str, Any]] = []
    for table, columns in UNIQUE_KEY_RULES.items():
        records = records_by_table.get(table, [])
        key_map: dict[tuple[Any, ...], list[int]] = {}
        for idx, record in enumerate(records):
            values: list[Any] = []
            missing = False
            for col in columns:
                value = record.get(col)
                if value in (None, ""):
                    missing = True
                    break
                values.append(value)
            if missing:
                continue
            key = tuple(values)
            key_map.setdefault(key, []).append(idx)
        for key, idxs in key_map.items():
            if len(idxs) <= 1:
                continue
            if max_groups is not None and len(duplicates) >= max_groups:
                return duplicates
            duplicates.append(
                {
                    "table": table,
                    "columns": columns,
                    "key": {col: val for col, val in zip(columns, key)},
                    "record_indexes": idxs,
                }
            )
    return duplicates


def build_feedback_by_table(
    fk_issues: list[tuple[str, int, str, str]],
    duplicate_groups: list[dict[str, Any]],
) -> dict[str, dict[int, list[str]]]:
    feedback: dict[str, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    for table, idx, field, message in fk_issues:
        feedback[table][idx].append(f"{field}: {message}")

    for group in duplicate_groups:
        table = group["table"]
        columns = group["columns"]
        key = group["key"]
        key_text = ", ".join(f"{col}={key.get(col)}" for col in columns)
        message = (
            "Duplicate unique key on "
            f"({', '.join(columns)}): {key_text}. "
            "Choose a different match if possible to make this combination unique."
        )
        for idx in group["record_indexes"]:
            feedback[table][idx].append(message)

    return feedback


def build_retry_plan(
    records_by_table: dict[str, list[dict]],
    max_duplicate_groups: int = 50,
) -> tuple[
    list[tuple[str, int, str, str]],
    list[dict[str, Any]],
    dict[str, dict[int, list[str]]],
]:
    pk_index = build_pk_index(records_by_table)
    fk_issues = find_fk_issues(records_by_table, pk_index)
    duplicate_groups = find_duplicate_groups(
        records_by_table, max_groups=max_duplicate_groups
    )
    feedback_by_table = build_feedback_by_table(fk_issues, duplicate_groups)
    return fk_issues, duplicate_groups, feedback_by_table


__all__ = [
    "UNIQUE_KEY_RULES",
    "build_retry_plan",
    "build_feedback_by_table",
    "find_duplicate_groups",
]
