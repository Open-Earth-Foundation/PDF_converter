"""File I/O utilities."""

import json
import logging
from pathlib import Path
from typing import Sequence

LOGGER = logging.getLogger(__name__)

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"


def load_markdown(markdown_path: Path) -> str:
    """Load markdown file content."""
    if not markdown_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {markdown_path}")
    return markdown_path.read_text(encoding="utf-8")


def load_existing(output_path: Path) -> list[dict]:
    """Load existing JSON data from output file."""
    if not output_path.exists():
        return []
    try:
        return json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.warning("Existing JSON at %s could not be parsed: %s", output_path, exc)
        return []


def persist_instances(output_path: Path, instances: Sequence[dict]) -> None:
    """Write instances to JSON output file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(list(instances), indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

