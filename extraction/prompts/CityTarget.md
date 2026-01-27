Context: Targets defined in the Climate City Contract (e.g., emission reductions, renewable share, energy savings).

**Available fields ONLY** (no other fields are permitted):

- `cityTargetId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `indicatorId`: Indicator UUID reference (optional, auto-linked if context available)
- `description`: Target description (REQUIRED)
- **VERIFIED FIELDS** (each requires three fields: value, _quote, _confidence):
  - `targetYear`: Target year as 4-digit year (YYYY) (REQUIRED)
  - `targetYear_quote`: Verbatim quote from document (REQUIRED)
  - `targetYear_confidence`: Confidence score 0.0-1.0 (REQUIRED)
  - `targetValue`: Target value as decimal/number (REQUIRED)
  - `targetValue_quote`: Verbatim quote from document (REQUIRED)
  - `targetValue_confidence`: Confidence score 0.0-1.0 (REQUIRED)
  - `baselineYear`: Baseline year as 4-digit year (YYYY) - OPTIONAL
  - `baselineYear_quote`: Verbatim quote from document - OPTIONAL
  - `baselineYear_confidence`: Confidence score 0.0-1.0 - OPTIONAL
  - `baselineValue`: Baseline value as decimal/number - OPTIONAL
  - `baselineValue_quote`: Verbatim quote from document - OPTIONAL
  - `baselineValue_confidence`: Confidence score 0.0-1.0 - OPTIONAL
  - `status`: Target status (e.g., "Set", "On track", "At risk", "Achieved") - OPTIONAL
  - `status_quote`: Verbatim quote from document - OPTIONAL
  - `status_confidence`: Confidence score 0.0-1.0 - OPTIONAL
- `notes`: Catch-all field for any valuable insights (e.g., measurement methodology, assumptions, risk factors, policy drivers) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For verified fields (`targetYear`, `targetValue`, `baselineYear`, `baselineValue`, `status`):
- Each verified field requires THREE fields in your output: the value, the `_quote`, and the `_confidence`
- The `_quote` must be verbatim text from the document (exact match required)
- The `_confidence` must be a number between 0.0 and 1.0
- The value can be null ONLY if the document explicitly states absence (e.g., "not specified", "N/A", "not available") AND you can quote that text verbatim
- If the document is silent about a field (just doesn't mention it), OMIT ALL THREE FIELDS—do not include the field, _quote, or _confidence
- No inference or normalization - only literal values and quotes from source

**Example**:
```json
{
  "description": "80% reduction by 2030",
  "targetYear": "2030",
  "targetYear_quote": "by 2030",
  "targetYear_confidence": 0.95,
  "targetValue": "80",
  "targetValue_quote": "80% reduction",
  "targetValue_confidence": 0.95
}
```

**Important: Quote Validation**
- Your quotes will be validated against the source document
- If a quote is NOT found in the source, the entire record will be REJECTED
- Use only exact verbatim text from the document as quotes

**Rules**:

- Skip entries missing both year AND value
- Keep numeric values and dates exactly as stated in document
- Leave ID fields blank if not present (placeholders will be assigned)
- Do NOT convert or normalize units in verified fields (e.g., keep "%", "tonnes", etc. as stated)
