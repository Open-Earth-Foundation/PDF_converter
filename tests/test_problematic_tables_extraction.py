"""
Helper script to re-run extraction for the previously empty tables on a fixed markdown sample.

Uses the same extraction CLI (`extraction.scripts.extract`) and saves outputs under
`output/test_extraction_missing_tables` for inspection.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

MISSING_TABLE_CLASSES = ["BudgetFunding", "CityBudget", "CityTarget", "IndicatorValue"]


def main() -> int:
    load_dotenv()

    repo_root = Path(__file__).resolve().parent
    markdown_path = repo_root / "tests" / "testdocs" / "combined_markdown.md"
    output_dir = repo_root / "output" / "test_extraction_missing_tables"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not markdown_path.exists():
        print(f"❌ Markdown file not found: {markdown_path}")
        return 1

    cmd = [
        sys.executable,
        "-m",
        "extraction.scripts.extract",
        "--markdown",
        str(markdown_path),
        "--output-dir",
        str(output_dir),
        "--class-names",
        *MISSING_TABLE_CLASSES,
        "--max-rounds",
        "1",
        "--timeout",
        "180",
    ]

    print("Running extraction for missing tables...")
    print(f"  Markdown : {markdown_path}")
    print(f"  Output   : {output_dir}")
    print(f"  Classes  : {', '.join(MISSING_TABLE_CLASSES)}")
    print(f"  Command  : {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=repo_root)
    if result.returncode != 0:
        print(f"❌ Extraction failed with exit code {result.returncode}")
        return result.returncode

    print("✅ Extraction completed. Check outputs in:", output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
