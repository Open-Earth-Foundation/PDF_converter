Context: Funding sources listed in Climate City Contract documents (e.g., EU programs, municipal funds, private investors).

**Available fields ONLY** (no other fields are permitted):

- `fundingSourceId`: UUID identifier (auto-generated if missing)
- `name`: Funding source name (REQUIRED) - exactly as written in document
- `type`: Funding source type (e.g., "EU grant", "municipal budget", "private investment", "green bond") - only if explicitly stated
- `description`: Description of the funding source - only if provided
- `notes`: Catch-all field for any valuable insights (e.g., eligibility criteria, application deadlines, past performance, availability) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Record the exact name and type as written in document
- Skip entries that do not clearly specify a funding source
- Do NOT invent funding types or descriptions
- Leave optional fields null if not present
