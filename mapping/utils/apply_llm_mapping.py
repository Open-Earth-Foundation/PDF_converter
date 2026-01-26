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
from mapping.utils.retry_planner import build_retry_plan
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

DEFAULT_CITY_TARGET_STATUS = "unknown"

EXPECTED_INPUT_FILES = [
    "City.json",
    "ClimateCityContract.json",
    "CityAnnualStats.json",
    "EmissionRecord.json",
    "CityBudget.json",
    "FundingSource.json",
    "BudgetFunding.json",
    "Initiative.json",
    "Stakeholder.json",
    "InitiativeStakeholder.json",
    "Indicator.json",
    "IndicatorValue.json",
    "CityTarget.json",
    "InitiativeIndicator.json",
    "Sector.json",
    "TefCategory.json",
    "InitiativeTef.json",
]

MAPPER_TARGETS = {
    "emission_sector",
    "indicator_sector",
    "budget_funding",
    "initiative_stakeholder",
    "initiative_indicator",
    "initiative_tef",
    "indicator_value",
    "city_target",
    "tef_parent",
}

RETRY_TABLE_TO_MAPPER = {
    "EmissionRecord.json": "emission_sector",
    "Indicator.json": "indicator_sector",
    "BudgetFunding.json": "budget_funding",
    "InitiativeStakeholder.json": "initiative_stakeholder",
    "InitiativeIndicator.json": "initiative_indicator",
    "InitiativeTef.json": "initiative_tef",
    "IndicatorValue.json": "indicator_value",
    "CityTarget.json": "city_target",
    "TefCategory.json": "tef_parent",
}


def ensure_city_target_status(
    city_targets: list[dict], default_status: str = DEFAULT_CITY_TARGET_STATUS
) -> int:
    """Set a deterministic status for CityTarget records when missing."""
    updated = 0
    for target in city_targets:
        if target.get("status") in (None, ""):
            target["status"] = default_status
            misc = target.get("misc")
            if not isinstance(misc, dict):
                misc = {}
            misc.setdefault("status_source", "default")
            target["misc"] = misc
            updated += 1
    return updated


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
    parser.add_argument(
        "--only",
        default=None,
        help=(
            "Comma-separated mapper targets to run "
            "(e.g. emission_sector,indicator_sector)."
        ),
    )
    parser.add_argument(
        "--emission-guidance",
        default=None,
        help="Extra prompt guidance appended to the EmissionRecord sector mapper.",
    )
    parser.add_argument(
        "--retry-on-issues",
        action="store_true",
        help="Re-run LLM mapping for records with FK/duplicate issues using feedback.",
    )
    parser.add_argument(
        "--retry-rounds",
        type=int,
        default=1,
        help="Max retry rounds for re-mapping problematic records (default: 1).",
    )
    parser.add_argument(
        "--retry-max-duplicates",
        type=int,
        default=50,
        help="Max duplicate groups to include when planning retries (default: 50).",
    )
    parser.add_argument(
        "--use-option-indexes",
        action="store_true",
        help="Use numeric indexes for LLM option selection and map them back to IDs.",
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
    targets: set[str] | None = None,
    emission_guidance: str | None = None,
    retry_on_issues: bool = False,
    retry_max_rounds: int = 1,
    retry_max_duplicate_groups: int = 50,
    use_option_indexes: bool = False,
) -> dict[str, list[dict]]:
    """Execute modular LLM mapping with batch processing and parallel execution."""
    load_dotenv()
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    if client is None:
        if not openrouter_key:
            raise RuntimeError("OPENROUTER_API_KEY must be set for LLM mapping.")
        client = OpenAI(api_key=openrouter_key, base_url=base_url or None)

    selector = LLMSelector(
        client, model_name, use_option_indexes=use_option_indexes
    )

    if targets is not None and not targets:
        targets = None

    if targets:
        unknown = targets - MAPPER_TARGETS
        if unknown:
            raise RuntimeError(f"Unknown mapper target(s): {', '.join(sorted(unknown))}")

    # Load inputs - load_json_list raises ValueError on corrupted files (prevents silent data loss)
    try:
        all_inputs: dict[str, list[dict]] = {}
        for path in sorted(input_dir.glob("*.json")):
            all_inputs[path.name] = load_json_list(path)
        for fname in EXPECTED_INPUT_FILES:
            all_inputs.setdefault(fname, [])

        city_records = all_inputs["City.json"]
        climate_contracts = all_inputs["ClimateCityContract.json"]
        city_stats = all_inputs["CityAnnualStats.json"]
        emissions = all_inputs["EmissionRecord.json"]
        city_budgets = all_inputs["CityBudget.json"]
        funding_sources = all_inputs["FundingSource.json"]
        budget_funding = all_inputs["BudgetFunding.json"]
        initiatives = all_inputs["Initiative.json"]
        stakeholders = all_inputs["Stakeholder.json"]
        initiative_stakeholders = all_inputs["InitiativeStakeholder.json"]
        indicators = all_inputs["Indicator.json"]
        indicator_values = all_inputs["IndicatorValue.json"]
        city_targets = all_inputs["CityTarget.json"]
        initiative_indicators = all_inputs["InitiativeIndicator.json"]
        sectors = all_inputs["Sector.json"]
        tef_categories = all_inputs["TefCategory.json"]
        initiative_tef = all_inputs["InitiativeTef.json"]
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
    sector_options = build_options(
        sectors,
        "sectorId",
        ("sectorName", "description"),
        include_index=use_option_indexes,
    )
    indicator_options = build_options(
        indicators,
        "indicatorId",
        ("name", "description"),
        include_index=use_option_indexes,
    )
    initiative_options = build_options(
        initiatives,
        "initiativeId",
        ("title", "description"),
        include_index=use_option_indexes,
    )
    stakeholder_options = build_options(
        stakeholders,
        "stakeholderId",
        ("name", "type"),
        include_index=use_option_indexes,
    )
    budget_options = build_options(
        city_budgets,
        "budgetId",
        ("description", "year", "totalAmount"),
        include_index=use_option_indexes,
    )
    funding_options = build_options(
        funding_sources,
        "fundingSourceId",
        ("name", "type", "description"),
        include_index=use_option_indexes,
    )
    tef_options = build_options(
        tef_categories,
        "tefId",
        ("code", "name", "description"),
        include_index=use_option_indexes,
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
    if targets is None or targets.intersection({"emission_sector", "indicator_sector"}):
        LOGGER.info("Group 1: Sector mappings (emission_sector, indicator_sector)...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            if targets is None or "emission_sector" in targets:
                futures[
                    executor.submit(
                        map_emission_sector,
                        emissions,
                        sector_options,
                        selector,
                        batch_size,
                        api_semaphore,
                        prompt_suffix=emission_guidance,
                    )
                ] = "emission_sector"
            if targets is None or "indicator_sector" in targets:
                futures[
                    executor.submit(
                        map_indicator_sector,
                        indicators,
                        sector_options,
                        selector,
                        batch_size,
                        api_semaphore,
                    )
                ] = "indicator_sector"
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                    LOGGER.info("Completed %s mapping", name)
                except Exception as exc:
                    LOGGER.error("Failed %s mapping: %s", name, exc)
                    raise

    # Group 2: Budget/Funding (single mapper, but batched internally)
    if targets is None or "budget_funding" in targets:
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
    if targets is None or targets.intersection(
        {"initiative_stakeholder", "initiative_indicator", "initiative_tef"}
    ):
        LOGGER.info("Group 3: Initiative mappings (stakeholder, indicator, tef)...")
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            if targets is None or "initiative_stakeholder" in targets:
                futures[
                    executor.submit(
                        map_initiative_stakeholder,
                        initiative_stakeholders,
                        initiative_options,
                        stakeholder_options,
                        selector,
                        batch_size,
                        api_semaphore,
                    )
                ] = "initiative_stakeholder"
            if targets is None or "initiative_indicator" in targets:
                futures[
                    executor.submit(
                        map_initiative_indicator,
                        initiative_indicators,
                        initiative_options,
                        indicator_options,
                        selector,
                        batch_size,
                        api_semaphore,
                    )
                ] = "initiative_indicator"
            if targets is None or "initiative_tef" in targets:
                futures[
                    executor.submit(
                        map_initiative_tef,
                        initiative_tef,
                        initiative_options,
                        tef_options,
                        selector,
                        batch_size,
                        api_semaphore,
                    )
                ] = "initiative_tef"
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                    LOGGER.info("Completed %s mapping", name)
                except Exception as exc:
                    LOGGER.error("Failed %s mapping: %s", name, exc)
                    raise

    # Group 4: Indicator mappings (2 parallel mappers)
    if targets is None or targets.intersection({"indicator_value", "city_target"}):
        LOGGER.info("Group 4: Indicator mappings (indicator_value, city_target)...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            if targets is None or "indicator_value" in targets:
                futures[
                    executor.submit(
                        map_indicator_value,
                        indicator_values,
                        indicator_options,
                        selector,
                        batch_size,
                        api_semaphore,
                    )
                ] = "indicator_value"
            if targets is None or "city_target" in targets:
                futures[
                    executor.submit(
                        map_city_target,
                        city_targets,
                        indicator_options,
                        selector,
                        batch_size,
                        api_semaphore,
                    )
                ] = "city_target"
            for future in as_completed(futures):
                name = futures[future]
                try:
                    future.result()
                    LOGGER.info("Completed %s mapping", name)
                except Exception as exc:
                    LOGGER.error("Failed %s mapping: %s", name, exc)
                    raise

    # Group 5: Self-referential (sequential, after Group 3)
    if targets is None or "tef_parent" in targets:
        LOGGER.info("Group 5: TEF category parent mapping...")
        map_tef_parent(tef_categories, tef_options, selector, batch_size, api_semaphore)
        LOGGER.info("Completed tef_parent mapping")

    if targets is None or "city_target" in targets:
        status_filled = ensure_city_target_status(city_targets)
        if status_filled:
            LOGGER.info(
                "CityTarget: set default status=%s for %d record(s).",
                DEFAULT_CITY_TARGET_STATUS,
                status_filled,
            )

    if retry_on_issues:
        if retry_max_rounds < 1:
            LOGGER.warning("retry_on_issues set, but retry_max_rounds < 1. Skipping.")
        else:
            retry_prompt_suffix = (
                "These records are being re-mapped because FK validation or uniqueness checks failed. "
                "Each record includes a mapping_feedback field describing the issue. "
                "Use it to correct the IDs. Prefer a valid option over null and avoid duplicates when possible."
            )

            def combine_prompt(*parts: str | None) -> str:
                return " ".join(part.strip() for part in parts if part and part.strip())

            def build_retry_payload(
                records: list[dict],
                feedback_by_index: dict[int, list[str]],
                table: str,
            ) -> tuple[list[dict], list[str]]:
                retry_records: list[dict] = []
                retry_feedback: list[str] = []
                for idx in sorted(feedback_by_index.keys()):
                    if idx >= len(records):
                        LOGGER.warning(
                            "Retry index out of range for %s: %d (records=%d)",
                            table,
                            idx,
                            len(records),
                        )
                        continue
                    retry_records.append(records[idx])
                    messages = feedback_by_index[idx]
                    retry_feedback.append(" ".join(messages))
                return retry_records, retry_feedback

            for round_idx in range(retry_max_rounds):
                records_by_table = {
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
                fk_issues, duplicate_groups, feedback_by_table = build_retry_plan(
                    records_by_table,
                    max_duplicate_groups=retry_max_duplicate_groups,
                )

                if not fk_issues and not duplicate_groups:
                    LOGGER.info("No FK or duplicate issues detected (retry round %d).", round_idx + 1)
                    break

                tables_to_retry: dict[str, dict[int, list[str]]] = {}
                for table, feedback_map in feedback_by_table.items():
                    mapper_name = RETRY_TABLE_TO_MAPPER.get(table)
                    if not mapper_name:
                        continue
                    if targets is not None and mapper_name not in targets:
                        continue
                    tables_to_retry[table] = feedback_map

                if not tables_to_retry:
                    LOGGER.warning(
                        "Retry round %d: issues found but no matching mappers to retry.",
                        round_idx + 1,
                    )
                    break

                LOGGER.warning(
                    "Retry round %d: FK issues=%d duplicate groups=%d tables=%d",
                    round_idx + 1,
                    len(fk_issues),
                    len(duplicate_groups),
                    len(tables_to_retry),
                )

                for table, feedback_map in tables_to_retry.items():
                    if table == "EmissionRecord.json":
                        retry_records, retry_feedback = build_retry_payload(
                            emissions, feedback_map, table
                        )
                        if retry_records:
                            prompt = combine_prompt(emission_guidance, retry_prompt_suffix)
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_emission_sector(
                                retry_records,
                                sector_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=prompt,
                                feedback=retry_feedback,
                            )
                        continue

                    if table == "Indicator.json":
                        retry_records, retry_feedback = build_retry_payload(
                            indicators, feedback_map, table
                        )
                        if retry_records:
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_indicator_sector(
                                retry_records,
                                sector_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=retry_prompt_suffix,
                                feedback=retry_feedback,
                            )
                        continue

                    if table == "BudgetFunding.json":
                        retry_records, retry_feedback = build_retry_payload(
                            budget_funding, feedback_map, table
                        )
                        if retry_records:
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_budget_funding(
                                retry_records,
                                budget_options,
                                funding_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=retry_prompt_suffix,
                                feedback=retry_feedback,
                            )
                        continue

                    if table == "InitiativeStakeholder.json":
                        retry_records, retry_feedback = build_retry_payload(
                            initiative_stakeholders, feedback_map, table
                        )
                        if retry_records:
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_initiative_stakeholder(
                                retry_records,
                                initiative_options,
                                stakeholder_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=retry_prompt_suffix,
                                feedback=retry_feedback,
                            )
                        continue

                    if table == "InitiativeIndicator.json":
                        retry_records, retry_feedback = build_retry_payload(
                            initiative_indicators, feedback_map, table
                        )
                        if retry_records:
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_initiative_indicator(
                                retry_records,
                                initiative_options,
                                indicator_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=retry_prompt_suffix,
                                feedback=retry_feedback,
                            )
                        continue

                    if table == "InitiativeTef.json":
                        retry_records, retry_feedback = build_retry_payload(
                            initiative_tef, feedback_map, table
                        )
                        if retry_records:
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_initiative_tef(
                                retry_records,
                                initiative_options,
                                tef_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=retry_prompt_suffix,
                                feedback=retry_feedback,
                            )
                        continue

                    if table == "IndicatorValue.json":
                        retry_records, retry_feedback = build_retry_payload(
                            indicator_values, feedback_map, table
                        )
                        if retry_records:
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_indicator_value(
                                retry_records,
                                indicator_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=retry_prompt_suffix,
                                feedback=retry_feedback,
                            )
                        continue

                    if table == "CityTarget.json":
                        retry_records, retry_feedback = build_retry_payload(
                            city_targets, feedback_map, table
                        )
                        if retry_records:
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_city_target(
                                retry_records,
                                indicator_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=retry_prompt_suffix,
                                feedback=retry_feedback,
                            )
                        continue

                    if table == "TefCategory.json":
                        retry_records, retry_feedback = build_retry_payload(
                            tef_categories, feedback_map, table
                        )
                        if retry_records:
                            LOGGER.warning(
                                "Retrying %s: records=%d", table, len(retry_records)
                            )
                            map_tef_parent(
                                retry_records,
                                tef_options,
                                selector,
                                batch_size,
                                api_semaphore,
                                prompt_suffix=retry_prompt_suffix,
                                feedback=retry_feedback,
                            )
                        continue

    outputs = dict(all_inputs)
    outputs.update({
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
    })

    if apply:
        for fname in sorted(outputs):
            write_json(output_dir / fname, outputs[fname])

    return outputs


def main() -> int:
    args = parse_args()
    llm_cfg = load_llm_config().get("mapping", {})
    model_name = args.model or llm_cfg.get("model")
    if not model_name:
        raise RuntimeError(
            "Mapping model not configured. Set mapping.model in llm_config.yml."
        )

    targets = None
    if args.only:
        targets = {item.strip() for item in args.only.split(",") if item.strip()}
        if not targets:
            targets = None

    outputs = run_llm_mapping(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        model_name=model_name,
        apply=args.apply,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
        max_concurrent_api_calls=args.max_concurrent_api_calls,
        targets=targets,
        emission_guidance=args.emission_guidance,
        retry_on_issues=args.retry_on_issues,
        retry_max_rounds=args.retry_rounds,
        retry_max_duplicate_groups=args.retry_max_duplicates,
        use_option_indexes=args.use_option_indexes,
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
