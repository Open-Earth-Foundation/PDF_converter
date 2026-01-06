"""OpenRouter-only client for vision refinement."""

import os
from openai import OpenAI


def create_vision_client() -> OpenAI:
    """Create an OpenRouter-compatible OpenAI client for vision refinement."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("Missing OpenRouter API key. Set OPENROUTER_API_KEY.")

    resolved_base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    default_headers = {"HTTP-Referer": "https://github.com/docling/pdf-ocr-refinement"}

    return OpenAI(
        api_key=key,
        base_url=resolved_base_url,
        default_headers=default_headers,
    )
