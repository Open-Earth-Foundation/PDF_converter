Context: Annual demographic and economic statistics for the city found in the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `statId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `year`: Year as integer (REQUIRED)
- `population`: Population count as integer - only if explicitly stated
- `populationDensity`: Population density as decimal/number - only if explicitly stated
- `gdpPerCapita`: GDP per capita as decimal/number - only if explicitly stated
- `notes`: Catch-all field for any valuable insights (e.g., data source, methodology, trends, qualifications) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Do NOT invent numeric values; only extract what is explicitly stated
- Keep numbers exactly as provided in the document
- Leave optional fields null if not present
- Include measurement units or qualifications in `notes` if relevant
