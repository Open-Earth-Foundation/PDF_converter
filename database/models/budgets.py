from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class CityBudget(Base):
    __tablename__ = "CityBudget"
    __table_args__ = (UniqueConstraint("cityId", "year"),)

    budget_id: Mapped[UUID] = mapped_column(
        "budgetId", PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    city_id: Mapped[UUID | None] = mapped_column(
        "cityId", PG_UUID(as_uuid=True), ForeignKey("City.cityId"), nullable=True
    )
    year: Mapped[int] = mapped_column("year", Integer, nullable=False)
    total_amount: Mapped[int] = mapped_column("totalAmount", Integer, nullable=False)
    currency: Mapped[str] = mapped_column("currency", String, nullable=False)
    description: Mapped[str | None] = mapped_column("description", Text, nullable=True)
    notes: Mapped[str | None] = mapped_column("notes", Text, nullable=True)


class FundingSource(Base):
    __tablename__ = "FundingSource"

    funding_source_id: Mapped[UUID] = mapped_column(
        "fundingSourceId", PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column("name", String, nullable=False)
    type: Mapped[str] = mapped_column("type", String, nullable=False)
    description: Mapped[str | None] = mapped_column("description", Text, nullable=True)
    notes: Mapped[str | None] = mapped_column("notes", Text, nullable=True)


class BudgetFunding(Base):
    __tablename__ = "BudgetFunding"

    budget_funding_id: Mapped[UUID] = mapped_column(
        "budgetFundingId", PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    budget_id: Mapped[UUID | None] = mapped_column(
        "budgetId",
        PG_UUID(as_uuid=True),
        ForeignKey("CityBudget.budgetId"),
        nullable=True,
    )
    funding_source_id: Mapped[UUID | None] = mapped_column(
        "fundingSourceId",
        PG_UUID(as_uuid=True),
        ForeignKey("FundingSource.fundingSourceId"),
        nullable=True,
    )
    amount: Mapped[int] = mapped_column("amount", Integer, nullable=False)
    currency: Mapped[str] = mapped_column("currency", String, nullable=False)
    notes: Mapped[str | None] = mapped_column("notes", Text, nullable=True)
