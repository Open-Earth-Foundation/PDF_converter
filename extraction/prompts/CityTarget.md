Context: Targets defined in the Climate City Contract (e.g., emission reductions, renewable share, energy savings).

**Available fields ONLY** (no other fields are permitted):

- `cityTargetId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `indicatorId`: Indicator UUID reference (optional, auto-linked if context available)
- `description`: Target description (REQUIRED)
- `targetYear`: **VERIFIED FIELD** - Target year as 4-digit year (YYYY) (REQUIRED). Output as `{"value": "2030", "quote": "by 2030", "confidence": 0.95}`
- `targetValue`: **VERIFIED FIELD** - Target value as decimal/number (REQUIRED). Output as `{"value": "80", "quote": "80% reduction", "confidence": 0.95}`
- `baselineYear`: **VERIFIED FIELD** - Baseline year as 4-digit year (YYYY) - only if explicitly stated in document. Use null with verbatim quote ONLY if document explicitly says "not specified", "not available", "N/A", etc. Otherwise OMIT THIS FIELD.
- `baselineValue`: **VERIFIED FIELD** - Baseline value as decimal/number - only if explicitly stated in document. Use null with verbatim quote ONLY if document explicitly says "not specified", "not available", "N/A", etc. Otherwise OMIT THIS FIELD.
- `status`: **VERIFIED FIELD** - Target status (e.g., "on track", "at risk", "achieved") - OPTIONAL. Output as `{"value": "on track", "quote": "on track", "confidence": 0.9}` or omit the field if status is not mentioned in document.
- `notes`: Catch-all field for any valuable insights (e.g., measurement methodology, assumptions, risk factors, policy drivers) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For `targetYear`, `targetValue`, `baselineYear`, `baselineValue`, and `status`:
- Each must be output as a VerifiedField object with `value`, `quote`, and `confidence` properties (only when the field is present)
- The `quote` must be verbatim text from the document
- The `value` can be null ONLY if the document explicitly states absence (e.g., "not specified", "N/A", "not available") AND you can quote that text verbatim
- If the document is silent about a field (just doesn't mention it), OMIT THE FIELD ENTIRELY—do not use null
- No inference or normalization - only literal values and quotes from source

**Important: Quote Validation**
- Your quotes will be validated against the source document
- If a quote is NOT found in the source, the entire record will be REJECTED
- Use only exact verbatim text from the document as quotes

**Rules**:

- Skip entries missing both year AND value
- Keep numeric values and dates exactly as stated in document
- Leave ID fields blank if not present (placeholders will be assigned)
- Do NOT convert or normalize units in verified fields (e.g., keep "%", "tonnes", etc. as stated)
