"""
Integration test for RouterNode inside a LangGraph StateGraph.
"""

import tempfile

import pytest
from langgraph.graph import END, StateGraph

from mnemosyne.iris.router_node import RouterNode, RouterState
from mnemosyne.iris.semantic_router import QueryCacheStore, SemanticRouter


def dummy_embedder(text: str) -> list[float]:
    return [float(len(text)), 1.0]


@pytest.mark.integration
def test_router_node_runs_in_langgraph():
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        cache = QueryCacheStore(tmp.name)
        router = SemanticRouter(embedder=dummy_embedder, cache_store=cache)
        node = RouterNode(router)

        graph = StateGraph(RouterState)
        graph.add_node("router", node)
        graph.add_edge("router", END)
        graph.set_entry_point("router")
        compiled = graph.compile()

        result = compiled.invoke({"query": "Project status update", "result": {"answer": "ok"}})

        assert result["route"] == "ananke"
        assert result["cache_hit"] is False
        cache.close()
