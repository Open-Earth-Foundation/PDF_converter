Context: Indicators defined in the Climate City Contract for monitoring, evaluation, or learning.

**Available fields ONLY** (no other fields are permitted):

- `indicatorId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `sectorId`: Sector UUID reference (optional, auto-linked if context available)
- `name`: Indicator name (REQUIRED) - exactly as written
- `description`: Indicator description or definition - only if explicitly provided
- `unit`: Measurement unit (e.g., "%", "tonnes", "MWh") (REQUIRED) - exactly as written
- `notes`: Catch-all field for any valuable insights (e.g., data source, calculation methodology, frequency, baseline, targets linked to this indicator) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Record indicator name and unit exactly as stated in document
- Do NOT invent indicator IDs or units
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Preserve units exactly as written
