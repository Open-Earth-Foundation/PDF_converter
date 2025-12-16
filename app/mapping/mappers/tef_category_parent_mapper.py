"""
TefCategory -> parentId mapping.

Structured output:
{
  "selections": [
    {"field": "parentId", "id": "<uuid-or-null>", "reason": "<why this parent>"}
  ]
}
"""

from __future__ import annotations

from app.mapping.llm_utils import LLMSelector, summarise_record

PROMPT = (
    "You map TefCategory.parentId. Pick the parent TEF category (or null) that best matches this category. "
    "Never select the category itself as its parent. Only use ids from options or null."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_tef_parent(records: list[dict], tef_options: list[dict], selector: LLMSelector) -> None:
    """Populate parentId on TefCategory records."""
    for record in records:
        filtered_options = [opt for opt in tef_options if opt.get("id") != record.get("tefId")]
        candidate_sets = [{"field": "parentId", "options": filtered_options}]
        summary = summarise_record(record, ["code", "name", "description"])
        selections = selector.select_fields(
            record_label="TefCategory",
            record=summary,
            candidate_sets=candidate_sets,
            prompt=PROMPT,
            response_format=RESPONSE_FORMAT,
        )
        if "parentId" in selections:
            record["parentId"] = selections["parentId"]


__all__ = ["map_tef_parent", "PROMPT", "RESPONSE_FORMAT"]
