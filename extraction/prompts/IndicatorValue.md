Context: Time-series indicator values appearing in monitoring sections or annex tables of the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `indicatorValueId`: UUID identifier (auto-generated if missing)
- `indicatorId`: Indicator UUID reference (optional, auto-linked if context available)
- `year`: Year/date of measurement as date (REQUIRED)
- `value`: Measured value as decimal/number (REQUIRED)
- `valueType`: Type/category of value (e.g., "actual", "target", "forecast", "baseline") (REQUIRED)
- `notes`: Catch-all field for any valuable insights (e.g., data quality, verification status, calculation method, seasonal notes, data source) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Skip entries missing year OR value
- Do NOT fill data gaps with estimates or interpolations
- Keep values exactly as stated in document
- Extract valueType exactly as indicated (e.g., "actual", "forecast")
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
