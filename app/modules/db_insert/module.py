"""Core loader logic for db insert module."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import models as db_models
from database import schemas as db_schemas
from database.config import DBSettings
from database.session import create_db_engine, create_session_factory
from app.modules.db_insert.models import (
    LoadReport,
    StopProcessing,
    TableCounts,
    TableSpec,
)
from app.modules.db_insert.utils.normalization import normalize_record
from app.modules.db_insert.utils.reporting import write_report
from app.modules.db_insert.utils.schema_utils import get_schema_info, to_model_payload

LOGGER = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT_DIR = REPO_ROOT / "mapping" / "workflow_output" / "step3_llm"
DEFAULT_REPORT_DIR = REPO_ROOT / "output" / "db_load_reports"

TABLE_SPECS: list[TableSpec] = [
    TableSpec("City", "City.json", db_schemas.City, db_models.City, "city_id", "cityId"),
    TableSpec(
        "Sector",
        "Sector.json",
        db_schemas.Sector,
        db_models.Sector,
        "sector_id",
        "sectorId",
    ),
    TableSpec(
        "Indicator",
        "Indicator.json",
        db_schemas.Indicator,
        db_models.Indicator,
        "indicator_id",
        "indicatorId",
    ),
    TableSpec(
        "CityAnnualStats",
        "CityAnnualStats.json",
        db_schemas.CityAnnualStats,
        db_models.CityAnnualStats,
        "stat_id",
        "statId",
    ),
    TableSpec(
        "EmissionRecord",
        "EmissionRecord.json",
        db_schemas.EmissionRecord,
        db_models.EmissionRecord,
        "emission_record_id",
        "emissionRecordId",
    ),
    TableSpec(
        "CityBudget",
        "CityBudget.json",
        db_schemas.CityBudget,
        db_models.CityBudget,
        "budget_id",
        "budgetId",
    ),
    TableSpec(
        "FundingSource",
        "FundingSource.json",
        db_schemas.FundingSource,
        db_models.FundingSource,
        "funding_source_id",
        "fundingSourceId",
    ),
    TableSpec(
        "BudgetFunding",
        "BudgetFunding.json",
        db_schemas.BudgetFunding,
        db_models.BudgetFunding,
        "budget_funding_id",
        "budgetFundingId",
    ),
    TableSpec(
        "Initiative",
        "Initiative.json",
        db_schemas.Initiative,
        db_models.Initiative,
        "initiative_id",
        "initiativeId",
    ),
    TableSpec(
        "Stakeholder",
        "Stakeholder.json",
        db_schemas.Stakeholder,
        db_models.Stakeholder,
        "stakeholder_id",
        "stakeholderId",
    ),
    TableSpec(
        "InitiativeStakeholder",
        "InitiativeStakeholder.json",
        db_schemas.InitiativeStakeholder,
        db_models.InitiativeStakeholder,
        "initiative_stakeholder_id",
        "initiativeStakeholderId",
    ),
    TableSpec(
        "InitiativeIndicator",
        "InitiativeIndicator.json",
        db_schemas.InitiativeIndicator,
        db_models.InitiativeIndicator,
        "initiative_indicator_id",
        "initiativeIndicatorId",
    ),
    TableSpec(
        "CityTarget",
        "CityTarget.json",
        db_schemas.CityTarget,
        db_models.CityTarget,
        "city_target_id",
        "cityTargetId",
    ),
    TableSpec(
        "IndicatorValue",
        "IndicatorValue.json",
        db_schemas.IndicatorValue,
        db_models.IndicatorValue,
        "indicator_value_id",
        "indicatorValueId",
    ),
    TableSpec(
        "ClimateCityContract",
        "ClimateCityContract.json",
        db_schemas.ClimateCityContract,
        db_models.ClimateCityContract,
        "climate_city_contract_id",
        "climateCityContractId",
    ),
    TableSpec(
        "TefCategory",
        "TefCategory.json",
        db_schemas.TefCategory,
        db_models.TefCategory,
        "tef_id",
        "tefId",
    ),
    TableSpec(
        "InitiativeTef",
        "InitiativeTef.json",
        db_schemas.InitiativeTef,
        db_models.InitiativeTef,
        "initiative_tef_id",
        "initiativeTefId",
    ),
]


def ensure_report_path(path: Path | None) -> Path:
    if path:
        return path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return DEFAULT_REPORT_DIR / f"db_load_report_{timestamp}.json"


def read_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, list):
        raise ValueError(
            f"Expected list at top-level in {path}, got {type(payload).__name__}"
        )
    return payload


def load_records_for_tables(input_dir: Path) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {}
    for spec in TABLE_SPECS:
        path = input_dir / spec.filename
        try:
            data = read_json_list(path)
        except ValueError as exc:
            LOGGER.error("Failed to load %s: %s", path, exc)
            raise
        records[spec.name] = data
    return records


def get_record_id(
    record: dict[str, Any],
    spec: TableSpec,
) -> str | None:
    if spec.pk_alias and spec.pk_alias in record:
        return str(record.get(spec.pk_alias))
    if spec.pk_field and spec.pk_field in record:
        return str(record.get(spec.pk_field))
    return None


def process_table_records(
    spec: TableSpec,
    raw_records: list[dict[str, Any]],
    mode: str,
    on_error: str,
    report: LoadReport,
) -> list[dict[str, Any]]:
    info = get_schema_info(spec.schema)
    processed: list[dict[str, Any]] = []
    drop_unknown = mode == "permissive"
    for idx, raw in enumerate(raw_records):
        if not isinstance(raw, dict):
            report.tables[spec.name].failed += 1
            report.record_error(
                {
                    "table": spec.name,
                    "record_index": idx,
                    "record_id": None,
                    "stage": "validation" if mode == "validate" else "normalization",
                    "field": None,
                    "message": f"Expected object, got {type(raw).__name__}",
                    "error_type": "type_error",
                }
            )
            if on_error == "stop":
                raise StopProcessing("Non-dict record encountered.")
            continue

        normalized, _unknown = normalize_record(raw, info, drop_unknown=drop_unknown)
        record_id = get_record_id(raw, spec)
        if mode == "validate":
            try:
                model = spec.schema.model_validate(normalized)
                processed.append(model.model_dump(by_alias=False))
                report.tables[spec.name].validated += 1
            except ValidationError as exc:
                report.tables[spec.name].failed += 1
                for err in exc.errors():
                    loc = err.get("loc", [])
                    field_name = ".".join(str(item) for item in loc) if loc else None
                    err_type = err.get("type")
                    report.record_error(
                        {
                            "table": spec.name,
                            "record_index": idx,
                            "record_id": record_id,
                            "stage": "validation",
                            "field": field_name,
                            "message": err.get("msg"),
                            "error_type": err_type,
                        }
                    )
                    if err_type in {"missing", "value_error.missing"}:
                        if field_name:
                            report.record_missing_field(field_name)
                if on_error == "stop":
                    raise StopProcessing("Validation errors encountered.")
            except Exception as exc:
                report.tables[spec.name].failed += 1
                report.record_error(
                    {
                        "table": spec.name,
                        "record_index": idx,
                        "record_id": record_id,
                        "stage": "validation",
                        "field": None,
                        "message": str(exc),
                        "error_type": "validation_error",
                    }
                )
                if on_error == "stop":
                    raise StopProcessing("Validation errors encountered.")
        else:
            payload = to_model_payload(normalized, info)
            processed.append(payload)
            report.tables[spec.name].validated += 1
    return processed


def prepare_payload_for_insert(
    spec: TableSpec,
    payload: dict[str, Any],
) -> dict[str, Any]:
    sanitized = payload.copy()
    if spec.pk_field and sanitized.get(spec.pk_field) is None:
        sanitized.pop(spec.pk_field, None)
    return sanitized


def insert_records(
    session: Session,
    spec: TableSpec,
    payloads: list[dict[str, Any]],
    report: LoadReport,
    on_error: str,
) -> None:
    if not payloads:
        LOGGER.info("Skipping %s (no records).", spec.name)
        return
    LOGGER.info("Inserting %d records into %s", len(payloads), spec.name)
    for idx, payload in enumerate(payloads):
        record_id = payload.get(spec.pk_field) if spec.pk_field else None
        nested = session.begin_nested()
        try:
            model_payload = prepare_payload_for_insert(spec, payload)
            session.add(spec.model(**model_payload))
            session.flush()
            nested.commit()
            report.tables[spec.name].inserted += 1
        except IntegrityError as exc:
            nested.rollback()
            report.tables[spec.name].failed += 1
            report.record_error(
                {
                    "table": spec.name,
                    "record_index": idx,
                    "record_id": str(record_id) if record_id else None,
                    "stage": "insert",
                    "field": None,
                    "message": str(exc.orig) if exc.orig else str(exc),
                    "error_type": "integrity_error",
                }
            )
            if on_error == "stop":
                raise StopProcessing("Insert failed due to integrity error.")
        except Exception as exc:
            nested.rollback()
            report.tables[spec.name].failed += 1
            report.record_error(
                {
                    "table": spec.name,
                    "record_index": idx,
                    "record_id": str(record_id) if record_id else None,
                    "stage": "insert",
                    "field": None,
                    "message": str(exc),
                    "error_type": "insert_error",
                }
            )
            if on_error == "stop":
                raise StopProcessing("Insert failed due to insert error.")


def run_load(
    *,
    input_dir: Path,
    mode: str,
    report_path: Path,
    dry_run: bool,
    on_error: str,
    atomic: bool,
) -> int:
    if not input_dir.exists():
        LOGGER.error("Input directory does not exist: %s", input_dir)
        return 1

    report = LoadReport(
        mode=mode,
        dry_run=dry_run,
        atomic=atomic,
        on_error=on_error,
        input_dir=str(input_dir),
        report_path=str(report_path),
        validation_skipped=mode == "permissive",
        tables={spec.name: TableCounts() for spec in TABLE_SPECS},
    )

    records_by_table = load_records_for_tables(input_dir)
    for spec in TABLE_SPECS:
        report.tables[spec.name].loaded = len(records_by_table.get(spec.name, []))

    validation_failed = False

    def handle_tables(session: Session | None = None) -> None:
        nonlocal validation_failed
        for spec in TABLE_SPECS:
            raw_records = records_by_table.get(spec.name, [])
            if not raw_records:
                LOGGER.info("No records for %s", spec.name)
                continue
            LOGGER.info("Processing %s (%d records)", spec.name, len(raw_records))
            try:
                processed = process_table_records(
                    spec=spec,
                    raw_records=raw_records,
                    mode=mode,
                    on_error=on_error,
                    report=report,
                )
            except StopProcessing:
                validation_failed = True
                raise

            if mode == "validate" and report.tables[spec.name].failed:
                validation_failed = True
            if dry_run:
                continue
            if session is None:
                raise RuntimeError("Session is required for inserts.")
            insert_records(session, spec, processed, report, on_error)

    engine = None
    try:
        if dry_run:
            handle_tables()
        else:
            settings = DBSettings.from_env()
            engine = create_db_engine(settings=settings)
            session_factory = create_session_factory(engine)
            if atomic:
                with session_factory() as session:
                    txn = session.begin()
                    try:
                        LOGGER.info("Starting atomic transaction across all tables.")
                        handle_tables(session)
                        if report.error_count_total > 0:
                            raise StopProcessing("Errors detected in atomic mode.")
                        txn.commit()
                        LOGGER.info("Atomic transaction committed.")
                    except StopProcessing as exc:
                        LOGGER.warning("Atomic transaction rolled back: %s", exc)
                        txn.rollback()
                        raise
            else:
                for spec in TABLE_SPECS:
                    raw_records = records_by_table.get(spec.name, [])
                    if not raw_records:
                        LOGGER.info("No records for %s", spec.name)
                        continue
                    with session_factory() as session:
                        try:
                            LOGGER.info("Starting transaction for %s", spec.name)
                            with session.begin():
                                processed = process_table_records(
                                    spec=spec,
                                    raw_records=raw_records,
                                    mode=mode,
                                    on_error=on_error,
                                    report=report,
                                )
                                if mode == "validate" and report.tables[spec.name].failed:
                                    validation_failed = True
                                if dry_run:
                                    continue
                                insert_records(
                                    session, spec, processed, report, on_error
                                )
                            LOGGER.info("Committed transaction for %s", spec.name)
                        except StopProcessing:
                            LOGGER.warning("Rolling back transaction for %s", spec.name)
                            validation_failed = True
                            break
    except StopProcessing as exc:
        LOGGER.warning("Stopped early: %s", exc)
    finally:
        if engine is not None:
            engine.dispose()

    write_report(report, report_path)
    LOGGER.info("Report written to %s", report_path)

    if report.error_count_total > 0 or validation_failed:
        return 1
    return 0
