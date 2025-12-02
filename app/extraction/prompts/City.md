Context: City-level metadata referenced in Climate City Contract documents.

**Available fields ONLY** (no other fields are permitted):

- `cityId`: UUID identifier (auto-generated if missing)
- `cityName`: City name (REQUIRED) - exactly as written
- `country`: Country name (REQUIRED) - exactly as written
- `locode`: UN/LOCODE identifier - ONLY if explicitly stated in document
- `areaKm2`: Area in km² - can be number or string (e.g., "almost 300 km²") - ONLY if explicitly stated
- `notes`: Catch-all field for any valuable insights, context, or additional data not covered by other fields (e.g., city rank, population trends, climate goals) - USE THIS FIELD for anything meaningful that doesn't fit elsewhere
- `misc`: Any extra relevant data (population, density, etc.) as a JSON object - optional

**Rules**:

- Extract ONLY fields that are explicitly present in the document
- Do NOT fabricate UUIDs or invent numerical values
- Keep city name and country exactly as written
- If area is stated as "almost 300 km²" or similar, keep the phrasing
- Capture population, density, or other metadata in `misc`, not as extra fields
