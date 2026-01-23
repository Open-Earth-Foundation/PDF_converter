# DB Load Implementation Plan

## Why the schema mismatch is an issue
- `database/schemas.py` is used for validation, so any field marked required there will fail validation even if the DB allows nulls.
- Example: `FundingSource.description` and `FundingSource.notes` are required in schemas but nullable in the DB model, so valid DB rows are rejected before insert.
- This creates false negatives, blocks loading, and hides real data quality issues.

## Goals
- Load `mapping/workflow_output/step3_llm` outputs into the DB.
- Validate with `database/schemas.py` first, with clear and actionable error reporting.
- Provide a permissive mode for troubleshooting or emergency loads.

## Plan (validate-first, with permissive fallback)

### 1) Verify schema alignment with DB models
- Schema alignment is confirmed as of 2026-01-23: `database/schemas.py` already matches nullability and types in `database/models/*`
  - `FundingSource.description`, `FundingSource.notes`: already optional
  - `Stakeholder.description`, `Indicator.description`, `Initiative.description`: already optional
  - `CityBudget.year`: both schema and DB use `int` (no mismatch)
- If any drift is detected during development, update schemas first before proceeding
- Consider adding unit tests to prevent future schema drift (e.g., auto-check in CI)

Result: validation failures reflect true data problems, not schema drift.

### 2) Create a DB loader script (validation-first)
Add `app/modules/db_insert/scripts/load_mapped_data.py` (and ensure the module utilities live under `app/modules/db_insert/utils/`).

Script requirements:
- Top-level docstring (per AGENTS rules).
- `argparse` inputs:
  - `--input-dir` (default: `mapping/workflow_output/step3_llm`)
  - `--mode` (`validate` | `permissive`, default `validate`)
  - `--report-path` (optional, default to timestamped report under `output/db_load_reports/`)
  - `--dry-run` (optional, default `False`): validation only, no DB inserts. When False, inserts are performed.
  - `--on-error` (`stop` | `continue`, default `stop`)
- Use `DATABASE_URL` (or `DB_URL`) from env (via `database/config.py`).
- Use `database/session.py` for sessions.
- Use `app.utils.logging_config.setup_logger()` for logging.

### 3) Validation flow (mode=validate)
For each table:
- Load JSON list and normalize fields where needed:
  - Convert camelCase JSON keys to match schema aliases
  - Trim whitespace from string fields
  - Ensure numeric types (int, Decimal) are properly typed
  - Convert date strings to datetime/date objects where needed
  - Remove any extra fields not in the schema (or error in validate mode)
- Validate each record with the matching Pydantic model in `database/schemas.py`.
- Collect structured errors:
  - table name, record index, primary key (if any), missing fields, type errors
- If any validation errors:
  - Write report and fail fast by default (`--on-error stop`).

### 4) Insert flow (mode=validate or permissive)
Insert in FK-safe order:
1. City
2. Sector
3. Indicator
4. CityAnnualStats
5. EmissionRecord
6. CityBudget
7. FundingSource
8. BudgetFunding
9. Initiative
10. Stakeholder
11. InitiativeStakeholder
12. InitiativeIndicator
13. CityTarget
14. IndicatorValue
15. ClimateCityContract
16. TefCategory
17. InitiativeTef

**Transaction strategy:**
- Use per-table transactions by default (allows partial success and easier debugging)
- Add `--atomic` flag option for all-or-nothing behavior if needed later
- Log transaction boundaries for debugging (table start, commit/rollback, record counts)

**Duplicate handling:**
- Phase 1 (initial implementation): Insert-only, log `IntegrityError` as failures per record
- Phase 2 (if needed): Add `--on-conflict` option (`error` | `skip` | `update`)

Notes:
- Empty tables should be skipped with an info log.
- Add a follow-up option for upsert if needed.

### 5) Error reporting
Emit a report file (JSON or Markdown) with:
- Per-table counts: loaded, validated, inserted, failed.
- Missing field summary (by field name).
- First N row-level errors for quick triage.

### 6) Permissive mode (mode=permissive)
- Skip Pydantic validation.
- Minimal normalization only (drop unknown keys, keep required types where possible).
- Attempt inserts and log DB errors.
- Still emit the same report format.

### 7) Manual run checklist
- `DATABASE_URL` set in environment
- Mapping outputs are up to date (step3)
- Run validation-only: `python -m app.modules.db_insert.scripts.load_mapped_data --dry-run`
- Run with inserts: `python -m app.modules.db_insert.scripts.load_mapped_data`
- Review report at `output/db_load_reports/` for detailed results

## Open questions

- Should we add an upsert mode (on conflict do nothing/update)? (Deferred to Phase 2)
