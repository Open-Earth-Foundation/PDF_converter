# Pipeline Report: ccc_leipzig.pdf (OCR only)

## Run context
- Command: `python -m run_pipeline --input documents/ccc_leipzig.pdf --no-vision`
- OCR output: `output/pdf2markdown/20260120_190357_ccc_leipzig/combined_markdown.md` (268 pages)
- Extraction model: `xiaomi/mimo-v2-flash:free` via OpenRouter (token count: 114,785; max rounds: 12)
- Outputs:
  - `output/extraction`
  - `output/mapping/step3_llm`

## Log-derived issues
- Repeated 404 responses for tool use on OpenRouter; the pipeline fell back to `tool_choice="auto"` for many classes.
- City extraction initially failed validation for `areaKm2` value "almost 300 km^2"; later accepted 2 records.
- FundingSource extraction:
  - Round 1: all 7 items missing `fundingSourceId`.
  - Round 2: 5 items had `type` = null.
- CityTarget extraction reported a duplicate item; one duplicate was skipped.
- BudgetFunding completed with 0 records.

## Table-by-table findings

### BudgetFunding
- Extraction: 0 records (`output/extraction/BudgetFunding.json`)
- Mapping: 0 records (`output/mapping/step3_llm/BudgetFunding.json`)
- Issues:
  - No budget-to-funding links despite 5 budgets and 7 funding sources. Likely blocked by missing `budgetId` values in budgets and/or missing linkage extraction.

### City
- Extraction: 2 records (`output/extraction/City.json`) for the same city (Leipzig, Germany).
- Mapping: 1 record (`output/mapping/step3_llm/City.json`)
- Issues:
  - Duplicate city records in extraction (same name/country, different IDs).
  - Mapping kept the placeholder zero UUID (`00000000-0000-0000-0000-000000000000`) as the canonical cityId.
  - `misc` contains OCR/encoding artifacts and inconsistent keys; treat `misc` as noisy.

### CityAnnualStats
- Extraction: 2 records (`output/extraction/CityAnnualStats.json`)
- Mapping: 2 records (`output/mapping/step3_llm/CityAnnualStats.json`)
- Issues:
  - Extraction used two different `cityId` values; mapping normalized them to the zero UUID.
  - `gdpPerCapita` missing for all records.
  - `populationDensity` stored as string; normalize to numeric before DB insert.

### CityBudget
- Extraction: 5 records (`output/extraction/CityBudget.json`)
- Mapping: 5 records (`output/mapping/step3_llm/CityBudget.json`)
- Issues:
  - `budgetId` missing for all records (no stable PK for linking).
  - `cityId` missing in extraction; mapping added zero UUID.
  - `year` stored as int; DB expects datetime (normalize to date/datetime).
  - Some `year_proof` quotes omit the year, and one `totalAmount` quote includes OCR artifacts (non-ASCII symbols).

### CityTarget
- Extraction: 27 records (`output/extraction/CityTarget.json`)
- Mapping: 27 records (`output/mapping/step3_llm/CityTarget.json`)
- Issues:
  - `cityId` and `indicatorId` missing for all records in extraction; mapping adds `cityId` but `indicatorId` remains null for all 27 records.
  - Duplicate descriptions detected (4 duplicated descriptions).
  - `baselineYear` missing for 2 records; `baselineValue` missing for 3 records.
  - `targetYear`/`baselineYear` are ints and `targetValue`/`baselineValue` are strings (DB expects date/decimal).

### ClimateCityContract
- Extraction: 1 record (`output/extraction/ClimateCityContract.json`)
- Mapping: 1 record (`output/mapping/step3_llm/ClimateCityContract.json`)
- Issues:
  - `cityId` normalized to the zero UUID during mapping.
  - `contractDate` stored as ISO string; parse to datetime before DB insert.

### EmissionRecord
- Extraction: 44 records (`output/extraction/EmissionRecord.json`)
- Mapping: 44 records (`output/mapping/step3_llm/EmissionRecord.json`)
- Issues:
  - `emissionRecordId` missing for all records (no stable PK).
  - `cityId` and `sectorId` missing in extraction; mapping filled both.
  - `year` stored as int; DB expects date (normalize).

### FundingSource
- Extraction: 7 records (`output/extraction/FundingSource.json`)
- Mapping: 7 records (`output/mapping/step3_llm/FundingSource.json`)
- Issues:
  - `type` empty for 5 of 7 records (from log validation failures).
  - IDs are placeholder zero-prefixed UUIDs (00000000-...-00000000000X).

### Indicator
- Extraction: 0 records (`output/extraction/Indicator.json`)
- Mapping: 0 records (`output/mapping/step3_llm/Indicator.json`)
- Issues:
  - No indicators extracted, which blocks CityTarget `indicatorId` mapping and IndicatorValue linkage.

### IndicatorWithValues
- Extraction: 0 records (`output/extraction/IndicatorWithValues.json`)
- Issues:
  - Combined Indicator + IndicatorValue extraction returned nothing; suggests no indicator tables recognized or model missed them.

### IndicatorValue
- Mapping: 0 records (`output/mapping/step3_llm/IndicatorValue.json`)
- Issues:
  - No indicator values present, consistent with missing indicators.

### Initiative
- Extraction: 45 records (`output/extraction/Initiative.json`)
- Mapping: 45 records (`output/mapping/step3_llm/Initiative.json`)
- Issues:
  - `initiativeId` missing for all records (no stable PK).
  - `cityId` missing in extraction; mapping added zero UUID.
  - All 45 records are missing `startYear`, `endYear`, `totalEstimatedCost`, and `status`; only title/description/currency populated.
  - Missing IDs and sparse fields block relationship tables.

### InitiativeIndicator
- Extraction: 0 records (`output/extraction/InitiativeIndicator.json`)
- Mapping: 0 records (`output/mapping/step3_llm/InitiativeIndicator.json`)
- Issues:
  - No initiative-to-indicator links extracted.

### InitiativeStakeholder
- Extraction: 0 records (`output/extraction/InitiativeStakeholder.json`)
- Mapping: 0 records (`output/mapping/step3_llm/InitiativeStakeholder.json`)
- Issues:
  - No initiative-to-stakeholder links extracted.

### InitiativeTef
- Extraction: 0 records (`output/extraction/InitiativeTef.json`)
- Mapping: 0 records (`output/mapping/step3_llm/InitiativeTef.json`)
- Issues:
  - No initiative-to-TEF links extracted; TEF categories absent.

### Sector
- Extraction: 5 records (`output/extraction/Sector.json`)
- Mapping: 5 records (`output/mapping/step3_llm/Sector.json`)
- Issues:
  - `description` missing for all sectors (optional but reduces usefulness).

### Stakeholder
- Extraction: 62 records (`output/extraction/Stakeholder.json`)
- Mapping: 62 records (`output/mapping/step3_llm/Stakeholder.json`)
- Issues:
  - ID collisions: 30 duplicate `stakeholderId` values, reused for different stakeholders (data integrity issue).
  - This breaks uniqueness and will block any future InitiativeStakeholder links.

### TefCategory
- Extraction: 0 records (`output/extraction/TefCategory.json`)
- Mapping: 0 records (`output/mapping/step3_llm/TefCategory.json`)
- Issues:
  - No TEF categories extracted; InitiativeTef cannot be populated.

## Cross-table integrity summary (mapping outputs)
- CityTarget: `indicatorId` missing for all 27 records.
- All city-linked tables point to the placeholder cityId (`00000000-0000-0000-0000-000000000000`).
- Relationship tables are empty (BudgetFunding, InitiativeIndicator, InitiativeStakeholder, InitiativeTef, IndicatorValue).

## Recommendations
- Use a model/provider that supports tool use natively to avoid repeated 404 fallbacks.
- Enforce ID generation on the app side for records missing IDs (especially Initiative, CityBudget, EmissionRecord, CityTarget).
- Override or ignore LLM-provided stakeholder IDs; generate unique IDs per record.
- Improve indicator extraction (prompt tuning or targeted pass) so CityTarget can map to Indicator.
- Add post-processing to normalize year/date fields and numeric strings before DB load.
