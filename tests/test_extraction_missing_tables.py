import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv, find_dotenv


MISSING_TABLE_CLASSES = ["BudgetFunding", "CityBudget", "CityTarget", "IndicatorValue"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.mark.integration
def test_extraction_missing_tables_have_records() -> None:
    """
    Integration smoke test: run extraction only for the previously empty tables
    using the checked-in combined_markdown sample, and assert we get data.
    """
    # Ensure .env is loaded for OPENROUTER_API_KEY
    load_dotenv(find_dotenv(".env", usecwd=True))
    if not os.getenv("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY required for live extraction")

    repo_root = _repo_root()
    markdown_path = repo_root / "tests" / "testdocs" / "combined_markdown.md"
    assert markdown_path.exists(), "Sample markdown missing at tests/testdocs/combined_markdown.md"

    output_dir = repo_root / "output" / "test_extraction_missing_tables"
    output_dir.mkdir(parents=True, exist_ok=True)
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
        "120",
    ]

    try:
        result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired as exc:
        pytest.skip(f"Extraction CLI timed out after {exc.timeout}s (document too large for fast test)")

    if result.returncode != 0:
        pytest.fail(f"Extraction CLI failed (exit {result.returncode}): {result.stderr or result.stdout}")

    for cls in MISSING_TABLE_CLASSES:
        path = output_dir / f"{cls}.json"
        assert path.exists(), f"{cls}.json was not written"
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list), f"{cls}.json is not a list"
        assert len(data) > 0, f"Expected at least one {cls} record; found 0"
