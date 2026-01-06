"""PDF2Markdown client factories (Mistral OCR + OpenRouter vision)."""

import os
from openai import OpenAI

from pdf2markdown.utils.create_mistral_client import create_mistral_client


def create_vision_client() -> OpenAI:
    """Create an OpenRouter-compatible OpenAI client for vision refinement."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("Missing OpenRouter API key. Set OPENROUTER_API_KEY.")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    default_headers = {"HTTP-Referer": "https://github.com/docling/pdf-ocr-refinement"}
    return OpenAI(api_key=key, base_url=base_url, default_headers=default_headers)


__all__ = ["create_mistral_client", "create_vision_client"]
