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

from typing import Any

from mapping.utils import LLMSelector, summarise_record

PROMPT = (
    "You map EmissionRecord.sectorId. Choose the best sectorId from the options or null if nothing fits. "
    "Favor semantic alignment between scope/notes and sector names. Only use ids from options."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_emission_sector(records: list[dict], sector_options: list[dict], selector: LLMSelector) -> None:
    """Populate sectorId on emission records using the LLM."""
    if not sector_options:
        for record in records:
            record["sectorId"] = None
        return

    for record in records:
        candidate_sets = [{"field": "sectorId", "options": sector_options}]
        summary = summarise_record(record, ["year", "scope", "ghgType", "value", "unit", "notes", "misc"])
        selections = selector.select_fields(
            record_label="EmissionRecord",
            record=summary,
            candidate_sets=candidate_sets,
            prompt=PROMPT,
            response_format=RESPONSE_FORMAT,
        )
        if "sectorId" in selections:
            record["sectorId"] = selections["sectorId"]


__all__ = ["map_emission_sector", "PROMPT", "RESPONSE_FORMAT"]
