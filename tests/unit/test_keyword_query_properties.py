"""Unit tests for keyword/BM25 query property defaults."""

from mnemosyne.iris.keyword_search import resolve_keyword_query_properties


def test_default_keyword_properties_include_context_header(monkeypatch):
    monkeypatch.delenv("KEYWORD_QUERY_PROPERTIES", raising=False)

    properties = resolve_keyword_query_properties()

    assert "text" in properties
    assert "contextHeader" in properties
