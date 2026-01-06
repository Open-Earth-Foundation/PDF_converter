from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from database.base import Base


class Sector(Base):
    __tablename__ = "Sector"

    sector_id: Mapped[UUID] = mapped_column(
        "sectorId", PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    sector_name: Mapped[str] = mapped_column("sectorName", String, nullable=False)
    description: Mapped[str | None] = mapped_column("description", Text, nullable=True)
    notes: Mapped[str | None] = mapped_column("notes", Text, nullable=True)
