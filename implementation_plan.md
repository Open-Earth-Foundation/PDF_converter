# Implementation Plan: Large-Document Chunked Extraction

Goal: Process documents larger than the model context window (e.g., Aachen ~700 pages) by auto-chunking Markdown above 300k tokens into ~200k-token windows with 10k overlap, using tiktoken counting and only paragraph/sentence boundaries (tables kept intact even if we overflow).

## Ticket 1: Baseline sizing and chunking spec
- Goal: Confirm real token counts and define chunking rules for large PDFs.
- Tasks:
  - Measure token count for the Aachen combined_markdown.md and record size/structure notes (headings, tables, section breaks).
  - Define chunk size defaults (200k tokens, 10k overlap) and auto-chunk threshold (300k tokens) in terms of tiktoken counts.
  - Define boundaries: only end-of-paragraph or end-of-sentence; allow overflow to reach the next valid boundary.
  - Define table handling: keep tables intact even if that overflows the chunk size.
- Acceptance criteria:
  - A short spec section in this file describing chunk sizes, overlap, auto-threshold, boundary rules, and table handling.

## Ticket 2: Token-based chunker utility
- Goal: Add a reusable chunking helper that splits Markdown by tokens with overlap.
- Tasks:
  - Create `extraction/utils/chunking.py` with a `chunk_markdown()` function using tiktoken for token counting.
  - Return chunk objects with index, token counts, and start/end offsets or line numbers.
  - Split only on end of paragraph or end of sentence; allow overflow to reach a valid boundary.
  - Detect Markdown tables and keep each table intact even if the chunk exceeds the target size.
- Acceptance criteria:
  - Unit tests cover chunk size limits, overlap correctness, and boundary preference.

## Ticket 3: Config and CLI support for chunking
- Goal: Make chunking configurable and easy to enable.
- Tasks:
  - Add `extraction.chunking` settings to `llm_config.yml` (enabled, auto_threshold_tokens=300000, chunk_size_tokens=200000, chunk_overlap_tokens=10000, boundary_mode=paragraph_or_sentence, keep_tables_intact=true).
  - Add CLI overrides to `extraction.scripts.extract` (e.g., `--chunk-size-tokens`, `--chunk-overlap-tokens`, `--chunking`).
  - Extend `extraction/utils/config_utils.py` to load defaults cleanly.
- Acceptance criteria:
  - Chunking can be enabled via config or CLI without code changes.

## Ticket 4: Chunked extraction flow in `extraction/extract.py`
- Goal: Run extraction across chunks when a document exceeds token limits.
- Tasks:
  - If token count exceeds `auto_threshold_tokens` or chunking is enabled, split Markdown into chunks and process sequentially.
  - Inject a chunk header in the prompt (chunk index, total chunks, overlap note, heading path) to preserve context.
  - Include a compact summary of previously extracted instances for the same table (only from completed chunks/ranks) in the chunk prompt to reduce duplicates.
- Acceptance criteria:
  - Large documents no longer fail with "File too large" and extraction completes per chunk.

## Ticket 5: Dedup and provenance for overlapping chunks
- Goal: Avoid duplicate records from overlap and retain traceability.
- Tasks:
  - Add `source_notes` (chunk id + heading path or offset) into tool calls for each record.
  - Track table identifiers (heading path + table index or header hash) so prior extractions from the same table can be reused in prompts.
  - Use only same-table extractions from completed chunks/ranks; do not share cross-table context.
  - Add a secondary dedup pass based on primary-key fields and normalized content.
  - Optionally merge near-duplicates created by overlap.
- Acceptance criteria:
  - Overlap does not materially inflate record counts for a test document.

## Ticket 6: Resume and failure isolation
- Goal: Make chunked runs resumable and robust while coordinating parallel workers.
- Tasks:
  - Track per-chunk per-class completion in a lightweight shared state so re-runs can skip completed work.
  - Define processing order for parallel runs (chunk index rank) and only share same-table context from completed ranks.
  - Continue processing remaining chunks if one chunk fails; log failures clearly without adding verbose logging.
- Acceptance criteria:
  - Re-running with `--resume` skips completed chunks and continues where it left off.

## Ticket 7: Pipeline and docs updates
- Goal: Expose chunking in user-facing workflows.
- Tasks:
  - Update `README.md` and `extraction/README.md` with chunking usage and examples.
  - Update `run_pipeline.py` to auto-enable chunking for large Markdown or pass through CLI flags.
- Acceptance criteria:
  - Docs include a worked example for a large file (Aachen) and the new flags are documented.

## Ticket 8: Validation on Aachen document
- Goal: Verify end-to-end behavior on the 700-page Aachen PDF.
- Tasks:
  - Run chunked extraction on the Aachen markdown and review outputs for missing sections and duplicates.
  - Record basic metrics: total tokens, number of chunks, runtime, record counts per class.
- Acceptance criteria:
  - Aachen extraction completes without context errors, with sensible record counts and no obvious gaps.
