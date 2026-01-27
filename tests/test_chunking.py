from __future__ import annotations

import tiktoken

from extraction.utils.chunking import chunk_markdown


def test_chunking_respects_paragraph_boundaries() -> None:
    encoding = tiktoken.get_encoding("cl100k_base")
    paragraphs = [
        "Alpha beta gamma.",
        "Delta epsilon zeta.",
        "Eta theta iota.",
    ]
    markdown = "\n\n".join(paragraphs)
    token_counts = [len(encoding.encode(p)) for p in paragraphs]
    chunk_size = token_counts[0] + token_counts[1] - 1

    chunks = chunk_markdown(
        markdown,
        chunk_size_tokens=chunk_size,
        chunk_overlap_tokens=0,
    )

    assert chunks, "Expected at least one chunk."
    assert paragraphs[0] in chunks[0].text
    assert paragraphs[1] in chunks[1].text
    assert paragraphs[0] not in chunks[1].text


def test_chunking_splits_long_paragraph_on_sentence_end() -> None:
    encoding = tiktoken.get_encoding("cl100k_base")
    paragraph = "First sentence. Second sentence! Third sentence?"
    sentence_tokens = [
        len(encoding.encode("First sentence.")),
        len(encoding.encode("Second sentence!")),
        len(encoding.encode("Third sentence?")),
    ]
    chunk_size = sentence_tokens[0] + 1

    chunks = chunk_markdown(
        paragraph,
        chunk_size_tokens=chunk_size,
        chunk_overlap_tokens=0,
    )

    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.text.strip()[-1] in ".!?"


def test_chunking_keeps_tables_intact() -> None:
    table = "\n".join(
        [
            "| A | B |",
            "| --- | --- |",
            "| 1 | 2 |",
            "| 3 | 4 |",
        ]
    )
    markdown = "\n\n".join(["Intro text.", table, "Outro text."])

    chunks = chunk_markdown(
        markdown,
        chunk_size_tokens=5,
        chunk_overlap_tokens=0,
        keep_tables_intact=True,
    )

    occurrences = sum(1 for chunk in chunks if table in chunk.text)
    assert occurrences == 1
