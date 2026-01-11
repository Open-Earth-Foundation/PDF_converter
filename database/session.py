from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.config import DBSettings


def create_db_engine(*, settings: DBSettings):
    """
    Create a synchronous SQLAlchemy engine.

    Sync engine is the simplest + most compatible option for Alembic migrations.
    """
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        future=True,
    )


def create_session_factory(engine):
    """Create a session factory (use Session() context manager for unit of work)."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
