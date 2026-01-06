## Link to the data model

https://dbdiagram.io/d/NZCs-Data-Model-69160b2e6735e11170b30725

## Explanation of the data model

### 1. Big picture

At the center of the schema is the City.
Almost everything is either:

- describing the city itself
- tracking its emissions and indicators
- tracking its budgets and funding
- describing its initiatives and who is involved.

The following provides an overview of the individual tables.

### 2. Core tables

#### 2.1 City

Table: City

Represents a real world city.

Key fields:

- cityId - unique identifier
- cityName, country
- areaKm2, population, populationYear, populationDensity
- notes

Main idea:
Everything else is anchored to a City. A city can have contracts, budgets, emissions, indicators, targets and initiatives.

#### 2.2 Climate City Contract

Table: ClimateCityContract

Represents a climate contract document for a city.

Key fields:

- climateCityContractId
- cityId - references City.cityId, unique and not null
- contractDate, title, version, language
- documentUrl
- notes

Relationship to City:

- Each ClimateCityContract belongs to exactly one City.
- Because cityId is unique in this table, each City can have at most one ClimateCityContract.

Cardinality:

- "A City can have zero or one climate city contract."
- "A ClimateCityContract must always be attached to exactly one City."

#### 2.3 Sector

Table: Sector

Represents a sector taxonomy (for GPC sectors, CCC sectors etc.).

Key fields:

- sectorId
- sectorName
- description
- notes

How it is used:

- Emission time series are recorded per City and Sector.
- Indicators can optionally be linked to a Sector.
- A Sector is a reusable label that can be shared across many records.

### 3. Emissions time series

#### 3.1 EmissionRecord

Table: EmissionRecord

Represents a time series of GHG emissions for a city.

Key fields:

- emissionRecordId
- cityId - references City.cityId
- year - which year the record belongs to
- sectorId - references Sector.sectorId
- scope - emissions scope (e.g. Scope 1, 2, 3)
- ghgType - e.g. "CO2", "CH4", "CO2e"
- value - emission amount
- unit
- notes

Relationships:

- A City can have many EmissionRecords.
- A Sector can have many EmissionRecords.
- Each EmissionRecord belongs to exactly one City and one Sector.

Interpretation:
"In year X, City Y emitted Z units of GHG type T in Sector S, for scope N."

### 4. Budgets and funding

#### 4.1 Budget

Table: Budget

Represents a city budget for a given year (overall or climate related).

Key fields:

- budgetId
- cityId - references City.cityId
- year
- totalAmount
- currency
- description
- notes

Relationships:

- A City can have many Budgets (for different years or purposes).
- Each Budget belongs to exactly one City.

#### 4.2 FundingSource

Table: FundingSource

Represents where money comes from.

Key fields:

- fundingSourceId
- name - e.g. "EU Green Fund", "National Program X"
- type - e.g. EU, national, private
- description
- notes

A FundingSource exists independently of a specific city or budget.

#### 4.3 BudgetFunding

Table: BudgetFunding

Defines how a Budget is financed by different funding sources.

Key fields:

- budgetFundingId
- budgetId - references Budget.budgetId
- fundingSourceId - references FundingSource.fundingSourceId
- amount
- currency
- notes

Relationships:

- One Budget can be financed by many FundingSources.
- One FundingSource can fund many Budgets.
- BudgetFunding is the many to many link table between Budgets and FundingSources.

Summary:

- "A Budget has one City."
- "A Budget can be funded by several FundingSources."
- "A FundingSource can contribute to several Budgets."
- "BudgetFunding tells us which FundingSource gave how much money to which Budget."

### 5. Initiatives and stakeholders

#### 5.1 Initiative

Table: Initiative

Represents a concrete program, project or action carried out by a city.

Key fields:

- initiativeId
- cityId - references City.cityId
- title, description
- startYear, endYear
- budget, currency
- expectedEmissionReduction, unit
- status - e.g. planned, ongoing, completed
- notes

Relationships:

- A City can have many Initiatives.
- Each Initiative belongs to exactly one City.

Example:
"City X runs Initiative Y from year A to B with budget C, aiming to reduce D units of emissions."

#### 5.2 Stakeholder

Table: Stakeholder

Represents an actor involved in initiatives.

Key fields:

- stakeholderId
- name
- type - e.g. "city department", "NGO", "company"
- description
- notes

Stakeholders are generic and not tied to a specific city in this schema. The same stakeholder could work with multiple cities or initiatives.

#### 5.3 InitiativeStakeholder

Table: InitiativeStakeholder

Links Initiatives and Stakeholders, and captures the stakeholder role.

Key fields:

- initiativeStakeholderId
- initiativeId - references Initiative.initiativeId
- stakeholderId - references Stakeholder.stakeholderId
- role - e.g. "lead", "partner", "funder", "beneficiary"
- notes

Relationships:

- One Initiative can involve many Stakeholders.
- One Stakeholder can be involved in many Initiatives.
- InitiativeStakeholder is the many to many link table between them.

Summary:

- "An Initiative is led and supported by one or more Stakeholders."
- "A Stakeholder can take part in multiple Initiatives with different roles."

### 6. Indicators, values and targets

This block is how we describe "what is measured" and "where the city wants to go".

#### 6.1 Indicator

Table: Indicator

Represents what we are measuring for a city, optionally for a specific sector.

Key fields:

- indicatorId
- cityId - references City.cityId
- sectorId - references Sector.sectorId, nullable
- name - e.g. "Citywide GHG emissions", "EV share of new registrations"
- description
- unit - e.g. "tCO2e", "%", "km", "count"
- notes

Relationships:

- A City can have many Indicators.
- A Sector can have many Indicators (but the link is optional).
- Each Indicator belongs to exactly one City, and optionally one Sector.

Possible cases:

- city level indicators not tied to any sector, or
- sector specific indicators like "building sector emissions" for a certain city.

#### 6.2 IndicatorValue

Table: IndicatorValue

Represents the time series values for an Indicator.

Key fields:

- indicatorValueId
- indicatorId - references Indicator.indicatorId
- year
- value
- valueType - e.g. "baseline", "historical", "current", "projection"
- notes

Relationships:

- One Indicator can have many IndicatorValues (one per year or scenario).
- Each IndicatorValue belongs to exactly one Indicator.

Examples:

- "Historical value of total city emissions in 2015"
- "Projection for EV share in 2030"

#### 6.3 CityTarget

Table: CityTarget

Represents the city’s official target for a given Indicator, plus optional baseline info.

Key fields:

- cityTargetId
- cityId - references City.cityId
- indicatorId - references Indicator.indicatorId
- description - narrative description of the target
- targetYear
- targetValue
- baselineYear
- baselineValue
- status - e.g. "planned", "adopted", "achieved", "under_revision"
- notes

Relationships:

- A City can have many CityTargets.
- An Indicator can have many CityTargets (for different target years or scenarios).
  Example: 2030 and 2040 targets for the same indicator.

Each CityTarget belongs to one City and one Indicator.

How to interpret:
"City X has set a target for Indicator Y to reach value V by year T, starting from a baseline value B in year Y0, and the target is currently in status S."

### 7. Linking initiatives to indicators

#### 7.1 InitiativeIndicator

Table: InitiativeIndicator

Links Initiatives to Indicators and describes how the initiative impacts the indicator.

Key fields:

- initiativeIndicatorId
- initiativeId - references Initiative.initiativeId
- indicatorId - references Indicator.indicatorId
- contributionType - e.g. "expected", "monitored"
- expectedChange - numeric change, e.g. -5000 tCO2e, +10 percentage points
- notes

Relationships:

- One Initiative can affect many Indicators.
- One Indicator can be affected by many Initiatives.
- InitiativeIndicator is the many to many link table between Initiatives and Indicators.

Examples:

- "Retrofit program initiative is expected to reduce citywide 2030 emissions by 5000 tCO2e"
- "Cycling initiative is monitored via an indicator measuring kilometers of bike lanes and share of trips by bike"

### 8. Relationship summary in plain language

Putting it all together:

#### City and Contract

A City is the core object in the system.

Each City can have zero or one ClimateCityContract.

Each ClimateCityContract must belong to exactly one City.

#### City and Sectors

Sectors define a taxonomy that can be reused.

A Sector can have many EmissionRecords and Indicators attached.

A City has emissions and indicators that may be broken down by Sector.

#### Emissions

A City has many EmissionRecords.

Each EmissionRecord is for one City, one Sector, one year.

EmissionRecord is essentially a specialized indicator table for GHG emissions.

#### Budgets and Funding

A City has many Budgets (for different years).

A Budget belongs to one City and can be financed by many FundingSources.

A FundingSource can finance many Budgets.

BudgetFunding is the bridge that says "FundingSource X contributed amount A to Budget B."

#### Initiatives and Stakeholders

A City has many Initiatives.

Each Initiative belongs to one City.

Initiatives involve Stakeholders.

A Stakeholder can be part of many Initiatives.

InitiativeStakeholder links Initiatives and Stakeholders and stores the Stakeholder’s role.

#### Indicators, Values and Targets

A City has many Indicators, some citywide, some sector specific.

Each Indicator can have many IndicatorValues over time that represent baselines, history, current values or projections.

Each Indicator can also have many CityTargets representing goals for certain years, including baselines and statuses.

Each CityTarget is tied to one City and one Indicator.

#### Initiatives and Indicators

Initiatives affect Indicators.

One Initiative can impact several Indicators.

One Indicator can be influenced by several Initiatives.

InitiativeIndicator describes that relationship and how big the expected or monitored impact is.
