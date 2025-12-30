"""
InitiativeTef -> initiativeId, tefId mapping.

Structured output:
{
  "selections": [
    {"field": "initiativeId", "id": "<uuid-or-null>", "reason": "<why this initiative>"},
    {"field": "tefId", "id": "<uuid-or-null>", "reason": "<why this TEF category>"}
  ]
}
"""

from __future__ import annotations

from mapping.utils import LLMSelector, summarise_record

PROMPT = (
    "You map InitiativeTef to initiativeId and tefId. Choose the best matches using the notes/context. "
    "Only use ids from options or null."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_initiative_tef(
    records: list[dict],
    initiative_options: list[dict],
    tef_options: list[dict],
    selector: LLMSelector,
) -> None:
    """Populate initiativeId and tefId on InitiativeTef records."""
    for record in records:
        candidate_sets = [
            {"field": "initiativeId", "options": initiative_options},
            {"field": "tefId", "options": tef_options},
        ]
        summary = summarise_record(record, ["notes"])
        selections = selector.select_fields(
            record_label="InitiativeTef",
            record=summary,
            candidate_sets=candidate_sets,
            prompt=PROMPT,
            response_format=RESPONSE_FORMAT,
        )
        for field in ("initiativeId", "tefId"):
            if field in selections:
                record[field] = selections[field]


__all__ = ["map_initiative_tef", "PROMPT", "RESPONSE_FORMAT"]
