"""Logging utilities."""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage

from .data_utils import extract_text

if TYPE_CHECKING:
    from openai.types.responses import Response

LOGGER = logging.getLogger(__name__)

LOG_SNIPPET_LEN = 320
DEBUG_LOG_DIR = Path(__file__).resolve().parents[1] / "debug_logs"


def truncate(text: str, limit: int = LOG_SNIPPET_LEN) -> str:
    """Truncate text to specified limit with ellipsis."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def log_response_preview(model_name: str, assistant_messages: list[str], tool_calls: list[ResponseFunctionToolCall]) -> None:
    """Log a preview of assistant response and tool calls."""
    if assistant_messages:
        preview = truncate(" | ".join(assistant_messages))
        LOGGER.info("[%s] Assistant preview: %s", model_name, preview)
    if tool_calls:
        names = [call.name for call in tool_calls]
        LOGGER.info("[%s] Tool calls: %s", model_name, ", ".join(names))


def log_full_response(class_name: str, response: "Response", round_idx: int, config: dict | None = None) -> None:
    """Write full response to a debug log file for inspection.
    
    Args:
        class_name: Name of the class being extracted.
        response: The response object from OpenAI.
        round_idx: The current round index.
        config: Configuration dict. If provided, checks debug_logs_enabled setting.
    """
    # Check if debug logging is enabled in config
    if config is not None:
        if not config.get("debug_logs_enabled", True):
            LOGGER.debug("Debug logging disabled; skipping full response log for %s (round %d)", class_name, round_idx)
            return
    
    DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DEBUG_LOG_DIR / f"{class_name}_round{round_idx}.json"
    
    debug_info = {
        "response_id": response.id,
        "model": getattr(response, "model", None),
        "status": getattr(response, "status", None),
        "has_output_field": hasattr(response, "output"),
        "output_length": len(response.output) if hasattr(response, "output") and response.output else 0,
        "output_items": [],
    }
    
    # Parse each item in response.output
    for idx, item in enumerate(response.output or []):
        if isinstance(item, ResponseFunctionToolCall):
            debug_info["output_items"].append({
                "index": idx,
                "type": "ResponseFunctionToolCall",
                "name": item.name,
                "call_id": item.call_id,
                "arguments": item.arguments,
            })
        elif isinstance(item, ResponseOutputMessage):
            debug_info["output_items"].append({
                "index": idx,
                "type": "ResponseOutputMessage",
                "role": getattr(item, "role", "unknown"),
                "content": extract_text(item),
            })
        else:
            # For ResponseReasoningItem and other types, just note them
            debug_info["output_items"].append({
                "index": idx,
                "type": type(item).__name__,
                "note": f"Type: {type(item).__name__} (encrypted or non-text content)",
                "has_attributes": list(vars(item).keys()) if hasattr(item, "__dict__") else "no __dict__",
            })
    
    try:
        log_file.write_text(json.dumps(debug_info, indent=2, ensure_ascii=False), encoding="utf-8")
    except (TypeError, ValueError) as e:
        LOGGER.error(
            "Failed to serialize debug_info for %s (round %d): %s\nProblematic data: %r",
            class_name,
            round_idx,
            e,
            debug_info,
        )
        return
    LOGGER.info(
        "[%s] Response logged to %s (round %d, %d items)",
        class_name,
        log_file,
        round_idx,
        debug_info["output_length"]
    )

