from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select

from database.config import DBSettings
from database.session import create_db_engine, create_session_factory
from database.models.tef import TefCategory


def main() -> None:
    settings = DBSettings.from_env()
    engine = create_db_engine(settings=settings)
    Session = create_session_factory(engine)

    taxonomy_path = Path("data/tef_taxonomy.json")
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))

    with Session() as session:
        existing = session.execute(select(TefCategory.tef_id).limit(1)).first()
        if existing:
            print("TEF already seeded; skipping.")
            return

        # TODO: Insert nodes + parent linking based on your JSON format.
        # session.add_all([...])
        session.commit()
        print("Seeded TEF taxonomy successfully.")


if __name__ == "__main__":
    main()
