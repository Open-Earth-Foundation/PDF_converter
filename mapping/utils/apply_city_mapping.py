"""
Apply canonical city mapping and propagate the cityId across extracted JSON outputs.

- Reads extraction outputs (expected to be cleaned with clear_foreign_keys.py).
- Writes mapped copies to mapping/output by default.
- Sets a single canonical cityId for all city-linked records.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterable

from mapping.utils.llm_utils import load_json_list as load_json_list_base

LOGGER = logging.getLogger(__name__)

DEFAULT_INPUT_DIR = Path(__file__).resolve().parents[2] / "extraction" / "output"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"

# Canonical city for this run (Leipzig); reuse this cityId everywhere.
CANONICAL_CITY_ID = "b1f03c92-6f8a-4f27-bf5a-c1d58ddc3e17"
CANONICAL_CITY_TEMPLATE = {
    "cityId": CANONICAL_CITY_ID,
    "cityName": "Leipzig",
    "country": "Germany",
    "locode": None,
    "areaKm2": "300",
    "notes": "City area described as 'almost 300 km2' in source document. Context: Climate City Contract for EU Mission participation.",
    "misc": {
        "population_2023": "628718 main residents",
        "population_density": "2129 people per square kilometre",
        "foreign_population_percent": "14",
        "state": "Free State of Saxony",
        "national_rank": "seventh largest city in Germany",
        "area_qualifier": "almost 300 km2",
        "eu_mission": "Participant in EU Mission '100 climate-neutral and smart cities by 2030'",
    },
}

# Files that should carry cityId once the canonical city is set.
CITY_ID_FIELDS: dict[str, list[str]] = {
    "ClimateCityContract.json": ["cityId"],
    "CityAnnualStats.json": ["cityId"],
    "EmissionRecord.json": ["cityId"],
    "CityBudget.json": ["cityId"],
    "Initiative.json": ["cityId"],
    "Indicator.json": ["cityId"],
    "CityTarget.json": ["cityId"],
}


def load_json_list(path: Path) -> tuple[list[dict] | None, str]:
    """
    Load a JSON list from disk and return (payload, status).
    """
    try:
        payload = load_json_list_base(path)
        return payload, "ok"
    except ValueError as exc:
        error_msg = str(exc)
        if "Invalid JSON" in error_msg:
            LOGGER.warning(f"Skipping {path.name}: corrupted JSON")
            return None, f"invalid json ({error_msg})"
        elif "Expected top-level JSON list" in error_msg:
            LOGGER.warning(f"Skipping {path.name}: not a JSON list")
            return None, "expected list at top-level"
        else:
            LOGGER.warning(f"Skipping {path.name}: {error_msg}")
            return None, str(error_msg)


def write_json(path: Path, payload: list[dict]) -> None:
    """Persist payload to disk with pretty-printing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_city_record(source: dict | None) -> dict:
    """Merge canonical city values with the first extracted City record."""
    misc = {**(source.get("misc") or {})} if source else {}
    misc.update(CANONICAL_CITY_TEMPLATE["misc"])

    record = {**(source or {}), **CANONICAL_CITY_TEMPLATE}
    record["cityId"] = CANONICAL_CITY_ID
    record["misc"] = misc
    return record


def apply_city_fk(records: list[dict], fields: Iterable[str]) -> int:
    """Set cityId on provided fields; return how many fields were updated."""
    updated = 0
    for record in records:
        for field in fields:
            if record.get(field) != CANONICAL_CITY_ID:
                record[field] = CANONICAL_CITY_ID
                updated += 1
    return updated


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate canonical cityId across extraction outputs.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing cleaned extraction JSON (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory to write mapped JSON (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write mapped files. Without this flag, only a summary is shown.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir

    results: list[dict] = []
    processed: set[str] = set()

    # City record
    city_payload, city_status = load_json_list(input_dir / "City.json")
    city_record = build_city_record(city_payload[0] if city_payload else None)
    if args.apply:
        write_json(output_dir / "City.json", [city_record])
    results.append(
        {
            "file": "City.json",
            "status": city_status,
            "source_records": len(city_payload or []),
            "cityId": CANONICAL_CITY_ID,
            "written": args.apply,
        }
    )
    processed.add("City.json")

    # Files that need cityId populated.
    for fname, fields in CITY_ID_FIELDS.items():
        processed.add(fname)
        records, status = load_json_list(input_dir / fname)
        if status != "ok" or records is None:
            results.append(
                {"file": fname, "status": status, "records": 0, "city_fields_set": 0, "written": False}
            )
            continue

        updated = apply_city_fk(records, fields)
        if args.apply:
            write_json(output_dir / fname, records)
        results.append(
            {"file": fname, "status": status, "records": len(records), "city_fields_set": updated, "written": args.apply}
        )

    # Pass-through copies for other JSON files.
    for path in sorted(input_dir.glob("*.json")):
        fname = path.name
        if fname in processed:
            continue

        records, status = load_json_list(path)
        if status != "ok" or records is None:
            results.append({"file": fname, "status": status, "records": 0, "city_fields_set": 0, "written": False})
            continue

        if args.apply:
            write_json(output_dir / fname, records)
        results.append(
            {"file": fname, "status": "copied", "records": len(records), "city_fields_set": 0, "written": args.apply}
        )

    print(f"Canonical cityId: {CANONICAL_CITY_ID}")
    for result in results:
        print(
            f"{result['file']}: {result['status']} "
            f"(records={result.get('records', result.get('source_records', 0))}, "
            f"city_fields_set={result.get('city_fields_set', 0)}, "
            f"written={'yes' if result.get('written') else 'no'})"
        )

    if not args.apply:
        print("\nDry run only. Re-run with --apply to write mapped files.")
    else:
        print(f"\nMapped files written to: {output_dir}")


if __name__ == "__main__":
    main()
