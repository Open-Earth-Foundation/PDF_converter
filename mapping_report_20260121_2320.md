# Mapping Report (workflow_output, step3_llm)

## Run context
- Command: `python -m mapping.scripts.mapping --apply --delete-old`
- Input dir: `extraction/output`
- Work dir: `mapping/workflow_output`
- Output stage: `mapping/workflow_output/step3_llm`
- Canonical cityId: `c9b1d9f0-6a4b-4c2f-9d8e-1234567890ab`

## Stage notes
- Step 1 cleared existing FK fields; Step 2 enforced a single canonical cityId.
- Step 3 ran LLM mapping for FK choices (sector/indicator/budget/stakeholder/etc.).
- `IndicatorWithValues.json` exists in `mapping/workflow_output/step2_city` but is **not** present in `mapping/workflow_output/step3_llm` (dropped during LLM mapping output assembly).

## Table-by-table results (step3_llm)

### BudgetFunding
- Records: 81
- Missing FKs:
  - `budgetId`: 21 missing
  - `fundingSourceId`: 16 missing
- Notes: These are partially linked; the remainder will stay null unless a deterministic or manual pass is added.

### City
- Records: 1
- Issues: None (canonical cityId present, no duplicates).

### CityAnnualStats
- Records: 9
- Issues: None (all cityId values match canonical).

### CityBudget
- Records: 10
- Issues: None (all cityId values match canonical).

### CityTarget
- Records: 22
- Missing FKs:
  - `indicatorId`: 10 missing
- Required field missing:
  - `status`: 22 missing (required by schema)
- Notes: `status` is required by the DB schema but is absent in all mapped rows.

### ClimateCityContract
- Records: 0
- Issues: No data in mapping output (likely missing upstream).

### EmissionRecord
- Records: 33
- Missing FKs:
  - `sectorId`: 14 missing
- Notes: CityId is fully populated; sector mapping is partial.

### FundingSource
- Records: 17
- Issues: None.

### Indicator
- Records: 41
- Issues: None (cityId + sectorId populated; no missing required fields).

### IndicatorValue
- Records: 0
- Issues: Empty in mapping output (input was empty in `extraction/output`).

### Initiative
- Records: 94
- Issues: None (cityId populated; no missing required fields).

### InitiativeIndicator
- Records: 54
- Issues: None (both FKs present).

### InitiativeStakeholder
- Records: 79
- Missing FKs:
  - `initiativeId`: 15 missing
  - `stakeholderId`: 39 missing
- Notes: Roughly half of links are still unassigned.

### InitiativeTef
- Records: 0
- Issues: Empty (no TEF data).

### Sector
- Records: 22
- Issues: None.

### Stakeholder
- Records: 41
- Issues: None.

### TefCategory
- Records: 0
- Issues: Empty (no TEF taxonomy data).

## Cross-table integrity summary
- All `cityId` values match the canonical cityId; no mismatches.
- No dangling FKs (all non-null FK values point to existing IDs).
- Missing FK hotspots:
  - BudgetFunding: missing `budgetId` (21), `fundingSourceId` (16)
  - CityTarget: missing `indicatorId` (10)
  - EmissionRecord: missing `sectorId` (14)
  - InitiativeStakeholder: missing `initiativeId` (15), `stakeholderId` (39)
- `IndicatorWithValues.json` is dropped between step2 and step3.

## Semantic evidence check (markdown-based)
- Markdown source used: `output/pdf2markdown/20260120_190357_ccc_leipzig/combined_markdown.md`
- Evidence levels:
  - **Internal evidence**: linked label appears in the record's own text fields (`notes`, `description`, `misc`).
  - **Markdown-only**: linked label appears in the markdown, but not in the record text.
  - **No evidence**: linked label not found in markdown (likely mismatch or noisy label).

### Evidence summary by mapping
- BudgetFunding -> CityBudget (`budgetId`): 60 linked; internal evidence 4, markdown-only 42, no-evidence 14.
- BudgetFunding -> FundingSource (`fundingSourceId`): 65 linked; internal evidence 1, markdown-only 64.
- CityTarget -> Indicator (`indicatorId`): 12 linked; markdown-only 12.
- EmissionRecord -> Sector (`sectorId`): 19 linked; markdown-only 19.
- InitiativeStakeholder -> Initiative (`initiativeId`): 64 linked; markdown-only 64.
- InitiativeStakeholder -> Stakeholder (`stakeholderId`): 40 linked; internal evidence 31, markdown-only 8, no-evidence 1.
- InitiativeIndicator -> Initiative (`initiativeId`): 54 linked; internal evidence 43, markdown-only 11.
- InitiativeIndicator -> Indicator (`indicatorId`): 54 linked; internal evidence 25, markdown-only 29.
- IndicatorValue -> Indicator (`indicatorId`): no records in this run.

### No-evidence examples
- BudgetFunding -> CityBudget: "Photovoltaic systems on municipal roofs (costs listed for 2023)", "REFILL project - Study cost (Raffinerie Energie)".
- InitiativeStakeholder -> Stakeholder: "Verbraucherzentrale Sachsen e.V."

Notes:
- Most links are **markdown-only**, meaning the linked entity label exists in the document but is not echoed in the record fields. This makes semantic verification weak and suggests the mappings may be correct but are not self-evident from record text.
- Adding `misc.linkingSignals` at extraction time (or deterministic post-processing) would raise internal evidence rates and improve auditability.

## Recommendations
- Preserve pass-through files in step3 (e.g., `IndicatorWithValues.json`) so diagnostics are not lost.
- Address missing `status` in CityTarget (prompt or deterministic default) since it is schema-required.
- Add deterministic pre-mapping for:
  - EmissionRecord -> sectorId
  - CityTarget -> indicatorId
  - InitiativeStakeholder -> stakeholderId/initiativeId where exact name matches exist
