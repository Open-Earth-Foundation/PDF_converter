"""
Brief: Analyze mapping output structure and statistics.

Inputs:
- --input-dir: directory with step3 mapping outputs (default: output/mapping/step3_llm)
- --sample-size: number of sample records to show per table (default: 1)

Outputs:
- Displays file counts, record counts, sample data
- Shows any files that don't exist
- Logs to stdout

Usage (from project root):
- python -m app.scripts.analyze_mapping_output
- python -m app.scripts.analyze_mapping_output --sample-size 2
- python -m app.scripts.analyze_mapping_output --input-dir custom/mapping/dir
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from utils.logging_config import setup_logger

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = [
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
    "ClimateCityContract",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze mapping output structure and statistics."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=REPO_ROOT / "output" / "mapping" / "step3_llm",
        help="Directory with step3 mapping outputs.",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=1,
        help="Number of sample records to show per table (default: 1).",
    )
    return parser.parse_args()


def format_size(size_bytes: int) -> str:
    """Format byte size to human readable."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def analyze_table(file_path: Path, sample_size: int) -> dict[str, Any]:
    """Analyze a single table file."""
    if not file_path.exists():
        return {
            "exists": False,
            "size": 0,
            "record_count": 0,
            "sample_records": [],
            "error": "File not found",
        }

    try:
        content = file_path.read_text(encoding="utf-8")
        size = file_path.stat().st_size
        data = json.loads(content)

        if not isinstance(data, list):
            return {
                "exists": True,
                "size": size,
                "record_count": 0,
                "sample_records": [],
                "error": f"Expected list, got {type(data).__name__}",
            }

        sample_records = data[:sample_size] if sample_size > 0 else []

        return {
            "exists": True,
            "size": size,
            "record_count": len(data),
            "sample_records": sample_records,
            "error": None,
        }
    except json.JSONDecodeError as e:
        return {
            "exists": True,
            "size": file_path.stat().st_size,
            "record_count": 0,
            "sample_records": [],
            "error": f"Invalid JSON: {str(e)}",
        }
    except Exception as e:
        return {
            "exists": True,
            "size": 0,
            "record_count": 0,
            "sample_records": [],
            "error": f"Error reading file: {str(e)}",
        }


def main() -> int:
    args = parse_args()
    setup_logger()

    input_dir = args.input_dir
    if not input_dir.exists():
        LOGGER.error("Input directory does not exist: %s", input_dir)
        return 1

    print("\n" + "=" * 80)
    print("Mapping Output Analysis")
    print("=" * 80)
    print(f"\nDirectory: {input_dir}")
    print(f"Sample size per table: {args.sample_size} record(s)")

    total_files = 0
    total_records = 0
    total_size = 0
    files_with_errors = []

    print("\n" + "-" * 80)
    print(f"{'Table':<30} {'Records':<15} {'Size':<15} {'Status':<20}")
    print("-" * 80)

    for table_name in EXPECTED_TABLES:
        file_path = input_dir / f"{table_name}.json"
        analysis = analyze_table(file_path, args.sample_size)

        if analysis["error"]:
            status = f"ERROR: {analysis['error']}"
            files_with_errors.append((table_name, analysis["error"]))
        elif not analysis["exists"]:
            status = "MISSING"
        else:
            status = "OK"

        records = analysis["record_count"]
        size_str = format_size(analysis["size"])

        print(f"{table_name:<30} {records:<15} {size_str:<15} {status:<20}")

        total_files += 1
        total_records += records
        total_size += analysis["size"]

        # Show sample records if requested
        if args.sample_size > 0 and analysis["sample_records"]:
            for idx, record in enumerate(analysis["sample_records"], 1):
                # Get first few fields
                fields = list(record.keys())[:3]
                sample_str = ", ".join(f"{k}={repr(record[k])[:30]}" for k in fields)
                print(f"    Sample {idx}: {{{sample_str}...}}")

    print("-" * 80)
    files_present = len(
        [t for t in EXPECTED_TABLES if (input_dir / f"{t}.json").exists()]
    )
    total_files_count = f"{files_present}/{len(EXPECTED_TABLES)} files"
    print(
        f"{'TOTAL':<30} {total_records:<15} {format_size(total_size):<15} "
        f"{total_files_count:<20}"
    )
    print("=" * 80)

    if files_with_errors:
        print("\nFiles with errors:")
        for table_name, error in files_with_errors:
            print(f"  - {table_name}: {error}")

    print(f"\nReady to insert: {len(files_with_errors) == 0}")
    print()

    return 1 if files_with_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
