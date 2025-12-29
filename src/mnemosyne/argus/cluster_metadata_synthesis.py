"""Structured metadata synthesis for clusters."""

from __future__ import annotations

from collections import Counter
import json
import logging
import re
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
                if isinstance(payload, dict):
                    data = payload
                else:
                    data = self._safe_parse_json(payload)
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
            "Use JSON mode only. Ensure theme_summary includes 1-3 key terms "
            "copied verbatim from the representative notes.\n\n"
            f"Cluster ID: {cluster.cluster_id}\n"
            f"Representative Note IDs: {cluster.representative_note_ids}\n"
            f"Known Tags: {cluster.tags or []}\n\n"
            f"Representative Notes:\n{notes}\n"
        )

    def _validate_profile(self, cluster: ClusterData, data: dict[str, Any]) -> ClusterProfile:
        keywords = self._extract_keywords(cluster.representative_notes)
        if "cluster_id" not in data:
            data["cluster_id"] = cluster.cluster_id
        if "representative_note_ids" not in data:
            data["representative_note_ids"] = cluster.representative_note_ids
        if not isinstance(data.get("tags"), list):
            data["tags"] = cluster.tags or []
        if not isinstance(data.get("metadata"), dict):
            data["metadata"] = cluster.metadata or {}
        if "created_at" not in data:
            data["created_at"] = datetime.utcnow().isoformat()
        if "theme_summary" not in data or not isinstance(data["theme_summary"], str):
            data["theme_summary"] = self._fallback_theme_summary(cluster)
        data["theme_summary"] = self._ensure_keywords_in_summary(
            data["theme_summary"],
            keywords,
        )
        if not isinstance(data.get("key_entities"), list):
            data["key_entities"] = keywords[:3]
        if not isinstance(data.get("dominant_topics"), list):
            data["dominant_topics"] = keywords[:3]
        if not isinstance(data.get("confidence_score"), (int, float)):
            data["confidence_score"] = 0.5

        return ClusterProfile.model_validate(data)

    def _safe_parse_json(self, payload: str) -> dict[str, Any]:
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            start = payload.find("{")
            end = payload.rfind("}")
            if start == -1 or end == -1 or end <= start:
                logger.warning("LLM returned non-JSON payload; using fallback")
                return {}
            try:
                return json.loads(payload[start : end + 1])
            except json.JSONDecodeError:
                logger.warning("LLM returned malformed JSON; using fallback")
                return {}

    def _extract_keywords(self, notes: list[str], limit: int = 5) -> list[str]:
        text = " ".join(notes).lower()
        tokens = re.findall(r"[a-z][a-z0-9-]+", text)
        stopwords = {
            "about",
            "across",
            "after",
            "again",
            "analysis",
            "and",
            "are",
            "based",
            "before",
            "between",
            "case",
            "cases",
            "data",
            "deep",
            "for",
            "from",
            "have",
            "into",
            "note",
            "notes",
            "over",
            "that",
            "this",
            "with",
            "work",
        }
        filtered = [t for t in tokens if len(t) > 3 and t not in stopwords]
        return [token for token, _ in Counter(filtered).most_common(limit)]

    def _fallback_theme_summary(self, cluster: ClusterData) -> str:
        notes = " ".join(cluster.representative_notes).strip()
        if not notes:
            return "Cluster themes summary unavailable."
        sentence = re.split(r"[.!?]\s+", notes)[0].strip()
        return sentence if sentence else notes[:200]

    def _ensure_keywords_in_summary(self, summary: str, keywords: list[str]) -> str:
        if not keywords:
            return summary
        summary_lower = summary.lower()
        if any(keyword in summary_lower for keyword in keywords):
            return summary
        return f"{summary} Key themes: {', '.join(keywords)}"
