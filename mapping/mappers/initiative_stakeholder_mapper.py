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

import threading

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
    batch_size: int = 15,
    api_semaphore: threading.Semaphore | None = None,
    prompt_suffix: str | None = None,
    feedback: list[str | None] | None = None,
) -> None:
    """Populate initiativeId and stakeholderId on InitiativeStakeholder records with batch processing."""
    prompt = PROMPT
    if prompt_suffix:
        prompt = f"{PROMPT} {prompt_suffix.strip()}"

    candidate_sets = [
        {"field": "initiativeId", "options": initiative_options},
        {"field": "stakeholderId", "options": stakeholder_options},
    ]

    # Process in batches (sequential within mapper, but throttled by semaphore)
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        batch_feedback = feedback[i : i + batch_size] if feedback else None
        batch_summaries = [
            summarise_record(
                r,
                ["role", "notes", "misc"],
                feedback=batch_feedback[idx] if batch_feedback else None,
            )
            for idx, r in enumerate(batch)
        ]

        # Acquire semaphore before API call (if provided)
        if api_semaphore:
            api_semaphore.acquire()

        try:
            batch_selections = selector.select_fields_batch(
                records=batch_summaries,
                candidate_sets=candidate_sets,
                prompt=prompt,
                response_format=RESPONSE_FORMAT,
                batch_label=f"InitiativeStakeholder_batch_{i // batch_size}",
            )

            # Apply selections to batch
            for record, selections in zip(batch, batch_selections):
                for field in ("initiativeId", "stakeholderId"):
                    if field in selections:
                        record[field] = selections[field]
        finally:
            if api_semaphore:
                api_semaphore.release()  # Release semaphore after API call


__all__ = ["map_initiative_stakeholder", "PROMPT", "RESPONSE_FORMAT"]
