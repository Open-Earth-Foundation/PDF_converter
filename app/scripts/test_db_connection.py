"""
Brief: Test database connectivity using the configured DATABASE_URL (or DB_URL).

Inputs:
- --db-url: optional override connection string
- Env: DATABASE_URL or DB_URL in the repo root .env file

Outputs:
- Logs connection status and a simple SELECT 1 result
- Exit code 0 on success, 1 on failure

Usage (from project root):
- python -m app.scripts.test_db_connection
- python -m app.scripts.test_db_connection --db-url postgresql+psycopg://user:pass@localhost:5432/db
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import text

from app.utils.logging_config import setup_logger
from database.config import DBSettings
from database.session import create_db_engine

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test database connectivity.")
    parser.add_argument(
        "--db-url",
        dest="db_url",
        default=None,
        help="Optional DB URL override (otherwise uses .env).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(REPO_ROOT / ".env")

    try:
        settings = (
            DBSettings(database_url=args.db_url)
            if args.db_url
            else DBSettings.from_env()
        )
    except RuntimeError as exc:
        LOGGER.error("%s", exc)
        return 1

    engine = create_db_engine(settings=settings)
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar_one()
            LOGGER.info("DB connection OK (SELECT 1 -> %s).", result)
    except Exception as exc:
        LOGGER.exception("DB connection failed: %s", exc)
        return 1
    finally:
        engine.dispose()

    return 0


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
