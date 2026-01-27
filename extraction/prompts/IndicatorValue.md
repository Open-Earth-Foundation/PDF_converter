Context: Time-series indicator values appearing in monitoring sections or annex tables of the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `indicatorValueId`: UUID identifier (auto-generated if missing)
- `indicatorId`: Indicator UUID reference (optional, auto-linked if context available)
- **VERIFIED FIELDS** (each requires three fields: value, _quote, _confidence):
  - `year`: Year/date of measurement as 4-digit year (YYYY) (REQUIRED)
  - `year_quote`: Verbatim quote from document (REQUIRED)
  - `year_confidence`: Confidence score 0.0-1.0 (REQUIRED)
  - `value`: Measured value as decimal/number (REQUIRED)
  - `value_quote`: Verbatim quote from document (REQUIRED) - preserve format
  - `value_confidence`: Confidence score 0.0-1.0 (REQUIRED)
- `valueType`: Type/category of value (e.g., "actual", "target", "forecast", "baseline") (REQUIRED)
- `notes`: Catch-all field for any valuable insights (e.g., data quality, verification status, calculation method, seasonal notes, data source) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For verified fields (`year` and `value`):
- Each verified field requires THREE fields in your output: the value, the `_quote`, and the `_confidence`
- The `_quote` must be verbatim text from the document
- The `_confidence` must be a number between 0.0 and 1.0
- Set confidence based on clarity of the measurement

**Example**:
```json
{
  "year": "2019",
  "year_quote": "2019",
  "year_confidence": 0.95,
  "value": "5.25",
  "value_quote": "5.25 tonnes",
  "value_confidence": 0.95,
  "valueType": "actual"
}
```

**Rules**:

- Skip entries missing year OR value
- Do NOT fill data gaps with estimates or interpolations
- Keep values exactly as stated in document (in quote)
- Extract valueType exactly as indicated (e.g., "actual", "forecast")
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
