import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
import pytest

from extraction.utils.verified_utils import normalize_text_for_match

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TESTDOCS_DIR = PROJECT_ROOT / "tests" / "testdocs"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "test_outputs"
VERIFIED_FIELDS_BY_FILE = {
    "CityTarget.json": {
        "required": {"targetYear", "targetValue"},
        "optional": {"baselineYear", "baselineValue", "status"},
    },
    "EmissionRecord.json": {
        "required": {"year", "value"},
        "optional": set(),
    },
    "CityBudget.json": {
        "required": {"year", "totalAmount"},
        "optional": set(),
    },
    "IndicatorValue.json": {
        "required": {"year", "value"},
        "optional": set(),
    },
    "BudgetFunding.json": {
        "required": {"amount"},
        "optional": set(),
    },
    "Initiative.json": {
        "required": set(),
        "optional": {"startYear", "endYear", "totalEstimatedCost", "status"},
    },
}


def _alloc_dir(name: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Allocate an output directory.
    Always write inside the repository (under test_outputs/ by default) so artifacts persist.
    """
    root = Path(os.getenv("TEST_OUTPUT_ROOT") or DEFAULT_OUTPUT_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _load_json_list(path: Path) -> list[dict]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise AssertionError(f"Expected list JSON in {path}, got {type(payload).__name__}")
    return payload


def _assert_citation_proofs(output_dir: Path, markdown_text: str) -> None:
    normalized_source = normalize_text_for_match(markdown_text)
    total_verified_records = 0

    for filename, fields in VERIFIED_FIELDS_BY_FILE.items():
        records = _load_json_list(output_dir / filename)
        if not records:
            continue
        total_verified_records += len(records)

        required = fields.get("required", set())
        optional = fields.get("optional", set())

        for idx, record in enumerate(records):
            misc = record.get("misc") or {}
            if not isinstance(misc, dict):
                raise AssertionError(f"{filename} record {idx} misc is not a dict")

            for field in required:
                if field not in record:
                    raise AssertionError(f"{filename} record {idx} missing required field {field}")

            for field in required | optional:
                if field not in record:
                    continue
                proof_key = f"{field}_proof"
                if proof_key not in misc:
                    raise AssertionError(f"{filename} record {idx} missing proof for {field}")
                proof = misc.get(proof_key, {})
                if not isinstance(proof, dict):
                    raise AssertionError(f"{filename} record {idx} proof for {field} is not a dict")
                quote = proof.get("quote", "")
                if not isinstance(quote, str) or not quote.strip():
                    raise AssertionError(f"{filename} record {idx} proof for {field} missing quote")
                if normalize_text_for_match(quote) not in normalized_source:
                    raise AssertionError(
                        f"{filename} record {idx} proof for {field} quote not found in source"
                    )
                if "confidence" not in proof:
                    raise AssertionError(f"{filename} record {idx} proof for {field} missing confidence")

    if total_verified_records == 0:
        raise AssertionError(
            "No verified records extracted; cannot validate citation proofs. "
            "Consider increasing max rounds."
        )


@pytest.fixture(scope="session")
def env_vars() -> dict[str, str]:
    """Load .env once and return a mutable env mapping for subprocess calls."""
    load_dotenv(PROJECT_ROOT / ".env")
    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")):
        pytest.skip("Missing required API key: OPENROUTER_API_KEY or OPENAI_API_KEY")
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT))
    return env


def test_extraction_only_real_markdown(
    env_vars: dict[str, str], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Run extraction only (no OCR or mapping) on a real combined markdown document."""
    markdown_path = TESTDOCS_DIR / "combined_markdown.md"
    assert markdown_path.exists(), "Combined markdown fixture is missing"

    output_dir = _alloc_dir("extraction_only_output", tmp_path_factory)
    env = env_vars.copy()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "extraction.scripts.extract",
            "--markdown",
            str(markdown_path),
            "--output-dir",
            str(output_dir),
            "--class-names",
            "CityTarget",
            "EmissionRecord",
            "CityBudget",
            "IndicatorValue",
            "BudgetFunding",
            "Initiative",
            "--max-rounds",
            "1",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )

    markdown_text = markdown_path.read_text(encoding="utf-8")
    _assert_citation_proofs(output_dir, markdown_text)
