Context: Sectors used for GHG accounting (BISKO) or action portfolio grouping within Climate City Contracts.

**Available fields ONLY** (no other fields are permitted):

- `sectorId`: UUID identifier (auto-generated if missing)
- `sectorName`: Sector name (REQUIRED) - exactly as written (e.g., "Energy", "Buildings", "Mobility", "Industry", "AFOLU")
- `description`: Sector description - only if explicitly present in document
- `notes`: Catch-all field for any valuable insights or additional data about the sector (e.g., emission sources, key stakeholders, policy drivers, targets) - USE THIS FIELD for anything meaningful not covered by other fields
- `misc`: Any extra relevant data as a JSON object - optional

**Rules**:

- Extract ONLY fields that appear in the document
- Keep sector names exactly as written; do not normalize or invent variations
- Capture standard BISKO sectors or domain-specific classifications as mentioned
- Put additional info in `notes` or `misc`, NOT as extra fields
