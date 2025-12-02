Context: Indicator contributions tied to specific initiatives in the Climate City Contract.

**Available fields ONLY** (no other fields are permitted):

- `initiativeIndicatorId`: UUID identifier (auto-generated if missing)
- `initiativeId`: Initiative UUID reference (optional, auto-linked if context available)
- `indicatorId`: Indicator UUID reference (optional, auto-linked if context available)
- `contributionType`: Type of contribution (e.g., "direct", "indirect", "co-benefit", "monitoring") (REQUIRED)
- `expectedChange`: Expected change in indicator value as decimal/number - only if explicitly stated
- `notes`: Catch-all field for any valuable insights (e.g., contribution assumptions, risk factors, dependencies, measurement methodology) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Only extract rows with a clear initiative-indicator link
- Include numeric change values only when explicitly quantified
- Leave ID fields blank if not explicitly present (placeholders will be assigned)
- Skip entries lacking both a clear link AND numeric data
