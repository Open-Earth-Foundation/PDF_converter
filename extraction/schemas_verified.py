"""Extraction-specific Pydantic schemas with flat quote/confidence fields for Evidence Pattern enforcement."""

from __future__ import annotations

from typing import Any, Dict, Optional
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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
    CityTarget with flat quote/confidence fields for numeric/date/status values.

    Verified fields use flat structure:
    - targetYear (str) + targetYear_quote (str) + targetYear_confidence (float)
    - targetValue (str) + targetValue_quote (str) + targetValue_confidence (float)
    - baselineYear (str) + baselineYear_quote (str) + baselineYear_confidence (float)
    - baselineValue (str) + baselineValue_quote (str) + baselineValue_confidence (float)
    - status (str) + status_quote (str) + status_confidence (float)

    Other fields remain as regular types.
    """

    city_target_id: UUID | None = Field(alias="cityTargetId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    description: str = Field(alias="description")

    # Verified field: targetYear
    target_year: str = Field(alias="targetYear")
    target_year_quote: str = Field(alias="targetYear_quote")
    target_year_confidence: float = Field(alias="targetYear_confidence", ge=0.0, le=1.0)

    # Verified field: targetValue
    target_value: str = Field(alias="targetValue")
    target_value_quote: str = Field(alias="targetValue_quote")
    target_value_confidence: float = Field(
        alias="targetValue_confidence", ge=0.0, le=1.0
    )

    # Verified field: baselineYear (optional)
    baseline_year: str | None = Field(default=None, alias="baselineYear")
    baseline_year_quote: str | None = Field(default=None, alias="baselineYear_quote")
    baseline_year_confidence: float | None = Field(
        default=None, alias="baselineYear_confidence", ge=0.0, le=1.0
    )

    # Verified field: baselineValue (optional)
    baseline_value: str | None = Field(default=None, alias="baselineValue")
    baseline_value_quote: str | None = Field(default=None, alias="baselineValue_quote")
    baseline_value_confidence: float | None = Field(
        default=None, alias="baselineValue_confidence", ge=0.0, le=1.0
    )

    # Verified field: status (optional)
    status: str | None = Field(default=None, alias="status")
    status_quote: str | None = Field(default=None, alias="status_quote")
    status_confidence: float | None = Field(
        default=None, alias="status_confidence", ge=0.0, le=1.0
    )

    notes: str | None = Field(default=None, alias="notes")


class VerifiedEmissionRecord(BaseDBModel):
    """
    EmissionRecord with flat quote/confidence fields for year and value.

    Verified fields use flat structure:
    - year (str) + year_quote (str) + year_confidence (float)
    - value (str) + value_quote (str) + value_confidence (float)

    Other fields remain as regular types.
    """

    emission_record_id: UUID | None = Field(alias="emissionRecordId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)

    # Verified field: year
    year: str = Field(alias="year")
    year_quote: str = Field(alias="year_quote")
    year_confidence: float = Field(alias="year_confidence", ge=0.0, le=1.0)

    sector_id: UUID | None = Field(alias="sectorId", default=None)
    scope: str = Field(alias="scope")  # TODO: enum when vocabulary set
    ghg_type: str = Field(alias="ghgType")  # TODO: enum when vocabulary set

    # Verified field: value
    value: str = Field(alias="value")
    value_quote: str = Field(alias="value_quote")
    value_confidence: float = Field(alias="value_confidence", ge=0.0, le=1.0)

    unit: str = Field(alias="unit")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class VerifiedCityBudget(BaseDBModel):
    """
    CityBudget with flat quote/confidence fields for year and totalAmount.

    Verified fields use flat structure:
    - year (str) + year_quote (str) + year_confidence (float)
    - totalAmount (str) + totalAmount_quote (str) + totalAmount_confidence (float)

    Other fields remain as regular types.
    """

    budget_id: UUID | None = Field(alias="budgetId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)

    # Verified field: year
    year: str = Field(alias="year")
    year_quote: str = Field(alias="year_quote")
    year_confidence: float = Field(alias="year_confidence", ge=0.0, le=1.0)

    # Verified field: totalAmount
    total_amount: str = Field(alias="totalAmount")
    total_amount_quote: str = Field(alias="totalAmount_quote")
    total_amount_confidence: float = Field(
        alias="totalAmount_confidence", ge=0.0, le=1.0
    )

    currency: str = Field(alias="currency")  # TODO: enum when vocabulary set
    description: str | None = Field(default=None, alias="description")
    notes: str | None = Field(default=None, alias="notes")


class VerifiedIndicatorValue(BaseDBModel):
    """
    IndicatorValue with flat quote/confidence fields for year and value.

    Verified fields use flat structure:
    - year (str) + year_quote (str) + year_confidence (float)
    - value (str) + value_quote (str) + value_confidence (float)

    Other fields remain as regular types.
    """

    indicator_value_id: UUID | None = Field(alias="indicatorValueId", default=None)
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)

    # Verified field: year
    year: str = Field(alias="year")
    year_quote: str = Field(alias="year_quote")
    year_confidence: float = Field(alias="year_confidence", ge=0.0, le=1.0)

    # Verified field: value
    value: str = Field(alias="value")
    value_quote: str = Field(alias="value_quote")
    value_confidence: float = Field(alias="value_confidence", ge=0.0, le=1.0)

    value_type: str = Field(alias="valueType")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class VerifiedBudgetFunding(BaseDBModel):
    """
    BudgetFunding with flat quote/confidence fields for amount.

    Verified fields use flat structure:
    - amount (str) + amount_quote (str) + amount_confidence (float)

    Other fields remain as regular types.
    """

    budget_funding_id: UUID | None = Field(alias="budgetFundingId", default=None)
    budget_id: UUID | None = Field(alias="budgetId", default=None)
    funding_source_id: UUID | None = Field(alias="fundingSourceId", default=None)

    # Verified field: amount
    amount: str = Field(alias="amount")
    amount_quote: str = Field(alias="amount_quote")
    amount_confidence: float = Field(alias="amount_confidence", ge=0.0, le=1.0)

    currency: str = Field(alias="currency")  # TODO: enum when vocabulary set
    notes: str | None = Field(default=None, alias="notes")


class IndicatorWithValues(BaseDBModel):
    """
    Combined schema for extracting an Indicator with its associated IndicatorValues.

    This allows grouping multiple measurements with a single indicator definition,
    making it easier to link values to their parent indicator.
    """

    # Indicator fields
    indicator_id: UUID | None = Field(alias="indicatorId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    sector_id: UUID | None = Field(default=None, alias="sectorId")
    name: str = Field(alias="name")
    description: str = Field(alias="description")
    unit: str = Field(alias="unit")

    # Indicator values as nested array
    values: list[dict[str, Any]] | None = Field(default=None, alias="values")

    notes: str | None = Field(default=None, alias="notes")


class VerifiedInitiative(BaseDBModel):
    """
    Initiative with flat quote/confidence fields for startYear, endYear, totalEstimatedCost, and status.

    Verified fields use flat structure:
    - startYear (str) + startYear_quote (str) + startYear_confidence (float)
    - endYear (str) + endYear_quote (str) + endYear_confidence (float)
    - totalEstimatedCost (str) + totalEstimatedCost_quote (str) + totalEstimatedCost_confidence (float)
    - status (str) + status_quote (str) + status_confidence (float)

    Other fields remain as regular types.
    """

    initiative_id: UUID | None = Field(alias="initiativeId", default=None)
    city_id: UUID | None = Field(alias="cityId", default=None)
    title: str = Field(alias="title")
    description: str = Field(alias="description")

    # Verified field: startYear (optional)
    start_year: str | None = Field(default=None, alias="startYear")
    start_year_quote: str | None = Field(default=None, alias="startYear_quote")
    start_year_confidence: float | None = Field(
        default=None, alias="startYear_confidence", ge=0.0, le=1.0
    )

    # Verified field: endYear (optional)
    end_year: str | None = Field(default=None, alias="endYear")
    end_year_quote: str | None = Field(default=None, alias="endYear_quote")
    end_year_confidence: float | None = Field(
        default=None, alias="endYear_confidence", ge=0.0, le=1.0
    )

    # Verified field: totalEstimatedCost (optional)
    total_estimated_cost: str | None = Field(default=None, alias="totalEstimatedCost")
    total_estimated_cost_quote: str | None = Field(
        default=None, alias="totalEstimatedCost_quote"
    )
    total_estimated_cost_confidence: float | None = Field(
        default=None, alias="totalEstimatedCost_confidence", ge=0.0, le=1.0
    )

    currency: str = Field(alias="currency")  # TODO: enum when vocabulary set

    # Verified field: status (optional)
    status: str | None = Field(default=None, alias="status")
    status_quote: str | None = Field(default=None, alias="status_quote")
    status_confidence: float | None = Field(
        default=None, alias="status_confidence", ge=0.0, le=1.0
    )

    notes: str | None = Field(default=None, alias="notes")
