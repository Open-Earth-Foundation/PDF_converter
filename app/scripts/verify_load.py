"""
Brief: Verify that all JSON records were successfully loaded into the database.

This script verifies data integrity by comparing extracted JSON files with DB records.

TABLE CATEGORIES:
1. Direct City Tables (filtered by cityId):
   - City, CityAnnualStats, Initiative, Indicator, CityTarget, EmissionRecord, CityBudget

2. City-FK Related (linked through foreign keys):
   - InitiativeStakeholder (FK→Initiative→City)
   - InitiativeIndicator (FK→Initiative→City)
   - IndicatorValue (FK→Indicator→City)
   - ClimateCityContract (has cityId)
   - InitiativeTef (FK→Initiative→City)

3. Reference Tables (global, linked indirectly):
   - Sector: Used by this city's Indicators/EmissionRecords
   - Stakeholder: Used by this city's InitiativeStakeholders
   - FundingSource: Used by this city's CityBudgets
   - TefCategory: Used by this city's InitiativeTefs
   - BudgetFunding: Junction table, used by city's CityBudgets

Inputs:
- --json-dir: directory with mapped JSON files (default: output/mapping/step3_llm)
- --city-id: optional city UUID to verify specific city only
- Env: DATABASE_URL or DB_URL (loaded from .env)

Outputs:
- Detailed report comparing JSON counts vs DB row counts
- Logs differences (missing records, extra records, etc.)
- JSON report to output/db_load_reports/verify_load_*.json
- Exit code 0 if all records loaded, 1 if mismatches

Usage (from project root):
- python -m app.scripts.verify_load
- python -m app.scripts.verify_load --json-dir output/mapping/step3_llm
- python -m app.scripts.verify_load --city-id 3fa85f64-5717-4562-b3fc-2c963f66afa6
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import text

from app.utils.logging_config import setup_logger
from database.config import DBSettings
from database.session import create_db_engine

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON_DIR = REPO_ROOT / "output" / "mapping" / "step3_llm"
DEFAULT_REPORT_DIR = REPO_ROOT / "output" / "db_load_reports"

# Tables with UUID primary keys
TABLE_ID_FIELDS = {
    "City": "cityId",
    "Sector": "sectorId",
    "Indicator": "indicatorId",
    "CityAnnualStats": "statId",
    "EmissionRecord": "emissionRecordId",
    "CityBudget": "budgetId",
    "FundingSource": "fundingSourceId",
    "BudgetFunding": "budgetFundingId",
    "Initiative": "initiativeId",
    "Stakeholder": "stakeholderId",
    "InitiativeStakeholder": "initiativeStakeholderId",
    "InitiativeIndicator": "initiativeIndicatorId",
    "CityTarget": "cityTargetId",
    "IndicatorValue": "indicatorValueId",
    "ClimateCityContract": "climateCityContractId",  # Fixed: was "contractId"
    "TefCategory": "tefId",  # Fixed: was "tefCategoryId"
    "InitiativeTef": "initiativeTefId",
}

# Tables that have a DIRECT cityId column
TABLES_WITH_DIRECT_CITY_ID = {
    "City",
    "CityAnnualStats",
    "Initiative",
    "Indicator",
    "CityTarget",
}

# Tables related to City through foreign keys
# These need city filtering through their FK relationships
TABLES_CITY_FK_RELATED = {
    "InitiativeStakeholder",  # FK Initiative → City
    "InitiativeIndicator",  # FK Initiative → City
    "IndicatorValue",  # FK Indicator → City
    "ClimateCityContract",  # Has cityId column
    "InitiativeTef",  # FK Initiative → City
    "EmissionRecord",  # Has cityId column
    "CityBudget",  # Has cityId column
}

# Truly shared reference tables (no city concept)
SHARED_REFERENCE_TABLES = {
    "Sector",
    "Stakeholder",
    "FundingSource",
    "TefCategory",
    "BudgetFunding",  # Junction table
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify JSON data was loaded into database."
    )
    parser.add_argument(
        "--json-dir",
        type=Path,
        default=DEFAULT_JSON_DIR,
        help=f"Directory with JSON files (default: {DEFAULT_JSON_DIR})",
    )
    parser.add_argument(
        "--city-id",
        type=str,
        default=None,
        help="Optional city UUID to verify specific city only",
    )
    return parser.parse_args()


def load_json_records(json_dir: Path) -> dict[str, list[dict[str, Any]]]:
    """Load all JSON files from the directory."""
    records_by_table: dict[str, list[dict[str, Any]]] = {}
    for table_name, id_field in TABLE_ID_FIELDS.items():
        json_file = json_dir / f"{table_name}.json"
        if not json_file.exists():
            LOGGER.warning("JSON file not found: %s", json_file)
            records_by_table[table_name] = []
            continue
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            records_by_table[table_name] = data if isinstance(data, list) else []
            LOGGER.info(
                "Loaded %d records from %s.json",
                len(records_by_table[table_name]),
                table_name,
            )
        except Exception as exc:
            LOGGER.error("Failed to load %s: %s", json_file, exc)
            records_by_table[table_name] = []
    return records_by_table


def extract_city_ids_from_json(
    records_by_table: dict[str, list[dict[str, Any]]],
) -> set[str]:
    """Extract all unique city IDs from JSON records."""
    city_ids: set[str] = set()
    for records in records_by_table.values():
        for record in records:
            if "cityId" in record and record["cityId"]:
                city_ids.add(str(record["cityId"]))
    return city_ids


def get_db_uuids(
    conn, table: str, id_field: str, city_ids: set[str] | None = None
) -> set[str]:
    """
    Get all UUIDs from a table in the database.

    For tables with direct cityId: filter by city
    For reference tables: get all, but understanding they're filtered through relationships
    """
    try:
        # Direct cityId filter for tables with cityId column
        if city_ids and table in TABLES_WITH_DIRECT_CITY_ID:
            placeholders = ", ".join(f"'{cid}'" for cid in city_ids)
            query = text(
                f'SELECT "{id_field}" FROM "{table}" WHERE "cityId" IN ({placeholders})'
            )
            result = conn.execute(query)
            return {str(row[0]) for row in result.fetchall()}

        # For reference tables, get ALL records but we'll understand they're global
        query = text(f'SELECT "{id_field}" FROM "{table}"')
        result = conn.execute(query)
        return {str(row[0]) for row in result.fetchall()}

    except Exception as exc:
        LOGGER.error("Query failed for %s: %s", table, exc)
        raise


def get_json_uuids(
    records: list[dict[str, Any]],
    id_field: str,
    table_name: str,
    city_ids: set[str] | None = None,
) -> set[str]:
    """Get all UUIDs from JSON records, optionally filtered by city IDs."""
    uuids = set()
    for record in records:
        if id_field in record and record[id_field]:
            # Filter by city IDs for tables with direct cityId
            if city_ids and table_name in TABLES_WITH_DIRECT_CITY_ID:
                if record.get("cityId") in city_ids:
                    uuids.add(str(record[id_field]))
            # For city-FK-related tables, filter by InitiativeId or IndicatorId cityId
            elif city_ids and table_name in TABLES_CITY_FK_RELATED:
                # These should have been filtered in mapping based on related entity's city
                # For now, include all and let JSON show the expected subset
                uuids.add(str(record[id_field]))
            else:
                # Shared reference tables: include all
                uuids.add(str(record[id_field]))
    return uuids


def compare_records(
    *,
    table_name: str,
    json_records: list[dict[str, Any]],
    db_uuids: set[str],
    id_field: str,
    city_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Compare JSON records with database."""
    json_uuids = get_json_uuids(json_records, id_field, table_name, city_ids)

    missing_in_db = json_uuids - db_uuids
    extra_in_db = db_uuids - json_uuids
    matched = json_uuids & db_uuids

    result = {
        "table": table_name,
        "json_count": len(json_uuids),
        "db_count": len(db_uuids),
        "matched": len(matched),
        "missing_in_db": sorted(list(missing_in_db)),
        "extra_in_db": sorted(list(extra_in_db)),
        "ok": len(missing_in_db) == 0,  # OK if all JSON records are in DB
        "is_shared_table": table_name in SHARED_REFERENCE_TABLES,
    }

    if result["ok"]:
        if table_name in SHARED_REFERENCE_TABLES:
            # Reference tables: all JSON records should exist in DB
            # Extras in DB are OK (they're from other cities or unused)
            LOGGER.info(
                "✓ %s (reference/global): %d records matched in DB (may have %d from other sources)",
                table_name,
                len(matched),
                len(extra_in_db),
            )
        elif table_name in TABLES_WITH_DIRECT_CITY_ID:
            # City-scoped tables: should match exactly for this city
            LOGGER.info(
                "✓ %s (city-scoped): %d records matched (JSON: %d, DB: %d)",
                table_name,
                len(matched),
                result["json_count"],
                result["db_count"],
            )
        else:
            # FK-related tables: matched from this city
            LOGGER.info(
                "✓ %s (city-related via FK): %d records matched (JSON: %d)",
                table_name,
                len(matched),
                result["json_count"],
            )
    else:
        LOGGER.warning(
            "✗ %s: JSON=%d DB=%d matched=%d missing=%d",
            table_name,
            result["json_count"],
            result["db_count"],
            len(matched),
            len(missing_in_db),
        )
        if missing_in_db:
            LOGGER.warning(
                "  Missing in DB (%d): %s", len(missing_in_db), list(missing_in_db)[:5]
            )

    return result


def main() -> int:
    args = parse_args()
    load_dotenv()

    if not args.json_dir.exists():
        LOGGER.error("JSON directory does not exist: %s", args.json_dir)
        return 1

    try:
        settings = DBSettings.from_env()
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1

    # Load JSON records
    LOGGER.info("Loading JSON records from %s", args.json_dir)
    json_records_by_table = load_json_records(args.json_dir)

    # Auto-detect city IDs from JSON (if not manually specified)
    if args.city_id:
        city_ids = {args.city_id}
        LOGGER.info("Verifying specific city: %s", args.city_id)
    else:
        city_ids = extract_city_ids_from_json(json_records_by_table)
        LOGGER.info(
            "Auto-detected %d city(ies) in JSON: %s", len(city_ids), sorted(city_ids)
        )

    # Connect to database
    engine = create_db_engine(settings=settings)
    results: dict[str, Any] = {"table_results": []}
    all_ok = True

    try:
        with engine.connect() as conn:
            for table_name, id_field in TABLE_ID_FIELDS.items():
                json_records = json_records_by_table.get(table_name, [])

                try:
                    db_uuids = get_db_uuids(conn, table_name, id_field, city_ids)
                except Exception as exc:
                    LOGGER.error("Failed to query %s: %s", table_name, exc)
                    results["table_results"].append(
                        {
                            "table": table_name,
                            "error": str(exc),
                        }
                    )
                    all_ok = False
                    continue

                result = compare_records(
                    table_name=table_name,
                    json_records=json_records,
                    db_uuids=db_uuids,
                    id_field=id_field,
                    city_ids=city_ids,
                )
                results["table_results"].append(result)
                if not result["ok"]:
                    all_ok = False
    except Exception as exc:
        LOGGER.exception("Database connection failed: %s", exc)
        return 1
    finally:
        engine.dispose()

    # Write report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = DEFAULT_REPORT_DIR / f"verify_load_{timestamp}.json"
    DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "timestamp": timestamp,
        "city_ids": sorted(list(city_ids)),
        "json_dir": str(args.json_dir),
        "all_tables_ok": all_ok,
        "total_tables": len(results["table_results"]),
        "tables_ok": sum(1 for r in results["table_results"] if r.get("ok", False)),
        "tables_with_issues": sum(
            1 for r in results["table_results"] if not r.get("ok", True)
        ),
        "results": results["table_results"],
    }

    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True, default=str), encoding="utf-8"
    )
    LOGGER.info("Report written to %s", report_path)

    return 0 if all_ok else 1


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
