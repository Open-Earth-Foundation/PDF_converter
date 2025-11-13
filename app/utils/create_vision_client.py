"""Utility function to create an OpenAI-compatible vision client.

This client is used for the optional vision refinement step. It supports both
OpenRouter (vendor-prefixed model ids) and direct OpenAI usage depending on the
environment configuration.
"""

import os
from openai import OpenAI


def create_vision_client() -> OpenAI:
    """Create and return an OpenAI-compatible client for vision refinement.

    The API key is resolved in the following order:
    1) explicit `api_key` argument
    2) environment variable `OPENROUTER_API_KEY`
    3) environment variable `OPENAI_API_KEY`

    The base URL is resolved in the following order:
    1) explicit `base_url` argument
    2) environment variable `OPENAI_BASE_URL`
    3) default `https://openrouter.ai/api/v1`

    Returns:
        OpenAI: Initialized client instance.

    Raises:
        RuntimeError: If the OpenAI dependency is missing or no API key is set.
    """

    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing OpenRouter/OpenAI API key. Set OPENROUTER_API_KEY or OPENAI_API_KEY."
        )

    resolved_base_url = (
        os.environ.get("OPENAI_BASE_URL") or "https://openrouter.ai/api/v1"
    )

    # Set HTTP-Referer for OpenRouter (required for their API)
    default_headers = {
        "HTTP-Referer": "https://github.com/docling/pdf-ocr-refinement",
    }

    return OpenAI(
        api_key=key,
        base_url=resolved_base_url,
        default_headers=default_headers,
    )
