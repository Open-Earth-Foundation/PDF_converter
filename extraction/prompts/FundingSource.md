Context: Funding sources listed in Climate City Contract documents (e.g., EU programs, municipal funds, private investors).

**Available fields ONLY** (no other fields are permitted):

- `fundingSourceId`: UUID identifier (auto-generated if missing)
- `name`: Funding source name (REQUIRED) - exactly as written in document
- `type`: Funding source type (e.g., "EU grant", "municipal budget", "private investment", "green bond") - only if explicitly stated
- `description`: Description of the funding source (REQUIRED) - extract purpose, scope, or any descriptive text about the funding source. If no explicit description exists, infer from context (e.g., for "EU Horizon 2020" write "European Union research and innovation funding program")
- `notes`: Additional context and details (REQUIRED) - Extract any valuable information including: eligibility criteria, application deadlines, funding amounts, past performance, availability, or any other relevant context. If no additional context is available, write "No additional details provided"

**Rules**:

- **ALWAYS provide `description` and `notes` fields - they are REQUIRED**
- Record the exact name and type as written in document
- Skip entries that do not clearly specify a funding source
- Do NOT invent funding types unless you can reasonably infer them from context
- Provide meaningful descriptions and notes for all funding sources
