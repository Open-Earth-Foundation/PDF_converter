"""
EmissionRecord -> sectorId mapping.

Structured output:
{
  "selections": [
    {"field": "sectorId", "id": "<uuid-or-null>", "reason": "<why this sector>"}
  ]
}
"""

from __future__ import annotations

import threading
from typing import Any

from mapping.utils import LLMSelector, summarise_record

PROMPT = (
    "You map EmissionRecord.sectorId. Choose the best sectorId from the options or null if nothing fits. "
    "Favor semantic alignment between scope/notes and sector names. Only use ids from options."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_emission_sector(
    records: list[dict],
    sector_options: list[dict],
    selector: LLMSelector,
    batch_size: int = 15,
    api_semaphore: threading.Semaphore | None = None,
) -> None:
    """Populate sectorId on emission records using the LLM with batch processing."""
    if not sector_options:
        for record in records:
            record["sectorId"] = None
        return

    candidate_sets = [{"field": "sectorId", "options": sector_options}]

    # Process in batches (sequential within mapper, but throttled by semaphore)
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        batch_summaries = [
            summarise_record(
                r, ["year", "scope", "ghgType", "value", "unit", "notes", "misc"]
            )
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
                batch_label=f"EmissionRecord_batch_{i // batch_size}",
            )

            # Apply selections to batch
            for record, selections in zip(batch, batch_selections):
                if "sectorId" in selections:
                    record["sectorId"] = selections["sectorId"]
        finally:
            if api_semaphore:
                api_semaphore.release()  # Release semaphore after API call


__all__ = ["map_emission_sector", "PROMPT", "RESPONSE_FORMAT"]
