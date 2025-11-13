#!/usr/bin/env python3
"""Convert PDFs to Markdown using the Mistral Document AI OCR service.

Vision refinement (optional):
- Set VISION_MODEL in your environment to enable a secondary vision pass.
  - OpenRouter: use vendor-prefixed ids like "openai/gpt-4o-mini" or "anthropic/claude-haiku-4.5"
  - OpenAI direct: use OpenAI ids like "gpt-4o-mini" and set OPENAI_BASE_URL=https://api.openai.com/v1
If VISION_MODEL is empty or unset, the vision refinement step is skipped.

Example usage (using OpenAI directly):

Ensure that in the .env file that:
- the OPENROUTER_API_KEY is NOT set
- the OPENROUTER_BASE_URL is NOT set
- the OPENAI_API_KEY is set
- the OPENAI_BASE_URL is set to https://api.openai.com/v1

```
cd app
python -m scripts.pdf_to_markdown_mistral --input documents/heidelberg_nzc_ccc_small.pdf --output-dir output/mistral
```

"""

from __future__ import annotations

import argparse
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from utils.logging_config import setup_logger
from utils.pdf_to_markdown_pipeline import pdf_to_markdown_pipeline

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

    ocr_model = (os.environ.get("OCR_MODEL") or "mistral-ocr-latest").strip()
    vision_model = (os.environ.get("VISION_MODEL") or "").strip()

    # Load vision refinement parameters from environment variables with defaults
    vision_max_rounds = int(os.environ.get("VISION_MAX_ROUNDS", "3"))
    vision_max_retries = int(os.environ.get("VISION_MAX_RETRIES", "3"))
    vision_retry_base_delay = float(os.environ.get("VISION_RETRY_BASE_DELAY", "2.0"))
    vision_temperature = float(os.environ.get("VISION_TEMPERATURE", "0.1"))

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
        default=str(Path("output") / "mistral_OCR"),
        help="Directory where conversion artefacts will be written.",
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
    args = parser.parse_args()
    raise SystemExit(main(args))
