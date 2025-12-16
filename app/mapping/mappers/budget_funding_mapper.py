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

from app.mapping.llm_utils import LLMSelector, summarise_record

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
) -> None:
    """Populate budgetId and fundingSourceId on BudgetFunding records."""
    for record in records:
        candidate_sets = [
            {"field": "budgetId", "options": budget_options},
            {"field": "fundingSourceId", "options": funding_options},
        ]
        summary = summarise_record(record, ["amount", "currency", "notes", "misc"])
        selections = selector.select_fields(
            record_label="BudgetFunding",
            record=summary,
            candidate_sets=candidate_sets,
            prompt=PROMPT,
            response_format=RESPONSE_FORMAT,
        )
        for field in ("budgetId", "fundingSourceId"):
            if field in selections:
                record[field] = selections[field]


__all__ = ["map_budget_funding", "PROMPT", "RESPONSE_FORMAT"]
