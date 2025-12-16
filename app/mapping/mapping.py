"""
End-to-end mapping runner.

Steps:
1) Clear hallucinated foreign keys from extraction outputs.
2) Apply canonical city mapping (fixed Leipzig cityId).
3) Run LLM-based FK mapping (modular mappers with structured outputs).
4) Verify FK coverage after each step.

Run from repo root:
  python app/mapping/mapping.py --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.mapping import apply_city_mapping
from app.mapping.apply_llm_mapping import run_llm_mapping
from app.mapping.clear_foreign_keys import FK_FIELDS, clear_fields
from app.mapping.llm_utils import CANONICAL_CITY_ID, write_json

# Paths relative to mapping.py location
MAPPING_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_DIR = MAPPING_DIR.parent / "extraction" / "output"
DEFAULT_WORK_DIR = MAPPING_DIR / "workflow_output"

# Fields that must be present after LLM mapping.
FK_VERIFY_FIELDS: dict[str, list[str]] = {
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


def read_any_json(path: Path) -> list[dict]:
    """
    Load JSON list from disk.
    
    Missing files return [] (OK - not all files are always present).
    Corrupted/invalid files raise ValueError (critical error - prevents silent data loss).
    """
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid or malformed JSON in {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError(f"Expected top-level JSON list in {path}, got {type(payload).__name__}")
    return payload


def ensure_dir(path: Path) -> None:
    """Create directory if missing (no clearing)."""
    path.mkdir(parents=True, exist_ok=True)


def reset_dir(path: Path) -> None:
    """Ensure the directory exists and is empty (prevents stale outputs across runs)."""
    if path.exists():
        for entry in path.iterdir():
            if entry.is_file():
                entry.unlink()
            elif entry.is_dir():
                shutil.rmtree(entry)
    path.mkdir(parents=True, exist_ok=True)


def clear_fk_step(input_dir: Path, output_dir: Path) -> dict:
    """Clear FK fields (per FK_FIELDS) from input_dir into output_dir."""
    summary: dict[str, dict] = {}
    # Process listed FK files
    for fname, fields in FK_FIELDS.items():
        src = input_dir / fname
        records = read_any_json(src)
        cleared = clear_fields(records, fields) if records else 0
        if records:
            write_json(output_dir / fname, records)
        summary[fname] = {"records": len(records), "cleared": cleared}

    # Copy any other json files untouched
    for src in input_dir.glob("*.json"):
        if src.name in FK_FIELDS:
            continue
        records = read_any_json(src)
        if records:
            write_json(output_dir / src.name, records)
            summary[src.name] = {"records": len(records), "cleared": 0}
    return summary


def city_step(input_dir: Path, output_dir: Path) -> dict:
    """Apply canonical city mapping on cleared data."""
    summary: dict[str, dict] = {}

    city_records, city_status = apply_city_mapping.load_json_list(input_dir / "City.json")
    if city_status not in ("ok", "missing"):
        raise ValueError(f"Invalid City.json: {city_status}")
    city_record = apply_city_mapping.build_city_record(city_records[0] if city_records else None)
    apply_city_mapping.write_json(output_dir / "City.json", [city_record])
    summary["City.json"] = {"records": len(city_records or []), "updated": 1, "status": city_status}

    for src in input_dir.glob("*.json"):
        if src.name == "City.json":
            continue
        records, status = apply_city_mapping.load_json_list(src)
        if status not in ("ok", "missing"):
            raise ValueError(f"Invalid {src.name}: {status}")
        if status != "ok" or not records:
            summary[src.name] = {"records": len(records or []), "updated": 0, "status": status}
            continue

        updated = 0
        if src.name in apply_city_mapping.CITY_ID_FIELDS:
            updated = apply_city_mapping.apply_city_fk(records, apply_city_mapping.CITY_ID_FIELDS[src.name])
        apply_city_mapping.write_json(output_dir / src.name, records)
        summary[src.name] = {"records": len(records), "updated": updated, "status": status}
    return summary


def verify_city_ids(path: Path) -> dict[str, dict]:
    """Check that cityId equals canonical across city-linked files."""
    report: dict[str, dict] = {}
    for fname, fields in apply_city_mapping.CITY_ID_FIELDS.items():
        try:
            records = read_any_json(path / fname)
        except ValueError as exc:
            raise ValueError(f"Cannot verify cityId in {fname}: {exc}") from exc
        missing = 0
        for rec in records:
            for field in fields:
                if rec.get(field) != CANONICAL_CITY_ID:
                    missing += 1
        report[fname] = {"records": len(records), "cityId_mismatch": missing}
    return report


def verify_fk_presence(path: Path) -> dict[str, dict]:
    """Check for null/missing foreign keys in final mapped data."""
    report: dict[str, dict] = {}
    for fname, fields in FK_VERIFY_FIELDS.items():
        src = path / fname
        if not src.exists():
            report[fname] = {"records": 0, "missing_fk_fields": "missing file"}
            continue
        try:
            records = read_any_json(src)
        except ValueError as exc:
            raise ValueError(f"Cannot verify FK in {fname}: {exc}") from exc
        missing = 0
        for rec in records:
            for field in fields:
                if rec.get(field) in (None, ""):
                    missing += 1
        report[fname] = {"records": len(records), "missing_fk_fields": missing}
    return report


def verify_fk_presence_in_memory(outputs: dict[str, list[dict]]) -> dict[str, dict]:
    """Check FK presence using in-memory payloads (when not written)."""
    report: dict[str, dict] = {}
    for fname, fields in FK_VERIFY_FIELDS.items():
        if fname not in outputs:
            report[fname] = {"records": 0, "missing_fk_fields": "missing payload"}
            continue
        records = outputs.get(fname, [])
        missing = 0
        for rec in records:
            for field in fields:
                if rec.get(field) in (None, ""):
                    missing += 1
        report[fname] = {"records": len(records), "missing_fk_fields": missing}
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="End-to-end mapping runner.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Source extraction/output directory.")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=DEFAULT_WORK_DIR,
        help="Working directory for staged outputs (cleared/city/llm).",
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model for FK mapping.")
    parser.add_argument("--apply", action="store_true", help="Persist outputs to work-dir stages.")
    parser.add_argument(
        "--delete-old",
        action="store_true",
        help="When writing outputs, clear existing stage directories first (replaces previous runs).",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    staging_root: Path = args.work_dir if args.apply else args.work_dir / "dry_run"
    clear_dir = staging_root / "step1_cleared"
    city_dir = staging_root / "step2_city"
    llm_dir = staging_root / "step3_llm"

    print(f"Input dir: {args.input_dir}")
    print(f"Work dir: {staging_root}")

    try:
        # Prepare stage directories
        if args.delete_old:
            reset_dir(clear_dir)
            reset_dir(city_dir)
            if args.apply:
                reset_dir(llm_dir)
            else:
                reset_dir(llm_dir)
        else:
            ensure_dir(clear_dir)
            ensure_dir(city_dir)
            ensure_dir(llm_dir)

        # Step 1: clear FK hallucinations
        clear_summary = clear_fk_step(args.input_dir, clear_dir)
        print("\nStep 1 - cleared foreign keys:")
        for fname, stats in clear_summary.items():
            print(f"  {fname}: records={stats['records']}, fields_cleared={stats.get('cleared', 0)}")

        # Step 2: apply city mapping
        city_summary = city_step(clear_dir, city_dir)
        city_verification = verify_city_ids(city_dir)
        print("\nStep 2 - city mapping applied:")
        for fname, stats in city_summary.items():
            extra = city_verification.get(fname, {})
            print(
                f"  {fname}: records={stats['records']}, updated={stats['updated']}, "
                f"cityId_mismatch={extra.get('cityId_mismatch', 'n/a')}"
            )

        # Step 3: LLM FK mapping
        print("\nStep 3 - LLM mapping (this calls the LLM for FK choices)...")
        outputs = run_llm_mapping(
            input_dir=city_dir, output_dir=llm_dir, model_name=args.model, apply=args.apply
        )

        for fname, payload in outputs.items():
            print(f"  {fname}: records={len(payload)} {'(written)' if args.apply else '(dry-run)'}")

        if args.apply:
            fk_report = verify_fk_presence(llm_dir)
        else:
            fk_report = verify_fk_presence_in_memory(outputs)
        print("\nFK verification after LLM step:")
        for fname, stats in fk_report.items():
            print(f"  {fname}: records={stats['records']}, missing_fk_fields={stats['missing_fk_fields']}")

        if args.apply:
            print(f"\nOutputs staged under: {staging_root}")
            print(f"  Cleared: {clear_dir}")
            print(f"  City-mapped: {city_dir}")
            print(f"  LLM-mapped: {llm_dir}")
        else:
            print("\nDry run (no files written). Use --apply to persist staged outputs.")

    except ValueError as exc:
        print(f"\nERROR: Data validation failed: {exc}", file=sys.stderr)
        print("This usually indicates corrupted or truncated JSON files.", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        if "API_KEY" in str(exc):
            print("Ensure OPENAI_API_KEY or OPENROUTER_API_KEY is set.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"\nERROR: Unexpected failure: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

