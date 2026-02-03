"""
Shared helpers for LLM-based mapping scripts.

Each mapping module defines its own prompt and structured output at the top,
and calls into LLMSelector to obtain IDs for foreign key fields.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Iterable

import tiktoken

LOGGER = logging.getLogger(__name__)
_CANONICAL_CITY_ID: str | None = None

# Track unmapped records for reporting
UNMAPPED_RECORDS: dict[str, list[dict]] = {}


def load_json_list(path: Path) -> list[dict]:
    """
    Load a JSON list from disk.

    Missing files return [] (OK - entity types may not be present in all documents).
    A debug log is emitted for missing files.

    Raises:
        ValueError: If the file exists but is corrupted/invalid JSON or doesn't contain a top-level list.
    """
    if not path.exists():
        LOGGER.debug(f"File not found, treating as empty: {path.name}")
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        LOGGER.error(f"JSON parsing failed for {path}: {exc}")
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(payload, list):
        LOGGER.error(
            f"Expected list at top-level of {path}, got {type(payload).__name__}"
        )
        raise ValueError(
            f"Expected top-level JSON list in {path}, got {type(payload).__name__}"
        )
    return payload


def write_json(path: Path, payload: list[dict]) -> None:
    """Persist payload to disk with pretty-printing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def set_canonical_city_id(city_id: str | None) -> None:
    """Set global canonical cityId for mapping helpers."""
    global _CANONICAL_CITY_ID
    _CANONICAL_CITY_ID = city_id


def set_city_id(
    records: list[dict], fields: Iterable[str], city_id: str | None = None
) -> int:
    """
    Set canonical cityId across given fields; return count updated.

    If city_id is not provided, fallback to the global canonical id, and if that is missing,
    attempt to derive it from the first record that already has a cityId.
    """
    global _CANONICAL_CITY_ID
    canonical = city_id or _CANONICAL_CITY_ID
    if canonical is None:
        for rec in records:
            cid = rec.get("cityId")
            if cid:
                canonical = cid
                _CANONICAL_CITY_ID = cid
                break
    if canonical is None:
        return 0

    updated = 0
    for record in records:
        for field in fields:
            if record.get(field) != canonical:
                record[field] = canonical
                updated += 1
    return updated


def build_options(
    records: list[dict],
    id_key: str,
    label_keys: tuple[str, ...],
    *,
    include_index: bool = False,
) -> list[dict]:
    """Build selectable option list: [{id, label...}]."""
    options: list[dict] = []
    option_index = 1
    for record in records:
        rid = record.get(id_key)
        if not rid:
            continue
        option = {"id": rid}
        if include_index:
            option["index"] = option_index
            option_index += 1
        label_parts: list[str] = []
        for key in label_keys:
            if key in record:
                value = record.get(key)
                option[key] = value
                if value not in (None, ""):
                    label_parts.append(f"{key}={value}")
        if label_parts:
            option["label"] = " | ".join(label_parts)
        options.append(option)
    return options


def summarise_record(
    record: dict,
    keep_fields: Iterable[str] | None = None,
    feedback: str | None = None,
) -> dict:
    """Lightweight projection of a record to reduce prompt size."""
    if keep_fields is None:
        keep_fields = [k for k in record.keys() if k not in {"misc"}]
    summary = {k: record.get(k) for k in keep_fields if k in record}
    if record.get("misc"):
        summary["misc"] = record.get("misc")
    if feedback:
        summary["mapping_feedback"] = feedback
    return summary


class LLMSelector:
    """Helper to call the LLM with structured output."""

    def __init__(
        self,
        client: Any,
        model: str,
        default_temperature: float = 0.0,
        use_option_indexes: bool = False,
    ):
        self.client = client
        self.model = model
        self.default_temperature = default_temperature
        self.use_option_indexes = use_option_indexes

    def _prepare_candidate_sets(
        self,
        candidate_sets: list[dict],
    ) -> tuple[list[dict], dict[str, dict[int, Any]]]:
        if not self.use_option_indexes:
            return candidate_sets, {}
        prompt_sets: list[dict] = []
        index_maps: dict[str, dict[int, Any]] = {}
        for candidate_set in candidate_sets:
            field = candidate_set["field"]
            options = candidate_set.get("options") or []
            prompt_options: list[dict] = []
            index_map: dict[int, Any] = {}
            for option in options:
                idx = option.get("index")
                if idx is None:
                    continue
                try:
                    idx_int = int(idx)
                except (TypeError, ValueError):
                    continue
                label = option.get("label")
                if not label:
                    label = "(missing label)"
                prompt_options.append({"index": idx_int, "label": label})
                index_map[idx_int] = option.get("id")
            prompt_sets.append({"field": field, "options": prompt_options})
            index_maps[field] = index_map
        return prompt_sets, index_maps

    def select_fields(
        self,
        *,
        record_label: str,
        record: dict,
        candidate_sets: list[dict],
        prompt: str,
        response_format: dict | None = None,
        temperature: float | None = None,
        record_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Ask the LLM to choose IDs for the provided fields.

        candidate_sets example: [{"field": "sectorId", "options": [{"id": "...", "name": "..."}]}]
        record_id: unique identifier for this record (for logging unmapped records)
        """
        selections: dict[str, Any] = {}
        reasons: dict[str, str] = {}
        pending: list[dict] = []
        empty_fields: list[str] = []

        for candidate_set in candidate_sets:
            field = candidate_set["field"]
            options = candidate_set.get("options") or []
            if not options:
                selections[field] = None
                empty_fields.append(field)
                continue
            pending.append({"field": field, "options": options})

        if not pending:
            return selections

        prompt_candidate_sets, index_maps = self._prepare_candidate_sets(pending)
        options_text = json.dumps(prompt_candidate_sets, indent=2, ensure_ascii=False)
        record_text = json.dumps(record, indent=2, ensure_ascii=False)
        if self.use_option_indexes:
            structure_hint = '{"selections":[{"field":"fieldName","index":1,"reason":"short justification"}]}'
            response_note = "Return index values from options. Do not return ids."
        else:
            structure_hint = '{"selections":[{"field":"fieldName","id":"<uuid or null>","reason":"short justification"}]}'
            response_note = "Return ids from options."
        user_content = (
            f"{prompt}\n\n"
            f"Record ({record_label}):\n{record_text}\n\n"
            f"Options by field:\n{options_text}\n\n"
            f"Return a JSON object exactly like: {structure_hint}. "
            f"{response_note} Do not include any text outside the JSON object. "
            "Use null when no option fits."
        )

        # Calculate and log prompt size
        enc = tiktoken.get_encoding("cl100k_base")
        system_tokens = len(
            enc.encode(
                "You are a careful data mapper. Only select IDs from the provided options or null. Respond ONLY with JSON matching the requested schema."
            )
        )
        user_tokens = len(enc.encode(user_content))
        total_tokens = system_tokens + user_tokens

        LOGGER.debug(
            "Mapping prompt for %s: system=%d tokens, user=%d tokens, total=%d tokens",
            record_label,
            system_tokens,
            user_tokens,
            total_tokens,
        )

        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a careful data mapper. Only select IDs from the provided options or null. "
                    "Respond ONLY with JSON matching the requested schema.",
                },
                {"role": "user", "content": user_content},
            ],
            response_format=response_format or {"type": "json_object"},
            temperature=(
                self.default_temperature if temperature is None else temperature
            ),
        )

        try:
            payload = json.loads(resp.choices[0].message.content or "{}")
        except Exception:
            payload = {}

        for entry in payload.get("selections", []):
            field = entry.get("field")
            if not field:
                continue
            if "id" in entry:
                selections[field] = entry.get("id")
                continue
            if "index" in entry:
                try:
                    idx = int(entry.get("index"))
                except (TypeError, ValueError):
                    continue
                mapped = index_maps.get(field, {}).get(idx)
                if mapped is not None:
                    selections[field] = mapped

        return selections

    def select_fields_batch(
        self,
        *,
        records: list[dict],
        candidate_sets: list[dict],
        prompt: str,
        response_format: dict | None = None,
        temperature: float | None = None,
        batch_label: str = "Batch",
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ) -> list[dict[str, Any]]:
        """
        Process multiple records in a single LLM call.

        Args:
            records: List of record dictionaries to process
            candidate_sets: List of candidate field/options dicts
            prompt: Prompt to use for the LLM
            response_format: Response format override
            temperature: Temperature override
            batch_label: Label for logging
            max_retries: Maximum number of retries on API errors (default: 3)
            retry_delay: Initial retry delay in seconds, exponential backoff (default: 2.0)

        Returns:
            List of selection dicts, one per input record.
            Each dict maps field names to selected IDs (or None).
        """
        if not records:
            return []

        # Check if any candidate set has options
        has_options = any(cs.get("options") for cs in candidate_sets)
        if not has_options:
            # All fields empty, return None for all
            return [{cs["field"]: None for cs in candidate_sets} for _ in records]

        # Build batch prompt with all records
        prompt_candidate_sets, index_maps = self._prepare_candidate_sets(candidate_sets)
        options_text = json.dumps(prompt_candidate_sets, indent=2, ensure_ascii=False)
        records_text = json.dumps(records, indent=2, ensure_ascii=False)
        if self.use_option_indexes:
            structure_hint = '{"batch_results":[{"record_index":0,"selections":[{"field":"fieldName","index":1,"reason":"short justification"}]}]}'
            response_note = "Return index values from options. Do not return ids."
        else:
            structure_hint = '{"batch_results":[{"record_index":0,"selections":[{"field":"fieldName","id":"<uuid or null>","reason":"short justification"}]}]}'
            response_note = "Return ids from options."
        max_idx = len(records) - 1
        user_content = (
            f"{prompt}\n\n"
            f"Process the following {len(records)} records:\n{records_text}\n\n"
            f"Options by field:\n{options_text}\n\n"
            f"Return a JSON object exactly like: {structure_hint}. "
            f"Include one entry per record, indexed 0 to {max_idx}, each with selections array. "
            f"{response_note} Do not include any text outside the JSON object. "
            "Use null when no option fits."
        )

        # Calculate and log prompt size
        enc = tiktoken.get_encoding("cl100k_base")
        system_tokens = len(
            enc.encode(
                "You are a careful data mapper. Only select IDs from the provided options or null. Respond ONLY with JSON matching the requested schema."
            )
        )
        user_tokens = len(enc.encode(user_content))
        total_tokens = system_tokens + user_tokens

        LOGGER.debug(
            "Batch mapping prompt for %s: %d records, system=%d tokens, user=%d tokens, total=%d tokens",
            batch_label,
            len(records),
            system_tokens,
            user_tokens,
            total_tokens,
        )

        # Make API call with retry logic
        resp = None
        last_exception = None
        for attempt in range(max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a careful data mapper. Only select IDs from the provided options or null. "
                            "Respond ONLY with JSON matching the requested schema.",
                        },
                        {"role": "user", "content": user_content},
                    ],
                    response_format=response_format or {"type": "json_object"},
                    temperature=(
                        self.default_temperature if temperature is None else temperature
                    ),
                )
                break  # Success, exit retry loop
            except Exception as exc:
                last_exception = exc
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2**attempt)  # Exponential backoff
                    LOGGER.warning(
                        "Batch API call failed for %s (attempt %d/%d), retrying in %.1fs: %s",
                        batch_label,
                        attempt + 1,
                        max_retries,
                        wait_time,
                        exc,
                    )
                    time.sleep(wait_time)
                else:
                    LOGGER.error(
                        "Batch API call failed for %s after %d attempts: %s",
                        batch_label,
                        max_retries,
                        exc,
                    )

        if resp is None:
            # All retries failed, initialize empty results
            LOGGER.warning(
                "Batch mapping %s failed after retries, returning null selections",
                batch_label,
            )
            batch_results: list[dict[str, Any]] = [
                {cs["field"]: None for cs in candidate_sets} for _ in records
            ]
            return batch_results

        # Parse batch results
        try:
            payload = json.loads(resp.choices[0].message.content or "{}")
        except Exception as exc:
            LOGGER.error("Failed to parse batch response for %s: %s", batch_label, exc)
            payload = {}

        raw_results = payload.get("batch_results")
        if isinstance(raw_results, dict):
            if "record_index" in raw_results or "selections" in raw_results:
                raw_results = [raw_results]
            else:
                normalized: list[dict[str, Any]] = []
                for key, value in raw_results.items():
                    if not isinstance(value, dict):
                        continue
                    entry = dict(value)
                    if "record_index" not in entry:
                        try:
                            entry["record_index"] = int(key)
                        except (TypeError, ValueError):
                            entry["record_index"] = None
                    normalized.append(entry)
                raw_results = normalized
        elif isinstance(raw_results, list):
            pass
        elif isinstance(payload, dict) and "selections" in payload:
            raw_results = [
                {
                    "record_index": 0,
                    "selections": payload.get("selections", []),
                }
            ]
        else:
            if raw_results is not None:
                LOGGER.warning(
                    "Unexpected batch_results type for %s: %s",
                    batch_label,
                    type(raw_results).__name__,
                )
            raw_results = []

        # Initialize results: one entry per record with all fields mapped to None
        batch_results: list[dict[str, Any]] = [
            {cs["field"]: None for cs in candidate_sets} for _ in records
        ]

        # Populate results from LLM response
        for result_entry in raw_results:
            if not isinstance(result_entry, dict):
                LOGGER.warning(
                    "Invalid batch result entry for %s: %s",
                    batch_label,
                    type(result_entry).__name__,
                )
                continue
            record_idx = result_entry.get("record_index")
            if record_idx is None or not isinstance(record_idx, int):
                continue
            if record_idx < 0 or record_idx >= len(records):
                LOGGER.warning(
                    "Batch result index out of range for %s: %d (valid: 0-%d)",
                    batch_label,
                    record_idx,
                    len(records) - 1,
                )
                continue

            selections = result_entry.get("selections")
            if not isinstance(selections, list):
                continue
            for selection in selections:
                if not isinstance(selection, dict):
                    continue
                field = selection.get("field")
                if not field:
                    continue
                if "id" in selection:
                    batch_results[record_idx][field] = selection.get("id")
                    continue
                if "index" in selection:
                    try:
                        idx = int(selection.get("index"))
                    except (TypeError, ValueError):
                        continue
                    mapped = index_maps.get(field, {}).get(idx)
                    if mapped is not None:
                        batch_results[record_idx][field] = mapped

        LOGGER.debug(
            "Batch mapping complete for %s: %d records processed",
            batch_label,
            len(records),
        )
        return batch_results
