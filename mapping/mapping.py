"""
Brief: End-to-end mapping runner for linking foreign keys.

Inputs:
- --input-dir: directory with extraction outputs
- --work-dir: staging directory for mapping steps
- --model: override mapping model (defaults to llm_config.yml mapping.model)
- --apply/--delete-old
- --only-table: re-map a single table (e.g. EmissionRecord)
- --emission-guidance: extra prompt guidance for EmissionRecord mapping
- --retry-on-issues: re-run LLM mapping for FK/duplicate issues with feedback
- --retry-rounds: max retry rounds (default: 1)
- --retry-max-duplicates: max duplicate groups to include in retry planning
- --use-option-indexes: use numeric option indexes for LLM selection
- Env: OPENROUTER_API_KEY (for LLM mapping)

Outputs:
- Staged JSON outputs under mapping/workflow_output (or custom work-dir)
- Logs to stdout/stderr

Usage (from project root):
- python -m mapping.scripts.mapping --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv

from utils import load_llm_config, setup_logger
from mapping.utils import FK_FIELDS, clear_fields, write_json
from mapping.utils.apply_llm_mapping import run_llm_mapping
from mapping.utils.apply_city_mapping import (
    apply_city_fk,
    build_city_record,
    CITY_ID_FIELDS,
    load_json_list,
    write_json as write_city_json,
)

LOGGER = logging.getLogger(__name__)

# Paths relative to mapping.py location
MAPPING_DIR = Path(__file__).resolve().parent
REPO_ROOT = MAPPING_DIR.parent
DEFAULT_INPUT_DIR = REPO_ROOT / "output" / "extraction"
DEFAULT_WORK_DIR = REPO_ROOT / "output" / "mapping"

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

TABLE_RERUN_CONFIG: dict[str, dict[str, object]] = {
    "EmissionRecord": {
        "file": "EmissionRecord.json",
        "mapper": "emission_sector",
        "dependencies": ["Sector.json"],
    },
    "Indicator": {
        "file": "Indicator.json",
        "mapper": "indicator_sector",
        "dependencies": ["Sector.json"],
    },
    "BudgetFunding": {
        "file": "BudgetFunding.json",
        "mapper": "budget_funding",
        "dependencies": ["CityBudget.json", "FundingSource.json"],
    },
    "InitiativeStakeholder": {
        "file": "InitiativeStakeholder.json",
        "mapper": "initiative_stakeholder",
        "dependencies": ["Initiative.json", "Stakeholder.json"],
    },
    "InitiativeIndicator": {
        "file": "InitiativeIndicator.json",
        "mapper": "initiative_indicator",
        "dependencies": ["Initiative.json", "Indicator.json"],
    },
    "InitiativeTef": {
        "file": "InitiativeTef.json",
        "mapper": "initiative_tef",
        "dependencies": ["Initiative.json", "TefCategory.json"],
    },
    "IndicatorValue": {
        "file": "IndicatorValue.json",
        "mapper": "indicator_value",
        "dependencies": ["Indicator.json"],
    },
    "CityTarget": {
        "file": "CityTarget.json",
        "mapper": "city_target",
        "dependencies": ["Indicator.json"],
    },
    "TefCategory": {
        "file": "TefCategory.json",
        "mapper": "tef_parent",
        "dependencies": ["TefCategory.json"],
    },
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
        raise ValueError(
            f"Expected top-level JSON list in {path}, got {type(payload).__name__}"
        )
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


def normalize_table_name(value: str) -> str:
    name = value.strip()
    if name.lower().endswith(".json"):
        name = name[:-5]
    return name


def resolve_table_config(name: str) -> tuple[str, dict[str, object]]:
    for key, config in TABLE_RERUN_CONFIG.items():
        if key.lower() == name.lower():
            return key, config
    available = ", ".join(sorted(TABLE_RERUN_CONFIG.keys()))
    raise ValueError(f"Unknown table '{name}'. Available: {available}")


def ensure_dependency_files(
    *,
    input_dir: Path,
    city_dir: Path,
    dependencies: Iterable[str],
) -> None:
    for fname in dependencies:
        dest = city_dir / fname
        if dest.exists():
            continue
        src = input_dir / fname
        records = read_any_json(src)
        if records:
            write_json(dest, records)


def prepare_single_table(
    *,
    input_dir: Path,
    clear_dir: Path,
    city_dir: Path,
    target_file: str,
) -> tuple[str, int, int]:
    city_records, city_status = load_json_list(input_dir / "City.json")
    if city_status not in ("ok", "missing"):
        raise ValueError(f"Invalid City.json: {city_status}")
    city_record, canonical_city_id = build_city_record(
        city_records[0] if city_records else None
    )
    write_city_json(city_dir / "City.json", [city_record])

    records = read_any_json(input_dir / target_file)
    cleared = 0
    if target_file in FK_FIELDS:
        cleared = clear_fields(records, FK_FIELDS[target_file])
    updated = 0
    if target_file in CITY_ID_FIELDS:
        updated = apply_city_fk(records, CITY_ID_FIELDS[target_file], canonical_city_id)

    if records:
        write_json(clear_dir / target_file, records)
        write_city_json(city_dir / target_file, records)

    LOGGER.info(
        "Prepared %s: records=%d cleared=%d city_updated=%d",
        target_file,
        len(records),
        cleared,
        updated,
    )
    return canonical_city_id, len(records), cleared


def verify_fk_for_file(
    records: list[dict],
    fields: Iterable[str],
) -> int:
    missing = 0
    for rec in records:
        for field in fields:
            if rec.get(field) in (None, ""):
                missing += 1
    return missing


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


def city_step(input_dir: Path, output_dir: Path) -> tuple[dict, str]:
    """Apply canonical city mapping on cleared data."""
    summary: dict[str, dict] = {}

    city_records, city_status = load_json_list(input_dir / "City.json")
    if city_status not in ("ok", "missing"):
        raise ValueError(f"Invalid City.json: {city_status}")
    city_record, canonical_city_id = build_city_record(
        city_records[0] if city_records else None
    )
    write_city_json(output_dir / "City.json", [city_record])
    summary["City.json"] = {
        "records": len(city_records or []),
        "updated": 1,
        "status": city_status,
        "canonical_city_id": canonical_city_id,
    }

    for src in input_dir.glob("*.json"):
        if src.name == "City.json":
            continue
        records, status = load_json_list(src)
        if status not in ("ok", "missing"):
            raise ValueError(f"Invalid {src.name}: {status}")
        if status != "ok" or not records:
            summary[src.name] = {
                "records": len(records or []),
                "updated": 0,
                "status": status,
            }
            continue

        updated = 0
        if src.name in CITY_ID_FIELDS:
            updated = apply_city_fk(
                records, CITY_ID_FIELDS[src.name], canonical_city_id
            )
        write_city_json(output_dir / src.name, records)
        summary[src.name] = {
            "records": len(records),
            "updated": updated,
            "status": status,
        }
    return summary, canonical_city_id


def verify_city_ids(path: Path, canonical_city_id: str) -> dict[str, dict]:
    """Check that cityId equals canonical across city-linked files."""
    report: dict[str, dict] = {}
    for fname, fields in CITY_ID_FIELDS.items():
        try:
            records = read_any_json(path / fname)
        except ValueError as exc:
            raise ValueError(f"Cannot verify cityId in {fname}: {exc}") from exc
        missing = 0
        for rec in records:
            for field in fields:
                if rec.get(field) != canonical_city_id:
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
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Source extraction/output directory.",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=DEFAULT_WORK_DIR,
        help="Working directory for staged outputs (cleared/city/llm).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override mapping model (defaults to llm_config.yml mapping.model).",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Persist outputs to work-dir stages."
    )
    parser.add_argument(
        "--delete-old",
        action="store_true",
        help="When writing outputs, clear existing stage directories first (replaces previous runs).",
    )
    parser.add_argument(
        "--only-table",
        default=None,
        help="Re-map a single table (e.g. EmissionRecord).",
    )
    parser.add_argument(
        "--emission-guidance",
        default=None,
        help="Extra prompt guidance appended to EmissionRecord mapping.",
    )
    parser.add_argument(
        "--retry-on-issues",
        action="store_true",
        help="Re-run LLM mapping for records with FK/duplicate issues using feedback.",
    )
    parser.add_argument(
        "--retry-rounds",
        type=int,
        default=1,
        help="Max retry rounds for re-mapping problematic records (default: 1).",
    )
    parser.add_argument(
        "--retry-max-duplicates",
        type=int,
        default=50,
        help="Max duplicate groups to include when planning retries (default: 50).",
    )
    parser.add_argument(
        "--use-option-indexes",
        action="store_true",
        help="Use numeric option indexes for LLM selection and map them back to IDs.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    if args.only_table and args.delete_old:
        LOGGER.warning("--delete-old ignored for --only-table runs.")
    staging_root: Path = args.work_dir if args.apply else args.work_dir / "dry_run"
    clear_dir = staging_root / "step1_cleared"
    city_dir = staging_root / "step2_city"
    llm_dir = staging_root / "step3_llm"

    LOGGER.info("Input dir: %s", args.input_dir)
    LOGGER.info("Work dir: %s", staging_root)

    try:
        # Prepare stage directories
        if args.delete_old and not args.only_table:
            reset_dir(clear_dir)
            reset_dir(city_dir)
            reset_dir(llm_dir)
        else:
            ensure_dir(clear_dir)
            ensure_dir(city_dir)
            ensure_dir(llm_dir)

        if args.only_table:
            table_name = normalize_table_name(args.only_table)
            _, config = resolve_table_config(table_name)
            target_file = str(config["file"])
            mapper_name = str(config["mapper"])
            dependencies = [str(item) for item in config["dependencies"]]

            prepare_single_table(
                input_dir=args.input_dir,
                clear_dir=clear_dir,
                city_dir=city_dir,
                target_file=target_file,
            )
            ensure_dependency_files(
                input_dir=args.input_dir,
                city_dir=city_dir,
                dependencies=dependencies,
            )

            llm_cfg = load_llm_config().get("mapping", {})
            model_name = args.model or llm_cfg.get("model")
            if not model_name:
                raise RuntimeError(
                    "Mapping model not configured. Set mapping.model in llm_config.yml."
                )

            outputs = run_llm_mapping(
                input_dir=city_dir,
                output_dir=llm_dir,
                model_name=model_name,
                apply=False,
                targets={mapper_name},
                emission_guidance=args.emission_guidance,
                retry_on_issues=args.retry_on_issues,
                retry_max_rounds=args.retry_rounds,
                retry_max_duplicate_groups=args.retry_max_duplicates,
                use_option_indexes=args.use_option_indexes,
            )

            payload = outputs.get(target_file, [])
            if args.apply:
                write_json(llm_dir / target_file, payload)
                LOGGER.info(
                    "Wrote %s (%d records) to %s",
                    target_file,
                    len(payload),
                    llm_dir,
                )
            else:
                LOGGER.info("Dry run only. %s not written.", target_file)

            fk_fields = FK_VERIFY_FIELDS.get(target_file, [])
            if fk_fields:
                missing = verify_fk_for_file(payload, fk_fields)
                LOGGER.info(
                    "FK verification for %s: records=%d missing_fk_fields=%d",
                    target_file,
                    len(payload),
                    missing,
                )
            return 0

        # Step 1: clear FK hallucinations
        clear_summary = clear_fk_step(args.input_dir, clear_dir)
        LOGGER.info("Step 1 - cleared foreign keys:")
        for fname, stats in clear_summary.items():
            LOGGER.info(
                "  %s: records=%s, fields_cleared=%s",
                fname,
                stats["records"],
                stats.get("cleared", 0),
            )

        # Step 2: apply city mapping
        city_summary, canonical_city_id = city_step(clear_dir, city_dir)
        city_verification = verify_city_ids(city_dir, canonical_city_id)
        LOGGER.info("Step 2 - city mapping applied:")
        for fname, stats in city_summary.items():
            extra = city_verification.get(fname, {})
            LOGGER.info(
                "  %s: records=%s, updated=%s, cityId_mismatch=%s",
                fname,
                stats["records"],
                stats["updated"],
                extra.get("cityId_mismatch", "n/a"),
            )

        # Step 3: LLM FK mapping
        LOGGER.info("Step 3 - LLM mapping (this calls the LLM for FK choices)...")
        llm_cfg = load_llm_config().get("mapping", {})
        model_name = args.model or llm_cfg.get("model")
        if not model_name:
            raise RuntimeError(
                "Mapping model not configured. Set mapping.model in llm_config.yml."
            )
        outputs = run_llm_mapping(
            input_dir=city_dir,
            output_dir=llm_dir,
            model_name=model_name,
            apply=args.apply,
            emission_guidance=args.emission_guidance,
            retry_on_issues=args.retry_on_issues,
            retry_max_rounds=args.retry_rounds,
            retry_max_duplicate_groups=args.retry_max_duplicates,
            use_option_indexes=args.use_option_indexes,
        )

        for fname, payload in outputs.items():
            LOGGER.info(
                "  %s: records=%s %s",
                fname,
                len(payload),
                "(written)" if args.apply else "(dry-run)",
            )

        if args.apply:
            fk_report = verify_fk_presence(llm_dir)
        else:
            fk_report = verify_fk_presence_in_memory(outputs)
        LOGGER.info("FK verification after LLM step:")
        for fname, stats in fk_report.items():
            LOGGER.info(
                "  %s: records=%s, missing_fk_fields=%s",
                fname,
                stats["records"],
                stats["missing_fk_fields"],
            )

        if args.apply:
            LOGGER.info("Outputs staged under: %s", staging_root)
            LOGGER.info("  Cleared: %s", clear_dir)
            LOGGER.info("  City-mapped: %s", city_dir)
            LOGGER.info("  LLM-mapped: %s", llm_dir)
        else:
            LOGGER.info(
                "Dry run (no files written). Use --apply to persist staged outputs."
            )

    except ValueError as exc:
        LOGGER.error("Data validation failed: %s", exc)
        LOGGER.error("This usually indicates corrupted or truncated JSON files.")
        return 1
    except RuntimeError as exc:
        LOGGER.error("Error: %s", exc)
        if "API_KEY" in str(exc):
            LOGGER.error("Ensure OPENAI_API_KEY or OPENROUTER_API_KEY is set.")
        return 1
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Unexpected failure: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
