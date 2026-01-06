"""Configuration and file loading utilities."""

import logging
from pathlib import Path

import yaml

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "prompts"
CONFIG_PATH = BASE_DIR / "config.yaml"
DEBUG_LOG_DIR = BASE_DIR / "debug_logs"


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_config() -> dict:
    """Load configuration from config.yaml."""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file required: {CONFIG_PATH}")
    try:
        data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Config file {CONFIG_PATH} is not a mapping.")
        return data
    except Exception as exc:
        raise RuntimeError(f"Failed to load config {CONFIG_PATH}: {exc}")


def load_class_context(class_name: str) -> str:
    """Load class-specific extraction guidance from prompt file."""
    path = PROMPTS_DIR / f"{class_name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return (
        f"Focus on extracting {class_name} entries related to Climate City Contract "
        "and climate-action programs. If key identifiers are missing, skip that row rather than inventing data."
    )


def clean_debug_logs() -> None:
    """Remove debug logs directory if it exists (for fresh extraction runs)."""
    if DEBUG_LOG_DIR.exists():
        import shutil
        try:
            shutil.rmtree(DEBUG_LOG_DIR)
            LOGGER.info("Cleaned debug logs directory: %s", DEBUG_LOG_DIR)
        except Exception as exc:
            LOGGER.warning("Failed to clean debug logs directory %s: %s", DEBUG_LOG_DIR, exc)

