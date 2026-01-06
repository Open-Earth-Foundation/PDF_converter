"""
Derive a canonical cityId from extracted data and propagate it across JSON outputs.

- Reads extraction outputs (expected to be cleaned with clear_foreign_keys.py).
- Writes mapped copies to mapping/output by default.
- Uses the first extracted City record as the canonical city (fallback: generated UUID if none found).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterable
import uuid

from mapping.utils.llm_utils import load_json_list as load_json_list_base

LOGGER = logging.getLogger(__name__)

DEFAULT_INPUT_DIR = Path(__file__).resolve().parents[2] / "extraction" / "output"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"

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


def build_city_record(source: dict | None) -> tuple[dict, str]:
    """
    Derive the canonical city record from the first extracted City entry.

    If no City is present, generate a placeholder with a new UUID so downstream mapping can proceed.
    """
    if source and source.get("cityId"):
        canonical_id = source["cityId"]
        record = dict(source)
    elif source:
        canonical_id = str(uuid.uuid4())
        record = dict(source, cityId=canonical_id)
    else:
        canonical_id = str(uuid.uuid4())
        record = {
            "cityId": canonical_id,
            "cityName": "Unknown City",
            "country": None,
            "locode": None,
            "areaKm2": None,
            "notes": "Placeholder city generated because no City record was extracted.",
            "misc": None,
        }
    return record, canonical_id


def apply_city_fk(records: list[dict], fields: Iterable[str], city_id: str) -> int:
    """Set cityId on provided fields; return how many fields were updated."""
    updated = 0
    for record in records:
        for field in fields:
            if record.get(field) != city_id:
                record[field] = city_id
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
    city_record, canonical_city_id = build_city_record(city_payload[0] if city_payload else None)
    if args.apply:
        write_json(output_dir / "City.json", [city_record])
    results.append(
        {
            "file": "City.json",
            "status": city_status,
            "source_records": len(city_payload or []),
            "cityId": canonical_city_id,
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

        updated = apply_city_fk(records, fields, canonical_city_id)
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

    print(f"Canonical cityId: {canonical_city_id}")
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
