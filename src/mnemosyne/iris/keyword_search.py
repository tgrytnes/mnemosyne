"""Keyword/BM25 search helpers."""

from __future__ import annotations

import os


def resolve_keyword_query_properties() -> list[str]:
    """Return properties to use for keyword/BM25 search."""
    raw = os.getenv("KEYWORD_QUERY_PROPERTIES", "")
    properties = [item.strip() for item in raw.split(",") if item.strip()]
    if not properties:
        properties = ["text", "contextHeader"]

    for required in ("text", "contextHeader"):
        if required not in properties:
            properties.append(required)

    return properties
