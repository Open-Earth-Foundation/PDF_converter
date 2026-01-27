"""Utilities for storing and loading table-specific extraction context."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Mapping, Sequence


TABLE_SIGNATURE_RE = re.compile(r"table_signature\s*=\s*([A-Za-z0-9_-]+)")


def parse_table_signature(source_notes: str | None) -> str | None:
    """Extract table_signature from source_notes."""
    if not source_notes:
        return None
    match = TABLE_SIGNATURE_RE.search(source_notes)
    if not match:
        return None
    return match.group(1)


def load_table_context(
    store_root: Path,
    *,
    class_name: str,
    chunk_index: int,
    table_signatures: Sequence[str],
    max_items: int,
) -> dict[str, list[dict]]:
    """Load prior table context for a class from completed chunks."""
    if not table_signatures:
        return {}

    class_dir = store_root / class_name
    if not class_dir.exists():
        return {}

    signatures = set(table_signatures)
    collected: dict[str, list[dict]] = {sig: [] for sig in signatures}
    seen: dict[str, set[str]] = {sig: set() for sig in signatures}

    for path in sorted(class_dir.glob("chunk_*.json")):
        index = _chunk_index_from_path(path)
        if index is None or index >= chunk_index:
            continue
        payload = _read_json(path)
        tables = payload.get("tables", {})
        if not isinstance(tables, dict):
            continue
        for sig, items in tables.items():
            if sig not in signatures or not isinstance(items, list):
                continue
            for item in items:
                key = json.dumps(item, sort_keys=True, ensure_ascii=False)
                if key in seen[sig]:
                    continue
                seen[sig].add(key)
                collected[sig].append(item)

    return _limit_table_items(collected, max_items)


def write_table_context(
    store_root: Path,
    *,
    class_name: str,
    chunk_index: int,
    table_items: Mapping[str, Sequence[dict]],
    max_items: int,
) -> None:
    """Persist table context for a class and chunk."""
    if not table_items:
        return

    class_dir = store_root / class_name
    class_dir.mkdir(parents=True, exist_ok=True)

    limited_items = _limit_table_items(table_items, max_items)
    payload = {"chunk_index": chunk_index, "tables": limited_items}

    if not payload["tables"]:
        return

    tmp_path = class_dir / f".chunk_{chunk_index:04d}.json.tmp"
    final_path = class_dir / f"chunk_{chunk_index:04d}.json"
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(final_path)


def _chunk_index_from_path(path: Path) -> int | None:
    match = re.search(r"chunk_(\d+)\.json$", path.name)
    if not match:
        return None
    return int(match.group(1))


def _read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def _limit_table_items(
    table_items: Mapping[str, Sequence[dict]],
    max_items: int,
) -> dict[str, list[dict]]:
    if max_items <= 0:
        return {key: list(items) for key, items in table_items.items() if items}
    limited: dict[str, list[dict]] = {}
    for signature, items in table_items.items():
        if not items:
            continue
        limited[signature] = list(items)[:max_items]
    return limited
