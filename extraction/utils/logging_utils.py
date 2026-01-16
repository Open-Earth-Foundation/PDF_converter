"""Logging utilities."""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage

from extraction.utils.data_utils import extract_text

if TYPE_CHECKING:
    from openai.types.responses import Response

LOGGER = logging.getLogger(__name__)

LOG_SNIPPET_LEN = 320
DEBUG_LOG_DIR = Path(__file__).resolve().parent.parent / "debug_logs"


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


def log_full_response(class_name: str, response: object, round_idx: int, config: dict | None = None) -> None:
    """Write full response to a debug log file for inspection."""
    if config is not None and not config.get("debug_logs_enabled", True):
        LOGGER.debug("Debug logging disabled; skipping full response log for %s (round %d)", class_name, round_idx)
        return

    DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = DEBUG_LOG_DIR / f"{class_name}_round{round_idx}.json"

    debug_info = {
        "response_id": getattr(response, "id", None),
        "model": getattr(response, "model", None),
        "status": getattr(response, "status", None),
        "output_items": [],
    }

    # Responses API
    if hasattr(response, "output"):
        output_items = getattr(response, "output") or []
        debug_info["output_length"] = len(output_items)
        for idx, item in enumerate(output_items):
            if isinstance(item, ResponseFunctionToolCall):
                debug_info["output_items"].append(
                    {
                        "index": idx,
                        "type": "ResponseFunctionToolCall",
                        "name": item.name,
                        "call_id": item.call_id,
                        "arguments": item.arguments,
                    }
                )
            elif isinstance(item, ResponseOutputMessage):
                debug_info["output_items"].append(
                    {
                        "index": idx,
                        "type": "ResponseOutputMessage",
                        "role": getattr(item, "role", "unknown"),
                        "content": extract_text(item),
                    }
                )
            else:
                debug_info["output_items"].append(
                    {
                        "index": idx,
                        "type": type(item).__name__,
                        "note": f"Type: {type(item).__name__} (encrypted or non-text content)",
                        "has_attributes": list(vars(item).keys()) if hasattr(item, "__dict__") else "no __dict__",
                    }
                )
    # chat.completions API
    elif hasattr(response, "choices"):
        choices = getattr(response, "choices") or []
        if not choices:
            debug_info["output_length"] = 0
            debug_info["assistant_content"] = None
        else:
            choice = choices[0]
            message = getattr(choice, "message", None)
            tool_calls = getattr(message, "tool_calls", None) if message else None
            debug_info["output_length"] = len(tool_calls or [])
            debug_info["assistant_content"] = getattr(message, "content", None) if message else None
            if tool_calls:
                for idx, tc in enumerate(tool_calls):
                    debug_info["output_items"].append(
                        {
                            "index": idx,
                            "type": "ChatCompletionToolCall",
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                    )
    else:
        debug_info["output_length"] = 0

    try:
        log_file.write_text(json.dumps(debug_info, indent=2, ensure_ascii=False), encoding="utf-8")
    except (TypeError, ValueError) as exc:
        LOGGER.error(
            "Failed to serialize debug_info for %s (round %d): %s\nProblematic data: %r",
            class_name,
            round_idx,
            exc,
            debug_info,
        )
        return

    LOGGER.info(
        "[%s] Response logged to %s (round %d, %d items)",
        class_name,
        log_file,
        round_idx,
        debug_info.get("output_length", 0),
    )

