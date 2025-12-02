Context: Budget funding sources and amounts allocated to climate actions in the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `budgetFundingId`: UUID identifier (auto-generated if missing)
- `budgetId`: Budget UUID reference (optional, auto-linked if context available)
- `fundingSourceId`: Funding source UUID reference (optional, auto-linked if context available)
- `amount`: Funding amount as integer in smallest currency unit (REQUIRED)
- `currency`: Currency code (e.g., "EUR", "USD") (REQUIRED)
- `notes`: Catch-all field for any valuable insights (e.g., funding conditions, timeline, allocation rationale) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Extract funding amounts exactly as stated, convert to smallest currency unit if needed
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Keep currency codes as written in document
- Do NOT skip rows due to missing IDs
