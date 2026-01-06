"""Provider selection helpers for extraction."""

from __future__ import annotations

import os
from typing import Any, Dict


def select_provider(llm_cfg: dict[str, Any], config: dict[str, Any], env_prefix: str = "EXTRACTION") -> Any:
    """
    Choose a provider hint in priority order:
    1) llm_config.yml extraction.provider
    2) extraction/config.yaml provider
    3) environment override (EXTRACTION_PROVIDER or custom prefix)
    4) OPENROUTER_PROVIDER (router-wide override)
    """
    return (
        llm_cfg.get("provider")
        or config.get("provider")
        or os.getenv(f"{env_prefix}_PROVIDER")
        or os.getenv("OPENROUTER_PROVIDER")
    )


def apply_default_provider(
    model_name: str,
    extra_body: dict[str, Any] | None,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Ensure a provider is set for models that require a specific endpoint.

    Pass a dict in `default` if you want to force a provider object (schema depends on the router).
    """
    body: Dict[str, Any] = dict(extra_body or {})
    if default and not body.get("provider"):
        body["provider"] = default
    return body
