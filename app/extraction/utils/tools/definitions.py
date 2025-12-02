"""Tool definitions for OpenAI extraction API."""

from __future__ import annotations

from typing import Any


def get_record_instances_tool() -> dict[str, Any]:
    """
    Get the 'record_instances' tool definition.
    
    This tool allows the model to store one or more instances for the current
    Pydantic class using schema field names (aliases) as keys.
    
    Returns:
        Tool definition dict compatible with OpenAI Responses API.
    """
    return {
        "type": "function",
        "name": "record_instances",
        "description": (
            "Store one or more instances for the current Pydantic class. "
            "Use the schema field names (aliases) as keys."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": (
                        "List of objects for the current class, using alias field names."
                    ),
                    "items": {
                        "type": "object",
                        "description": "A single instance matching the current class schema.",
                    },
                    "minItems": 1,
                },
                "source_notes": {
                    "type": "string",
                    "description": (
                        "Optional short note about how the values were derived or any uncertainty."
                    ),
                },
            },
            "required": ["items"],
            "additionalProperties": False,
        },
        "strict": True,
    }


def get_all_extracted_tool() -> dict[str, Any]:
    """
    Get the 'all_extracted' tool definition.
    
    This tool signals that every instance for the current class has been extracted.
    Should be called even if zero instances exist.
    
    Returns:
        Tool definition dict compatible with OpenAI Responses API.
    """
    return {
        "type": "function",
        "name": "all_extracted",
        "description": (
            "Signal that every instance for the current class has been extracted "
            "(call even if zero instances exist)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why extraction is finished or why no instances were found.",
                }
            },
            "required": ["reason"],
            "additionalProperties": False,
        },
        "strict": True,
    }


def get_all_tools() -> list[dict[str, Any]]:
    """
    Get all tool definitions for the extraction process.
    
    Returns:
        List of tool definition dicts compatible with OpenAI Responses API.
    """
    return [
        get_record_instances_tool(),
        get_all_extracted_tool(),
    ]

