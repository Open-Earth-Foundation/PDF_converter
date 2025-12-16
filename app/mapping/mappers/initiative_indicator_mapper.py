"""
InitiativeIndicator -> initiativeId, indicatorId mapping.

Structured output:
{
  "selections": [
    {"field": "initiativeId", "id": "<uuid-or-null>", "reason": "<why this initiative>"},
    {"field": "indicatorId", "id": "<uuid-or-null>", "reason": "<why this indicator>"}
  ]
}
"""

from __future__ import annotations

from app.mapping.llm_utils import LLMSelector, summarise_record

PROMPT = (
    "You map InitiativeIndicator to initiativeId and indicatorId. Choose the best matches using contributionType, "
    "expectedChange, notes, and the overall semantics. Only use ids from options or null."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_initiative_indicator(
    records: list[dict],
    initiative_options: list[dict],
    indicator_options: list[dict],
    selector: LLMSelector,
) -> None:
    """Populate initiativeId and indicatorId on InitiativeIndicator records."""
    for record in records:
        candidate_sets = [
            {"field": "initiativeId", "options": initiative_options},
            {"field": "indicatorId", "options": indicator_options},
        ]
        summary = summarise_record(record, ["contributionType", "expectedChange", "notes"])
        selections = selector.select_fields(
            record_label="InitiativeIndicator",
            record=summary,
            candidate_sets=candidate_sets,
            prompt=PROMPT,
            response_format=RESPONSE_FORMAT,
        )
        for field in ("initiativeId", "indicatorId"):
            if field in selections:
                record[field] = selections[field]


__all__ = ["map_initiative_indicator", "PROMPT", "RESPONSE_FORMAT"]
