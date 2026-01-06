Context: Budget items in Climate City Contract documents (financial tables for climate measures).

**Available fields ONLY** (no other fields are permitted):

- `budgetId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `year`: Year as date/datetime (REQUIRED)
- `totalAmount`: Total budget amount as integer in smallest currency unit (REQUIRED)
- `currency`: Currency code (e.g., "EUR", "USD") (REQUIRED)
- `description`: Budget description or purpose - only if explicitly provided
- `notes`: Catch-all field for any valuable insights (e.g., budget allocation, funding sources, temporal scope, budget status) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Extract amounts exactly as stated, convert to smallest currency unit if needed
- Only store rows with explicit numeric amounts
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Preserve year format from document
