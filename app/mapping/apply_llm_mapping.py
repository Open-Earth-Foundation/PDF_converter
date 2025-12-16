"""
LLM-assisted mapping orchestrator. Each mapping is defined in its own module with a prompt and structured output.

Workflow expectation:
- Run clear_foreign_keys.py --apply (remove hallucinated FKs).
- Run apply_city_mapping.py --apply (sets canonical cityId).
- Run this script to map remaining foreign keys with an LLM choosing IDs.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from app.mapping.llm_utils import LLMSelector, build_options, load_json_list, set_city_id, write_json
from app.mapping.mappers.budget_funding_mapper import map_budget_funding
from app.mapping.mappers.city_target_mapper import map_city_target
from app.mapping.mappers.emission_sector_mapper import map_emission_sector
from app.mapping.mappers.indicator_sector_mapper import map_indicator_sector
from app.mapping.mappers.indicator_value_mapper import map_indicator_value
from app.mapping.mappers.initiative_indicator_mapper import map_initiative_indicator
from app.mapping.mappers.initiative_stakeholder_mapper import map_initiative_stakeholder
from app.mapping.mappers.initiative_tef_mapper import map_initiative_tef
from app.mapping.mappers.tef_category_parent_mapper import map_tef_parent

BASE_DIR = Path(__file__).resolve().parent
CITY_MAPPED_DIR = BASE_DIR / "output"
EXTRACTION_DIR = BASE_DIR.parent / "extraction" / "output"
DEFAULT_INPUT_DIR = CITY_MAPPED_DIR if CITY_MAPPED_DIR.exists() else EXTRACTION_DIR
DEFAULT_OUTPUT_DIR = BASE_DIR / "mapped_output"




def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="LLM-assisted foreign key mapping (modular).")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR, help="Directory to read JSON inputs from.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write mapped JSON outputs (dry-run if --apply not set).",
    )
    parser.add_argument("--model", default=os.getenv("OPENROUTER_MODEL", "gpt-4o-mini"), help="LLM model name.")
    parser.add_argument("--apply", action="store_true", help="Persist mapped JSON files.")
    return parser.parse_args()


def run_llm_mapping(
    *,
    input_dir: Path,
    output_dir: Path,
    model_name: str,
    apply: bool,
    client: OpenAI | None = None,
) -> dict[str, list[dict]]:
    """Execute modular LLM mapping and return mapped payloads."""
    load_dotenv()
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if client is None:
        if not openrouter_key:
            raise RuntimeError("OPENROUTER_API_KEY must be set for LLM mapping.")
        client = OpenAI(api_key=openrouter_key, base_url=base_url or None)

    selector = LLMSelector(client, model_name)

    # Load inputs - load_json_list raises ValueError on corrupted files (prevents silent data loss)
    try:
        city_records = load_json_list(input_dir / "City.json")
        climate_contracts = load_json_list(input_dir / "ClimateCityContract.json")
        city_stats = load_json_list(input_dir / "CityAnnualStats.json")
        emissions = load_json_list(input_dir / "EmissionRecord.json")
        city_budgets = load_json_list(input_dir / "CityBudget.json")
        funding_sources = load_json_list(input_dir / "FundingSource.json")
        budget_funding = load_json_list(input_dir / "BudgetFunding.json")
        initiatives = load_json_list(input_dir / "Initiative.json")
        stakeholders = load_json_list(input_dir / "Stakeholder.json")
        initiative_stakeholders = load_json_list(input_dir / "InitiativeStakeholder.json")
        indicators = load_json_list(input_dir / "Indicator.json")
        indicator_values = load_json_list(input_dir / "IndicatorValue.json")
        city_targets = load_json_list(input_dir / "CityTarget.json")
        initiative_indicators = load_json_list(input_dir / "InitiativeIndicator.json")
        sectors = load_json_list(input_dir / "Sector.json")
        tef_categories = load_json_list(input_dir / "TefCategory.json")
        initiative_tef = load_json_list(input_dir / "InitiativeTef.json")
    except ValueError as exc:
        raise RuntimeError(f"Failed to load input data: {exc}") from exc

    # Canonical city application (idempotent)
    set_city_id(city_records, ["cityId"])
    set_city_id(climate_contracts, ["cityId"])
    set_city_id(city_stats, ["cityId"])
    set_city_id(emissions, ["cityId"])
    set_city_id(city_budgets, ["cityId"])
    set_city_id(initiatives, ["cityId"])
    set_city_id(indicators, ["cityId"])
    set_city_id(city_targets, ["cityId"])

    # Build selection options
    sector_options = build_options(sectors, "sectorId", ("sectorName", "description"))
    indicator_options = build_options(indicators, "indicatorId", ("name", "description"))
    initiative_options = build_options(initiatives, "initiativeId", ("title", "description"))
    stakeholder_options = build_options(stakeholders, "stakeholderId", ("name", "type"))
    budget_options = build_options(city_budgets, "budgetId", ("description", "year", "totalAmount"))
    funding_options = build_options(funding_sources, "fundingSourceId", ("name", "type", "description"))
    tef_options = build_options(tef_categories, "tefId", ("code", "name", "description"))

    # Mapping steps (each module has its own prompt + schema)
    map_emission_sector(emissions, sector_options, selector)
    map_indicator_sector(indicators, sector_options, selector)
    map_budget_funding(budget_funding, budget_options, funding_options, selector)
    map_initiative_stakeholder(initiative_stakeholders, initiative_options, stakeholder_options, selector)
    map_indicator_value(indicator_values, indicator_options, selector)
    map_city_target(city_targets, indicator_options, selector)
    map_initiative_indicator(initiative_indicators, initiative_options, indicator_options, selector)
    map_initiative_tef(initiative_tef, initiative_options, tef_options, selector)
    map_tef_parent(tef_categories, tef_options, selector)

    outputs = {
        "City.json": city_records,
        "ClimateCityContract.json": climate_contracts,
        "CityAnnualStats.json": city_stats,
        "EmissionRecord.json": emissions,
        "CityBudget.json": city_budgets,
        "FundingSource.json": funding_sources,
        "BudgetFunding.json": budget_funding,
        "Initiative.json": initiatives,
        "Stakeholder.json": stakeholders,
        "InitiativeStakeholder.json": initiative_stakeholders,
        "Indicator.json": indicators,
        "IndicatorValue.json": indicator_values,
        "CityTarget.json": city_targets,
        "InitiativeIndicator.json": initiative_indicators,
        "Sector.json": sectors,
        "TefCategory.json": tef_categories,
        "InitiativeTef.json": initiative_tef,
    }

    if apply:
        for fname, payload in outputs.items():
            write_json(output_dir / fname, payload)

    return outputs


def main() -> None:
    args = parse_args()
    outputs = run_llm_mapping(
        input_dir=args.input_dir, output_dir=args.output_dir, model_name=args.model, apply=args.apply
    )

    for fname, payload in outputs.items():
        print(f"{fname}: records={len(payload)} {'(written)' if args.apply else '(dry-run)'}")

    if args.apply:
        print(f"\nMapped files written to: {args.output_dir}")
    else:
        print("\nDry run only. Re-run with --apply to persist.")


if __name__ == "__main__":
    main()
