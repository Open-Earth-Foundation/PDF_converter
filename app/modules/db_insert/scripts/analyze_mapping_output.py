"""
Brief: Analyze mapped JSON outputs for duplicate keys and unique constraint issues.

The mapping pipeline has 3 stages:
- step1_cleared: Clear and prepare raw extracted data
- step2_city: Map and anchor city data
- step3_llm: LLM-based mapping to generate final normalized JSON files (this script's input)

Inputs:
- --input-dir: Directory with step3_llm outputs (final normalized JSON files to analyze).
  Scans for duplicate primary/composite keys before database insertion.
  Default: output/mapping/step3_llm
- --report-path: Optional custom path for JSON report output. Default: auto-generated timestamp
- --max-details: Maximum number of duplicate groups to include in detailed report (default: 50).
  Limits report size while maintaining summary statistics for all tables

Outputs:
- Logs summary of duplicate key issues per table (printed to stdout)
- JSON report with duplicate details and table summaries
  Contains: duplicate record indices, affected keys, and suggestions for resolution

Usage (from project root):
- python -m app.modules.db_insert.scripts.analyze_mapping_output
- python -m app.modules.db_insert.scripts.analyze_mapping_output --input-dir output/mapping/step3_llm
- python -m app.modules.db_insert.scripts.analyze_mapping_output --max-details 100
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from sqlalchemy import UniqueConstraint

from app.modules.db_insert.models import TableSpec
from app.modules.db_insert.loader import (
    DEFAULT_INPUT_DIR,
    DEFAULT_REPORT_DIR,
    TABLE_SPECS,
    get_record_id,
    read_json_list,
)
from utils.logging_config import setup_logger

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze mapped JSON outputs for duplicate keys."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory with step3 outputs (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional report output path (JSON).",
    )
    parser.add_argument(
        "--max-details",
        type=int,
        default=50,
        help="Max duplicate groups to include in the report (default: 50).",
    )
    return parser.parse_args()


def ensure_report_path(path: Path | None) -> Path:
    if path:
        return path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_REPORT_DIR / f"db_input_analysis_report_{timestamp}.json"


def get_unique_constraints(model: type[Any]) -> list[tuple[str, list[str]]]:
    constraints: list[tuple[str, list[str]]] = []
    for constraint in model.__table__.constraints:
        if not isinstance(constraint, UniqueConstraint):
            continue
        columns = [col.name for col in constraint.columns]
        name = cast(str, constraint.name or f"unique_{'_'.join(columns)}")
        constraints.append((name, columns))
    return constraints


def analyze_table(
    *,
    records: list[dict[str, Any]],
    spec: TableSpec,
    max_details: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    pk_alias = spec.pk_alias or spec.pk_field
    pk_map: dict[str, list[int]] = {}
    pk_missing = 0
    if pk_alias:
        for idx, record in enumerate(records):
            value = record.get(pk_alias)
            if value is None:
                pk_missing += 1
                continue
            key = str(value)
            pk_map.setdefault(key, []).append(idx)

    unique_constraints = get_unique_constraints(spec.model)
    constraint_maps: dict[str, dict[tuple[Any, ...], list[int]]] = {}
    constraint_missing: dict[str, int] = {}
    for name, _columns in unique_constraints:
        constraint_maps[name] = {}
        constraint_missing[name] = 0

    for idx, record in enumerate(records):
        for name, columns in unique_constraints:
            values: list[Any] = []
            missing = False
            for column in columns:
                value = record.get(column)
                if value is None:
                    missing = True
                    break
                values.append(value)
            if missing:
                constraint_missing[name] += 1
                continue
            key = tuple(values)
            constraint_maps[name].setdefault(key, []).append(idx)

    duplicates: list[dict[str, Any]] = []
    pk_duplicates = {key: idxs for key, idxs in pk_map.items() if len(idxs) > 1}
    duplicate_groups_total = len(pk_duplicates)

    if pk_alias and pk_duplicates:
        for key, idxs in pk_duplicates.items():
            if len(duplicates) >= max_details:
                break
            record_ids = [get_record_id(records[i], spec) for i in idxs]
            duplicates.append(
                {
                    "table": spec.name,
                    "constraint": "primary_key",
                    "columns": [pk_alias],
                    "key": {pk_alias: key},
                    "record_indexes": idxs,
                    "record_ids": record_ids,
                }
            )

    unique_summary: dict[str, dict[str, Any]] = {}
    for name, columns in unique_constraints:
        groups = {
            key: idxs for key, idxs in constraint_maps[name].items() if len(idxs) > 1
        }
        duplicate_groups_total += len(groups)
        unique_summary[name] = {
            "columns": columns,
            "duplicate_groups": len(groups),
            "missing_key_fields": constraint_missing[name],
        }
        if not groups:
            continue
        for key, idxs in groups.items():
            if len(duplicates) >= max_details:
                break
            record_ids = [get_record_id(records[i], spec) for i in idxs]
            key_payload = {col: value for col, value in zip(columns, key)}
            duplicates.append(
                {
                    "table": spec.name,
                    "constraint": name,
                    "columns": columns,
                    "key": key_payload,
                    "record_indexes": idxs,
                    "record_ids": record_ids,
                }
            )

    summary = {
        "records": len(records),
        "missing_primary_key": pk_missing if pk_alias else 0,
        "duplicate_primary_keys": len(pk_duplicates),
        "unique_constraints": unique_summary,
    }
    return summary, duplicates, duplicate_groups_total


def write_report(report_path: Path, payload: dict[str, Any]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.max_details < 0:
        LOGGER.error("--max-details must be >= 0.")
        return 1

    report_path = ensure_report_path(args.report_path)
    duplicates: list[dict[str, Any]] = []
    tables_summary: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    duplicate_groups_total = 0

    for spec in TABLE_SPECS:
        path = args.input_dir / spec.filename
        try:
            records = read_json_list(path)
        except ValueError as exc:
            message = str(exc)
            LOGGER.error("Failed to load %s: %s", path, message)
            errors.append(
                {
                    "table": spec.name,
                    "file": str(path),
                    "message": message,
                }
            )
            tables_summary[spec.name] = {"records": 0, "error": message}
            continue

        summary, table_duplicates, table_duplicate_groups = analyze_table(
            records=records, spec=spec, max_details=args.max_details
        )
        tables_summary[spec.name] = summary
        duplicate_groups_total += table_duplicate_groups

        for entry in table_duplicates:
            if len(duplicates) >= args.max_details:
                break
            duplicates.append(entry)

        LOGGER.info(
            "Table %s: records=%d duplicate_pk=%d",
            spec.name,
            summary["records"],
            summary["duplicate_primary_keys"],
        )
        for constraint_name, detail in summary["unique_constraints"].items():
            if detail["duplicate_groups"] > 0:
                LOGGER.warning(
                    "Table %s: duplicate unique groups=%d (%s)",
                    spec.name,
                    detail["duplicate_groups"],
                    constraint_name,
                )

    report_payload = {
        "summary": {
            "input_dir": str(args.input_dir),
            "report_path": str(report_path),
            "tables_analyzed": len(TABLE_SPECS),
            "duplicate_groups_total": duplicate_groups_total,
            "duplicates_truncated": duplicate_groups_total > len(duplicates),
            "max_details": args.max_details,
        },
        "tables": tables_summary,
        "duplicates": duplicates,
        "errors": errors,
    }
    write_report(report_path, report_payload)
    LOGGER.info("Report written to %s", report_path)

    if duplicate_groups_total > 0 or errors:
        return 1
    return 0


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
