"""Run the full PDF -> Markdown -> Extraction -> Mapping pipeline.

Steps per PDF:
1) Convert PDF to Markdown with Mistral OCR (pdf2markdown).
2) Extract structured JSON from the combined Markdown (extraction).

After all PDFs:
3) Run mapping workflow (--apply) to stage FK-mapped outputs.

Prereqs:
- MISTRAL_API_KEY (for OCR)
- OPENAI_API_KEY or OPENROUTER_API_KEY (for extraction)
- OPENROUTER_API_KEY (for mapping LLM step)

Usage:
    python run_pipeline.py                                    # Process all PDFs in documents/
    python run_pipeline.py --input documents/sample.pdf      # Process single PDF
    python run_pipeline.py --no-vision                        # OCR only, no vision refinement
    python run_pipeline.py --input documents/file.pdf --no-vision  # Single PDF, OCR only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from dotenv import load_dotenv


def find_pdfs(documents_dir: Path) -> list[Path]:
    return sorted(p for p in documents_dir.glob("*.pdf") if p.is_file())


def find_latest_markdown(output_root: Path, pdf_stem: str) -> Optional[Path]:
    """Find the newest combined_markdown.md for a given PDF stem."""
    candidates: list[tuple[float, Path]] = []
    for entry in output_root.glob(f"*_{pdf_stem}"):
        combined = entry / "combined_markdown.md"
        if combined.exists():
            candidates.append((combined.stat().st_mtime, combined))
    if not candidates:
        return None
    _, path = max(candidates, key=lambda item: item[0])
    return path


def run_cmd(args: Iterable[str]) -> int:
    result = subprocess.run(args, check=False)
    return result.returncode


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run PDF -> Markdown -> Extraction -> Mapping pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py                           # All PDFs with vision refinement
  python run_pipeline.py --input documents/sample.pdf   # Single PDF with vision
  python run_pipeline.py --no-vision               # All PDFs, OCR only
  python run_pipeline.py --input documents/sample.pdf --no-vision  # Single PDF, OCR only
        """,
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Single PDF file to process (default: all PDFs in documents/)",
    )
    parser.add_argument(
        "--no-vision",
        action="store_true",
        help="Skip vision refinement, run OCR only (faster)",
    )
    parser.add_argument(
        "--no-mapping",
        action="store_true",
        help="Skip mapping stage (default: run mapping)",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    repo_root = Path(__file__).resolve().parent
    documents_dir = repo_root / "documents"
    # Unified output directory at root level
    output_root = repo_root / "output"
    pdf_output_root = output_root / "pdf2markdown"
    extraction_output_dir = output_root / "extraction"
    mapping_work_dir = output_root / "mapping"

    # Get PDFs to process
    if args.input:
        # Single PDF specified
        if not args.input.exists():
            print(f"Error: File not found: {args.input}")
            return 1
        pdfs = [args.input]
        print(f"Processing single file: {args.input.name}")
    else:
        # All PDFs in documents/
        pdfs = find_pdfs(documents_dir)
        if not pdfs:
            print("No PDFs found in documents/. Nothing to do.")
            return 0
        print(f"Processing {len(pdfs)} PDFs from documents/")

    # Show processing info
    if args.no_vision:
        print("Mode: OCR only (vision refinement DISABLED)")
    else:
        print("Mode: OCR + Vision refinement")

    # Create unified output structure
    output_root.mkdir(parents=True, exist_ok=True)
    pdf_output_root.mkdir(parents=True, exist_ok=True)
    extraction_output_dir.mkdir(parents=True, exist_ok=True)
    mapping_work_dir.mkdir(parents=True, exist_ok=True)

    for pdf_path in pdfs:
        print(f"\n[1/3] Converting PDF -> Markdown: {pdf_path.name}")
        cmd = [
            sys.executable,
            "-m",
            "pdf2markdown.pdf_to_markdown",
            "--input",
            str(pdf_path),
            "--output-dir",
            str(pdf_output_root),
        ]

        # Add vision model flag if --no-vision is set
        if args.no_vision:
            cmd.extend(["--vision-model", ""])

        code = run_cmd(cmd)
        if code != 0:
            print(
                f"Conversion failed for {pdf_path.name} (exit {code}); skipping extraction."
            )
            continue

        markdown_path = find_latest_markdown(pdf_output_root, pdf_path.stem)
        if not markdown_path:
            print(
                f"Could not locate combined_markdown.md for {pdf_path.name}; skipping extraction."
            )
            continue

        print(
            f"[2/3] Extracting structured data from {markdown_path.relative_to(repo_root)}"
        )
        code = run_cmd(
            [
                sys.executable,
                "-m",
                "extraction.scripts.extract",
                "--markdown",
                str(markdown_path),
                "--output-dir",
                str(extraction_output_dir),
            ]
        )
        if code != 0:
            print(f"Extraction failed for {markdown_path} (exit {code}).")

    # Run mapping stage unless --no-mapping is set
    if not args.no_mapping:
        print("\n[3/3] Running mapping workflow (--apply)...")
        map_code = run_cmd(
            [
                sys.executable,
                "-m",
                "mapping.scripts.mapping",
                "--apply",
                "--input-dir",
                str(extraction_output_dir),
                "--work-dir",
                str(mapping_work_dir),
            ]
        )
        if map_code != 0:
            print(f"Mapping workflow finished with exit {map_code}.")
            return map_code
    else:
        print("\nMapping stage skipped (--no-mapping flag)")

    print("\n✅ Pipeline completed!")
    print(f"   Outputs in: {output_root.relative_to(repo_root)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
