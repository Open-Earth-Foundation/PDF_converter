# Extraction

Structured data extraction from Markdown using the OpenAI Responses API with tool-calling.

## Layout
- `scripts/extract.py` – CLI entrypoint.
- `utils/` – extraction-specific helpers (config, data validation, file I/O, logging).
- `prompts/` – system/user prompts and per-class context.
- `config.yaml` – default model and runtime settings.
- `output/` – extracted JSON files.
- `debug_logs/` – optional per-round response logs (controlled by config).

## Usage
```bash
# from repo root
python -m extraction.scripts.extract --markdown path/to/combined_markdown.md
```

Flags:
- `--model` to override the model in `config.yaml`.
- `--max-rounds` to override the configured round limit.
- `--class-names` to target specific Pydantic classes.
- `--log-level` to override `LOG_LEVEL` (default INFO).

Environment:
- `OPENAI_API_KEY` or `OPENROUTER_API_KEY` is required.
- `LOG_LEVEL` can control verbosity.

Debug logs:
- Controlled by `debug_logs_enabled` in `config.yaml`.
- Set `clean_debug_logs_on_start` to remove `extraction/debug_logs` at startup.
