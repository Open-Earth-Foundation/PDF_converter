"""Pydantic models used for LLM extraction (strict per prompt requirements)."""

from __future__ import annotations

from typing import Any, Dict
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# These schemas are intentionally strict to match the extraction prompts.
# Database nullability is defined in database/models and migrations.


class BaseDBModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True, validate_assignment=True, extra="forbid"
    )
    misc: Dict[str, Any] | None = Field(default=None, alias="misc")


class ClimateCityContract(BaseDBModel):
    climate_city_contract_id: UUID | None = Field(
        alias="climateCityContractId", default=None
    )
    city_id: UUID | None = Field(alias="cityId", default=None)
    contract_date: datetime = Field(alias="contractDate")
    title: str = Field(alias="title")
    version: str | None = Field(default=None, alias="version")
    language: str | None = Field(default=None, alias="language")
    document_url: str | None = Field(default=None, alias="documentUrl")
    notes: str | None = Field(default=None, alias="notes")


class City(BaseDBModel):
    city_id: UUID = Field(alias="cityId")
    city_name: str = Field(alias="cityName")
    country: str = Field(alias="country")
    locode: str | None = Field(default=None, alias="locode")
    area_km2: Decimal | None = Field(default=None, alias="areaKm2")
    notes: str | None = Field(default=None, alias="notes")


class CityAnnualStats(BaseDBModel):
    stat_id: UUID | None = Field(alias="statId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    year: int = Field(alias="year")
    population: int | None = Field(default=None, alias="population")
    population_density: Decimal | None = Field(default=None, alias="populationDensity")
    gdp_per_capita: Decimal | None = Field(default=None, alias="gdpPerCapita")
    notes: str | None = Field(default=None, alias="notes")


class Sector(BaseDBModel):
    sector_id: UUID = Field(alias="sectorId")
    sector_name: str = Field(alias="sectorName")
    description: str | None = Field(default=None, alias="description")
    notes: str | None = Field(default=None, alias="notes")


class EmissionRecord(BaseDBModel):
    emission_record_id: UUID | None = Field(alias="emissionRecordId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    year: date = Field(alias="year")
    sector_id: UUID | None = Field(alias="sectorId", default=None)
    scope: str = Field(alias="scope")
    ghg_type: str = Field(alias="ghgType")
    value: int = Field(alias="value")
    unit: str = Field(alias="unit")
    notes: str | None = Field(default=None, alias="notes")


class CityBudget(BaseDBModel):
    budget_id: UUID | None = Field(alias="budgetId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    year: datetime = Field(alias="year")
    total_amount: int = Field(alias="totalAmount")
    currency: str = Field(alias="currency")
    description: str | None = Field(default=None, alias="description")
    notes: str | None = Field(default=None, alias="notes")


class FundingSource(BaseDBModel):
    funding_source_id: UUID = Field(alias="fundingSourceId")
    name: str = Field(alias="name")
    type: str = Field(alias="type")
    description: str = Field(alias="description")
    notes: str = Field(alias="notes")


class BudgetFunding(BaseDBModel):
    budget_funding_id: UUID | None = Field(alias="budgetFundingId", default=None)
    budget_id: UUID | None = Field(alias="budgetId", default=None)
    funding_source_id: UUID | None = Field(alias="fundingSourceId", default=None)
    amount: int = Field(alias="amount")
    currency: str = Field(alias="currency")
    notes: str | None = Field(default=None, alias="notes")


class Initiative(BaseDBModel):
    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    title: str = Field(alias="title")
    description: str = Field(alias="description")
    start_year: int | None = Field(default=None, alias="startYear")
    end_year: int | None = Field(default=None, alias="endYear")
    total_estimated_cost: int | None = Field(default=None, alias="totalEstimatedCost")
    currency: str = Field(alias="currency")
    status: str | None = Field(default=None, alias="status")
    notes: str = Field(alias="notes")


class Stakeholder(BaseDBModel):
    stakeholder_id: UUID = Field(alias="stakeholderId")
    name: str = Field(alias="name")
    type: str | None = Field(default=None, alias="type")
    description: str = Field(alias="description")
    notes: str = Field(alias="notes")


class InitiativeStakeholder(BaseDBModel):
    initiative_stakeholder_id: UUID | None = Field(
        alias="initiativeStakeholderId", default=None
    )
    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    stakeholder_id: UUID | None = Field(alias="stakeholderId", default=None)
    role: str | None = Field(default=None, alias="role")
    notes: str | None = Field(default=None, alias="notes")


class Indicator(BaseDBModel):
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    sector_id: UUID | None = Field(default=None, alias="sectorId")
    name: str = Field(alias="name")
    description: str = Field(alias="description")
    unit: str = Field(alias="unit")
    notes: str = Field(alias="notes")


class IndicatorValue(BaseDBModel):
    indicator_value_id: UUID | None = Field(alias="indicatorValueId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    year: date = Field(alias="year")
    value: Decimal = Field(alias="value")
    value_type: str = Field(alias="valueType")
    notes: str | None = Field(default=None, alias="notes")


class CityTarget(BaseDBModel):
    city_target_id: UUID | None = Field(alias="cityTargetId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    description: str = Field(alias="description")
    target_year: date = Field(alias="targetYear")
    target_value: Decimal = Field(alias="targetValue")
    baseline_year: date | None = Field(default=None, alias="baselineYear")
    baseline_value: Decimal | None = Field(default=None, alias="baselineValue")
    status: str = Field(alias="status")
    notes: str | None = Field(default=None, alias="notes")


class InitiativeIndicator(BaseDBModel):
    initiative_indicator_id: UUID | None = Field(
        alias="initiativeIndicatorId", default=None
    )
    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    contribution_type: str = Field(alias="contributionType")
    expected_change: Decimal | None = Field(default=None, alias="expectedChange")
    notes: str = Field(alias="notes")


class TefCategory(BaseDBModel):
    tef_id: UUID | None = Field(alias="tefId", default=None)
    parent_id: UUID | None = Field(default=None, alias="parentId")
    code: str = Field(alias="code")
    name: str = Field(alias="name")
    description: str | None = Field(default=None, alias="description")


class InitiativeTef(BaseDBModel):
    initiative_tef_id: UUID | None = Field(alias="initiativeTefId", default=None)
    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    tef_id: UUID | None = Field(alias="tefId", default=None)
    notes: str | None = Field(default=None, alias="notes")
