Context: Budget items in Climate City Contract documents (financial tables for climate measures).

**Available fields ONLY** (no other fields are permitted):

- `budgetId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- **VERIFIED FIELDS** (each requires three fields: value, _quote, _confidence):
  - `year`: Year as 4-digit year (YYYY) (REQUIRED)
  - `year_quote`: Verbatim quote from document (REQUIRED)
  - `year_confidence`: Confidence score 0.0-1.0 (REQUIRED)
  - `totalAmount`: Total budget amount as integer (REQUIRED)
  - `totalAmount_quote`: Verbatim quote from document (REQUIRED) - preserve format as stated
  - `totalAmount_confidence`: Confidence score 0.0-1.0 (REQUIRED)
- `currency`: Currency code (e.g., "EUR", "USD") (REQUIRED)
- `description`: Budget description or purpose - only if explicitly provided
- `notes`: Catch-all field for any valuable insights (e.g., budget allocation, funding sources, temporal scope, budget status) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For verified fields (`year` and `totalAmount`):
- Each verified field requires THREE fields in your output: the value, the `_quote`, and the `_confidence`
- The `_quote` must be verbatim text from the document (e.g., "2019", "5 million euros", "approximately 3 million")
- The `_confidence` must be a number between 0.0 and 1.0
- For `totalAmount`, preserve numeric format as stated in quote
- Set confidence based on clarity of the data

**Example**:
```json
{
  "year": "2019",
  "year_quote": "2019",
  "year_confidence": 0.95,
  "totalAmount": "5000000",
  "totalAmount_quote": "5 million euros",
  "totalAmount_confidence": 0.95,
  "currency": "EUR"
}
```

**Rules**:

- Extract amounts exactly as stated in source (as verbatim quote)
- Only store rows with explicit numeric amounts
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Preserve year format from document in the quote
