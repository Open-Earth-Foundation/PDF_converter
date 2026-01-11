# Mapping Plan (step-by-step)

Each section shows one extraction and join path for every model in `database/schemas.py`. Use these as discrete prompts/steps rather than a single big graph. City is fixed for a run - map it automatically as the first step before other mappings and reuse that city for every `cityId` link.

## 1) City anchors
City fixed per run; resolve city once, then attach CCC and CAS to that city.
```mermaid
flowchart TD
    CitySrc[Extract city attributes] --> City[City]
    City --> CCC[ClimateCityContract<br/>FK: cityId]
    City --> CAS[CityAnnualStats<br/>FK: cityId]
```

## 2) Sector taxonomy
```mermaid
flowchart TD
    SectorSrc[Extract or lookup sector] --> Sector[Sector]
```

## 3) Emissions time series
City fixed per run; reuse the pre-mapped city when linking emission records.
```mermaid
flowchart TD
    EmSrc[Extract emissions record] --> ER[EmissionRecord]
    ER -->|cityId| City[City]
    ER -->|sectorId| Sector[Sector]
```

## 4) Budgets and funding
City fixed per run; link each city budget to the pre-mapped city.
```mermaid
flowchart TD
    BudgetSrc[Extract city budget] --> CB[CityBudget]
    CB -->|cityId| City[City]
    CB --> CBF[CityBudgetFunding]
    CBF -->|budgetId| CB
    CBF -->|fundingSourceId| FS[FundingSource]
```

## 5) Initiative core
City fixed per run; map city first, then link initiatives to that city.
```mermaid
flowchart TD
    InitSrc[Extract initiative record<br/>Context bundle: city fixed per run] --> I[Initiative]
    I -->|cityId| City[City]
```

## 6) Initiative -> Stakeholder
```mermaid
flowchart TD
    I[Initiative<br/>Context: title/description/status/years] --> StakeLLM[LLM: derive stakeholders and roles]
    StakeLLM --> ST[Stakeholder]
    ST --> IS[InitiativeStakeholder]
    IS -->|initiativeId| I
    IS -->|stakeholderId| ST
```

## 7) Initiative -> Indicator (cityId fixed per run)
City fixed per run; reuse the pre-mapped city when linking indicators (and downstream values/targets).
```mermaid
flowchart TD
    I[Initiative<br/>Context: title/description/status/years/cityId] --> IndLLM[LLM: derive indicators, contributionType, expectedChange]
    IndLLM --> IND[Indicator]
    IND -->|cityId fixed per run| City[City]
    IND -->|sectorId optional| Sector[Sector]
    IND --> II[InitiativeIndicator]
    II -->|initiativeId| I
    II -->|indicatorId| IND
```

## 8) Indicator -> IndicatorValue / CityTarget (after Initiative->Indicator mapping)
City fixed per run; CityTarget uses the pre-mapped city.
Assumption: Indicator already exists and is linked to Initiative. Always pass the initiative context (title/description/status/years/expected change) when asking for values/targets so lineage is preserved.
```mermaid
flowchart TD
    I[Initiative<br/>Context: title/description/status/years/expected change] --> II[InitiativeIndicator]
    II --> IND[Indicator]
    IND -->|cityId fixed per run| City[City]
    IND -->|sectorId optional| Sector[Sector]
    IND --> LVal[LLM: derive indicator values & targets<br/>Context bundle: initiative + indicator]
    LVal --> IV[IndicatorValue]
    LVal --> CT[CityTarget]
    CT -->|cityId| City
```

## 9) Initiative -> TEF taxonomy
```mermaid
flowchart TD
    I[Initiative<br/>Context: title/description/status/years] --> TefLLM[LLM: map to TEF codes]
    TefLLM --> Tef[TefCategory]
    Tef --> IT[InitiativeTef]
    IT -->|initiativeId| I
    IT -->|tefId| Tef
```
