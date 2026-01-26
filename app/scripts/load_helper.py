"""
Brief: Interactive helper script to test and load mapping output into database.

Inputs:
- User interactive menu selection
- Env: DATABASE_URL in .env

Outputs:
- Runs one of: test connection, validate dry-run, insert data, or verify DB
- Displays results inline
- Reports saved to output/db_load_reports/

Usage (from project root):
- python -m app.scripts.load_helper
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.modules.db_insert.module import run_load
from app.scripts.test_db_connection import main as test_connection
from app.scripts.test_insert import main as test_insert
from app.utils.logging_config import setup_logger

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def show_menu() -> str:
    """Display menu and get user choice."""
    print("\n" + "=" * 60)
    print("PDF Converter - Database Load Helper")
    print("=" * 60)
    print("\nChoose an option:")
    print("  1) Test database connection")
    print("  2) Validate mapping output (dry-run, no insert)")
    print("  3) Insert mapping output into database")
    print("  4) Verify database (show row counts and samples)")
    print("  5) Run full workflow (validate → insert → verify)")
    print("  6) Exit")
    print()
    choice = input("Enter choice [1-6]: ").strip()
    return choice


def print_section(title: str) -> None:
    """Print a section header."""
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}\n")


def load_latest_report(pattern: str) -> dict | None:
    """Load the latest report JSON file."""
    report_dir = REPO_ROOT / "output" / "db_load_reports"
    reports = sorted(
        report_dir.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not reports:
        return None
    try:
        return json.loads(reports[0].read_text(encoding="utf-8"))
    except Exception as e:
        LOGGER.error(f"Failed to load report: {e}")
        return None


def print_report_summary(report: dict) -> None:
    """Print a formatted summary of the report."""
    if not report:
        print("No report found.")
        return

    mode = report.get("mode", "N/A")
    dry_run = report.get("dry_run", False)
    tables = report.get("tables", {})
    errors = report.get("errors", [])
    missing_fields = report.get("missing_fields", {})
    error_count = report.get("error_count_total", 0)

    print(f"Mode: {mode} | Dry Run: {dry_run}")
    print(f"Total Errors: {error_count}\n")

    print("Table Summary:")
    print(
        f"  {'Table':<25} {'Loaded':<10} {'Validated':<12} {'Inserted':<10} {'Failed':<10}"
    )
    print("  " + "─" * 67)
    for table_name, counts in tables.items():
        loaded = counts.get("loaded", 0)
        validated = counts.get("validated", 0)
        inserted = counts.get("inserted", 0)
        failed = counts.get("failed", 0)
        print(
            f"  {table_name:<25} {loaded:<10} {validated:<12} "
            f"{inserted:<10} {failed:<10}"
        )

    if missing_fields:
        print(f"\nMissing Fields:")
        for field, count in sorted(
            missing_fields.items(), key=lambda x: x[1], reverse=True
        )[:10]:
            print(f"  - {field}: {count} records")

    if errors:
        print(f"\nErrors (showing first 5 of {len(errors)}):")
        for err in errors[:5]:
            table = err.get("table", "N/A")
            stage = err.get("stage", "N/A")
            field = err.get("field", "N/A")
            message = err.get("message", "N/A")
            print(f"  - {table} [{stage}] {field}: {message}")


def run_test_connection() -> int:
    """Test database connection."""
    print_section("Testing Database Connection")
    result = test_connection()
    if result == 0:
        print("\n✓ Database connection OK\n")
    else:
        print("\n✗ Database connection FAILED\n")
    return result


def run_validation() -> int:
    """Run dry-run validation."""
    print_section("Validating Mapping Output (Dry Run)")
    result = run_load(
        input_dir=REPO_ROOT / "output" / "mapping" / "step3_llm",
        mode="validate",
        report_path=None,  # auto-generate
        dry_run=True,
        on_error="stop",
        atomic=False,
    )
    if result == 0:
        print("\n✓ Validation passed\n")
        report = load_latest_report("db_load_report_*.json")
        if report:
            print_report_summary(report)
    else:
        print("\n✗ Validation FAILED\n")
        report = load_latest_report("db_load_report_*.json")
        if report:
            print_report_summary(report)
    return result


def run_insert() -> int:
    """Insert mapping output into database."""
    print_section("Inserting Mapping Output into Database")
    confirm = (
        input("Are you sure? This will insert data into the database. [y/N]: ")
        .strip()
        .lower()
    )
    if confirm != "y":
        print("Cancelled.")
        return 0

    result = run_load(
        input_dir=REPO_ROOT / "output" / "mapping" / "step3_llm",
        mode="validate",
        report_path=None,  # auto-generate
        dry_run=False,
        on_error="stop",
        atomic=False,
    )
    if result == 0:
        print("\n✓ Insert completed successfully\n")
        report = load_latest_report("db_load_report_*.json")
        if report:
            print_report_summary(report)
    else:
        print("\n✗ Insert FAILED\n")
        report = load_latest_report("db_load_report_*.json")
        if report:
            print_report_summary(report)
    return result


def run_verify() -> int:
    """Verify database contents."""
    print_section("Verifying Database Contents")
    # Override sys.argv for test_insert script
    original_argv = sys.argv
    try:
        sys.argv = ["test_insert", "--limit", "2"]
        result = test_insert()
        if result == 0:
            print("\n✓ Database verification completed\n")
            report = load_latest_report("test_insert_report_*.json")
            if report:
                tables = report.get("tables", {})
                print("Table Row Counts:")
                for table, data in tables.items():
                    count = data.get("count", 0)
                    samples = data.get("samples", [])
                    print(f"  {table}: {count} rows")
                    if samples:
                        for idx, sample in enumerate(samples, 1):
                            keys = list(sample.keys())[:3]  # Show first 3 fields
                            print(f"    Sample {idx}: {keys}...")
        else:
            print("\n✗ Database verification FAILED\n")
    finally:
        sys.argv = original_argv
    return result


def run_full_workflow() -> int:
    """Run complete workflow: test connection → validate → insert → verify."""
    print_section("Running Full Workflow")
    print("\nThis will: test connection → validate → insert → verify\n")
    confirm = input("Continue? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return 0

    steps = [
        ("Test Connection", run_test_connection),
        ("Validate Mapping", run_validation),
        ("Insert Data", run_insert),
        ("Verify Database", run_verify),
    ]

    for step_name, step_func in steps:
        result = step_func()
        if result != 0:
            print(f"\n✗ Workflow stopped at: {step_name}")
            return 1
        input(f"\nPress Enter to continue to next step...")

    print_section("Workflow Complete")
    print("✓ All steps completed successfully!")
    return 0


def main() -> int:
    """Main interactive menu."""
    load_dotenv(REPO_ROOT / ".env")
    setup_logger()

    while True:
        choice = show_menu()
        if choice == "1":
            run_test_connection()
        elif choice == "2":
            run_validation()
        elif choice == "3":
            run_insert()
        elif choice == "4":
            run_verify()
        elif choice == "5":
            run_full_workflow()
        elif choice == "6":
            print("\nGoodbye!")
            return 0
        else:
            print("Invalid choice. Please try again.")


if __name__ == "__main__":
    raise SystemExit(main())
