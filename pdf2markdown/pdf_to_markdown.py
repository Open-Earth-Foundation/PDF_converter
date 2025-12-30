#!/usr/bin/env python3
"""Convert PDFs to Markdown using Mistral OCR with optional OpenRouter vision refinement.

Usage (from repo root):
    python -m pdf2markdown.pdf_to_markdown --input documents/sample.pdf [--output-dir pdf2markdown/output]

Flags:
- --input: PDF file to process (required)
- --output-dir: where OCR artefacts go (default: pdf2markdown/output)
- --no-images: skip saving page images
- --save-response: persist raw OCR response JSON
- --max-upload-bytes: split large PDFs per page
- --vision-model: override vision model (defaults to llm_config.yml pdf2markdown.model)
- --vision-temperature: override vision temperature (defaults to llm_config.yml pdf2markdown.temperature)

Vision refinement:
- Requires OPENROUTER_API_KEY and (optionally) OPENROUTER_BASE_URL.
- If vision model is empty, the vision step is skipped.
"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from utils import load_llm_config, setup_logger
from pdf2markdown.utils.pdf_to_markdown_pipeline import pdf_to_markdown_pipeline

logger = logging.getLogger(__name__)


def main(args: argparse.Namespace) -> int:

    # Set input and output paths
    input_path = Path(args.input)
    output_root = Path(args.output_dir)

    # Validate input file exists
    if not input_path.exists():
        logger.error("Input file does not exist: %s", input_path)
        return 1

    if not input_path.is_file():
        logger.error("Input path is not a file: %s", input_path)
        return 1

    pdfs = [input_path]

    llm_cfg = load_llm_config().get("pdf2markdown", {})

    ocr_model = (os.environ.get("OCR_MODEL") or "mistral-ocr-latest").strip()
    vision_model = (args.vision_model or os.environ.get("VISION_MODEL") or llm_cfg.get("model", "")).strip()
    if vision_model.lower() in {"", "none", "off", "disable"}:
        vision_model = ""

    # Load vision refinement parameters from environment variables with defaults
    vision_max_rounds = int(os.environ.get("VISION_MAX_ROUNDS", "3"))
    vision_max_retries = int(os.environ.get("VISION_MAX_RETRIES", "3"))
    vision_retry_base_delay = float(os.environ.get("VISION_RETRY_BASE_DELAY", "2.0"))
    vision_temperature = float(
        args.vision_temperature
        if args.vision_temperature is not None
        else os.environ.get("VISION_TEMPERATURE", llm_cfg.get("temperature", 0.0))
    )

    successes = 0
    logger.info("Found %d PDF(s) to process.", len(pdfs))
    for pdf in pdfs:
        logger.info("Processing %s", pdf)
        try:
            pdf_to_markdown_pipeline(
                pdf,
                output_root,
                include_images=not args.no_images,
                ocr_model=ocr_model,
                save_response=args.save_response,
                save_page_markdown=True,
                vision_model=vision_model,
                vision_max_rounds=vision_max_rounds,
                vision_temperature=vision_temperature,
                vision_max_retries=vision_max_retries,
                vision_retry_base_delay=vision_retry_base_delay,
                max_upload_bytes=args.max_upload_bytes,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Failed to convert %s: %s", pdf, exc)
        else:
            successes += 1

    logger.info("Completed %d/%d conversions.", successes, len(pdfs))
    return 0 if successes else 2


if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Setup logging
    setup_logger()

    parser = argparse.ArgumentParser(
        description="Convert PDFs to Markdown using Mistral OCR.",
    )
    parser.add_argument(
        "--input",
        help="Path to a PDF file or a directory containing PDFs.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parents[1] / "output"),
        help="Directory where conversion artefacts will be written (default: pdf2markdown/output).",
    )
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip saving page images returned by the OCR service.",
    )
    parser.add_argument(
        "--save-response",
        action="store_true",
        help="Persist the raw OCR response JSON alongside the Markdown output.",
    )
    parser.add_argument(
        "--max-upload-bytes",
        type=int,
        default=int(os.environ.get("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024))),
        help="Maximum PDF size (bytes) to send in a single OCR request before splitting per page (default: 10485760). "
        "Smaller values reduce per-request payload and enable parallel processing (up to 3 requests).",
    )
    parser.add_argument(
        "--vision-model",
        default=None,
        help="Override vision model (defaults to llm_config.yml pdf2markdown.model or env VISION_MODEL).",
    )
    parser.add_argument(
        "--vision-temperature",
        type=float,
        default=None,
        help="Override vision temperature (defaults to llm_config.yml pdf2markdown.temperature).",
    )
    args = parser.parse_args()
    raise SystemExit(main(args))
