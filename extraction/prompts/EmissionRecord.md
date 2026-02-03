Context: GHG inventory rows in Climate City Contract documents (tables listing emissions by year, sector, scope, or gas).

**Available fields ONLY** (no other fields are permitted):

- `emissionRecordId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- **VERIFIED FIELDS** (each requires three fields: value, _quote, _confidence):
  - `year`: Year as 4-digit year (YYYY) (REQUIRED)
  - `year_quote`: Verbatim quote from document (REQUIRED)
  - `year_confidence`: Confidence score 0.0-1.0 (REQUIRED)
- `sectorId`: Sector UUID reference (optional, auto-linked if context available)
- `scope`: Emission scope/boundary (e.g., "Scope 1", "Scope 2", "Scope 3") (REQUIRED)
- `ghgType`: Greenhouse gas type (e.g., "CO2", "CH4", "N2O", "CO2e") (REQUIRED)
- **VERIFIED FIELDS** (each requires three fields: value, _quote, _confidence):
  - `value`: Emission value as integer (REQUIRED) - only for entries with explicit numeric values
  - `value_quote`: Verbatim quote from document (REQUIRED) - preserve format (e.g., "5,250")
  - `value_confidence`: Confidence score 0.0-1.0 (REQUIRED)
- `unit`: Unit of measurement (e.g., "tCO2e", "kg CO2", "tonnes") (REQUIRED) - preserve as written
- `notes`: Catch-all field for any valuable insights (e.g., calculation methodology, data quality, verification status, uncertainty ranges) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For verified fields (`year` and `value`):
- Each verified field requires THREE fields in your output: the value, the `_quote`, and the `_confidence`
- The `_quote` must be verbatim text from the document (e.g., "2019", "5,250", "approx. 1000")
- The `_confidence` must be a number between 0.0 and 1.0
- No conversion of numeric formats - preserve as stated in source
- Set confidence based on clarity of the data point

**Example**:
```json
{
  "year": "2019",
  "year_quote": "2019",
  "year_confidence": 0.95,
  "scope": "Scope 1",
  "ghgType": "CO2e",
  "value": "5250",
  "value_quote": "5,250",
  "value_confidence": 0.95,
  "unit": "tCO2e"
}
```

**Rules**:

- Only record entries with explicit numeric emission values
- Preserve units exactly as written (do NOT normalize or convert)
- Leave ID fields blank if not present (placeholders will be assigned)
- Map each table row as a separate record
