"""LangGraph-compatible router node for semantic routing."""

from __future__ import annotations

from typing import Any, TypedDict

from .semantic_router import SemanticRouter


class RouterState(TypedDict, total=False):
    """State payload for routing decisions."""

    query: str
    result: dict[str, Any] | None
    route: str
    route_source: str
    cache_hit: bool
    cache_similarity: float
    error: str


class RouterNode:
    """LangGraph node wrapper around SemanticRouter."""

    def __init__(
        self, router: SemanticRouter, query_key: str = "query", result_key: str = "result"
    ):
        self.router = router
        self.query_key = query_key
        self.result_key = result_key

    def __call__(self, state: RouterState) -> RouterState:
        query = state.get(self.query_key)
        if not query:
            return {**state, "error": "query not provided"}

        result = state.get(self.result_key)
        decision = self.router.route(query, result=result)

        updated: RouterState = {
            **state,
            "route": decision.route,
            "route_source": decision.source,
            "cache_hit": decision.cache_hit,
            "cache_similarity": decision.similarity,
        }

        if decision.result is not None:
            updated[self.result_key] = decision.result

        return updated
