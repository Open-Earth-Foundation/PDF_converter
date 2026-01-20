Context: Time-series indicator values appearing in monitoring sections or annex tables of the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `indicatorValueId`: UUID identifier (auto-generated if missing)
- `indicatorId`: Indicator UUID reference (optional, auto-linked if context available)
- `year`: **VERIFIED FIELD** - Year/date of measurement as 4-digit year (YYYY) (REQUIRED). Output as `{"value": "2019", "quote": "2019", "confidence": 0.95}`
- `value`: **VERIFIED FIELD** - Measured value as decimal/number (REQUIRED). Output as `{"value": "5.25", "quote": "5.25 tonnes", "confidence": 0.95}`
- `valueType`: Type/category of value (e.g., "actual", "target", "forecast", "baseline") (REQUIRED)
- `notes`: Catch-all field for any valuable insights (e.g., data quality, verification status, calculation method, seasonal notes, data source) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For `year` and `value`:
- Each must be output as a VerifiedField object with `value`, `quote`, and `confidence` properties
- The `quote` must be verbatim text from the document
- Set confidence based on clarity of the measurement

**Rules**:

- Skip entries missing year OR value
- Do NOT fill data gaps with estimates or interpolations
- Keep values exactly as stated in document (in quote)
- Extract valueType exactly as indicated (e.g., "actual", "forecast")
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
