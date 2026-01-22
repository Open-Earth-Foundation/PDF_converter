"""
BudgetFunding -> budgetId, fundingSourceId mapping.

Structured output:
{
  "selections": [
    {"field": "budgetId", "id": "<uuid-or-null>", "reason": "<why this budget>"},
    {"field": "fundingSourceId", "id": "<uuid-or-null>", "reason": "<why this funding source>"}
  ]
}
"""

from __future__ import annotations

import threading

from mapping.utils import LLMSelector, summarise_record

PROMPT = (
    "You map BudgetFunding to its budgetId and fundingSourceId. Select the best matching ids from the provided options "
    "using the notes, amount, currency, and misc context. Only use ids from options or null."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_budget_funding(
    records: list[dict],
    budget_options: list[dict],
    funding_options: list[dict],
    selector: LLMSelector,
    batch_size: int = 15,
    api_semaphore: threading.Semaphore | None = None,
) -> None:
    """Populate budgetId and fundingSourceId on BudgetFunding records with batch processing."""
    candidate_sets = [
        {"field": "budgetId", "options": budget_options},
        {"field": "fundingSourceId", "options": funding_options},
    ]

    # Process in batches (sequential within mapper, but throttled by semaphore)
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        batch_summaries = [
            summarise_record(r, ["amount", "currency", "notes", "misc"]) for r in batch
        ]

        # Acquire semaphore before API call (if provided)
        if api_semaphore:
            api_semaphore.acquire()

        try:
            batch_selections = selector.select_fields_batch(
                records=batch_summaries,
                candidate_sets=candidate_sets,
                prompt=PROMPT,
                response_format=RESPONSE_FORMAT,
                batch_label=f"BudgetFunding_batch_{i // batch_size}",
            )

            # Apply selections to batch
            for record, selections in zip(batch, batch_selections):
                for field in ("budgetId", "fundingSourceId"):
                    if field in selections:
                        record[field] = selections[field]
        finally:
            if api_semaphore:
                api_semaphore.release()  # Release semaphore after API call


__all__ = ["map_budget_funding", "PROMPT", "RESPONSE_FORMAT"]
