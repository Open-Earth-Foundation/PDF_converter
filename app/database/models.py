"""Pydantic models mirroring the planned database schema."""

from __future__ import annotations

from typing import Any, Dict
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# The schema marks several columns as "enum" but does not provide members.
# To remain faithful and avoid constraining inputs prematurely, those columns
# are modelled as plain strings. Replace with concrete StrEnum values later
# when the allowed vocabularies are finalized.


class BaseDBModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, validate_assignment=True, extra="forbid")
    misc: Dict[str, Any] | None = Field(default=None, alias="misc")


class ClimateCityContract(BaseDBModel):
    climate_city_contract_id: UUID | None = Field(alias="climateCityContractId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    contract_date: datetime = Field(alias="contractDate")
    title: str
    version: str | None = None
    language: str | None = Field(default=None, alias="language")  # TODO: enum when vocabulary set
    document_url: str | None = Field(default=None, alias="documentUrl")
    notes: str | None = None


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
    scope: str = Field(alias="scope")  # TODO: enum when vocabulary set
    ghg_type: str = Field(alias="ghgType")  # TODO: enum when vocabulary set
    value: int = Field(alias="value")
    unit: str = Field(alias="unit")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class CityBudget(BaseDBModel):
    budget_id: UUID | None = Field(alias="budgetId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    year: datetime = Field(alias="year")
    total_amount: int = Field(alias="totalAmount")
    currency: str = Field(alias="currency")  # TODO: enum when vocabulary set
    description: str | None = Field(default=None, alias="description")
    notes: str | None = Field(default=None, alias="notes")


class FundingSource(BaseDBModel):
    funding_source_id: UUID = Field(alias="fundingSourceId")
    name: str = Field(alias="name")
    type: str = Field(alias="type")
    description: str | None = Field(default=None, alias="description")
    notes: str | None = Field(default=None, alias="notes")


class BudgetFunding(BaseDBModel):
    budget_funding_id: UUID | None = Field(alias="budgetFundingId", default=None)
    budget_id: UUID | None = Field(alias="budgetId", default=None)
    funding_source_id: UUID | None = Field(alias="fundingSourceId", default=None)
    amount: int = Field(alias="amount")
    currency: str = Field(alias="currency")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class Initiative(BaseDBModel):
    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    title: str = Field(alias="title")
    description: str | None = Field(default=None, alias="description")
    start_year: int | None = Field(default=None, alias="startYear")
    end_year: int | None = Field(default=None, alias="endYear")
    total_estimated_cost: int | None = Field(default=None, alias="total_estimated_cost")
    currency: str | None = Field(default=None, alias="currency")  # TODO: enum when vocabulary set
    status: str | None = Field(default=None, alias="status")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class Stakeholder(BaseDBModel):
    stakeholder_id: UUID = Field(alias="stakeholderId")
    name: str = Field(alias="name")
    type: str | None = Field(default=None, alias="type")
    description: str | None = Field(default=None, alias="description")
    notes: str | None = Field(default=None, alias="notes")


class InitiativeStakeholder(BaseDBModel):
    initiative_stakeholder_id: UUID | None = Field(alias="initiativeStakeholderId", default=None)
    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    stakeholder_id: UUID | None = Field(alias="stakeholderId", default=None)
    role: str | None = Field(default=None, alias="role")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class Indicator(BaseDBModel):
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    sector_id: UUID | None = Field(default=None, alias="sectorId")
    name: str = Field(alias="name")
    description: str | None = Field(default=None, alias="description")
    unit: str = Field(alias="unit")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class IndicatorValue(BaseDBModel):
    indicator_value_id: UUID | None = Field(alias="indicatorValueId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    year: date = Field(alias="year")
    value: Decimal = Field(alias="value")
    value_type: str = Field(alias="valueType")  # TODO: enum when vocabulary set
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
    status: str = Field(alias="status")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class InitiativeIndicator(BaseDBModel):
    initiative_indicator_id: UUID | None = Field(alias="initiativeIndicatorId", default=None)
    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    contribution_type: str = Field(alias="contributionType")  # TODO: enum when vocabulary set
    expected_change: Decimal | None = Field(default=None, alias="expectedChange")
    notes: str | None = Field(default=None, alias="notes")


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
