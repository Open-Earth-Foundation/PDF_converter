from __future__ import annotations

import os
import logging
from logging.config import fileConfig

from dotenv import load_dotenv
from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from database.base import Base
import database.models  # noqa: F401

# Load .env automatically (searches current dir and parents)
load_dotenv()

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

LOGGER = logging.getLogger(__name__)

target_metadata = Base.metadata


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Alembic needs it.\n"
            "Example: postgresql+psycopg://user:pass@localhost:5432/dbname"
        )
    return url


def get_connect_timeout_seconds() -> int:
    raw = os.getenv("DB_CONNECT_TIMEOUT", "10").strip()
    try:
        timeout = int(raw)
    except ValueError:
        LOGGER.warning("Invalid DB_CONNECT_TIMEOUT=%r, using 10.", raw)
        return 10
    if timeout < 0:
        LOGGER.warning("Negative DB_CONNECT_TIMEOUT=%r, using 10.", raw)
        return 10
    return timeout


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without DB connection)."""
    url = get_database_url()
    LOGGER.info(
        "Running migrations in offline mode (url=%s).",
        make_url(url).render_as_string(hide_password=True),
    )
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects to DB)."""
    alembic_cfg = config.get_section(config.config_ini_section) or {}
    url = get_database_url()
    alembic_cfg["sqlalchemy.url"] = url
    timeout_seconds = get_connect_timeout_seconds()

    connectable = engine_from_config(
        alembic_cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": timeout_seconds} if timeout_seconds else {},
    )

    LOGGER.info(
        "Connecting to DB (url=%s, timeout=%ss).",
        make_url(url).render_as_string(hide_password=True),
        timeout_seconds,
    )
    with connectable.connect() as connection:
        LOGGER.info("DB connection established. Running migrations.")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
