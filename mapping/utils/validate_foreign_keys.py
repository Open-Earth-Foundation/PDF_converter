"""
Quick FK checker for step3 LLM outputs.

Run:
    python -m mapping.scripts.validate_foreign_keys [path-to-step3-dir]
Defaults to mapping/workflow_output/step3_llm when no path is provided.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Iterable

from mapping.utils.llm_utils import load_json_list as load_json_list_base

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent / "workflow_output" / "step3_llm"

# Configuration: primary key per file and the foreign keys it should resolve.
# fk tuple: (field_name, target_file, is_optional)
TABLE_CONFIG: dict[str, dict] = {
    "City.json": {"pk": "cityId"},
    "CityAnnualStats.json": {"pk": "statId", "fks": [("cityId", "City.json", False)]},
    "ClimateCityContract.json": {
        "pk": "climateCityContractId",
        "fks": [("cityId", "City.json", False)],
    },
    "Sector.json": {"pk": "sectorId"},
    "EmissionRecord.json": {
        "pk": "emissionRecordId",
        "fks": [
            ("cityId", "City.json", False),
            ("sectorId", "Sector.json", False),
        ],
    },
    "CityBudget.json": {"pk": "budgetId", "fks": [("cityId", "City.json", False)]},
    "FundingSource.json": {"pk": "fundingSourceId"},
    "BudgetFunding.json": {
        "pk": "budgetFundingId",
        "fks": [
            ("budgetId", "CityBudget.json", False),
            ("fundingSourceId", "FundingSource.json", False),
        ],
    },
    "Initiative.json": {"pk": "initiativeId", "fks": [("cityId", "City.json", False)]},
    "Stakeholder.json": {"pk": "stakeholderId"},
    "InitiativeStakeholder.json": {
        "pk": "initiativeStakeholderId",
        "fks": [
            ("initiativeId", "Initiative.json", False),
            ("stakeholderId", "Stakeholder.json", False),
        ],
    },
    "Indicator.json": {
        "pk": "indicatorId",
        "fks": [
            ("cityId", "City.json", False),
            ("sectorId", "Sector.json", True),
        ],
    },
    "IndicatorValue.json": {"pk": "indicatorValueId", "fks": [("indicatorId", "Indicator.json", False)]},
    "CityTarget.json": {
        "pk": "cityTargetId",
        "fks": [
            ("cityId", "City.json", False),
            ("indicatorId", "Indicator.json", False),
        ],
    },
    "InitiativeIndicator.json": {
        "pk": "initiativeIndicatorId",
        "fks": [
            ("initiativeId", "Initiative.json", False),
            ("indicatorId", "Indicator.json", False),
        ],
    },
    "TefCategory.json": {"pk": "tefId"},
    "InitiativeTef.json": {
        "pk": "initiativeTefId",
        "fks": [
            ("initiativeId", "Initiative.json", False),
            ("tefId", "TefCategory.json", False),
        ],
    },
}


def load_json_list(path: Path) -> list[dict] | None:
    """
    Load a JSON list from disk, returning None if missing or corrupted.
    """
    try:
        return load_json_list_base(path)
    except ValueError as exc:
        LOGGER.error(f"Failed to load {path}: {exc}")
        raise


def build_pk_index(records_by_table: dict[str, list[dict]]) -> dict[str, set]:
    pk_index: dict[str, set] = {}
    for table, cfg in TABLE_CONFIG.items():
        pk_field = cfg["pk"]
        values = {r[pk_field] for r in records_by_table.get(table, []) if r.get(pk_field)}
        pk_index[table] = values
    return pk_index


def find_fk_issues(
    records_by_table: dict[str, list[dict]],
    pk_index: dict[str, set],
) -> list[tuple[str, int, str, str]]:
    """
    Returns a list of issues:
    (table, record_index, field, message)
    """
    issues: list[tuple[str, int, str, str]] = []
    for table, cfg in TABLE_CONFIG.items():
        fks: Iterable[tuple[str, str, bool]] = cfg.get("fks", [])
        for idx, record in enumerate(records_by_table.get(table, [])):
            for field, target_table, optional in fks:
                value = record.get(field)
                if value in (None, ""):
                    if optional:
                        continue
                    issues.append((table, idx, field, "missing required FK value"))
                    continue
                if value not in pk_index.get(target_table, set()):
                    issues.append(
                        (table, idx, field, f"value {value!r} not found in {target_table}")
                    )
    return issues


def main() -> int:
    base_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else BASE_DIR
    if not base_dir.exists():
        print(f"Base directory does not exist: {base_dir}")
        return 1

    records_by_table: dict[str, list[dict]] = {}
    missing_files: list[str] = []
    for table in TABLE_CONFIG:
        path = base_dir / table
        data = load_json_list(path)
        if data is None:
            missing_files.append(table)
            data = []
        records_by_table[table] = data

    pk_index = build_pk_index(records_by_table)
    issues = find_fk_issues(records_by_table, pk_index)

    if missing_files:
        print("Missing files:", ", ".join(sorted(missing_files)))
    print(f"Checked {len(TABLE_CONFIG)} tables in {base_dir}")
    if not issues:
        print("No FK issues found.")
        return 0

    print(f"Found {len(issues)} FK issues:")
    for table, idx, field, msg in issues:
        print(f"- {table} record #{idx} field {field}: {msg}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
