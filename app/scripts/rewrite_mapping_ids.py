"""
Brief: Rewrite primary keys in mapped JSON and cascade updates to foreign keys.

Inputs:
- --input-dir: directory with mapping step3 outputs (JSON lists)
- --table: table name(s) to rewrite (e.g., Sector or Sector.json, or "all")
- --record-id: specific record UUIDs to rewrite (single table only)
- --all: rewrite all records in the table(s)
- --post-mapping: shorthand for --all + --verify-fks
- --verify-fks: validate FK coverage before rewriting
- --output-dir: optional output directory (default: in-place)
- --dry-run: preview changes without writing files

Outputs:
- Updated JSON files with rewritten IDs and updated references
- Logs to stdout/stderr

Usage (from project root):
- python -m app.scripts.rewrite_mapping_ids --table Sector --record-id <uuid>
- python -m app.scripts.rewrite_mapping_ids --table Sector --all
- python -m app.scripts.rewrite_mapping_ids --table all --post-mapping
"""

from __future__ import annotations

import argparse
import json
import logging
from collections import Counter
from pathlib import Path
from uuid import UUID, uuid5

from app.utils.logging_config import setup_logger
from mapping.utils.llm_utils import load_json_list, write_json
from mapping.utils.validate_foreign_keys import TABLE_CONFIG, build_pk_index, find_fk_issues

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "output" / "mapping" / "step3_llm"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rewrite mapping IDs and cascade updates to FK references."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help=f"Directory containing step3 JSON (default: {DEFAULT_INPUT_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory (default: overwrite input-dir).",
    )
    parser.add_argument(
        "--table",
        action="append",
        required=True,
        help="Table to rewrite (e.g., Sector or Sector.json). Can be repeated.",
    )
    parser.add_argument(
        "--record-id",
        action="append",
        default=None,
        help="Specific record UUIDs to rewrite (single table only).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Rewrite all records for the specified table(s).",
    )
    parser.add_argument(
        "--post-mapping",
        action="store_true",
        help="Shorthand for --all + --verify-fks (use after mapping completes).",
    )
    parser.add_argument(
        "--verify-fks",
        action="store_true",
        help="Verify FK coverage before rewriting (fails on issues).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )
    return parser.parse_args()


def normalize_table_name(value: str) -> str:
    name = value.strip()
    if name.lower().endswith(".json"):
        return name[:-5]
    return name


def resolve_table_config(table_name: str) -> tuple[str, str]:
    target = normalize_table_name(table_name).lower()
    for file_name, cfg in TABLE_CONFIG.items():
        base = (
            file_name[:-5].lower()
            if file_name.lower().endswith(".json")
            else file_name.lower()
        )
        if base == target:
            pk_field = str(cfg["pk"])
            return file_name, pk_field
    available = ", ".join(sorted(name[:-5] for name in TABLE_CONFIG.keys()))
    raise ValueError(f"Unknown table '{table_name}'. Available: {available}")


def build_reference_map() -> dict[str, list[tuple[str, str]]]:
    reference_map: dict[str, list[tuple[str, str]]] = {}
    for source_file, cfg in TABLE_CONFIG.items():
        for field, target_file, _optional in cfg.get("fks", []):
            reference_map.setdefault(target_file, []).append((source_file, field))
    return reference_map


def build_seed(record: dict, pk_field: str) -> str:
    payload = {key: value for key, value in record.items() if key != pk_field}
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def deterministic_uuid(
    *,
    table_label: str,
    record: dict,
    pk_field: str,
    salt: str | None = None,
) -> str:
    seed = build_seed(record, pk_field)
    if salt:
        seed = f"{seed}|{salt}"
    namespace = uuid5(UUID(int=0), f"rewrite:{table_label}")
    return str(uuid5(namespace, seed))


def load_all_json(input_dir: Path) -> dict[str, list[dict]]:
    records_by_file: dict[str, list[dict]] = {}
    for path in sorted(input_dir.glob("*.json")):
        records_by_file[path.name] = load_json_list(path)
    return records_by_file


def verify_fk_mapping(records_by_file: dict[str, list[dict]]) -> int:
    records_by_table = {
        table: records_by_file.get(table, []) for table in TABLE_CONFIG.keys()
    }
    pk_index = build_pk_index(records_by_table)
    issues = find_fk_issues(records_by_table, pk_index)
    if not issues:
        LOGGER.info("FK verification passed.")
        return 0
    LOGGER.error("FK verification failed with %d issue(s).", len(issues))
    for table, idx, field, msg in issues[:20]:
        LOGGER.error("FK issue: %s[%d] %s -> %s", table, idx, field, msg)
    return len(issues)


def rewrite_table_ids(
    *,
    records: list[dict],
    pk_field: str,
    target_ids: set[str] | None,
    table_label: str,
) -> tuple[dict[str, str], int]:
    current_ids = [str(rec.get(pk_field)) for rec in records if rec.get(pk_field)]
    used_ids = set(current_ids)
    duplicates = {rid for rid, count in Counter(current_ids).items() if count > 1}
    kept_duplicates: set[str] = set()
    rotations: dict[str, str] = {}
    touched = 0

    for record in records:
        raw_id = record.get(pk_field)
        if not raw_id:
            continue
        current_id = str(raw_id)
        if target_ids is not None and current_id not in target_ids:
            continue

        force_rotate = False
        if target_ids is not None:
            force_rotate = True
        elif current_id in duplicates:
            if current_id in kept_duplicates:
                force_rotate = True
            else:
                kept_duplicates.add(current_id)

        counter = 0
        while True:
            candidate = deterministic_uuid(
                table_label=table_label,
                record=record,
                pk_field=pk_field,
                salt=str(counter) if counter else None,
            )
            if candidate == current_id and not force_rotate:
                break
            if candidate == current_id and force_rotate:
                counter += 1
                continue
            if candidate in used_ids:
                counter += 1
                continue
            break

        if candidate == current_id and not force_rotate:
            continue

        rotations[current_id] = candidate
        used_ids.add(candidate)
        record[pk_field] = candidate
        touched += 1

    return rotations, touched


def apply_fk_updates(
    *,
    records_by_file: dict[str, list[dict]],
    reference_map: dict[str, list[tuple[str, str]]],
    rotations_by_target: dict[str, dict[str, str]],
) -> dict[str, int]:
    updates: dict[str, int] = {}
    for target_file, id_map in rotations_by_target.items():
        if not id_map:
            continue
        for source_file, field in reference_map.get(target_file, []):
            records = records_by_file.get(source_file)
            if not records:
                continue
            updated = 0
            for record in records:
                value = record.get(field)
                if value in id_map:
                    record[field] = id_map[value]
                    updated += 1
            if updated:
                updates[source_file] = updates.get(source_file, 0) + updated
    return updates


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir

    if args.post_mapping:
        if args.record_id:
            LOGGER.error("--post-mapping cannot be combined with --record-id.")
            return 2
        args.all = True
        args.verify_fks = True

    if args.record_id and args.all:
        LOGGER.error("Choose either --record-id or --all, not both.")
        return 2
    if not args.record_id and not args.all:
        LOGGER.error("You must provide --record-id or --all.")
        return 2

    table_names: list[str] = []
    for raw in args.table:
        table_names.extend(part.strip() for part in raw.split(",") if part.strip())

    expanded_all = any(name.lower() == "all" for name in table_names)
    if expanded_all:
        table_names = sorted(name[:-5] for name in TABLE_CONFIG.keys())

    if args.record_id and len(table_names) != 1:
        LOGGER.error("--record-id can only be used with a single --table.")
        return 2

    if not input_dir.exists():
        LOGGER.error("Input directory does not exist: %s", input_dir)
        return 1

    records_by_file = load_all_json(input_dir)
    if not records_by_file:
        LOGGER.error("No JSON files found in %s.", input_dir)
        return 1

    if args.verify_fks:
        issue_count = verify_fk_mapping(records_by_file)
        if issue_count:
            return 2

    reference_map = build_reference_map()
    rotations_by_target: dict[str, dict[str, str]] = {}
    changed_files: set[str] = set()

    for table_name in table_names:
        target_file, pk_field = resolve_table_config(table_name)
        records = records_by_file.get(target_file)
        if records is None:
            if expanded_all:
                LOGGER.warning("Missing file for table %s: %s", table_name, target_file)
                continue
            LOGGER.error("Missing file for table %s: %s", table_name, target_file)
            return 1

        existing_ids = {str(rec.get(pk_field)) for rec in records if rec.get(pk_field)}
        target_ids = set(args.record_id or []) if args.record_id else None
        if target_ids:
            missing = sorted(target_ids - existing_ids)
            if missing:
                LOGGER.warning(
                    "Requested IDs not found in %s: %s", target_file, ", ".join(missing)
                )

        rotations, touched = rewrite_table_ids(
            records=records,
            pk_field=pk_field,
            target_ids=target_ids,
            table_label=normalize_table_name(target_file),
        )
        rotations_by_target[target_file] = rotations

        if touched:
            changed_files.add(target_file)
        LOGGER.info(
            "Table %s: rewrote %d record(s).", normalize_table_name(target_file), touched
        )
        if rotations:
            LOGGER.debug("Rewrites for %s: %s", target_file, rotations)

    fk_updates = apply_fk_updates(
        records_by_file=records_by_file,
        reference_map=reference_map,
        rotations_by_target=rotations_by_target,
    )
    for file_name, count in fk_updates.items():
        if count:
            changed_files.add(file_name)
            LOGGER.info("Updated %d FK reference(s) in %s.", count, file_name)

    if args.dry_run:
        LOGGER.info("Dry run complete. No files written.")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    if output_dir.resolve() == input_dir.resolve():
        files_to_write = sorted(changed_files)
    else:
        files_to_write = sorted(records_by_file.keys())

    if not files_to_write:
        LOGGER.info("No changes to write.")
        return 0

    for file_name in files_to_write:
        payload = records_by_file.get(file_name)
        if payload is None:
            continue
        write_json(output_dir / file_name, payload)
        LOGGER.info("Wrote %s", output_dir / file_name)

    return 0


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
