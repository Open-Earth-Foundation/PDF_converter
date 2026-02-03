"""
Brief: Load mapped JSON outputs into the database with validation and reporting.

The mapping pipeline has 3 stages:
- step1_cleared: Clear and prepare raw extracted data
- step2_city: Map and anchor city data
- step3_llm: LLM-based mapping to generate final normalized JSON files (this script's input)

Inputs:
- --input-dir: Directory with step3_llm outputs (final normalized JSON files for all tables).
  Default: output/mapping/step3_llm
- --mode: Validation mode (default: validate)
  * validate: Strict mode - validate all records against schema, reject any with errors
  * permissive: Lenient mode - skip unknown fields, attempt to load even with minor issues
- --report-path: Optional custom path for JSON report output. Default: auto-generated timestamp
- --dry-run: Run validation without inserting into database (read-only audit run)
- --on-error: Error handling strategy (default: stop)
  * stop: Halt processing immediately on first error
  * continue: Skip failed records and keep processing remaining data
- --atomic: Use single transaction across all tables (all-or-nothing semantics for entire load).
  If any table fails, entire load is rolled back
- --per-city: Use per-city atomic transactions (each city's data is all-or-nothing,
  but different cities load independently). Useful for partial recovery if one city fails
- Env: DATABASE_URL or DB_URL (loaded from .env for database connection)

Outputs:
- Inserts rows into the database (unless --dry-run)
- Report JSON with per-table counts and error summaries
- Logs to stdout/stderr

Usage (from project root):
- python -m app.modules.db_insert.scripts.load_mapped_data --dry-run
- python -m app.modules.db_insert.scripts.load_mapped_data --per-city
- python -m app.modules.db_insert.scripts.load_mapped_data --mode permissive --on-error continue
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from app.modules.db_insert.loader import (
    DEFAULT_INPUT_DIR,
    ensure_report_path,
    run_load,
)
from app.utils.logging_config import setup_logger

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load mapped JSON outputs into the database."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory with step3 outputs (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--mode",
        choices=("validate", "permissive"),
        default="validate",
        help="Validation mode (default: validate).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional report output path (JSON).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only; skip DB inserts.",
    )
    parser.add_argument(
        "--on-error",
        choices=("stop", "continue"),
        default="stop",
        help="Stop on first error or continue (default: stop).",
    )
    parser.add_argument(
        "--atomic",
        action="store_true",
        help="Single transaction across all tables.",
    )
    parser.add_argument(
        "--per-city",
        action="store_true",
        help="Atomic per city (each city is all-or-nothing, but cities load independently).",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    report_path = ensure_report_path(args.report_path)
    LOGGER.info(
        "Starting DB load: mode=%s dry_run=%s atomic=%s per_city=%s on_error=%s input_dir=%s",
        args.mode,
        args.dry_run,
        args.atomic,
        args.per_city,
        args.on_error,
        args.input_dir,
    )
    return run_load(
        input_dir=args.input_dir,
        mode=args.mode,
        report_path=report_path,
        dry_run=args.dry_run,
        on_error=args.on_error,
        atomic=args.atomic,
        per_city=args.per_city,
    )


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
