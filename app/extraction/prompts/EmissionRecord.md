Context: GHG inventory rows in Climate City Contract documents (tables listing emissions by year, sector, scope, or gas).

- Map each table row to a record: year, sector_id, scope, ghg_type, value, unit, and notes when present.
- Only record entries that explicitly list numeric emission values; if IDs are missing, leave them blank (placeholders will be assigned).
- Preserve units as written (e.g., tCO2e); do not normalize or convert.
- Capture any additional useful information not covered by other fields in the `misc` field as a JSON object.
