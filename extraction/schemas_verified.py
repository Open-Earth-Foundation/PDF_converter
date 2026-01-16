"""Extraction-specific Pydantic schemas with VerifiedField for Evidence Pattern enforcement."""

from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from extraction.utils.verified_field import VerifiedField

# The schema marks several columns as "enum" but does not provide members.
# To remain faithful and avoid constraining inputs prematurely, those columns
# are modelled as plain strings. Replace with concrete StrEnum values later
# when the allowed vocabularies are finalized.


class BaseDBModel(BaseModel):
    """Base model for extraction schemas with misc field for metadata."""

    model_config = ConfigDict(
        populate_by_name=True, validate_assignment=True, extra="forbid"
    )
    misc: Dict[str, Any] | None = Field(default=None, alias="misc")


class VerifiedCityTarget(BaseDBModel):
    """
    CityTarget with verified fields for numeric/date/status values.

    The following fields are verified (include value, quote, confidence):
    - targetYear, targetValue, baselineYear, baselineValue, status

    Other fields remain as regular types.

    Note: status is optional (VerifiedField[str] | None) to allow evidence-based validation
    when status is not mentioned in source (with appropriate quote like "status not mentioned").
    """

    city_target_id: UUID | None = Field(alias="cityTargetId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    description: str = Field(alias="description")
    target_year: VerifiedField[str] = Field(alias="targetYear")  # date as string
    target_value: VerifiedField[str] = Field(alias="targetValue")  # decimal as string
    baseline_year: VerifiedField[str] | None = Field(
        default=None, alias="baselineYear"
    )  # date as string
    baseline_value: VerifiedField[str] | None = Field(
        default=None, alias="baselineValue"
    )  # decimal as string
    status: VerifiedField[str] | None = Field(
        default=None, alias="status"
    )  # Optional with verification
    notes: str | None = Field(default=None, alias="notes")


class VerifiedEmissionRecord(BaseDBModel):
    """
    EmissionRecord with verified fields for year and value.

    The following fields are verified (include value, quote, confidence):
    - year, value

    Other fields remain as regular types.
    """

    emission_record_id: UUID | None = Field(alias="emissionRecordId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    year: VerifiedField[str] = Field(alias="year")  # date as string
    sector_id: UUID | None = Field(alias="sectorId", default=None)
    scope: str = Field(alias="scope")  # TODO: enum when vocabulary set
    ghg_type: str = Field(alias="ghgType")  # TODO: enum when vocabulary set
    value: VerifiedField[str] = Field(alias="value")  # integer as string
    unit: str = Field(alias="unit")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class VerifiedCityBudget(BaseDBModel):
    """
    CityBudget with verified fields for year and totalAmount.

    The following fields are verified (include value, quote, confidence):
    - year, totalAmount

    Other fields remain as regular types.
    """

    budget_id: UUID | None = Field(alias="budgetId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    year: VerifiedField[str] = Field(alias="year")  # datetime as string
    total_amount: VerifiedField[str] = Field(alias="totalAmount")  # integer as string
    currency: str = Field(alias="currency")  # TODO: enum when vocabulary set
    description: str | None = Field(default=None, alias="description")
    notes: str | None = Field(default=None, alias="notes")


class VerifiedIndicatorValue(BaseDBModel):
    """
    IndicatorValue with verified fields for year and value.

    The following fields are verified (include value, quote, confidence):
    - year, value

    Other fields remain as regular types.
    """

    indicator_value_id: UUID | None = Field(alias="indicatorValueId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    year: VerifiedField[str] = Field(alias="year")  # date as string
    value: VerifiedField[str] = Field(alias="value")  # decimal as string
    value_type: str = Field(alias="valueType")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class VerifiedBudgetFunding(BaseDBModel):
    """
    BudgetFunding with verified fields for amount.

    The following fields are verified (include value, quote, confidence):
    - amount

    Other fields remain as regular types.
    """

    budget_funding_id: UUID | None = Field(alias="budgetFundingId", default=None)
    budget_id: UUID | None = Field(alias="budgetId", default=None)
    funding_source_id: UUID | None = Field(alias="fundingSourceId", default=None)
    amount: VerifiedField[str] = Field(alias="amount")  # integer as string
    currency: str = Field(alias="currency")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class VerifiedInitiative(BaseDBModel):
    """
    Initiative with verified fields for startYear, endYear, totalEstimatedCost, and status.

    The following fields are verified (include value, quote, confidence):
    - startYear, endYear, totalEstimatedCost, status

    Other fields remain as regular types.
    """

    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    title: str = Field(alias="title")
    description: str | None = Field(default=None, alias="description")
    start_year: VerifiedField[str] | None = Field(
        default=None, alias="startYear"
    )  # integer as string
    end_year: VerifiedField[str] | None = Field(
        default=None, alias="endYear"
    )  # integer as string
    total_estimated_cost: VerifiedField[str] | None = Field(
        default=None, alias="totalEstimatedCost"
    )  # integer as string
    currency: str | None = Field(
        default=None, alias="currency"
    )  # TODO: enum when vocabulary set
    status: VerifiedField[str] | None = Field(
        default=None, alias="status"
    )  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")
