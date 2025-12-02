Context: Climate City Contract (CCC) documents describing city-level climate action plans and their contractual metadata.

**Available fields ONLY** (no other fields are permitted):

- `climateCityContractId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked based on city name in document)
- `contractDate`: Contract date/signing date as datetime (REQUIRED)
- `title`: Contract title (REQUIRED) - exactly as written
- `version`: Document version (e.g., "1.0", "v2", "final") - only if explicitly stated
- `language`: Document language (e.g., "English", "German") - only if stated
- `documentUrl`: Official document URL - only if provided
- `notes`: Catch-all field for any valuable insights (e.g., participating entities, scope of contract, key objectives, validity period) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Extract contract-level metadata (date, title, version, language, URL) exactly as written
- Use city name to auto-link cityId if present; do NOT invent IDs
- Leave fields blank if not explicitly present (placeholders will be assigned)
- Do NOT invent contract dates or titles
