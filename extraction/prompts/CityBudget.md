Context: Budget items in Climate City Contract documents (financial tables for climate measures).

**Available fields ONLY** (no other fields are permitted):

- `budgetId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `year`: **VERIFIED FIELD** - Year as 4-digit year (YYYY) (REQUIRED). Output as `{"value": "2019", "quote": "2019", "confidence": 0.95}`
- `totalAmount`: **VERIFIED FIELD** - Total budget amount as integer (REQUIRED). Output as `{"value": "5000000", "quote": "5 million euros", "confidence": 0.95}`
- `currency`: Currency code (e.g., "EUR", "USD") (REQUIRED)
- `description`: Budget description or purpose - only if explicitly provided
- `notes`: Catch-all field for any valuable insights (e.g., budget allocation, funding sources, temporal scope, budget status) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For `year` and `totalAmount`:
- Each must be output as a VerifiedField object with `value`, `quote`, and `confidence` properties
- The `quote` must be verbatim text from the document (e.g., "2019", "5 million euros", "approximately 3 million")
- For `totalAmount`, preserve numeric format as stated (do NOT convert to smallest currency unit in quote - that's a parsing detail, the quote shows what was in source)
- Set confidence based on clarity of the data

**Rules**:

- Extract amounts exactly as stated in source (as verbatim quote)
- Only store rows with explicit numeric amounts
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Preserve year format from document in the quote
