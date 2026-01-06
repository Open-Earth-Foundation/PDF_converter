"""
InitiativeStakeholder -> initiativeId, stakeholderId mapping.

Structured output:
{
  "selections": [
    {"field": "initiativeId", "id": "<uuid-or-null>", "reason": "<why this initiative>"},
    {"field": "stakeholderId", "id": "<uuid-or-null>", "reason": "<why this stakeholder>"}
  ]
}
"""

from __future__ import annotations

from mapping.utils import LLMSelector, summarise_record

PROMPT = (
    "You map InitiativeStakeholder to initiativeId and stakeholderId. Use role, notes, and misc to choose the best "
    "matches from the provided options. Only use ids from options or null if no match is confident. "
    "Example: if the record mentions 'European Energy Exchange' and the options include 'Energy Exchange Services GmbH', "
    "pick that stakeholderId because it refers to the same organization."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_initiative_stakeholder(
    records: list[dict],
    initiative_options: list[dict],
    stakeholder_options: list[dict],
    selector: LLMSelector,
) -> None:
    """Populate initiativeId and stakeholderId on InitiativeStakeholder records."""
    for record in records:
        candidate_sets = [
            {"field": "initiativeId", "options": initiative_options},
            {"field": "stakeholderId", "options": stakeholder_options},
        ]

        summary = summarise_record(record, ["role", "notes", "misc"])
        selections = selector.select_fields(
            record_label="InitiativeStakeholder",
            record=summary,
            candidate_sets=candidate_sets,
            prompt=PROMPT,
            response_format=RESPONSE_FORMAT,
        )
        for field in ("initiativeId", "stakeholderId"):
            if field in selections:
                record[field] = selections[field]


__all__ = ["map_initiative_stakeholder", "PROMPT", "RESPONSE_FORMAT"]
