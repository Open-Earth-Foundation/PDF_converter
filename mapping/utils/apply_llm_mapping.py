"""
LLM-assisted mapping orchestrator. Each mapping is defined in its own module with a prompt and structured output.

Workflow expectation:
- Run clear_foreign_keys.py --apply (remove hallucinated FKs).
- Run apply_city_mapping.py --apply (sets canonical cityId).
- Run this script to map remaining foreign keys with an LLM choosing IDs.

Features:
- Batch processing: Multiple records per LLM call (configurable batch size)
- Parallel execution: Independent mapper groups run in parallel
- Rate limiting: Semaphore controls concurrent API calls to prevent rate limits
"""

from __future__ import annotations

import argparse
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from utils import load_llm_config
from mapping.utils import (
    LLMSelector,
    build_options,
    load_json_list,
    set_canonical_city_id,
    set_city_id,
    write_json,
)
from mapping.mappers.budget_funding_mapper import map_budget_funding
from mapping.mappers.city_target_mapper import map_city_target
from mapping.mappers.emission_sector_mapper import map_emission_sector
from mapping.mappers.indicator_sector_mapper import map_indicator_sector
from mapping.mappers.indicator_value_mapper import map_indicator_value
from mapping.mappers.initiative_indicator_mapper import map_initiative_indicator
from mapping.mappers.initiative_stakeholder_mapper import map_initiative_stakeholder
from mapping.mappers.initiative_tef_mapper import map_initiative_tef
from mapping.mappers.tef_category_parent_mapper import map_tef_parent

MAPPING_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = Path(__file__).resolve().parents[2]
CITY_MAPPED_DIR = MAPPING_DIR / "output"
EXTRACTION_DIR = ROOT_DIR / "extraction" / "output"
DEFAULT_INPUT_DIR = CITY_MAPPED_DIR if CITY_MAPPED_DIR.exists() else EXTRACTION_DIR
DEFAULT_OUTPUT_DIR = MAPPING_DIR / "mapped_output"

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LLM-assisted foreign key mapping with batch processing and parallel execution."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory to read JSON inputs from.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory to write mapped JSON outputs (dry-run if --apply not set).",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LLM model name (defaults to llm_config.yml mapping.model).",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Persist mapped JSON files."
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=15,
        help="Records per LLM batch call (default: 15). Smaller = more calls, Larger = higher token usage.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Max parallel mappers per group (default: 4).",
    )
    parser.add_argument(
        "--max-concurrent-api-calls",
        type=int,
        default=5,
        help="Max concurrent API requests across all parallel mappers (default: 5).",
    )
    return parser.parse_args()


def run_llm_mapping(
    *,
    input_dir: Path,
    output_dir: Path,
    model_name: str,
    apply: bool,
    client: OpenAI | None = None,
    batch_size: int = 15,
    max_workers: int = 4,
    max_concurrent_api_calls: int = 5,
) -> dict[str, list[dict]]:
    """Execute modular LLM mapping with batch processing and parallel execution."""
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
        initiative_stakeholders = load_json_list(
            input_dir / "InitiativeStakeholder.json"
        )
        indicators = load_json_list(input_dir / "Indicator.json")
        indicator_values = load_json_list(input_dir / "IndicatorValue.json")
        city_targets = load_json_list(input_dir / "CityTarget.json")
        initiative_indicators = load_json_list(input_dir / "InitiativeIndicator.json")
        sectors = load_json_list(input_dir / "Sector.json")
        tef_categories = load_json_list(input_dir / "TefCategory.json")
        initiative_tef = load_json_list(input_dir / "InitiativeTef.json")
    except ValueError as exc:
        raise RuntimeError(f"Failed to load input data: {exc}") from exc

    # Canonical city application (derive from extracted City)
    canonical_city_id = city_records[0].get("cityId") if city_records else None
    set_canonical_city_id(canonical_city_id)
    set_city_id(city_records, ["cityId"], canonical_city_id)
    set_city_id(climate_contracts, ["cityId"], canonical_city_id)
    set_city_id(city_stats, ["cityId"], canonical_city_id)
    set_city_id(emissions, ["cityId"], canonical_city_id)
    set_city_id(city_budgets, ["cityId"], canonical_city_id)
    set_city_id(initiatives, ["cityId"], canonical_city_id)
    set_city_id(indicators, ["cityId"], canonical_city_id)
    set_city_id(city_targets, ["cityId"], canonical_city_id)

    # Build selection options
    sector_options = build_options(sectors, "sectorId", ("sectorName", "description"))
    indicator_options = build_options(
        indicators, "indicatorId", ("name", "description")
    )
    initiative_options = build_options(
        initiatives, "initiativeId", ("title", "description")
    )
    stakeholder_options = build_options(stakeholders, "stakeholderId", ("name", "type"))
    budget_options = build_options(
        city_budgets, "budgetId", ("description", "year", "totalAmount")
    )
    funding_options = build_options(
        funding_sources, "fundingSourceId", ("name", "type", "description")
    )
    tef_options = build_options(
        tef_categories, "tefId", ("code", "name", "description")
    )

    # Create shared semaphore to throttle API calls across all parallel mappers
    api_semaphore = threading.Semaphore(max_concurrent_api_calls)

    LOGGER.info(
        "Starting parallel mapping with batch_size=%d, max_workers=%d, max_concurrent_api_calls=%d",
        batch_size,
        max_workers,
        max_concurrent_api_calls,
    )

    # Group 1: Sector mappings (2 parallel mappers, batches throttled by semaphore)
    LOGGER.info("Group 1: Sector mappings (emission_sector, indicator_sector)...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(
                map_emission_sector,
                emissions,
                sector_options,
                selector,
                batch_size,
                api_semaphore,
            ): "emission_sector",
            executor.submit(
                map_indicator_sector,
                indicators,
                sector_options,
                selector,
                batch_size,
                api_semaphore,
            ): "indicator_sector",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                LOGGER.info("Completed %s mapping", name)
            except Exception as exc:
                LOGGER.error("Failed %s mapping: %s", name, exc)
                raise

    # Group 2: Budget/Funding (single mapper, but batched internally)
    LOGGER.info("Group 2: Budget funding mappings...")
    map_budget_funding(
        budget_funding,
        budget_options,
        funding_options,
        selector,
        batch_size,
        api_semaphore,
    )
    LOGGER.info("Completed budget_funding mapping")

    # Group 3: Initiative mappings (3 parallel mappers)
    LOGGER.info("Group 3: Initiative mappings (stakeholder, indicator, tef)...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(
                map_initiative_stakeholder,
                initiative_stakeholders,
                initiative_options,
                stakeholder_options,
                selector,
                batch_size,
                api_semaphore,
            ): "initiative_stakeholder",
            executor.submit(
                map_initiative_indicator,
                initiative_indicators,
                initiative_options,
                indicator_options,
                selector,
                batch_size,
                api_semaphore,
            ): "initiative_indicator",
            executor.submit(
                map_initiative_tef,
                initiative_tef,
                initiative_options,
                tef_options,
                selector,
                batch_size,
                api_semaphore,
            ): "initiative_tef",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                LOGGER.info("Completed %s mapping", name)
            except Exception as exc:
                LOGGER.error("Failed %s mapping: %s", name, exc)
                raise

    # Group 4: Indicator mappings (2 parallel mappers)
    LOGGER.info("Group 4: Indicator mappings (indicator_value, city_target)...")
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(
                map_indicator_value,
                indicator_values,
                indicator_options,
                selector,
                batch_size,
                api_semaphore,
            ): "indicator_value",
            executor.submit(
                map_city_target,
                city_targets,
                indicator_options,
                selector,
                batch_size,
                api_semaphore,
            ): "city_target",
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                future.result()
                LOGGER.info("Completed %s mapping", name)
            except Exception as exc:
                LOGGER.error("Failed %s mapping: %s", name, exc)
                raise

    # Group 5: Self-referential (sequential, after Group 3)
    LOGGER.info("Group 5: TEF category parent mapping...")
    map_tef_parent(tef_categories, tef_options, selector, batch_size, api_semaphore)
    LOGGER.info("Completed tef_parent mapping")

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


def main() -> int:
    args = parse_args()
    llm_cfg = load_llm_config().get("mapping", {})
    model_name = args.model or llm_cfg.get("model")
    if not model_name:
        raise RuntimeError(
            "Mapping model not configured. Set mapping.model in llm_config.yml."
        )

    outputs = run_llm_mapping(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        model_name=model_name,
        apply=args.apply,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        max_concurrent_api_calls=args.max_concurrent_api_calls,
    )

    for fname, payload in outputs.items():
        LOGGER.info(
            "%s: records=%s %s",
            fname,
            len(payload),
            "(written)" if args.apply else "(dry-run)",
        )

    if args.apply:
        LOGGER.info("Mapped files written to: %s", args.output_dir)
    else:
        LOGGER.info("Dry run only. Re-run with --apply to persist.")
    return 0
