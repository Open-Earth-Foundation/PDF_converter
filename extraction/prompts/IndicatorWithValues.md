Context: Extract indicators with their associated time-series values in a single grouped structure. This enables linking measurements to their parent indicator definitions.

**Available fields ONLY** (no other fields are permitted):

- `indicatorId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `sectorId`: Sector UUID reference (optional, auto-linked if context available)
- `name`: Indicator name (REQUIRED) - exactly as written
- `description`: Indicator description or definition (REQUIRED) - extract what the indicator measures, its purpose, or any descriptive text. If no explicit description exists, infer from the name and context
- `unit`: Measurement unit (e.g., "%", "tonnes", "MWh", "people") (REQUIRED) - exactly as written
- `values`: Array of IndicatorValue objects (REQUIRED) - each value requires:
  - `year`: Year/date of measurement as 4-digit year (YYYY) (REQUIRED)
  - `year_quote`: Verbatim quote from document (REQUIRED)
  - `year_confidence`: Confidence score 0.0-1.0 (REQUIRED)
  - `value`: Measured value as decimal/number (REQUIRED)
  - `value_quote`: Verbatim quote from document (REQUIRED) - preserve format
  - `value_confidence`: Confidence score 0.0-1.0 (REQUIRED)
  - `valueType`: Type/category of value (e.g., "actual", "target", "forecast", "baseline") (REQUIRED)
  - `notes`: Optional insights (e.g., data quality, seasonal notes)
- `notes`: Additional context and methodology (REQUIRED) - Extract any relevant information including: data source, calculation methodology, measurement frequency, or any other context. If no additional context is available, write "No additional details provided"

**Verified Field Rules**:

For indicator value fields (`year` and `value`):
- Each verified field requires THREE fields: the value, the `_quote`, and the `_confidence`
- The `_quote` must be verbatim text from the document
- The `_confidence` must be a number between 0.0 and 1.0
- Set confidence based on clarity of the measurement

**Example**:
```json
{
  "name": "Population",
  "unit": "people",
  "description": "Total resident population",
  "values": [
    {
      "year": "2019",
      "year_quote": "In 2019",
      "year_confidence": 0.95,
      "value": "572240",
      "value_quote": "572,240 main residents",
      "value_confidence": 0.95,
      "valueType": "actual"
    },
    {
      "year": "2023",
      "year_quote": "As at 31.12.2023",
      "year_confidence": 0.95,
      "value": "572240",
      "value_quote": "Dresden had 572,240 main residents",
      "value_confidence": 0.95,
      "valueType": "actual"
    },
    {
      "year": "2030",
      "year_quote": "by 2030",
      "year_confidence": 0.85,
      "value": "585000",
      "value_quote": "around 585,000 people would live in Dresden in 2030",
      "value_confidence": 0.85,
      "valueType": "forecast"
    }
  ],
  "notes": "Population data from official records and forecasts"
}
```

**Rules**:

- **ALWAYS provide `description` and `notes` fields for the indicator - they are REQUIRED**
- Group all measurements for a single indicator together
- Record indicator name and unit exactly as stated in document
- Extract each measurement as a separate object in the `values` array
- Skip measurements missing year OR value
- Keep all values exactly as stated in document
- Do NOT fill data gaps with estimates or interpolations
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
