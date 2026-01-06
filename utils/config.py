"""Central LLM config loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

LLM_CONFIG_PATH = Path(__file__).resolve().parent.parent / "llm_config.yml"

DEFAULT_LLM_CONFIG: Dict[str, Dict[str, Any]] = {
    "pdf2markdown": {"model": "google/gemini-3-flash-preview", "temperature": 0.0},
    "extraction": {"model": "google/gemini-3-flash-preview", "temperature": 0.0},
    "mapping": {"model": "google/gemini-3-flash-preview", "temperature": 0.0},
}


def load_llm_config() -> Dict[str, Dict[str, Any]]:
    """Load llm_config.yml, falling back to defaults if missing or invalid."""
    if not LLM_CONFIG_PATH.exists():
        return DEFAULT_LLM_CONFIG.copy()
    try:
        payload = yaml.safe_load(LLM_CONFIG_PATH.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return DEFAULT_LLM_CONFIG.copy()
        merged = DEFAULT_LLM_CONFIG.copy()
        for section, cfg in payload.items():
            if isinstance(cfg, dict):
                merged[section] = {**merged.get(section, {}), **cfg}
        return merged
    except Exception:
        return DEFAULT_LLM_CONFIG.copy()


__all__ = ["load_llm_config", "LLM_CONFIG_PATH", "DEFAULT_LLM_CONFIG"]
