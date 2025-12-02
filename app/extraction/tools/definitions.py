"""Tool definitions for OpenAI extraction API using LangChain @tool decorator."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool


@tool
def record_instances(
    items: list[dict],
    source_notes: str | None = None
) -> dict:
    """
    Store one or more instances for the current Pydantic class.
    
    Use the schema field names (aliases) as keys.
    
    Args:
        items: List of objects for the current class, using alias field names.
               Each item should match the current class schema.
        source_notes: Optional short note about how the values were derived or any uncertainty.
    
    Returns:
        A status payload similar to what parse_record_instances produces.
    """
    # This function is wrapped by @tool decorator which handles
    # tool registration and definition generation. The actual handling of
    # tool calls is done in handle_response_output().
    pass


@tool
def all_extracted(reason: str) -> dict:
    """
    Signal that every instance for the current class has been extracted.
    
    Call this function even if zero instances were found.
    
    Args:
        reason: Why extraction is finished or why no instances were found.
    
    Returns:
        A status payload indicating extraction completion.
    """
    # This function is wrapped by @tool decorator which handles
    # tool registration and definition generation. The actual handling of
    # tool calls is done in handle_response_output().
    pass


def get_all_tools() -> list[dict[str, Any]]:
    """
    Get all tool definitions for the extraction process.
    
    Returns:
        List of tool definition dicts compatible with OpenAI Responses API.
    """
    # Convert LangChain tools to OpenAI format using convert_to_openai_tool()
    return [
        convert_to_openai_tool(record_instances),
        convert_to_openai_tool(all_extracted),
    ]

