Context: Indicators defined in the Climate City Contract for monitoring, evaluation, or learning.

**Available fields ONLY** (no other fields are permitted):

- `indicatorId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `sectorId`: Sector UUID reference (optional, auto-linked if context available)
- `name`: Indicator name (REQUIRED) - exactly as written
- `description`: Indicator description or definition (REQUIRED) - extract what the indicator measures, its purpose, or any descriptive text. If no explicit description exists, infer from the name and context (e.g., for "CO2 emissions" write "Total carbon dioxide emissions from city activities")
- `unit`: Measurement unit (e.g., "%", "tonnes", "MWh") (REQUIRED) - exactly as written
- `notes`: Additional context and methodology (REQUIRED) - Extract any relevant information including: data source, calculation methodology, measurement frequency, baseline values, associated targets, or any other context. If no additional context is available, write "No additional details provided"

**Rules**:

- **ALWAYS provide `description` and `notes` fields - they are REQUIRED**
- Record indicator name and unit exactly as stated in document
- Do NOT invent indicator IDs or units
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Preserve units exactly as written
