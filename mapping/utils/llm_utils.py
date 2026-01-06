"""
Shared helpers for LLM-based mapping scripts.

Each mapping module defines its own prompt and structured output at the top,
and calls into LLMSelector to obtain IDs for foreign key fields.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

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
        LOGGER.error(f"Expected list at top-level of {path}, got {type(payload).__name__}")
        raise ValueError(f"Expected top-level JSON list in {path}, got {type(payload).__name__}")
    return payload


def write_json(path: Path, payload: list[dict]) -> None:
    """Persist payload to disk with pretty-printing."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def set_canonical_city_id(city_id: str | None) -> None:
    """Set global canonical cityId for mapping helpers."""
    global _CANONICAL_CITY_ID
    _CANONICAL_CITY_ID = city_id


def set_city_id(records: list[dict], fields: Iterable[str], city_id: str | None = None) -> int:
    """
    Set canonical cityId across given fields; return count updated.

    If city_id is not provided, fallback to the global canonical id, and if that is missing,
    attempt to derive it from the first record that already has a cityId.
    """
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


def build_options(records: list[dict], id_key: str, label_keys: tuple[str, ...]) -> list[dict]:
    """Build selectable option list: [{id, label...}]."""
    options: list[dict] = []
    for record in records:
        rid = record.get(id_key)
        if not rid:
            continue
        option = {"id": rid}
        for key in label_keys:
            if key in record:
                option[key] = record.get(key)
        options.append(option)
    return options


def summarise_record(record: dict, keep_fields: Iterable[str] | None = None) -> dict:
    """Lightweight projection of a record to reduce prompt size."""
    if keep_fields is None:
        keep_fields = [k for k in record.keys() if k not in {"misc"}]
    summary = {k: record.get(k) for k in keep_fields if k in record}
    if record.get("misc"):
        summary["misc"] = record.get("misc")
    return summary


class LLMSelector:
    """Helper to call the LLM with structured output."""

    def __init__(self, client: Any, model: str, default_temperature: float = 0.0):
        self.client = client
        self.model = model
        self.default_temperature = default_temperature

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

        options_text = json.dumps(pending, indent=2, ensure_ascii=False)
        record_text = json.dumps(record, indent=2, ensure_ascii=False)
        structure_hint = '{"selections":[{"field":"fieldName","id":"<uuid or null>","reason":"short justification"}]}'
        user_content = (
            f"{prompt}\n\n"
            f"Record ({record_label}):\n{record_text}\n\n"
            f"Options by field:\n{options_text}\n\n"
            f"Return a JSON object exactly like: {structure_hint}. "
            "Do not include any text outside the JSON object. Use null when no option fits."
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
            temperature=self.default_temperature if temperature is None else temperature,
        )

        try:
            payload = json.loads(resp.choices[0].message.content or "{}")
        except Exception:
            payload = {}

        for entry in payload.get("selections", []):
            field = entry.get("field")
            if not field:
                continue
            selections[field] = entry.get("id")

        return selections
