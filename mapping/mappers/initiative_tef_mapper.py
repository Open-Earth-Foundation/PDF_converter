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

import threading

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
    batch_size: int = 15,
    api_semaphore: threading.Semaphore | None = None,
) -> None:
    """Populate initiativeId and tefId on InitiativeTef records with batch processing."""
    candidate_sets = [
        {"field": "initiativeId", "options": initiative_options},
        {"field": "tefId", "options": tef_options},
    ]

    # Process in batches (sequential within mapper, but throttled by semaphore)
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        batch_summaries = [summarise_record(r, ["notes"]) for r in batch]

        # Acquire semaphore before API call (if provided)
        if api_semaphore:
            api_semaphore.acquire()

        try:
            batch_selections = selector.select_fields_batch(
                records=batch_summaries,
                candidate_sets=candidate_sets,
                prompt=PROMPT,
                response_format=RESPONSE_FORMAT,
                batch_label=f"InitiativeTef_batch_{i // batch_size}",
            )

            # Apply selections to batch
            for record, selections in zip(batch, batch_selections):
                for field in ("initiativeId", "tefId"):
                    if field in selections:
                        record[field] = selections[field]
        finally:
            if api_semaphore:
                api_semaphore.release()  # Release semaphore after API call


__all__ = ["map_initiative_tef", "PROMPT", "RESPONSE_FORMAT"]
