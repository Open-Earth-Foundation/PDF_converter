"""Tool definitions for OpenAI extraction API (Responses API compatible)."""

from __future__ import annotations

from typing import Any


def get_all_tools() -> list[dict[str, Any]]:
    """Return tool definitions suitable for OpenAI/OpenRouter Responses API."""
    return [
        {
            "type": "function",
            "name": "record_instances",
            "description": "Store one or more instances for the current Pydantic class. Use alias field names.",
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of objects for the current class using alias keys.",
                    },
                    "source_notes": {
                        "type": "string",
                        "description": "Optional short note about how values were derived or uncertainty.",
                    },
                },
                "required": ["items"],
            },
        },
        {
            "type": "function",
            "name": "all_extracted",
            "description": "Signal that every instance for the current class has been extracted (even zero).",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why extraction is finished or why no instances were found.",
                    }
                },
                "required": ["reason"],
            },
        },
    ]

