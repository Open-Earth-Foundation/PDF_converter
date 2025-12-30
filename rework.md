# Rework TODOs

## Cross-cutting
- Trim tracked artefacts (`__pycache__`, generated `output/`, `workflow_output/`, `mistral_OCR/` dumps) and add ignores so only source + sample inputs stay in git.
- Align dependency manifests: `pyproject.toml` is missing items from `requirements.txt` (langchain-core, PyYAML, tiktoken, likely pydantic/openai response stack). Decide one source of truth and sync.
- Keep top-level `utils/` for shared plumbing only (logging setup, client factories); move domain-specific helpers into per-domain `utils/` packages.

## PDF2Markdown
- [x] Add `README` + CLI entrypoint; keep `pdf2markdown/pdf_to_markdown.py` at package root and use local utils imports.
- [x] `utils/pdf_to_markdown_pipeline.py` imports `scripts._shared.normalize_toc_markdown`, but no such module exists. Reintroduce the helper (or inline the logic) and fix the import so the pipeline runs.
- [x] `utils/utils.py` (iter_pdfs/resolve_inputs) is unused anywhere; either remove or relocate into a pdf2markdown utils module if still needed.
- [x] Decide where OCR outputs should live (e.g., `pdf2markdown/output/`) and stop committing generated `mistral_OCR` assets.

## Extraction
- [x] Current imports point to `app.utils` / `app.extraction.tools`, but there is no `app` package. Package `extraction/` properly (with `__init__.py`) and switch to relative imports (`from extraction.utils ...`, `from extraction.tools ...`).
- [x] Move extraction-specific helpers out of top-level `utils/` (config_utils, data_utils, file_utils, logging_utils) into `extraction/utils/`, and adjust call sites.
- [x] `extraction/tools/__init__.py` also uses the `app.` prefix; fix to relative import and ensure the tools package is discoverable.
- [x] Add `README` + `scripts/extract.py` entrypoint with updated usage; verify default paths (config/prompts/output) after the move.
- [x] `clean_debug_logs` currently points at `extraction/debug_logs` (folder absent). Decide the correct log location and wire it up or drop the cleanup.

## Mapping
- [x] All mapping modules import via `app.mapping...` and hack `sys.path` with `parents[2]` (resolves to `.../GitHub`, not repo root). Convert mapping into a package, use relative imports, and drop the path hack.
- [x] Add `scripts/` entrypoint(s) (e.g., `mapping.py`, `apply_llm_mapping.py`, `apply_city_mapping.py`, `clear_foreign_keys.py`, `validate_foreign_keys.py`) and refresh usage strings to match.
- [x] Ensure default input/output paths target the new extraction output location after the package reshuffle.
- [x] Generated `workflow_output/` and `debug_logs/` likely belong in data/ignored areas; move or ignore them once scripts are in `scripts/`.

## Docs / dead references
- README still references `granite_conversion.py` but that file no longer exists; update or remove the Granite section.
- Add per-domain READMEs (pdf2markdown/extraction/mapping) describing the new structure and entry scripts.
