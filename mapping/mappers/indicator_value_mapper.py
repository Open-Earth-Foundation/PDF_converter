"""
IndicatorValue -> indicatorId mapping.

Structured output:
{
  "selections": [
    {"field": "indicatorId", "id": "<uuid-or-null>", "reason": "<why this indicator>"}
  ]
}
"""

from __future__ import annotations

import threading

from mapping.utils import LLMSelector, summarise_record

PROMPT = (
    "You map IndicatorValue to indicatorId. Choose the indicator that best matches the value context (year, value, "
    "valueType, notes). Only use ids from the provided options or null."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_indicator_value(
    records: list[dict],
    indicator_options: list[dict],
    selector: LLMSelector,
    batch_size: int = 15,
    api_semaphore: threading.Semaphore | None = None,
) -> None:
    """Populate indicatorId on IndicatorValue records with batch processing."""
    candidate_sets = [{"field": "indicatorId", "options": indicator_options}]

    # Process in batches (sequential within mapper, but throttled by semaphore)
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        batch_summaries = [
            summarise_record(r, ["year", "value", "valueType", "notes", "misc"])
            for r in batch
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
                batch_label=f"IndicatorValue_batch_{i // batch_size}",
            )

            # Apply selections to batch
            for record, selections in zip(batch, batch_selections):
                if "indicatorId" in selections:
                    record["indicatorId"] = selections["indicatorId"]
        finally:
            if api_semaphore:
                api_semaphore.release()  # Release semaphore after API call


__all__ = ["map_indicator_value", "PROMPT", "RESPONSE_FORMAT"]
