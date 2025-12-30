# PDF2Markdown

OCR and vision refinement pipeline for converting PDFs into Markdown using Mistral OCR plus optional OpenRouter vision models.

## Layout
- `pdf_to_markdown.py` – CLI entrypoint.
- `utils/` – pipeline + helpers (`pdf_to_markdown_pipeline.py`, client factories, markdown normalizer).
- `output/` – default location for OCR artefacts (timestamped folders with pages, images, diffs).

## Usage
```bash
# from repo root
python -m pdf2markdown.pdf_to_markdown --input documents/my.pdf
```

Flags:
- `--output-dir` (default `pdf2markdown/output`) to change where artefacts are written.
- `--no-images` to skip saving page images.
- `--save-response` to persist the raw OCR response JSON.
- `--max-upload-bytes` to force per-page OCR splitting for large PDFs.

Environment:
- `MISTRAL_API_KEY` is required for OCR.
- Optional: `VISION_MODEL` + `OPENROUTER_API_KEY` for vision refinement (OpenRouter only).
- Logging level via `LOG_LEVEL` (defaults to INFO).
