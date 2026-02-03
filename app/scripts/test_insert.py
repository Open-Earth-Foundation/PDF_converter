"""
Brief: Report row counts and sample rows for all core tables.

Inputs:
- --limit: number of sample rows to show per table (default: 1)
- Env: DATABASE_URL in the repo root .env file

Outputs:
- Logs counts and sample rows for each table
- Writes a JSON report (defaults to output/db_load_reports/test_insert_report_*.json)
- Exit code 0 on success, 1 on failure

Usage (from project root):
- python -m app.scripts.test_insert
- python -m app.scripts.test_insert --limit 2
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from utils.logging_config import setup_logger
from database.config import DBSettings
from database.session import create_db_engine

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = REPO_ROOT / "output" / "db_load_reports"

TABLES: tuple[str, ...] = (
    "City",
    "Sector",
    "Indicator",
    "CityAnnualStats",
    "EmissionRecord",
    "CityBudget",
    "FundingSource",
    "BudgetFunding",
    "Initiative",
    "Stakeholder",
    "InitiativeStakeholder",
    "InitiativeIndicator",
    "CityTarget",
    "IndicatorValue",
    "ClimateCityContract",
    "TefCategory",
    "InitiativeTef",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report row counts and sample rows for core tables."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of sample rows to show per table (default: 1).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=None,
        help="Optional report output path (JSON).",
    )
    return parser.parse_args()


def fetch_count(conn, table: str) -> int:
    result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
    return int(result.scalar_one())


def fetch_samples(conn, table: str, limit: int) -> list[dict]:
    if limit <= 0:
        return []
    result = conn.execute(text(f'SELECT * FROM "{table}" LIMIT :limit'), {"limit": limit})
    return [dict(row) for row in result.mappings().all()]


def ensure_report_path(path: Path | None) -> Path:
    if path:
        return path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_REPORT_DIR / f"test_insert_report_{timestamp}.json"


def write_report(
    *,
    report_path: Path,
    limit: int,
    tables: dict[str, dict[str, object]],
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "summary": {
            "limit": limit,
            "report_path": str(report_path),
        },
        "tables": tables,
    }
    report_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True, default=str), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    if args.limit < 0:
        LOGGER.error("--limit must be >= 0.")
        return 1

    load_dotenv(REPO_ROOT / ".env")
    try:
        settings = DBSettings.from_env()
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1

    report_path = ensure_report_path(args.report_path)
    engine = create_db_engine(settings=settings)
    try:
        with engine.connect() as conn:
            tables: dict[str, dict[str, object]] = {}
            for table in TABLES:
                count = fetch_count(conn, table)
                LOGGER.info("Table %s: count=%d", table, count)
                samples = fetch_samples(conn, table, args.limit)
                if not samples:
                    LOGGER.info("Table %s: sample=None", table)
                else:
                    for idx, row in enumerate(samples, start=1):
                        LOGGER.info(
                            "Table %s: sample[%d]=%s",
                            table,
                            idx,
                            json.dumps(row, ensure_ascii=True, default=str),
                        )
                tables[table] = {"count": count, "samples": samples}
        write_report(report_path=report_path, limit=args.limit, tables=tables)
        LOGGER.info("Report written to %s", report_path)
    except Exception as exc:
        LOGGER.exception("Failed to query tables: %s", exc)
        return 1
    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
