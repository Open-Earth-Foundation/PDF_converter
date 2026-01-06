Context: GHG inventory rows in Climate City Contract documents (tables listing emissions by year, sector, scope, or gas).

**Available fields ONLY** (no other fields are permitted):

- `emissionRecordId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `year`: Year as date (REQUIRED)
- `sectorId`: Sector UUID reference (optional, auto-linked if context available)
- `scope`: Emission scope/boundary (e.g., "Scope 1", "Scope 2", "Scope 3") (REQUIRED)
- `ghgType`: Greenhouse gas type (e.g., "CO2", "CH4", "N2O", "CO2e") (REQUIRED)
- `value`: Emission value as integer (REQUIRED) - only for entries with explicit numeric values
- `unit`: Unit of measurement (e.g., "tCO2e", "kg CO2", "tonnes") (REQUIRED) - preserve as written
- `notes`: Catch-all field for any valuable insights (e.g., calculation methodology, data quality, verification status, uncertainty ranges) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Only record entries with explicit numeric emission values
- Preserve units exactly as written (do NOT normalize or convert)
- Leave ID fields blank if not present (placeholders will be assigned)
- Map each table row as a separate record
