# Extraction

Structured data extraction from Markdown using the OpenAI Responses API with tool-calling and Evidence Pattern verification.

## Layout
- `scripts/extract.py` – CLI entrypoint.
- `utils/` – extraction-specific helpers (config, data validation, file I/O, logging, verified fields).
  - `verified_field.py` – VerifiedField type definition for Evidence Pattern.
  - `verified_utils.py` – Quote validation and verified-to-database mapping utilities.
- `prompts/` – system/user prompts and per-class context.
- `schemas_verified.py` – Extraction-specific schemas with verified fields.
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

## Evidence Pattern (Verified Extraction)

### Overview

The Evidence Pattern enforcement adds trustworthiness to extracted data by requiring every numeric, date, and status value to be backed by:
1. **Value** – the extracted data point
2. **Quote** – exact verbatim text from the source document
3. **Confidence** – confidence score (0.0–1.0) for the extraction

### Verified Fields

Certain fields in extraction schemas are marked as "verified" and must include evidence:

- **CityTarget**: `targetYear`, `targetValue`, `baselineYear`, `baselineValue`, `status`
- **EmissionRecord**: `year`, `value`
- **CityBudget**: `year`, `totalAmount`
- **IndicatorValue**: `year`, `value`
- **BudgetFunding**: `amount`
- **Initiative**: `startYear`, `endYear`, `totalEstimatedCost`, `status`

### How It Works

1. **LLM Extraction**: The LLM receives the `VerifiedField` schema structure and outputs data matching it:
   ```json
   {
     "targetYear": {
       "value": "2030",
       "quote": "by 2030",
       "confidence": 0.95
     }
   }
   ```

2. **Quote Validation**: Each quote is validated against the source markdown:
   - Text is normalized (whitespace collapsed, case-insensitive, hyphens handled)
   - If quote is not found in source, the record is **rejected**

3. **Output Transformation**: After validation, verified fields are converted to scalar values:
   - Input: `{"value": "2030", "quote": "by 2030", "confidence": 0.95}`
   - Output: `"targetYear": 2030` with proof stored in `misc`

4. **Proof Storage**: Evidence is stored in the `misc` field:
   ```json
   {
     "targetYear": 2030,
     "misc": {
       "targetYear_proof": {
         "quote": "by 2030",
         "confidence": 0.95
       }
     }
   }
   ```

### Confidence Scoring

**Important**: Confidence scores  are **not used in validation logic**. All records are validated equally by quote matching only (see below).

The LLM is instructed to assign confidence based on text clarity:

- **0.95–1.0**: Clear, unambiguous text (e.g., "by 2030", "80% reduction")
- **0.8–0.94**: Reasonable inference from clear context (e.g., implied from table headers)
- **0.5–0.79**: Ambiguous text requiring interpretation (e.g., "around 300", conflicting sources)
- **Below 0.5**: Highly uncertain; LLM should use `null` value instead

These scores are stored in the `misc` field.

### Handling Missing Data

**CRITICAL**: `null` values are ONLY valid when backed by an explicit quote from the document.

**Rule**: If a field value is missing from the source, you MUST find evidence text in the document that confirms its absence (e.g., "not specified", "not available", "N/A", "information missing", etc.). The quote must be verbatim from the source.

**Valid Example** (document contains "no baseline specified"):

```json
{
  "baselineYear": {
    "value": null,
    "quote": "no baseline specified",
    "confidence": 0.9
  }
}
```

### Database Compatibility

Output JSON remains compatible with the database schema:
- Scalar values can be stored directly
- Proof entries in `misc` are optional for downstream processing
- Mapping pipeline continues to work without changes

### Validation Logic

- **Binary Matching**: Records are **rejected if ANY verified quote is not found** in source text (normalized matching handles whitespace, line breaks, case-insensitivity)
- **Confidence Ignored**: Confidence scores do not affect acceptance/rejection; validation is purely quote-based
- **Quote Validation**: All quotes are normalized and searched in source text; if not found, the entire record is rejected
- **Backward Compatible**: Non-verified schemas work as before; only classes with VerifiedField use this feature

### Testing

Run tests to verify the implementation:

```bash
pytest tests/test_verified_field.py       # VerifiedField validation
pytest tests/test_quote_validation.py     # Quote matching logic
pytest tests/test_verified_mapping.py     # Field mapping
pytest tests/test_extraction_verified.py  # Full extraction flow
```
