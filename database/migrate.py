"""
Brief: Database migration helper for Alembic.

Inputs:
- CLI: upgrade/downgrade/revision commands
- Env: DATABASE_URL
- Files: alembic.ini, database/alembic/versions

Outputs:
- Creates revision files and applies migrations
- Logs to stdout/stderr

Usage (from project root):
- python -m database.migrate upgrade head
"""

from __future__ import annotations

import argparse
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from dotenv import load_dotenv

from utils import setup_logger

REPO_ROOT = Path(__file__).resolve().parent.parent
ALEMBIC_INI = REPO_ROOT / "alembic.ini"
VERSIONS_DIR = Path(__file__).resolve().parent / "alembic" / "versions"

LOGGER = logging.getLogger(__name__)


def require_database_url() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError(
            "DATABASE_URL is not set.\n\n"
            "Example:\n"
            "  postgresql+psycopg://urbind:urbind@dev-db-aurora.cluster-c5ipsfxjhb0m.us-east-1.rds.amazonaws.com:5432/urbind"
        )


def load_alembic_config() -> Config:
    return Config(str(ALEMBIC_INI))


def slugify(message: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", message.strip().lower())
    return slug.strip("_") or "revision"


def _parse_revision_value(text: str) -> str | None:
    match = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
    return match.group(1) if match else None


def _parse_down_revision_value(text: str) -> str | None:
    match = re.search(r"^down_revision\s*=\s*(.+)$", text, re.MULTILINE)
    if not match:
        return None
    raw = match.group(1).strip()
    if raw == "None":
        return None
    if raw.startswith(("(", "[")):
        raise RuntimeError("Multiple down revisions detected; manual update required.")
    single = re.match(r"['\"]([^'\"]+)['\"]", raw)
    if not single:
        raise RuntimeError(f"Unsupported down_revision format: {raw}")
    return single.group(1)


def get_current_head() -> str | None:
    if not VERSIONS_DIR.exists():
        return None

    revisions: set[str] = set()
    referenced: set[str] = set()

    for path in VERSIONS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        revision = _parse_revision_value(text)
        if not revision:
            continue
        revisions.add(revision)

        down_revision = _parse_down_revision_value(text)
        if down_revision:
            referenced.add(down_revision)

    heads = [rev for rev in revisions if rev not in referenced]
    if len(heads) > 1:
        raise RuntimeError(f"Multiple heads detected: {', '.join(sorted(heads))}")
    return heads[0] if heads else None


def create_revision(*, message: str, revision_id: str | None) -> Path:
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)

    head = get_current_head()
    revision = revision_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    slug = slugify(message)
    filename = f"{revision}_{slug}.py"
    path = VERSIONS_DIR / filename

    if path.exists():
        raise RuntimeError(f"Revision file already exists: {path}")

    down_revision = "None" if head is None else f'"{head}"'
    safe_message = message.encode("ascii", "backslashreplace").decode("ascii")

    content = f'''"""{safe_message}"""

from alembic import op
import sqlalchemy as sa

revision = "{revision}"
down_revision = {down_revision}
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
'''

    path.write_text(content, encoding="utf-8", newline="\n")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Database migration helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upgrade_parser = subparsers.add_parser(
        "upgrade", help="Apply migrations (default: head)."
    )
    upgrade_parser.add_argument("revision", nargs="?", default="head")

    downgrade_parser = subparsers.add_parser(
        "downgrade", help="Rollback migrations (default: -1)."
    )
    downgrade_parser.add_argument("revision", nargs="?", default="-1")

    revision_parser = subparsers.add_parser(
        "revision", help="Create a new revision file."
    )
    revision_parser.add_argument("-m", "--message", required=True)
    revision_parser.add_argument("--rev-id", default=None)

    return parser.parse_args()


def main() -> int:
    load_dotenv()
    args = parse_args()

    if args.command == "revision":
        created = create_revision(message=args.message, revision_id=args.rev_id)
        LOGGER.info("Created migration: %s", created)
        return 0

    require_database_url()
    cfg = load_alembic_config()

    if args.command == "upgrade":
        LOGGER.info("Running Alembic upgrade to '%s'.", args.revision)
        try:
            command.upgrade(cfg, args.revision)
            LOGGER.info("Migration upgrade to '%s' completed successfully.", args.revision)
        except Exception as e:
            LOGGER.exception("Migration upgrade failed: %s", e)
            raise
        return 0
    if args.command == "downgrade":
        LOGGER.info("Running Alembic downgrade to '%s'.", args.revision)
        try:
            command.downgrade(cfg, args.revision)
            LOGGER.info("Migration downgrade to '%s' completed successfully.", args.revision)
        except Exception as e:
            LOGGER.exception("Migration downgrade failed: %s", e)
            raise
        return 0

    raise RuntimeError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    setup_logger()
    raise SystemExit(main())
