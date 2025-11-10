#!/usr/bin/env python3
"""Convert PDFs to Markdown using Docling's Granite-based configuration.

This workflow keeps images, saves them alongside the Markdown output, and
stores Granite-generated picture descriptions for later inspection.
"""

from __future__ import annotations

print("Starting granite_conversion.py")

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
    InputFormat,
    ConfidenceReport,
)
from docling_core.types.doc.document import (
    DoclingDocument,
    PictureItem,
)
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    granite_picture_description,
)
from docling.exceptions import ConversionError
from docling_core.types.doc.base import ImageRefMode

try:  # pragma: no cover - import convenience
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
    """Configure Docling to enrich images with Granite descriptions."""
    print("Ensuring artifacts directory...")
    artifacts_dir = ensure_artifacts_dir(
        include_granite=False
    )  # Temporarily disable granite
    print(f"Artifacts dir: {artifacts_dir}")
    print("Creating PDF options...")
    pdf_options = PdfPipelineOptions(
        do_table_structure=True,
        do_ocr=True,
        generate_page_images=False,
        generate_picture_images=True,
        do_picture_description=False,  # Temporarily disable picture description
        artifacts_path=artifacts_dir,
    )
    print("Creating DocumentConverter...")
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pdf_options)}
    )


def doc_with_image_refs(
    doc: DoclingDocument, markdown_path: Path, image_dir: Path
) -> DoclingDocument:
    """Create a copy with referenced image files ready for Markdown export."""
    return doc._with_pictures_refs(
        image_dir=image_dir, page_no=None, reference_path=markdown_path
    )


def extract_picture_metadata(doc: DoclingDocument) -> Tuple[int, int, list[dict]]:
    """Gather metadata about exported pictures and their annotations."""
    total = 0
    described = 0
    entries: list[dict] = []

    for node, _ in doc.iterate_items(with_groups=True, traverse_pictures=True):
        if not isinstance(node, PictureItem):
            continue

        total += 1
        prov = node.prov[0] if node.prov else None
        bbox = getattr(prov, "bbox", None)
        bbox_dict = (
            {"l": bbox.l, "t": bbox.t, "r": bbox.r, "b": bbox.b}
            if bbox is not None
            else None
        )

        annotations = [annotation.model_dump() for annotation in node.get_annotations()]
        description = next(
            (
                ann.get("text")
                for ann in annotations
                if ann.get("kind") == "description" and ann.get("text")
            ),
            None,
        )
        if description:
            described += 1

        entry = {
            "index": total,
            "relative_path": str(node.image.uri) if node.image else None,
            "page": getattr(prov, "page_no", None),
            "bbox": bbox_dict,
            "description": description,
            "annotations": annotations,
        }
        entries.append(entry)

    return total, described, entries


def serialize_metadata(
    result_status: ConversionStatus,
    doc: DoclingDocument,
    pdf_path: Path,
    markdown_path: Path,
    images_dir: Path,
    tables_info: Tuple[int, int],
    picture_info: Tuple[int, int],
    confidence: ConfidenceReport,
) -> dict:
    """Prepare metadata for later inspection."""
    tables_exported, tables_failed = tables_info
    pictures_exported, pictures_described = picture_info

    return {
        "source_pdf": str(pdf_path.resolve()),
        "markdown_file": str(markdown_path.resolve()),
        "images_dir": str(images_dir.resolve()),
        "converted_at": datetime.now(timezone.utc).isoformat(),
        "pages_converted": doc.num_pages(),
        "tables": {
            "exported": tables_exported,
            "export_failed": tables_failed,
        },
        "pictures": {
            "exported": pictures_exported,
            "with_descriptions": pictures_described,
            "description_model": granite_picture_description.repo_id,
        },
        "status": result_status.value,
        "confidence": json.loads(confidence.model_dump_json()),
    }


def process_pdf(
    converter: DocumentConverter,
    pdf_path: Path,
    output_root: Path,
    max_pages: Optional[int],
) -> Optional[Path]:
    """Run the Granite conversion workflow for a single PDF."""
    doc_output_dir = output_root / pdf_path.stem
    doc_output_dir.mkdir(parents=True, exist_ok=True)

    markdown_path = doc_output_dir / "document.md"
    images_dir = doc_output_dir / "images"

    convert_kwargs = {}
    if max_pages is not None:
        convert_kwargs["page_range"] = (1, max_pages)

    try:
        conversion_result = converter.convert(pdf_path, **convert_kwargs)
    except (ConversionError, OSError) as exc:
        logging.error("Failed to convert %s: %s", pdf_path.name, exc)
        return None
    except Exception as exc:  # pragma: no cover - defensive
        logging.exception("Unexpected failure while converting %s", pdf_path.name)
        return None

    image_doc = doc_with_image_refs(
        conversion_result.document, markdown_path, images_dir
    )
    tables_info = export_tables(image_doc, doc_output_dir)

    markdown_text = image_doc.export_to_markdown(
        image_mode=ImageRefMode.REFERENCED, include_annotations=True
    )
    markdown_path.write_text(
        normalize_toc_markdown(markdown_text),
        encoding="utf-8",
    )

    total_pictures, described_pictures, picture_entries = extract_picture_metadata(
        image_doc
    )
    (doc_output_dir / "images_metadata.json").write_text(
        json.dumps(picture_entries, indent=2), encoding="utf-8"
    )

    metadata = serialize_metadata(
        conversion_result.status,
        image_doc,
        pdf_path,
        markdown_path,
        images_dir,
        tables_info,
        (total_pictures, described_pictures),
        conversion_result.confidence,
    )
    (doc_output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )

    logging.info(
        "Converted %s -> %s (images stored in %s)",
        pdf_path.name,
        markdown_path.relative_to(output_root),
        images_dir.relative_to(output_root),
    )
    return doc_output_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PDFs with Docling Granite (images + descriptions)."
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
        default=Path("output") / "granite",
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    setup_logger()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.info("Input dir: %s", input_dir)
    logging.info("Output dir: %s", output_dir)
    logging.info("Pattern: %s", args.pattern)

    converter = build_converter()
    logging.info("Converter built successfully")

    pdf_files = list(iter_pdfs(input_dir, args.pattern))
    logging.info("Found %d PDF files: %s", len(pdf_files), [str(p) for p in pdf_files])
    if not pdf_files:
        logging.warning(
            "No PDF files found in %s with pattern %s", input_dir, args.pattern
        )
        return 1

    successes = 0
    for pdf_path in pdf_files:
        logging.info("Processing %s", pdf_path)
        if process_pdf(converter, pdf_path, output_dir, args.max_pages):
            successes += 1
            logging.info("Successfully processed %s", pdf_path)
        else:
            logging.error("Failed to process %s", pdf_path)

    logging.info("Completed %s/%s conversions.", successes, len(pdf_files))
    return 0 if successes else 2


if __name__ == "__main__":
    raise SystemExit(main())
