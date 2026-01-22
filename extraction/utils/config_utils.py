"""Configuration and file loading utilities."""

import logging
from pathlib import Path

from utils import load_llm_config

LOGGER = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "prompts"
DEBUG_LOG_DIR = BASE_DIR / "debug_logs"
DEFAULT_EXTRACTION_CONFIG = {
    "model": "google/gemini-3-flash-preview",
    "temperature": 0.0,
    "token_limit": 900000,
    "max_rounds": 12,
    "debug_logs_enabled": True,
    "clean_debug_logs_on_start": True,
    "debug_logs_full_response_once": True,
    "debug_logs_full_response": False,
}


def load_prompt(name: str) -> str:
    """Load a prompt template from the prompts directory."""
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_config() -> dict:
    """Load extraction configuration from llm_config.yml."""
    llm_config = load_llm_config()
    extraction_config = llm_config.get("extraction", {})
    if not isinstance(extraction_config, dict):
        LOGGER.warning("Extraction config is not a mapping; using defaults.")
        extraction_config = {}
    return {**DEFAULT_EXTRACTION_CONFIG, **extraction_config}


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

