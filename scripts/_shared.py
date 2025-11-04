"""Shared helpers for the Docling conversion scripts."""

from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Iterable, Optional, Tuple, List

from docling_core.types.doc.document import DoclingDocument, TableItem
from docling.utils.model_downloader import download_models


DEFAULT_ARTIFACTS_DIR = Path("D:/models")
STANDARD_SENTINEL = ".docling_standard_ready"
GRANITE_SENTINEL = ".docling_granite_ready"


def setup_logging(verbose: bool) -> None:
    """Initialise logging with a consistent format."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )


def iter_pdfs(input_dir: Path, pattern: str) -> Iterable[Path]:
    """Yield PDF files that match the glob pattern (sorted for determinism)."""
    yield from sorted(input_dir.glob(pattern))


def _normalized_text(value: str) -> str:
    """Normalize text for similarity comparisons."""
    return re.sub(r"\s+", " ", value).strip().lower()


def is_table_of_contents(table_item: TableItem) -> bool:
    """Check if a table is likely a table of contents that should not be extracted separately."""
    try:
        df = table_item.export_to_dataframe()
        if df.empty or len(df.columns) < 2:
            return False

        # Check for TOC-like patterns
        text_content = df.to_string().lower()

        # Common TOC indicators
        toc_indicators = [
            'table of contents',
            'contents',
            'chapter',
            'section',
            'page',
            'introduction',
            'summary',
            'conclusion',
            'appendix'
        ]

        # Check if any TOC indicators are present
        has_toc_indicators = any(indicator in text_content for indicator in toc_indicators)

        # Check for repetitive content across columns (common in malformed TOC detection)
        if len(df.columns) >= 3:
            # Check if columns have very similar content
            column_texts = []
            for col in df.columns[:3]:  # Check first 3 columns
                col_text = ' '.join(df[col].astype(str).map(_normalized_text))
                column_texts.append(col_text)

            # Check for high similarity between columns
            repetitive_content = False
            for i in range(len(column_texts)):
                for j in range(i+1, len(column_texts)):
                    # Simple similarity check - if columns share many common words
                    words_i = set(column_texts[i].split())
                    words_j = set(column_texts[j].split())
                    min_len = max(len(words_i), len(words_j))
                    if min_len == 0:
                        continue
                    # Require strong overlap in vocabulary to consider as duplicate column
                    if len(words_i & words_j) >= max(int(min_len * 0.6), 5):
                        repetitive_content = True
                        break
                if repetitive_content:
                    break

            if repetitive_content and has_toc_indicators:
                return True

        # Check for page number patterns (digits at end of rows)
        page_pattern = re.compile(r'\s+\d+\s*$', re.MULTILINE)
        page_matches = page_pattern.findall(text_content)
        has_page_numbers = len(page_matches) > 3  # Multiple page numbers suggest TOC

        # Check for section numbering patterns (1., 1.1, A., etc.)
        section_pattern = re.compile(r'\b\d+\.|\b[A-Z]\.|Module\s+[A-Z]-\d+', re.IGNORECASE)
        section_matches = section_pattern.findall(text_content)
        has_section_numbers = len(section_matches) > 2

        # If it has both page numbers and section numbers, likely a TOC
        if has_page_numbers and has_section_numbers and has_toc_indicators:
            return True

        return False

    except Exception:
        # If we can't analyze the table, err on the side of caution and don't filter it
        return False


def _split_markdown_row(row: str) -> List[str]:
    """Split a markdown table row into cells."""
    parts = row.strip().strip("|").split("|")
    return [part.strip() for part in parts]


def _normalize_toc_table_lines(table_lines: list[str]) -> Optional[list[str]]:
    """Return a simplified two-column representation of a TOC table."""
    # Bail out if table already looks normalized (two columns)
    sample_cells = _split_markdown_row(table_lines[0]) if table_lines else []
    if sample_cells and len(sample_cells) <= 2:
        return None

    data_rows: list[tuple[str, str]] = []
    numbering_pattern = re.compile(r"^\d+(?:\.\d+)*$")

    for line in table_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if set(stripped.replace("|", "").strip()) <= {"-", ":"}:
            # separator row
            continue
        cells = _split_markdown_row(stripped)
        if not cells:
            continue

        normalized_cells = [_normalized_text(cell) for cell in cells]
        if all("table of contents" in cell for cell in normalized_cells if cell):
            # Skip duplicated header rows
            continue

        last_cell = cells[-1]
        page_match = re.search(r"(\d+)\s*$", last_cell)
        if not page_match:
            # Without page number we can't normalise safely
            continue
        page = page_match.group(1)
        title_part = last_cell[: page_match.start()].rstrip(". \t")

        section_number = None
        # search other columns for numbering
        for candidate in reversed(cells[:-1]):
            candidate_clean = candidate.strip()
            if numbering_pattern.fullmatch(candidate_clean):
                section_number = candidate_clean
                break

        # If numbering was embedded in the title, extract it
        embedded_match = re.match(r"^(\d+(?:\.\d+)*)\s+(.*)$", title_part)
        if section_number is None and embedded_match:
            section_number = embedded_match.group(1)
            title_part = embedded_match.group(2)

        section_title = title_part.strip()
        if not section_title:
            section_title = section_number or ""
        if section_number:
            section = f"{section_number} {section_title}".strip()
        else:
            section = section_title

        if not section:
            continue

        data_rows.append((section, page))

    if not data_rows:
        return None

    normalized_lines = ["| Section | Page |", "| --- | --- |"]
    for section, page in data_rows:
        normalized_lines.append(f"| {section} | {page} |")
    return normalized_lines


def normalize_toc_markdown(markdown_text: str) -> str:
    """Detect and simplify malformed table-of-contents tables in Markdown."""
    lines = markdown_text.splitlines()
    heading_pattern = re.compile(r"^#{1,6}\s+table of contents\s*$", re.IGNORECASE)

    for idx, line in enumerate(lines):
        if not heading_pattern.match(line.strip()):
            continue

        # Locate the table block following the heading
        start = idx + 1
        # Skip blank lines
        while start < len(lines) and not lines[start].strip():
            start += 1

        if start >= len(lines) or not lines[start].lstrip().startswith("|"):
            continue

        end = start
        while end < len(lines) and lines[end].lstrip().startswith("|"):
            end += 1

        table_lines = lines[start:end]
        normalized = _normalize_toc_table_lines(table_lines)
        if normalized is None:
            continue

        lines = lines[:start] + normalized + lines[end:]
        break

    return "\n".join(lines)


def export_tables(doc: DoclingDocument, target_root: Path) -> Tuple[int, int]:
    """Persist each table both as Markdown and CSV."""
    tables_dir: Optional[Path] = None
    exported = 0
    failed = 0

    for node, _ in doc.iterate_items(with_groups=True):
        if not isinstance(node, TableItem):
            continue

        # Skip tables that are likely table of contents or similar non-tabular content
        if is_table_of_contents(node):
            logging.info("Skipping table that appears to be a table of contents or similar structure")
            continue

        if tables_dir is None:
            tables_dir = target_root / "tables"
            tables_dir.mkdir(parents=True, exist_ok=True)

        table_slug = f"table_{exported + 1:03d}"
        markdown_path = tables_dir / f"{table_slug}.md"
        csv_path = tables_dir / f"{table_slug}.csv"

        markdown_path.write_text(
            node.export_to_markdown(), encoding="utf-8"
        )

        try:
            dataframe = node.export_to_dataframe()
        except Exception as exc:  # pragma: no cover - defensive
            failed += 1
            logging.warning(
                "Skipping CSV export for %s: %s", table_slug, exc, exc_info=True
            )
        else:
            dataframe.to_csv(csv_path, index=False)

        exported += 1

    return exported, failed


def ensure_artifacts_dir(
    path: Optional[Path] = None, *, include_granite: bool = False
) -> Path:
    """Return an artifacts directory, ensuring it lives on drive D by default."""
    target = Path(path) if path is not None else DEFAULT_ARTIFACTS_DIR
    print(f"Target artifacts dir: {target}")
    try:
        target.mkdir(parents=True, exist_ok=True)
        print(f"Created artifacts directory: {target}")
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"Artifacts directory {target} could not be created. "
            "Please verify that drive D: is available or provide an existing path."
        ) from exc
    print(f"Calling _prepare_models with include_granite={include_granite}")
    _prepare_models(target, include_granite=include_granite)
    print("Models prepared successfully")
    return target


def _prepare_models(target: Path, *, include_granite: bool) -> None:
    """Download required Docling models into the artifacts directory if missing."""
    standard_flag = target / STANDARD_SENTINEL
    granite_flag = target / GRANITE_SENTINEL

    need_standard = not standard_flag.exists()
    need_granite = include_granite and not granite_flag.exists()

    if not (need_standard or need_granite):
        return

    download_models(
        output_dir=target,
        with_layout=True,
        with_tableformer=True,
        with_code_formula=True,
        with_picture_classifier=True,
        with_easyocr=True,
        with_granite_vision=need_granite,
        with_smolvlm=False,
        with_granitedocling=False,
        with_granitedocling_mlx=False,
        with_smoldocling=False,
        with_smoldocling_mlx=False,
    )

    standard_flag.touch(exist_ok=True)
    if include_granite:
        granite_flag.touch(exist_ok=True)
