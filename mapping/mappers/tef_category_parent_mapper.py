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

import threading

from mapping.utils import LLMSelector, summarise_record

PROMPT = (
    "You map TefCategory.parentId. Pick the parent TEF category (or null) that best matches this category. "
    "Never select the category itself as its parent. Only use ids from options or null."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_tef_parent(
    records: list[dict],
    tef_options: list[dict],
    selector: LLMSelector,
    batch_size: int = 15,
    api_semaphore: threading.Semaphore | None = None,
) -> None:
    """Populate parentId on TefCategory records with batch processing."""
    # Process in batches (sequential within mapper, but throttled by semaphore)
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        batch_summaries = []
        for r in batch:
            # Filter options to exclude self-reference
            filtered_options = [
                opt for opt in tef_options if opt.get("id") != r.get("tefId")
            ]
            summary = summarise_record(r, ["code", "name", "description"])
            batch_summaries.append((summary, filtered_options))

        # Acquire semaphore before API call (if provided)
        if api_semaphore:
            api_semaphore.acquire()

        try:
            # Process all records in batch with filtered options
            for record, (summary, filtered_options) in zip(batch, batch_summaries):
                candidate_sets = [{"field": "parentId", "options": filtered_options}]
                batch_selections = selector.select_fields_batch(
                    records=[summary],
                    candidate_sets=candidate_sets,
                    prompt=PROMPT,
                    response_format=RESPONSE_FORMAT,
                    batch_label=f"TefCategory_batch_{i // batch_size}_record_{batch.index(record)}",
                )

                # Apply selections
                if batch_selections and "parentId" in batch_selections[0]:
                    record["parentId"] = batch_selections[0]["parentId"]
        finally:
            if api_semaphore:
                api_semaphore.release()  # Release semaphore after API call


__all__ = ["map_tef_parent", "PROMPT", "RESPONSE_FORMAT"]
