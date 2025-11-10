A production-grade pipeline for converting PDFs into clean, corrected Markdown with **high-quality OCR** and **layout-aware reasoning**. Uses **Mistral OCR** for document recognition and **Claude/LLM agents** with function-calling for intelligent refinement.

## Overview

After testing multiple approaches:

- **docling library** (baseline) → mid to lowresults on complex layouts
- **Granite model** (LLM refinement) → slightly better but not working for tables even the less sophisticated ones
- **Mistral OCR** (API) → much better recognition, but needed validation for complex table
- **Mistral OCR + Agent Calling** (current, v4) → **best results** with multi-page context and intelligent edits

### Current Architecture

```
PDF
  ↓
[Mistral OCR] → Markdown + Screenshot per page
  ↓
[2-Page Window] → {image_left, markdown_left, image_right, markdown_right}
  ↓
[Vision Agent] → Tool calls (select + replace) or ACCEPTED
  ↓
[Edit Engine] → Apply diffs idempotently
  ↓
Final Markdown ✓

```

---

## Goals

1. **High-quality OCR + layout-aware text** in Markdown with proper structure.
2. **Preserve page boundaries and cross-page context** via 2-page sliding windows.
3. **Full visual reflow** to DOCX/HTML with 1:1 typography.
4. **Table structure repair** beyond simple Markdown (future: agent proposes precise diffs).
5. **Auditability and idempotency** via edit logs and diff-based outputs.

---

## Iterations & Findings

### 1. Baseline: Docling Library

- Setup with the native library only.
- **Result:** Works, but extraction quality is middling; weak on complex layouts.

### 2. Granite Model (LLM from Docling)

- **Result:** Slightly better normalization; still **average** and brittle on noisy scans.

### 3. Mistral OCR (API)

- Switched OCR to Mistral's endpoint for recognition → better markdown text.
- **Result:** **Much better** than (1) and (2), but still not robust enough in isolation.
- Issues with tables and cross-page content remain.

### 4. Final Approach (Current): Mistral OCR + Agent Calling

- OCR with Mistral → Markdown per page + screenshot image.
- Feed **page screenshot + Markdown** into an LLM agent that reasons with layout context.
- **Current behavior:** Agent returns full, adjusted text per call.
- **Planned behavior:** Agent returns **diff instructions** (function calls) and loops until `ACCEPTED`.
- **Recent enhancement:** Two-page rolling window with overlap for cross-page context.

---

## Current End-to-End Flow (v4)

### 1. OCR Processing

For each page `i`, run **Mistral OCR** → `markdown_i` and keep a **screenshot image** `image_i`.

**Example from codebase:**

```python
def _request_mistral_ocr(
    client: Mistral,
    *,
    document_payload: dict[str, object],
    include_images: bool,
    max_attempts: int = 3,
    base_delay: float = 2.0,
) -> object:
    """
    Request OCR processing from Mistral with automatic retry logic.
    Retries on transient network errors up to max_attempts times.
    """
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return client.ocr.process(
                model="mistral-ocr-latest",
                document=document_payload,
                include_image_base64=include_images,
            )
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts or not _is_retryable_ocr_error(exc):
                raise
            wait = base_delay * attempt
            LOGGER.warning(
                "Mistral OCR request failed (%s). Retrying in %.1f seconds (%d/%d).",
                exc.__class__.__name__,
                wait,
                attempt,
                max_attempts,
            )
            time.sleep(wait)
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected OCR retry loop termination.")

```

### 2. Sliding Window Reasoning

Build **overlapping 2-page windows:** `[1,2], [2,3], [3,4], …`

For each window, send:

```json
{
  "image_left": "base64_encoded_page_image",
  "image_right": "base64_encoded_next_page_image",
  "markdown_left": "Current OCR markdown for left page",
  "markdown_right": "Current OCR markdown for right page"
}
```

**Example from codebase:**

```python
def _apply_pairwise_vision_refinement(
    pages: Sequence[dict[str, Optional[object]]],
    *,
    client: OpenAI,
    model: str,
    output_dir: Path,
    max_rounds: int,
    temperature: float,
    max_attempts: int,
    retry_base_delay: float,
) -> None:
    """
    Apply vision refinement in pairs of consecutive pages.
    Processes pages in overlapping windows: [1,2], [2,3], [3,4], etc.
    """
    if not pages:
        return

    batch: list[tuple[int, dict[str, Optional[object]]]] = []
    total_pages = len(pages)
    for idx, page in enumerate(pages):
        page_number = idx + 1
        batch.append((page_number, page))
        is_last = idx == total_pages - 1
        if len(batch) < 2 and not is_last:
            continue

        # Process batch (either 2 pages or last single page)
        page_numbers = [entry[0] for entry in batch]
        original_markdowns = [
            (_extract_attr(entry[1], "markdown", "") or "") for entry in batch
        ]
        images_b64 = [_extract_attr(entry[1], "image_base64") for entry in batch]

        updated_markdowns = _refine_page_group_with_vision(
            client=client,
            model=model,
            page_numbers=page_numbers,
            original_markdowns=original_markdowns,
            images_b64=images_b64,
            output_dir=output_dir,
            max_rounds=max_rounds,
            temperature=temperature,
            max_attempts=max_attempts,
            retry_base_delay=retry_base_delay,
        )

        # Update pages with refined markdown
        for (page_number, page_entry), updated_markdown in zip(batch, updated_markdowns):
            if isinstance(page_entry, dict):
                page_entry["markdown"] = updated_markdown

        batch.clear()

```

### 3. Vision Agent Refinement (Current: Full-Page Edits)

**Current behavior:** Agent returns complete, adjusted text for pages in the window.

**Tool definition:**

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "apply_page_group_edits",
            "description": "Submit revised Markdown for one or more pages in the current group when changes are required.",
            "parameters": {
                "type": "object",
                "properties": {
                    "updated_pages": {
                        "type": "array",
                        "description": "List of per-page Markdown updates.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "page_number": {
                                    "type": "integer",
                                    "description": "The page number being updated.",
                                },
                                "updated_markdown": {
                                    "type": "string",
                                    "description": "The fully updated Markdown representation for the page.",
                                },
                                "notes": {
                                    "type": "string",
                                    "description": "Brief summary of the applied fixes.",
                                },
                            },
                            "required": ["page_number", "updated_markdown"],
                        },
                    },
                },
                "required": ["updated_pages"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "approve_page_group",
            "description": "Call when the Markdown accurately reflects the page content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "justification": {
                        "type": "string",
                        "description": "Explain why no further edits are necessary.",
                    }
                },
            },
        },
    },
]

```

### 4. Post-Processing & Output

Replace the markdown for those pages with the agent's result, then concatenate all final, corrected Markdown (page by page).

```python
# Concatenate all pages with separators
final_markdown = "\\n\\n---\\n\\n".join(
    chunk.strip() for chunk in markdown_chunks
).strip()

# Normalize table of contents if present
final_markdown = normalize_toc_markdown(final_markdown) if final_markdown else ""

# Save combined markdown
markdown_path = document_dir / "combined_markdown.md"
markdown_path.write_text(final_markdown, encoding="utf-8")

```

---

## Next Step: Diff-Based Editing via Function-Calling

### Planned Agent Loop Contract

The agent must **only** return:

1. **Pairs of function calls** per proposed change:
   - `select_span_to_replace(...)` — describes _what_ to replace
   - `propose_replacement(...)` — describes _with what_ to replace it
2. **Repeat pairs** until done, then **emit** the literal word `ACCEPTED` (no more tool calls)

### Example Agent Turn (within a window `[2,3]`)

```
Agent Call 1:
select_span_to_replace({
  "edit_id": "e-102",
  "page": 2,
  "selector": {
    "type": "text",
    "pattern": "Totla amount"
  },
  "occurrence": 1,
  "reason": "Fix OCR typo"
})

Agent Call 2:
propose_replacement({
  "edit_id": "e-102",
  "replacement_markdown": "Total amount"
})

Agent Call 3:
ACCEPTED

```

### Engine Behavior

- **Maintain an in-memory index** per page to resolve selectors.
- **Apply replacements idempotently** in order of arrival.
- **Reject with structured error** if a selector misses (no match), ask agent to re-target.
- **Continue until agent emits `ACCEPTED`.**
- **Log all edits** with `edit_id`, timestamp, and justification for auditability.

---

## Two-Page Sliding Window: Why & How

### Why?

Many artifacts span page boundaries:

- Headings flowing over to the next page
- Footnotes and hyphenation
- Table continuation
- Cross-page lists and paragraphs

### How?

Generate windows `(i, i+1)` for `i=1..N-1`, overlapping adjacent pages:

```
Page 1 | Page 2
         Page 2 | Page 3
                  Page 3 | Page 4
                           ...

```

### Edge Cases

- **Last page:** Process as single page or create a "ghost" neighbor with empty content.
- **Single-page PDFs:** Process as-is with one window.

---

## Operational Notes

### Idempotency

Applying the same replacement twice shouldn't break the document:

- Selectors should fail cleanly after first success
- Use `edit_id` to track and skip duplicate edits
- Store applied replacements in an edit log per window

### Auditability

Keep an **edit log** (who/when/why) keyed by `edit_id`:

```json
{
  "edit_id": "e-102",
  "page": 2,
  "timestamp": "2025-11-07T10:30:00Z",
  "selector": {
    "type": "text",
    "pattern": "Totla amount"
  },
  "replacement": "Total amount",
  "reason": "Fix OCR typo",
  "applied": true
}
```

### Performance

- **Batch windows:** Process in order; cap edit rounds to avoid infinite loops.
- **Compress images:** Reduce base64 payload before sending to vision API.
- **Parallel OCR:** Split large PDFs per page and process up to 3 chunks in parallel.

---

## Setup & Installation

### Requirements

```
docling[vlm]==2.55.1
mistralai>=0.4.0
python-dotenv>=1.0.0
pypdf>=4.0.0
openai>=1.0.0

```

### Environment Setup

Create a `.env` file in the project root (a `.env.example` is included):

```bash
MISTRAL_API_KEY=your_mistral_api_key
OPENROUTER_API_KEY=your_openrouter_api_key
OPENAI_BASE_URL=https://openrouter.ai/api/v1  # or your OpenAI endpoint

```

### Installation

```bash
pip install -r requirements.txt

```

---

## Usage

### Basic OCR Only

By default, vision refinement is enabled (model: anthropic/claude-haiku-4.5). To run OCR only, disable vision by passing an empty model:

```bash
python scripts/pdf_to_markdown_mistral.py path/to/document.pdf --vision-model ""

```

### With Vision Refinement

Vision refinement is enabled by default. To choose a different model:

```bash
python scripts/pdf_to_markdown_mistral.py path/to/document.pdf \\
  --vision-model "anthropic/claude-opus-4"

```

### Batch Processing

Process a directory of PDFs:

```bash
python scripts/pdf_to_markdown_mistral.py documents/ \\
  --output-dir output/mistral_OCR \\
  --pattern "*.pdf" \\
  --exclude-subdir old

```

### Advanced Options

```bash
python scripts/pdf_to_markdown_mistral.py path/to/document.pdf \\
  --no-images                 # Skip saving page images
  --save-response             # Persist raw OCR response JSON
  --max-upload-bytes 5242880  # Split large PDFs (default: 10MB)
  --vision-model "anthropic/claude-opus-4" \\
  --verbose                   # Enable debug logging

```

---

## Output Structure

```
output/mistral_OCR/
├── document_name/
│   ├── combined_markdown.md         # Final concatenated markdown
│   ├── page-0001.md                 # Individual page markdown
│   ├── page-0002.md
│   ├── ...
│   ├── images/
│   │   ├── page-0001.jpeg
│   │   ├── page-0002.jpeg
│   │   └── ...
│   └── vision_diffs/                # Diff files from refinement rounds
│       ├── page-0001-round-1.diff
│       ├── page-0002-round-1.diff
│       └── ...

```

---

## Core API: `pdf_to_markdown_mistral()`

The main entry point for PDF conversion:

```python
def pdf_to_markdown_mistral(
    pdf_path: Path,
    output_root: Path,
    *,
    client: Optional[Mistral] = None,
    include_images: bool = True,
    save_response: bool = False,
    save_page_markdown: bool = True,
    vision_client: Optional[OpenAI] = None,
    vision_model: Optional[str] = None,
    vision_max_rounds: int = 3,
    vision_temperature: float = 0.0,
    vision_max_attempts: int = 3,
    vision_retry_base_delay: float = 2.0,
    max_upload_bytes: int = 10 * 1024 * 1024,
) -> Path:

```

### Example Usage

```python
from pathlib import Path
from mistralai import Mistral
from openai import OpenAI
from scripts.pdf_to_markdown_mistral import pdf_to_markdown_mistral

mistral_client = Mistral(api_key="your-key")
vision_client = OpenAI(api_key="your-key", base_url="<https://openrouter.ai/api/v1>")

result_path = pdf_to_markdown_mistral(
    Path("documents/sample.pdf"),
    Path("output/mistral_OCR"),
    client=mistral_client,
    vision_client=vision_client,
    vision_model="anthropic/claude-haiku-4.5",
    include_images=True,
)

print(f"Output: {result_path}")

```

---

## Troubleshooting

### "Missing Mistral API key"

Ensure `MISTRAL_API_KEY` is set in `.env` or pass `--api-key` to the CLI.

### "Missing optional dependency 'openai'"

Install the OpenAI client:

```bash
pip install openai>=1.0.0

```

### "Vision refinement failed"

- Check that `OPENROUTER_API_KEY` or `OPENAI_API_KEY` is set.
- Verify the vision model identifier is correct.
- Programmatic use only (not exposed as CLI flags yet): you can tune `vision_max_attempts`, `vision_max_rounds`, and `vision_retry_base_delay` via the Python API in `pdf_to_markdown_mistral(...)`.

### Large PDFs timeout

Use `--max-upload-bytes` to split into smaller chunks:

```bash
python scripts/pdf_to_markdown_mistral.py huge.pdf \\
  --max-upload-bytes 5242880  # 5 MB chunks

```

---

## Project Structure

```
project_root/
│
├── app/                        # Main application code
│   ├── documentw/              # Documents workspace (project-specific)
│   ├── output/                 # Output artifacts (generated at runtime)
│   └── scripts/                # Conversion scripts
│       ├── _shared.py              # Shared utilities (logging, TOC normalization, etc.)
│       ├── granite_conversion.py   # Granite model conversion (v2)
│       ├── library_conversion.py   # Docling library conversion (v1)
│       └── pdf_to_markdown_mistral.py  # Main OCR + vision refinement (v4)
│
├── .env                        # API keys and configuration
├── .env.example                # Template for .env
├── requirements.txt            # Core dependencies
└── README.md                   # This file

```

---

## Backlog & Next Steps

- [ ] **Switch agent to diff-only outputs** — replace full-page rewrites with targeted edits
- [ ] **Add fuzzy selector fallback** — Levenshtein distance ≤ 2 for robustness
- [ ] **Optional table fixer** — repair simple grid tables beyond Markdown
- [ ] **Exporters** — convert final Markdown → HTML/DOCX with 1:1 typography
- [ ] **Evaluation set** — CER/WER metrics + structural checks against ground truth
- [ ] **UI dashboard** — visualize OCR progress and edit history
- [ ] **Multi-language support** — parameterize OCR prompts for non-English documents

---

## Done Criteria

✅ Agent consistently produces only tool calls and then `ACCEPTED`.
✅ All windows processed with no unresolved selectors.
✅ Final Markdown semantically matches screenshots (titles, paragraphs, lists, tables).
✅ Edit logs stored and queryable by `edit_id`.
✅ Diffs saved per refinement round for auditability.

---

## License

See `LICENSE.md` for details.

---

## Contributing

For bug reports, feature requests, or contributions, please open an issue or pull request.

---

## References

- **Mistral OCR:** [Mistral AI Documentation](https://docs.mistral.ai/)
- **OpenRouter:** [OpenRouter API](https://openrouter.ai/)
- **Docling:** [IBM Docling Project](https://github.com/DS4SD/docling)

---

**Last Updated:** November 7, 2025
