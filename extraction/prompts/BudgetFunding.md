Context: Budget funding sources and amounts allocated to climate actions in the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `budgetFundingId`: UUID identifier (auto-generated if missing)
- `budgetId`: Budget UUID reference (optional, auto-linked if context available)
- `fundingSourceId`: Funding source UUID reference (optional, auto-linked if context available)
- `amount`: **VERIFIED FIELD** - Funding amount as integer (REQUIRED). Output as `{"value": "5000000", "quote": "5 million euros", "confidence": 0.95}`
- `currency`: Currency code (e.g., "EUR", "USD") (REQUIRED)
- `notes`: Catch-all field for any valuable insights (e.g., funding conditions, timeline, allocation rationale) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For `amount`:
- Must be output as a VerifiedField object with `value`, `quote`, and `confidence` properties
- The `quote` must be verbatim text from the document (e.g., "5 million euros", "€3,500,000", "approximately 2 million")
- The `value` is the parsed numeric amount (exact parsing is internal; the quote shows the source)
- Set confidence based on clarity of the amount

**Rules**:

- Extract funding amounts exactly as stated in source (as verbatim quote)
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Keep currency codes as written in document
- Do NOT skip rows due to missing IDs
