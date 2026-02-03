"""Central LLM config loader.

NOTE: llm_config.yml is REQUIRED and must exist in the project root.
The application will fail to start without it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

LLM_CONFIG_PATH = Path(__file__).resolve().parent.parent / "llm_config.yml"


def load_llm_config() -> Dict[str, Dict[str, Any]]:
    """Load llm_config.yml from the project root.

    Raises:
        FileNotFoundError: If llm_config.yml does not exist.
        ValueError: If llm_config.yml is invalid or not a dictionary.
    """
    if not LLM_CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"llm_config.yml is required but not found at {LLM_CONFIG_PATH}\n"
            "Please create llm_config.yml in the project root with your LLM configuration."
        )
    try:
        payload = yaml.safe_load(LLM_CONFIG_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(
                f"llm_config.yml must contain a dictionary at the root level, "
                f"but got {type(payload).__name__}"
            )
        return payload
    except yaml.YAMLError as e:
        raise ValueError(f"Failed to parse llm_config.yml: {e}") from e


__all__ = ["load_llm_config", "LLM_CONFIG_PATH"]
