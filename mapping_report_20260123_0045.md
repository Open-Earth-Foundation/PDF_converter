# Mapping Report - 2026-01-23 00:45

## Context
- Work dir: mapping/workflow_output
- Step1: mapping\workflow_output\step1_cleared
- Step2: mapping\workflow_output\step2_city
- Step3: mapping\workflow_output\step3_llm
- Canonical cityId: c9b1d9f0-6a4b-4c2f-9d8e-1234567890ab
- Markdown source (semantic check): output/pdf2markdown/20260120_190357_ccc_leipzig/combined_markdown.md

## File presence
- Step2 files: 14
- Step3 files: 17
- Missing in step3: IndicatorWithValues.json
- Extra in step3: ClimateCityContract.json, IndicatorValue.json, InitiativeTef.json, TefCategory.json

## Table-by-table checks
### BudgetFunding
- Records: 81
- Missing FKs: budgetId: 22, fundingSourceId: 15
- Missing required fields: none

### City
- Records: 1
- Missing required fields: none

### CityAnnualStats
- Records: 9
- Missing FKs: none
- Missing required fields: none
- cityId mismatch vs canonical: 0

### CityBudget
- Records: 10
- Missing FKs: none
- Missing required fields: none
- cityId mismatch vs canonical: 0

### CityTarget
- Records: 22
- Missing FKs: indicatorId: 11
- Missing required fields: status: 22
- cityId mismatch vs canonical: 0

### ClimateCityContract
- Records: 0
- Missing required fields: none
- cityId mismatch vs canonical: 0

### EmissionRecord
- Records: 33
- Missing FKs: sectorId: 14
- Missing required fields: none
- cityId mismatch vs canonical: 0

### FundingSource
- Records: 17
- Missing required fields: description: 15, notes: 16

### Indicator
- Records: 41
- Missing FKs: none
- Missing required fields: none
- cityId mismatch vs canonical: 0

### IndicatorValue
- Records: 0
- Missing FKs: none
- Missing required fields: none

### Initiative
- Records: 94
- Missing FKs: none
- Missing required fields: description: 47
- cityId mismatch vs canonical: 0

### InitiativeIndicator
- Records: 54
- Missing FKs: none
- Missing required fields: none

### InitiativeStakeholder
- Records: 79
- Missing FKs: initiativeId: 9, stakeholderId: 39
- Missing required fields: none

### InitiativeTef
- Records: 0
- Missing FKs: none
- Missing required fields: none

### Sector
- Records: 22
- Missing required fields: none

### Stakeholder
- Records: 41
- Missing required fields: description: 41

### TefCategory
- Records: 0
- Missing FKs: none
- Missing required fields: none

## Key issues
- Pass-through file(s) missing in step3: IndicatorWithValues.json
- CityTarget.status missing in 22 record(s).
- IndicatorValue has 0 records in step3.
- EmissionRecord: missing sectorId in 14 record(s).
- BudgetFunding: missing budgetId in 22 record(s).
- InitiativeStakeholder: missing initiativeId in 9 record(s).
- CityTarget: missing indicatorId in 11 record(s).

## Semantic evidence check (markdown-based)
- Evidence levels: internal (label appears in record text), markdown-only (label only in markdown), no-evidence (label not found in markdown).

- BudgetFunding -> CityBudget (budgetId): linked 59; internal 4, markdown-only 41, no-evidence 14, missing-target 0, missing-label 0
- BudgetFunding -> FundingSource (fundingSourceId): linked 66; internal 1, markdown-only 65, no-evidence 0, missing-target 0, missing-label 0
- CityTarget -> Indicator (indicatorId): linked 11; internal 0, markdown-only 11, no-evidence 0, missing-target 0, missing-label 0
- EmissionRecord -> Sector (sectorId): linked 19; internal 0, markdown-only 19, no-evidence 0, missing-target 0, missing-label 0
- InitiativeStakeholder -> Initiative (initiativeId): linked 70; internal 0, markdown-only 70, no-evidence 0, missing-target 0, missing-label 0
- InitiativeStakeholder -> Stakeholder (stakeholderId): linked 40; internal 31, markdown-only 8, no-evidence 1, missing-target 0, missing-label 0
- InitiativeIndicator -> Initiative (initiativeId): linked 54; internal 43, markdown-only 11, no-evidence 0, missing-target 0, missing-label 0
- InitiativeIndicator -> Indicator (indicatorId): linked 54; internal 25, markdown-only 29, no-evidence 0, missing-target 0, missing-label 0
- IndicatorValue -> Indicator (indicatorId): no linked records.
- Indicator -> Sector (sectorId): linked 41; internal 8, markdown-only 33, no-evidence 0, missing-target 0, missing-label 0

## Recommendations
- Preserve all step2 JSON files into step3 before overwriting mapped tables (prevents loss of IndicatorWithValues).
- Address missing CityTarget.status deterministically or via post-processing before insert (schema requires it).
- Consider deterministic indicatorId mapping for CityTarget when description matches indicator names to reduce LLM nulls.
