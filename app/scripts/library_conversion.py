#!/usr/bin/env python3
"""Convert PDFs to Markdown with Docling using the standard library pipeline.

Images are removed to keep the focus on text and table structure. Each input PDF
is converted into its own subfolder that contains the Markdown output, extracted
tables (Markdown + CSV), and a small metadata summary.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import (
    ConversionStatus,
    ConfidenceReport,
    InputFormat,
)
from docling_core.types.doc.document import (
    DoclingDocument,
    PictureItem,
)
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.exceptions import ConversionError
from docling_core.types.doc.base import ImageRefMode

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

try:  # pragma: no cover - import convenience for script/module usage
    from scripts._shared import (
        ensure_artifacts_dir,
        export_tables,
        iter_pdfs,
        normalize_toc_markdown,
    )
except ModuleNotFoundError:  # pragma: no cover
    from _shared import (
        ensure_artifacts_dir,
        export_tables,
        iter_pdfs,
        normalize_toc_markdown,
    )

from utils.logging_config import setup_logger


def build_converter() -> DocumentConverter:
    """Configure the standard Docling pipeline for PDF conversion."""
    artifacts_dir = ensure_artifacts_dir(include_granite=False)
    pdf_options = PdfPipelineOptions(
        do_table_structure=True,
        do_ocr=True,
        generate_page_images=False,
        generate_picture_images=False,
        generate_table_images=False,
        artifacts_path=artifacts_dir,
    )
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)}
    )


def remove_pictures(doc: DoclingDocument) -> int:
    """Strip picture nodes from the document."""
    pictures = [
        node
        for node, _ in doc.iterate_items(with_groups=True, traverse_pictures=True)
        if isinstance(node, PictureItem)
    ]
    if pictures:
        doc.delete_items(node_items=pictures)
    return len(pictures)


def serialize_metadata(
    result_status: ConversionStatus,
    doc: DoclingDocument,
    pdf_path: Path,
    markdown_path: Path,
    tables_info: Tuple[int, int],
    pictures_removed: int,
    confidence: ConfidenceReport,
) -> dict:
    """Prepare metadata for later inspection."""
    tables_exported, tables_failed = tables_info

    return {
        "source_pdf": str(pdf_path.resolve()),
        "markdown_file": str(markdown_path.resolve()),
        "converted_at": datetime.now(timezone.utc).isoformat(),
        "pages_converted": doc.num_pages(),
        "tables": {
            "exported": tables_exported,
            "export_failed": tables_failed,
        },
        "pictures_removed": pictures_removed,
        "status": result_status.value,
        "confidence": json.loads(confidence.model_dump_json()),
    }


def combine_documents(docs: list[DoclingDocument]) -> DoclingDocument:
    """Combine multiple DoclingDocument instances into a single document."""
    if not docs:
        raise ValueError("No documents to combine")

    if len(docs) == 1:
        return docs[0]

    # Start with the first document as base
    combined = docs[0].model_copy(deep=True)

    # Add content from subsequent documents
    for doc in docs[1:]:
        # Combine text content
        for text_item in doc.texts:
            combined.texts.append(text_item.model_copy(deep=True))

        # Combine tables
        for table_item in doc.tables:
            combined.tables.append(table_item.model_copy(deep=True))

    return combined


def process_pdf(
    converter: DocumentConverter,
    pdf_path: Path,
    output_root: Path,
    max_pages: Optional[int],
    chunk_size: int = 10,
) -> Optional[Path]:
    """Run the conversion workflow for a single PDF, processing in chunks to handle memory constraints."""
    doc_output_dir = output_root / pdf_path.stem
    doc_output_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = doc_output_dir / "document.md"

    # Get total pages in the PDF
    try:
        with open(pdf_path, "rb") as f:
            pdf_reader = PdfReader(f)
            total_pages = len(pdf_reader.pages)
    except Exception as exc:
        logging.error("Failed to read PDF page count for %s: %s", pdf_path.name, exc)
        return None

    if max_pages is not None:
        total_pages = min(total_pages, max_pages)

    logging.info(
        "Processing %s with %d pages in chunks of %d",
        pdf_path.name,
        total_pages,
        chunk_size,
    )

    # Process PDF in chunks
    all_docs = []
    combined_tables_exported = 0
    combined_tables_failed = 0
    combined_pictures_removed = 0

    for start_page in range(1, total_pages + 1, chunk_size):
        end_page = min(start_page + chunk_size - 1, total_pages)
        logging.info(
            "Processing pages %d-%d of %s", start_page, end_page, pdf_path.name
        )

        convert_kwargs = {"page_range": (start_page, end_page)}

        try:
            conversion_result = converter.convert(pdf_path, **convert_kwargs)
        except ConversionError as exc:
            logging.error(
                "Failed to convert pages %d-%d of %s: %s",
                start_page,
                end_page,
                pdf_path.name,
                exc,
            )
            continue
        except Exception as exc:  # pragma: no cover - defensive
            logging.exception(
                "Unexpected failure while converting pages %d-%d of %s",
                start_page,
                end_page,
                pdf_path.name,
            )
            continue

        # Process this chunk
        working_doc = conversion_result.document.model_copy(deep=True)
        pictures_removed = remove_pictures(working_doc)
        tables_info = export_tables(working_doc, doc_output_dir)

        combined_pictures_removed += pictures_removed
        combined_tables_exported += tables_info[0]
        combined_tables_failed += tables_info[1]

        all_docs.append(working_doc)

    if not all_docs:
        logging.error("No chunks were successfully processed for %s", pdf_path.name)
        return None

    # Combine all document chunks
    try:
        combined_doc = combine_documents(all_docs)
    except Exception as exc:
        logging.error(
            "Failed to combine document chunks for %s: %s", pdf_path.name, exc
        )
        # Fallback: use the first chunk
        combined_doc = all_docs[0]

    # Export the combined document
    markdown_text = combined_doc.export_to_markdown(image_mode=ImageRefMode.PLACEHOLDER)
    markdown_path.write_text(
        normalize_toc_markdown(markdown_text),
        encoding="utf-8",
    )

    # Create combined metadata (using the last conversion result for status/confidence)
    metadata = serialize_metadata(
        (
            conversion_result.status
            if "conversion_result" in locals()
            else ConversionStatus.SUCCESS
        ),
        combined_doc,
        pdf_path,
        markdown_path,
        (combined_tables_exported, combined_tables_failed),
        combined_pictures_removed,
        (
            conversion_result.confidence
            if "conversion_result" in locals()
            else ConfidenceReport()
        ),
    )
    (doc_output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    logging.info(
        "Converted %s -> %s (%d pages processed in chunks)",
        pdf_path.name,
        markdown_path.relative_to(output_root),
        total_pages,
    )
    return doc_output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PDFs to Markdown using Docling (images removed)."
    )
    parser.add_argument(
        "input_dir",
        nargs="?",
        default="documents",
        help="Directory with input PDF files (default: %(default)s).",
    )
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=Path("output") / "library",
        help="Directory where conversion results will be written.",
    )
    parser.add_argument(
        "--pattern",
        default="*.pdf",
        help="Glob pattern for selecting PDFs (default: %(default)s).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optionally cap the number of pages processed per document.",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=10,
        help="Number of pages to process at once. Larger = faster but more memory (default: %(default)s).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    setup_logger()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    converter = build_converter()

    pdf_files = list(iter_pdfs(input_dir, args.pattern))
    if not pdf_files:
        logging.warning(
            "No PDF files found in %s with pattern %s", input_dir, args.pattern
        )
        return 1

    successes = 0
    for pdf_path in pdf_files:
        if process_pdf(
            converter, pdf_path, output_dir, args.max_pages, args.chunk_size
        ):
            successes += 1

    logging.info("Completed %s/%s conversions.", successes, len(pdf_files))
    return 0 if successes else 2


if __name__ == "__main__":
    raise SystemExit(main())
