"""
Brief: Seed TEF taxonomy data into the database.

Inputs:
- --taxonomy-path: path to the TEF taxonomy JSON file
- Env: DATABASE_URL (via DBSettings.from_env)

Outputs:
- Writes TEF taxonomy rows to the database
- Logs to stdout/stderr

Usage (from project root):
- python -m database.seeds.seed_tef --taxonomy-path data/tef_taxonomy.json
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from sqlalchemy import select
from dotenv import load_dotenv

from database.config import DBSettings
from database.session import create_db_engine, create_session_factory
from database.models.tef import TefCategory
from utils import setup_logger

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed TEF taxonomy data.")
    parser.add_argument(
        "--taxonomy-path",
        type=Path,
        default=Path("data/tef_taxonomy.json"),
        help="Path to TEF taxonomy JSON file.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()
    if not args.taxonomy_path.exists():
        LOGGER.error("Taxonomy file not found: %s", args.taxonomy_path)
        return 1

    settings = DBSettings.from_env()
    engine = create_db_engine(settings=settings)
    Session = create_session_factory(engine)

    taxonomy = json.loads(args.taxonomy_path.read_text(encoding="utf-8"))

    with Session() as session:
        existing = session.execute(select(TefCategory.tef_id).limit(1)).first()
        if existing:
            LOGGER.info("TEF already seeded; skipping.")
            return 0

        # TODO: Insert nodes + parent linking based on your JSON format.
        # session.add_all([...])
        session.commit()
        LOGGER.info("Seeded TEF taxonomy successfully.")
    return 0


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
