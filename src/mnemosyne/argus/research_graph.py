"""LangGraph research workflow with checkpointed state."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph

from .checkpointing import CheckpointStore, ResearchState


class ResearchGraph:
    """Minimal LangGraph workflow wired to checkpoint persistence."""

    def __init__(self, checkpoint_db_path: str, langgraph_db_path: str | None = None):
        self.store = CheckpointStore(checkpoint_db_path)
        self.langgraph_db_path = (
            langgraph_db_path
            if langgraph_db_path is not None
            else checkpoint_db_path.replace(".db", "_langgraph.db")
        )
        self.checkpointer = SqliteSaver(self.langgraph_db_path)
        self.graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(dict)
        graph.add_node("semantic_extraction", self._semantic_extraction)
        graph.add_node("search", self._search)
        graph.add_node("synthesis", self._synthesis)
        graph.add_edge("semantic_extraction", "search")
        graph.add_edge("search", "synthesis")
        graph.add_edge("synthesis", END)
        graph.set_entry_point("semantic_extraction")
        return graph.compile(checkpointer=self.checkpointer)

    def run(self, state: dict[str, Any]) -> ResearchState:
        result = self.graph.invoke(
            state, config={"configurable": {"thread_id": state["query_id"]}}
        )
        return ResearchState.model_validate(result)

    def resume(self, query_id: str) -> ResearchState | None:
        return self.store.load(query_id)

    def close(self) -> None:
        self.store.close()

    def _semantic_extraction(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = dict(state)
        updated["current_node"] = "semantic_extraction"
        updated.setdefault("intermediate_results", []).append(
            {"step": "semantic_extraction", "data": "extracted"}
        )
        updated["timestamp"] = datetime.utcnow().isoformat()
        self.store.save(ResearchState.model_validate(updated))
        return updated

    def _search(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = dict(state)
        updated["current_node"] = "search"
        updated.setdefault("search_results", []).append(
            {"source": "stub", "title": "Search Results"}
        )
        updated["timestamp"] = datetime.utcnow().isoformat()
        self.store.save(ResearchState.model_validate(updated))
        return updated

    def _synthesis(self, state: dict[str, Any]) -> dict[str, Any]:
        updated = dict(state)
        updated["current_node"] = "synthesis"
        updated["synthesis_draft"] = "Draft synthesis"
        updated["timestamp"] = datetime.utcnow().isoformat()
        self.store.save(ResearchState.model_validate(updated))
        return updated
