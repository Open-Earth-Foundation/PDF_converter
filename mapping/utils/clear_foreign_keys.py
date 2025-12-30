"""
Utility to clear hallucinated foreign keys in saved extraction output.

Defaults to dry-run. Pass --apply to overwrite the JSON files in-place.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "extraction" / "output"

# JSON filename -> fields to null out
FK_FIELDS: dict[str, list[str]] = {
    "ClimateCityContract.json": ["cityId"],
    "CityAnnualStats.json": ["cityId"],
    "EmissionRecord.json": ["cityId", "sectorId"],
    "CityBudget.json": ["cityId"],
    "BudgetFunding.json": ["budgetId", "fundingSourceId"],
    "Initiative.json": ["cityId"],
    "InitiativeStakeholder.json": ["initiativeId", "stakeholderId"],
    "Indicator.json": ["cityId", "sectorId"],
    "IndicatorValue.json": ["indicatorId"],
    "CityTarget.json": ["cityId", "indicatorId"],
    "InitiativeIndicator.json": ["initiativeId", "indicatorId"],
    "InitiativeTef.json": ["initiativeId", "tefId"],
    "TefCategory.json": ["parentId"],
}


def clear_fields(records: list[dict], fields: Iterable[str]) -> int:
    """Set given fields to None across records; return count of fields cleared."""
    cleared = 0
    for record in records:
        for field in fields:
            if field in record and record[field] is not None:
                record[field] = None
                cleared += 1
    return cleared


def process_file(path: Path, fields: Iterable[str], apply: bool) -> dict:
    """Load, clear fields, and optionally persist the changes."""
    if not path.exists():
        return {"file": path.name, "status": "missing", "records": 0, "cleared": 0}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"file": path.name, "status": f"invalid json ({exc})", "records": 0, "cleared": 0}

    if not isinstance(payload, list):
        return {"file": path.name, "status": "expected list at top-level", "records": 0, "cleared": 0}

    cleared = clear_fields(payload, fields)
    if apply and cleared:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"file": path.name, "status": "ok", "records": len(payload), "cleared": cleared}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clear foreign keys in extracted JSON files.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory containing extraction JSON outputs (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Overwrite files in-place. Without this flag, only a dry-run summary is shown.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir: Path = args.output_dir

    results = [process_file(output_dir / fname, fields, args.apply) for fname, fields in FK_FIELDS.items()]

    for result in results:
        print(
            f"{result['file']}: {result['status']} "
            f"(records={result['records']}, cleared={result['cleared']})"
        )

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write changes.")


if __name__ == "__main__":
    main()
