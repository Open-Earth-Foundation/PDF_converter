"""
Brief: Sort TefCategory records so parents come before children.

Inputs:
- --input-dir: directory with mapping step3 outputs (JSON lists)
- --output-dir: optional output directory (default: in-place)
- --file: JSON filename to sort (default: TefCategory.json)
- --dry-run: preview changes without writing files

Outputs:
- Sorted JSON file with parents ahead of children
- Logs to stdout/stderr

Usage (from project root):
- python -m app.scripts.sort_tef_categories
- python -m app.scripts.sort_tef_categories --input-dir output/mapping/step3_llm
"""

from __future__ import annotations

import argparse
import logging
from collections import deque
from pathlib import Path

from app.utils.logging_config import setup_logger
from mapping.utils.llm_utils import load_json_list, write_json

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT_DIR = REPO_ROOT / "output" / "mapping" / "step3_llm"
DEFAULT_FILE = "TefCategory.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sort TefCategory JSON so parents precede children."
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
        "--file",
        default=DEFAULT_FILE,
        help=f"Filename to sort (default: {DEFAULT_FILE}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing files.",
    )
    return parser.parse_args()


def topological_sort(records: list[dict]) -> tuple[list[dict], list[str], int]:
    by_id: dict[str, dict] = {}
    duplicates: list[dict] = []
    missing_parent_ids: set[str] = set()

    for record in records:
        tef_id = record.get("tefId")
        if not tef_id:
            duplicates.append(record)
            continue
        if tef_id in by_id:
            duplicates.append(record)
            continue
        by_id[tef_id] = record

    children: dict[str, list[str]] = {tef_id: [] for tef_id in by_id}
    in_degree: dict[str, int] = {tef_id: 0 for tef_id in by_id}

    for tef_id, record in by_id.items():
        parent_id = record.get("parentId")
        if not parent_id:
            continue
        if parent_id in by_id:
            children[parent_id].append(tef_id)
            in_degree[tef_id] += 1
        else:
            missing_parent_ids.add(str(parent_id))

    queue = deque([tef_id for tef_id, deg in in_degree.items() if deg == 0])
    ordered_ids: list[str] = []
    while queue:
        current = queue.popleft()
        ordered_ids.append(current)
        for child in children.get(current, []):
            in_degree[child] -= 1
            if in_degree[child] == 0:
                queue.append(child)

    if len(ordered_ids) < len(by_id):
        remaining = [
            tef_id for tef_id in by_id.keys() if tef_id not in set(ordered_ids)
        ]
        ordered_ids.extend(remaining)

    ordered_records = [by_id[tef_id] for tef_id in ordered_ids]
    if duplicates:
        ordered_records.extend(duplicates)

    return ordered_records, sorted(missing_parent_ids), len(duplicates)


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir
    output_dir = args.output_dir or input_dir

    if not input_dir.exists():
        LOGGER.error("Input directory does not exist: %s", input_dir)
        return 1

    input_path = input_dir / args.file
    if not input_path.exists():
        LOGGER.error("File not found: %s", input_path)
        return 1

    records = load_json_list(input_path)
    if not records:
        LOGGER.info("No records to sort in %s.", input_path)
        return 0

    ordered_records, missing_parent_ids, duplicate_count = topological_sort(records)

    if missing_parent_ids:
        LOGGER.warning(
            "Found %d parentId values missing from the file: %s",
            len(missing_parent_ids),
            ", ".join(missing_parent_ids[:10]),
        )
    if duplicate_count:
        LOGGER.warning("Found %d duplicate tefId records.", duplicate_count)

    if args.dry_run:
        LOGGER.info("Dry run complete. No files written.")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / args.file
    write_json(output_path, ordered_records)
    LOGGER.info("Wrote sorted records to %s", output_path)
    return 0


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
