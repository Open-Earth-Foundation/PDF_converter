"""Utility functions for PDF conversion scripts."""

import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)


def iter_pdfs(input_dir: Path, pattern: str) -> Iterable[Path]:
    """Yield PDF files that match the glob pattern (sorted for determinism).

    Args:
        input_dir: Directory path to search for PDF files.
        pattern: Glob pattern to match PDF files (e.g., "*.pdf").

    Yields:
        Path objects pointing to PDF files, sorted for determinism.
    """
    yield from sorted(input_dir.glob(pattern))


def resolve_inputs(
    input_path: Path, pattern: str, excluded_dirs: Iterable[str]
) -> list[Path]:
    """Resolve input paths to a list of PDF files.

    This function handles both single file inputs and directory inputs:
    - If input_path is a file, returns a list containing just that file.
    - If input_path is a directory, recursively searches for PDF files matching
      the pattern, excluding any files in directories specified in excluded_dirs.

    Args:
        input_path: Path to a single PDF file or a directory containing PDFs.
        pattern: Glob pattern to match PDF files (e.g., "*.pdf").
        excluded_dirs: Iterable of directory names to exclude from the search.

    Returns:
        List of Path objects pointing to PDF files to process.

    Raises:
        FileNotFoundError: If the input_path does not exist.

    Example:
        >>> from pathlib import Path
        >>> pdfs = resolve_inputs(Path("documents/file.pdf"), "*.pdf", [])
        >>> # Returns: [Path("documents/file.pdf")]

        >>> pdfs = resolve_inputs(Path("documents/"), "*.pdf", ["excluded"])
        >>> # Returns all PDFs in documents/ except those in "excluded" subdirectories
    """
    excluded = {entry.lower() for entry in excluded_dirs}
    if input_path.is_file():
        return [input_path]
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    pdfs: list[Path] = []
    for pdf in iter_pdfs(input_path, pattern):
        try:
            relative_parts = pdf.relative_to(input_path).parts
        except ValueError:
            relative_parts = pdf.parts
        if any(part.lower() in excluded for part in relative_parts):
            logger.debug("Skipping %s (excluded directory)", pdf)
            continue
        pdfs.append(pdf)
    return pdfs
