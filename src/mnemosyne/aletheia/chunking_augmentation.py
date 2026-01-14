"""Helpers for chunking augmentations (late/contextual)."""

from __future__ import annotations

from collections.abc import Iterable

from mnemosyne.aletheia.text_chunker import TextChunk


def compute_chunk_spans(
    text: str,
    chunks: Iterable[TextChunk],
    *,
    chunk_overlap: int = 0,
) -> list[tuple[int, int]] | None:
    """Return character spans for each chunk within the original text.

    Uses a moving cursor to avoid repeated-string ambiguity. Returns None when
    any chunk cannot be located.
    """
    spans: list[tuple[int, int]] = []
    cursor = 0
    last_end = 0
    last_start = -1
    for chunk in chunks:
        chunk_text = chunk.text
        search_start = max(0, last_end - max(0, chunk_overlap), last_start + 1)
        cursor = search_start
        start = text.find(chunk_text, cursor)
        if start == -1:
            return None
        end = start + len(chunk_text)
        spans.append((start, end))
        cursor = end
        last_end = end
        last_start = start
    return spans
