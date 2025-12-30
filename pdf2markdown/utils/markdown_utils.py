"""Markdown utilities for PDF2Markdown."""

import re
from typing import Iterable


def _collapse_blank_lines(lines: Iterable[str]) -> list[str]:
    """Collapse sequences of blank lines to a maximum of one."""
    collapsed: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line.strip()
        if is_blank and previous_blank:
            continue
        collapsed.append(line)
        previous_blank = is_blank
    return collapsed


def normalize_toc_markdown(text: str) -> str:
    """Lightweight normalization for combined Markdown output.

    - Strips trailing whitespace.
    - Collapses excessive blank lines.
    - Normalizes TOC bullets (removes stray leading digits or dots).
    """
    # Normalize newlines and trailing whitespace
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").split("\n")]

    normalized: list[str] = []
    toc_pattern = re.compile(r"^\s*[\d\.\-]*\s*(.+)$")
    for line in lines:
        match = toc_pattern.match(line)
        normalized.append(match.group(1) if match else line)

    normalized = _collapse_blank_lines(normalized)
    return "\n".join(normalized).strip()


__all__ = ["normalize_toc_markdown"]
