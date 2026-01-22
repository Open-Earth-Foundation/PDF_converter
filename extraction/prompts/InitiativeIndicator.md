Context: Indicator contributions tied to specific initiatives in the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `initiativeIndicatorId`: UUID identifier (auto-generated if missing)
- `initiativeId`: Initiative UUID reference (optional, auto-linked if context available)
- `indicatorId`: Indicator UUID reference (optional, auto-linked if context available)
- `contributionType`: Type of contribution (e.g., "direct", "indirect", "co-benefit", "monitoring") (REQUIRED)
- `expectedChange`: Expected change in indicator value as numeric string (OPTIONAL) - extract only if explicitly stated (e.g., "80", "23059", "400"). Include only the numeric value without units or currency symbols
- `notes`: Additional context and details (REQUIRED) - Extract any relevant information about the contribution including: assumptions, calculation methodology, risk factors, dependencies, measurement approach, or any quotes/context from the document. If no additional context is available, write "No additional details provided"

**Rules**:

- Only extract rows with a clear initiative-indicator link
- **ALWAYS provide `notes` field - it is REQUIRED**
- For `expectedChange`: extract numeric values only when explicitly quantified in the document
- Extract just the number for expectedChange (e.g., "80" not "80 tonnes/year")
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Skip entries lacking both a clear link AND numeric data
