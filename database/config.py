from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DBSettings:
    """
    Single source of truth for DB connectivity.

    Preferred env var: DATABASE_URL (DB_URL is accepted as an alias).
    Example:
      postgresql+psycopg://user:pass@localhost:5432/dbname
    """

    database_url: str

    @staticmethod
    def from_env() -> "DBSettings":
        url = os.getenv("DATABASE_URL") or os.getenv("DB_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL (or DB_URL) is not set.\n\n"
                "Example:\n"
                "  postgresql+psycopg://pdf_user:pdf_pass@localhost:5432/pdf_converter"
            )
        return DBSettings(database_url=url)
