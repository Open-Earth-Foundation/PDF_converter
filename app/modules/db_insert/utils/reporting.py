"""Report helpers for db insert loader."""

from __future__ import annotations

import json
from pathlib import Path

from app.modules.db_insert.models import LoadReport


def write_report(report: LoadReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "mode": report.mode,
            "dry_run": report.dry_run,
            "atomic": report.atomic,
            "on_error": report.on_error,
            "input_dir": report.input_dir,
            "report_path": report.report_path,
            "validation_skipped": report.validation_skipped,
            "error_count_total": report.error_count_total,
            "errors_truncated": report.error_count_total > len(report.errors),
        },
        "tables": {
            table: {
                "loaded": counts.loaded,
                "validated": counts.validated,
                "inserted": counts.inserted,
                "failed": counts.failed,
            }
            for table, counts in report.tables.items()
        },
        "missing_fields": report.missing_fields,
        "errors": report.errors,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True), encoding="utf-8")
