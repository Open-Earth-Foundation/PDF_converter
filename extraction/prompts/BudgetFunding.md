Context: Budget funding sources and amounts allocated to climate actions in the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `budgetFundingId`: UUID identifier (auto-generated if missing)
- `budgetId`: Budget UUID reference (optional, auto-linked if context available)
- `fundingSourceId`: Funding source UUID reference (optional, auto-linked if context available)
- **VERIFIED FIELDS** (each requires three fields: value, _quote, _confidence):
  - `amount`: Funding amount as integer (REQUIRED)
  - `amount_quote`: Verbatim quote from document (REQUIRED) - preserve format as stated
  - `amount_confidence`: Confidence score 0.0-1.0 (REQUIRED)
- `currency`: Currency code (e.g., "EUR", "USD") (REQUIRED)
- `notes`: Catch-all field for any valuable insights (e.g., funding conditions, timeline, allocation rationale) - USE THIS FIELD for anything meaningful not covered by other fields

**Verified Field Rules**:

For verified field (`amount`):
- The verified field requires THREE fields in your output: the value, the `_quote`, and the `_confidence`
- The `_quote` must be verbatim text from the document (e.g., "5 million euros", "€3,500,000", "approximately 2 million")
- The `_confidence` must be a number between 0.0 and 1.0
- The `amount` value is the parsed numeric amount
- Set confidence based on clarity of the amount

**Example**:
```json
{
  "amount": "5000000",
  "amount_quote": "5 million euros",
  "amount_confidence": 0.95,
  "currency": "EUR"
}
```

**Rules**:

- Extract funding amounts exactly as stated in source (as verbatim quote)
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Keep currency codes as written in document
- Do NOT skip rows due to missing IDs
