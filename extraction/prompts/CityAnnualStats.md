Context: Annual demographic and economic statistics for the city found in the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `statId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `year`: Year as integer (REQUIRED - CRITICAL: Every record MUST have a year)
- `population`: Population count as integer - only if explicitly stated
- `populationDensity`: Population density as decimal/number - only if explicitly stated
- `gdpPerCapita`: GDP per capita as decimal/number - only if explicitly stated
- `notes`: Catch-all field for any valuable insights (e.g., data source, methodology, trends, qualifications) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Do NOT invent numeric values; only extract what is explicitly stated
- Keep numbers exactly as provided in the document
- Leave optional fields null if not present
- Include measurement units or qualifications in `notes` if relevant

**YEAR EXTRACTION - CRITICAL INSTRUCTIONS**:

The year field is MANDATORY for every CityAnnualStats record. Extract years from:

1. **Date references**: "As at 31.12.2023" → extract year 2023
2. **Explicit mentions**: "base year 2019", "in 2023", "2022 data" → extract the 4-digit year
3. **Baseline references**: If document states "base year 2019" for statistics without explicit years, use 2019
4. **Census/Survey years**: Population data is typically from a specific year - extract that year
5. **Multiple data points**: If a paragraph contains statistics from different years, create SEPARATE records for each year

**Examples**:

- "As at 31.12.2023, the city had 628,718 residents" → year: 2023, population: 628718
- "The 2019 baseline GHG emissions were..." → year: 2019
- "Population forecast for 2030: 639,000" → year: 2030
- If you find "2023 data: 628,718 residents" and "2019 baseline: 3.1M tonnes CO2", create TWO records (one for 2023, one for 2019)
