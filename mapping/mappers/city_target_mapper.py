"""
CityTarget -> indicatorId mapping.

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
    "You map CityTarget.indicatorId. Choose the indicator that aligns with the target description, target year/value, "
    "baseline, and notes. Only use ids from options or null."
)

RESPONSE_FORMAT = {"type": "json_object"}


def map_city_target(records: list[dict], indicator_options: list[dict], selector: LLMSelector) -> None:
    """Populate indicatorId on CityTarget records."""
    for record in records:
        candidate_sets = [{"field": "indicatorId", "options": indicator_options}]
        summary = summarise_record(
            record, ["description", "targetYear", "targetValue", "baselineYear", "baselineValue", "status", "notes"]
        )
        selections = selector.select_fields(
            record_label="CityTarget",
            record=summary,
            candidate_sets=candidate_sets,
            prompt=PROMPT,
            response_format=RESPONSE_FORMAT,
        )
        if "indicatorId" in selections:
            record["indicatorId"] = selections["indicatorId"]


__all__ = ["map_city_target", "PROMPT", "RESPONSE_FORMAT"]
