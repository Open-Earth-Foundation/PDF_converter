"""Central LLM config loader."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

LLM_CONFIG_PATH = Path(__file__).resolve().parent.parent / "llm_config.yml"

DEFAULT_LLM_CONFIG: Dict[str, Dict[str, Any]] = {
    "pdf2markdown": {
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "ocr_model": "mistral-ocr-latest",
    },
    "extraction": {
        "model": "google/gemini-3-flash-preview",
        "temperature": 0.0,
        "token_limit": 900000,
        "max_rounds": 12,
        "debug_logs_enabled": True,
        "clean_debug_logs_on_start": True,
        "debug_logs_full_response_once": True,
        "debug_logs_full_response": False,
        "chunking": {
            "enabled": False,
            "auto_threshold_tokens": 300000,
            "chunk_size_tokens": 200000,
            "chunk_overlap_tokens": 10000,
            "boundary_mode": "paragraph_or_sentence",
            "keep_tables_intact": True,
            "table_context_max_items": 0,
        },
    },
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
