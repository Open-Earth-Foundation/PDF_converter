Context: Targets defined in the Climate City Contract (e.g., emission reductions, renewable share, energy savings).

**Available fields ONLY** (no other fields are permitted):

- `cityTargetId`: UUID identifier (auto-generated if missing)
- `cityId`: City UUID reference (optional, auto-linked if context available)
- `indicatorId`: Indicator UUID reference (optional, auto-linked if context available)
- `description`: Target description (REQUIRED)
- `targetYear`: Target year as date (REQUIRED)
- `targetValue`: Target value as decimal/number (REQUIRED)
- `baselineYear`: Baseline year as date - only if explicitly stated
- `baselineValue`: Baseline value as decimal/number - only if explicitly stated
- `status`: Target status (e.g., "on track", "at risk", "achieved") - only if explicitly stated
- `notes`: Catch-all field for any valuable insights (e.g., measurement methodology, assumptions, risk factors, policy drivers) - USE THIS FIELD for anything meaningful not covered by other fields

**Rules**:

- Skip entries missing both year AND value
- Keep numeric values and dates exactly as stated in document
- Leave ID fields blank if not present (placeholders will be assigned)
