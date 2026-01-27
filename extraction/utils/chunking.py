"""Token-based Markdown chunking with paragraph/sentence boundaries and table awareness."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Iterable, Sequence

import tiktoken


HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
TABLE_SEPARATOR_RE = re.compile(
    r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$"
)
SENTENCE_END_RE = re.compile(r"[.!?](?:\s+|$)")


@dataclass(frozen=True)
class TableInfo:
    """Metadata for a Markdown table."""

    signature: str
    header: str
    heading_path: str | None
    start_line: int
    end_line: int


@dataclass(frozen=True)
class TextBlock:
    """A chunkable unit of text."""

    kind: str  # "paragraph" or "table"
    text: str
    start_line: int
    end_line: int
    token_count: int
    table: TableInfo | None = None
    heading_path: str | None = None


@dataclass(frozen=True)
class Chunk:
    """A token-bounded chunk of Markdown."""

    index: int
    text: str
    token_count: int
    start_line: int
    end_line: int
    tables: Sequence[TableInfo]


def chunk_markdown(
    markdown_text: str,
    *,
    chunk_size_tokens: int,
    chunk_overlap_tokens: int,
    boundary_mode: str = "paragraph_or_sentence",
    encoding_name: str = "cl100k_base",
    keep_tables_intact: bool = True,
) -> list[Chunk]:
    """Split Markdown into token-bounded chunks with overlap."""
    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be positive.")
    if chunk_overlap_tokens < 0:
        raise ValueError("chunk_overlap_tokens must be non-negative.")
    if boundary_mode != "paragraph_or_sentence":
        raise ValueError(f"Unsupported boundary_mode: {boundary_mode}")

    encoding = tiktoken.get_encoding(encoding_name)
    blocks = _parse_blocks(markdown_text, encoding)
    blocks = _split_oversized_paragraphs(blocks, chunk_size_tokens, encoding)

    base_chunks: list[list[TextBlock]] = []
    current: list[TextBlock] = []
    current_tokens = 0

    for block in blocks:
        block_tokens = block.token_count
        if block.kind == "table" and keep_tables_intact:
            if current and current_tokens + block_tokens > chunk_size_tokens:
                base_chunks.append(current)
                current = []
                current_tokens = 0
            current.append(block)
            current_tokens += block_tokens
            continue

        if current and current_tokens + block_tokens > chunk_size_tokens:
            base_chunks.append(current)
            current = []
            current_tokens = 0

        current.append(block)
        current_tokens += block_tokens

    if current:
        base_chunks.append(current)

    chunks: list[Chunk] = []
    for idx, base in enumerate(base_chunks):
        overlap_blocks: list[TextBlock] = []
        if idx > 0 and chunk_overlap_tokens:
            overlap_blocks = _take_overlap_blocks(
                base_chunks[idx - 1], chunk_overlap_tokens
            )
        combined_blocks = overlap_blocks + base
        text = _join_blocks(combined_blocks)
        token_count = len(encoding.encode(text))
        start_line = combined_blocks[0].start_line
        end_line = combined_blocks[-1].end_line
        tables = [b.table for b in combined_blocks if b.table]
        chunks.append(
            Chunk(
                index=idx,
                text=text,
                token_count=token_count,
                start_line=start_line,
                end_line=end_line,
                tables=tables,
            )
        )

    return chunks


def extract_tables(markdown_text: str) -> list[TableInfo]:
    """Extract table metadata from Markdown text."""
    encoding = tiktoken.get_encoding("cl100k_base")
    blocks = _parse_blocks(markdown_text, encoding)
    return [block.table for block in blocks if block.table]


def _parse_blocks(markdown_text: str, encoding) -> list[TextBlock]:
    lines = markdown_text.splitlines()
    blocks: list[TextBlock] = []
    heading_path: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        heading_match = HEADING_RE.match(line.strip())
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            heading_path = heading_path[: max(level - 1, 0)] + [title]

        if _is_table_header(line) and _is_table_separator(lines, i + 1):
            start = i
            header_line = lines[i].strip()
            i += 2
            while i < len(lines) and lines[i].strip() and "|" in lines[i]:
                i += 1
            table_lines = lines[start:i]
            table_text = "\n".join(table_lines).strip()
            heading = " > ".join(heading_path) if heading_path else None
            signature = _table_signature(header_line, heading)
            table_info = TableInfo(
                signature=signature,
                header=header_line,
                heading_path=heading,
                start_line=start + 1,
                end_line=i,
            )
            blocks.append(
                TextBlock(
                    kind="table",
                    text=table_text,
                    start_line=start + 1,
                    end_line=i,
                    token_count=len(encoding.encode(table_text)),
                    table=table_info,
                    heading_path=heading,
                )
            )
            continue

        if not line.strip():
            i += 1
            continue

        start = i
        paragraph_lines: list[str] = []
        while i < len(lines):
            if not lines[i].strip():
                break
            if _is_table_header(lines[i]) and _is_table_separator(lines, i + 1):
                break
            paragraph_lines.append(lines[i])
            i += 1
        paragraph_text = "\n".join(paragraph_lines).strip()
        if paragraph_text:
            heading = " > ".join(heading_path) if heading_path else None
            blocks.append(
                TextBlock(
                    kind="paragraph",
                    text=paragraph_text,
                    start_line=start + 1,
                    end_line=i,
                    token_count=len(encoding.encode(paragraph_text)),
                    heading_path=heading,
                )
            )

    return blocks


def _split_oversized_paragraphs(
    blocks: Sequence[TextBlock],
    chunk_size_tokens: int,
    encoding,
) -> list[TextBlock]:
    split_blocks: list[TextBlock] = []
    for block in blocks:
        if block.kind != "paragraph" or block.token_count <= chunk_size_tokens:
            split_blocks.append(block)
            continue

        sentences = _split_into_sentences(block.text)
        if not sentences:
            split_blocks.append(block)
            continue

        for sentence in sentences:
            sentence_text = sentence.strip()
            if not sentence_text:
                continue
            split_blocks.append(
                TextBlock(
                    kind="paragraph",
                    text=sentence_text,
                    start_line=block.start_line,
                    end_line=block.end_line,
                    token_count=len(encoding.encode(sentence_text)),
                    heading_path=block.heading_path,
                )
            )

    return split_blocks


def _split_into_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    start = 0
    for match in SENTENCE_END_RE.finditer(text):
        end = match.end()
        sentences.append(text[start:end])
        start = end
    if start < len(text):
        remainder = text[start:].strip()
        if remainder:
            sentences.append(remainder)
    return sentences


def _take_overlap_blocks(blocks: Sequence[TextBlock], overlap_tokens: int) -> list[TextBlock]:
    selected: list[TextBlock] = []
    tokens = 0
    for block in reversed(blocks):
        selected.append(block)
        tokens += block.token_count
        if tokens >= overlap_tokens:
            break
    return list(reversed(selected))


def _join_blocks(blocks: Iterable[TextBlock]) -> str:
    return "\n\n".join(block.text for block in blocks if block.text)


def _is_table_header(line: str) -> bool:
    if "|" not in line:
        return False
    return bool(re.search(r"\w", line))


def _is_table_separator(lines: Sequence[str], index: int) -> bool:
    if index < 0 or index >= len(lines):
        return False
    return bool(TABLE_SEPARATOR_RE.match(lines[index]))


def _table_signature(header_line: str, heading_path: str | None) -> str:
    header_normalized = re.sub(r"\s+", " ", header_line.strip().lower())
    seed = f"{heading_path or ''}|{header_normalized}"
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:12]
