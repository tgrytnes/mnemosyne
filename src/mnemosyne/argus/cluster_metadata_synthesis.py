"""Structured metadata synthesis for clusters."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mnemosyne.alexandria.the_gates import ClusterProfile

logger = logging.getLogger(__name__)


@dataclass
class ClusterData:
    """Cluster data required for profile synthesis."""

    cluster_id: str
    representative_notes: list[str]
    representative_note_ids: list[str]
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class ClusterProfileResult:
    """Result wrapper for synthesis outcomes."""

    status: str
    profile: ClusterProfile | None = None
    error: str | None = None


class ClusterMetadataSynthesizer:
    """Generate structured cluster profiles using an LLM."""

    def __init__(
        self,
        ollama_client,
        model: str = "qwen3:0.6b",
        temperature: float = 0.3,
        max_retries: int = 1,
    ):
        self.ollama_client = ollama_client
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries

    def synthesize(self, cluster: ClusterData) -> ClusterProfileResult:
        """Generate a ClusterProfile from cluster data."""
        prompt = self._build_prompt(cluster)
        last_error: str | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self.ollama_client.generate(
                    model=self.model,
                    prompt=prompt,
                    format="json",
                    options={"temperature": self.temperature},
                )
                payload = response.get("response", "")
                data = json.loads(payload)
                profile = self._validate_profile(cluster, data)
                return ClusterProfileResult(status="success", profile=profile)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Cluster profile synthesis failed (attempt %s): %s",
                    attempt + 1,
                    last_error,
                )

        return ClusterProfileResult(status="failed", error=last_error)

    def _build_prompt(self, cluster: ClusterData) -> str:
        notes = "\n\n".join(cluster.representative_notes)
        return (
            "You are generating a structured cluster profile in JSON.\n"
            "Return a single JSON object with the following keys:\n"
            "cluster_id, theme_summary, key_entities, dominant_topics, tags, "
            "confidence_score, representative_note_ids, created_at, metadata.\n"
            "Use JSON mode only.\n\n"
            f"Cluster ID: {cluster.cluster_id}\n"
            f"Representative Note IDs: {cluster.representative_note_ids}\n"
            f"Known Tags: {cluster.tags or []}\n\n"
            f"Representative Notes:\n{notes}\n"
        )

    def _validate_profile(self, cluster: ClusterData, data: dict[str, Any]) -> ClusterProfile:
        if "cluster_id" not in data:
            data["cluster_id"] = cluster.cluster_id
        if "representative_note_ids" not in data:
            data["representative_note_ids"] = cluster.representative_note_ids
        if "tags" not in data and cluster.tags:
            data["tags"] = cluster.tags
        if "metadata" not in data:
            data["metadata"] = cluster.metadata or {}
        if "created_at" not in data:
            data["created_at"] = datetime.utcnow().isoformat()

        return ClusterProfile.model_validate(data)
