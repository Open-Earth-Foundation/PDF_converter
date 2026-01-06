import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pypdf import PdfReader, PdfWriter
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS_DIR = PROJECT_ROOT / "documents"
TESTDOCS_DIR = PROJECT_ROOT / "tests" / "testdocs"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "test_outputs"


def _alloc_dir(name: str, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """
    Allocate an output directory.
    Always write inside the repository (under test_outputs/ by default) so artefacts persist.
    """
    root = Path(os.getenv("TEST_OUTPUT_ROOT") or DEFAULT_OUTPUT_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    run_dir = root / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def _build_excerpt_pdf(source_pdf: Path, target_pdf: Path, pages: int = 10) -> Path:
    """Create a trimmed PDF with the first `pages` pages from source_pdf."""
    reader = PdfReader(str(source_pdf))
    if len(reader.pages) < pages:
        raise ValueError(f"{source_pdf.name} has only {len(reader.pages)} pages (need at least {pages}).")
    target_pdf.parent.mkdir(parents=True, exist_ok=True)
    writer = PdfWriter()
    for idx in range(pages):
        writer.add_page(reader.pages[idx])
    with target_pdf.open("wb") as handle:
        writer.write(handle)
    return target_pdf


def _latest_combined_markdown(output_root: Path) -> Path:
    """Locate the newest combined_markdown.md emitted by pdf2markdown."""
    matches = sorted(output_root.rglob("combined_markdown.md"))
    if not matches:
        raise FileNotFoundError(f"No combined_markdown.md under {output_root}")
    return matches[-1]


@pytest.fixture(scope="session")
def env_vars() -> dict[str, str]:
    """Load .env once and return a mutable env mapping for subprocess calls."""
    load_dotenv(PROJECT_ROOT / ".env")
    missing = [key for key in ("MISTRAL_API_KEY", "OPENROUTER_API_KEY") if not os.getenv(key)]
    if missing:
        pytest.skip(f"Missing required API keys: {', '.join(missing)}")
    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT))
    return env


@pytest.fixture(scope="session")
def ten_page_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a temporary 10-page excerpt from an existing document."""
    source_pdf = DOCUMENTS_DIR / "heidelberg_nzc_ccc_ok.pdf"
    target_dir = _alloc_dir("pdf_excerpt", tmp_path_factory)
    target_pdf = target_dir / "heidelberg_first10.pdf"
    return _build_excerpt_pdf(source_pdf, target_pdf, pages=10)


def test_full_pipeline_first_ten_pages(
    ten_page_pdf: Path, env_vars: dict[str, str], tmp_path_factory: pytest.TempPathFactory
) -> None:
    """Run the entire PDF->markdown->extraction->mapping pipeline on 10 pages."""
    pdf_output = _alloc_dir("pdf2md_output", tmp_path_factory)
    extraction_output = _alloc_dir("extraction_output", tmp_path_factory)
    mapping_output = _alloc_dir("mapping_output", tmp_path_factory)

    env = env_vars.copy()
    env.setdefault("VISION_MAX_ROUNDS", "1")
    env.setdefault("VISION_MAX_RETRIES", "1")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pdf2markdown.pdf_to_markdown",
            "--input",
            str(ten_page_pdf),
            "--output-dir",
            str(pdf_output),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )

    markdown_path = _latest_combined_markdown(pdf_output)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "extraction.scripts.extract",
            "--markdown",
            str(markdown_path),
            "--output-dir",
            str(extraction_output),
            "--max-rounds",
            "1",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )

    subprocess.run(
        [
            sys.executable,
            "-m",
            "mapping.scripts.mapping",
            "--apply",
            "--input-dir",
            str(extraction_output),
            "--work-dir",
            str(mapping_output),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )

    step3_llm = Path(mapping_output) / "step3_llm"
    assert step3_llm.exists(), "Mapping step did not materialise outputs"
    assert any(step3_llm.glob("*.json")), "No mapped JSON files were written"


def test_partial_extraction_from_markdown(env_vars: dict[str, str], tmp_path_factory: pytest.TempPathFactory) -> None:
    """Run the extraction script alone against a small markdown sample."""
    sample_markdown = TESTDOCS_DIR / "sample_partial_markdown.md"
    assert sample_markdown.exists(), "Sample markdown for partial test is missing"

    output_dir = _alloc_dir("partial_extraction_output", tmp_path_factory)
    env = env_vars.copy()

    subprocess.run(
        [
            sys.executable,
            "-m",
            "extraction.scripts.extract",
            "--markdown",
            str(sample_markdown),
            "--output-dir",
            str(output_dir),
            "--class-names",
            "City",
            "CityTarget",
            "--max-rounds",
            "1",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )

    produced_files = {path.name for path in Path(output_dir).glob("*.json")}
    assert {"City.json", "CityTarget.json"}.issubset(produced_files), "Expected partial outputs not found"
