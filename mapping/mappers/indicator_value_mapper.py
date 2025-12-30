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

from mapping.utils import LLMSelector, summarise_record

PROMPT = (
    "You map IndicatorValue to indicatorId. Choose the indicator that best matches the value context (year, value, "
    "valueType, notes). Only use ids from the provided options or null."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_indicator_value(records: list[dict], indicator_options: list[dict], selector: LLMSelector) -> None:
    """Populate indicatorId on IndicatorValue records."""
    for record in records:
        candidate_sets = [{"field": "indicatorId", "options": indicator_options}]
        summary = summarise_record(record, ["year", "value", "valueType", "notes", "misc"])
        selections = selector.select_fields(
            record_label="IndicatorValue",
            record=summary,
            candidate_sets=candidate_sets,
            prompt=PROMPT,
            response_format=RESPONSE_FORMAT,
        )
        if "indicatorId" in selections:
            record["indicatorId"] = selections["indicatorId"]


__all__ = ["map_indicator_value", "PROMPT", "RESPONSE_FORMAT"]
