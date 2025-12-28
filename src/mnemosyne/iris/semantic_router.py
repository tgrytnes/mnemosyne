"""Semantic routing for Iris query handling."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256
from typing import Any, Callable

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Routing decision for a query."""

    route: str
    source: str
    cache_hit: bool
    similarity: float
    result: dict[str, Any] | None = None


@dataclass
class CacheStats:
    """Cache hit/miss metrics."""

    hits: int = 0
    misses: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class QueryCacheStore:
    """SQLite-backed cache for query embeddings and results."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS query_cache (
                id INTEGER PRIMARY KEY,
                query_text TEXT NOT NULL,
                query_hash TEXT NOT NULL UNIQUE,
                query_embedding TEXT NOT NULL,
                result_json TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                access_count INTEGER DEFAULT 0
            )
        """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_query_hash ON query_cache(query_hash)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_last_accessed ON query_cache(last_accessed)"
        )
        self._conn.commit()

    def upsert(
        self,
        query_text: str,
        embedding: list[float],
        result: dict[str, Any],
        source: str,
    ) -> None:
        query_hash = self._hash_query(query_text)
        payload = json.dumps(embedding)
        result_json = json.dumps(result)
        now = datetime.utcnow().isoformat()

        self._conn.execute(
            """
            INSERT INTO query_cache (
                query_text,
                query_hash,
                query_embedding,
                result_json,
                source,
                created_at,
                last_accessed,
                access_count
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(query_hash) DO UPDATE SET
                query_text = EXCLUDED.query_text,
                query_embedding = EXCLUDED.query_embedding,
                result_json = EXCLUDED.result_json,
                source = EXCLUDED.source,
                last_accessed = EXCLUDED.last_accessed,
                access_count = query_cache.access_count + 1
        """,
            (query_text, query_hash, payload, result_json, source, now, now),
        )
        self._conn.commit()

    def get_all(self) -> list[sqlite3.Row]:
        return self._conn.execute("SELECT * FROM query_cache").fetchall()

    def update_access(self, cache_id: int) -> None:
        self._conn.execute(
            """
            UPDATE query_cache
            SET last_accessed = ?, access_count = access_count + 1
            WHERE id = ?
        """,
            (datetime.utcnow().isoformat(), cache_id),
        )
        self._conn.commit()

    def delete_stale(self, max_age_days: int) -> int:
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        cursor = self._conn.execute(
            "DELETE FROM query_cache WHERE created_at < ?",
            (cutoff.isoformat(),),
        )
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _hash_query(query_text: str) -> str:
        return sha256(query_text.strip().lower().encode("utf-8")).hexdigest()


class SemanticRouter:
    """Router node that selects cache, Weaviate, or web search."""

    def __init__(
        self,
        embedder: Callable[[str], list[float]],
        cache_store: QueryCacheStore,
        similarity_threshold: float = 0.95,
        cache_ttl_days: int = 7,
    ):
        self.embedder = embedder
        self.cache_store = cache_store
        self.similarity_threshold = similarity_threshold
        self.cache_ttl_days = cache_ttl_days
        self.stats = CacheStats()

    def route(self, query: str, result: dict[str, Any] | None = None) -> RoutingDecision:
        embedding = self.embedder(query)
        cached = self._check_cache(embedding)
        if cached:
            self.stats.hits += 1
            logger.info("Cache hit rate: %.2f", self.stats.hit_rate)
            return cached

        self.stats.misses += 1
        logger.info("Cache hit rate: %.2f", self.stats.hit_rate)

        route = self._classify(query)
        decision = RoutingDecision(route=route, source=route, cache_hit=False, similarity=0.0)
        if result is not None:
            self.cache_store.upsert(query, embedding, result, source=route)
            decision.result = result
        return decision

    def invalidate_cache(self) -> int:
        return self.cache_store.delete_stale(self.cache_ttl_days)

    def get_cache_stats(self) -> CacheStats:
        return self.stats

    def _check_cache(self, embedding: list[float]) -> RoutingDecision | None:
        rows = self.cache_store.get_all()
        if not rows:
            return None

        target = np.array(embedding)
        target_norm = np.linalg.norm(target)
        if target_norm == 0:
            return None

        best_row = None
        best_score = 0.0
        for row in rows:
            cached_embedding = np.array(json.loads(row["query_embedding"]))
            denom = np.linalg.norm(cached_embedding) * target_norm
            if denom == 0:
                continue
            score = float(np.dot(cached_embedding, target) / denom)
            if score > best_score:
                best_score = score
                best_row = row

        if best_row and best_score >= self.similarity_threshold:
            result = json.loads(best_row["result_json"])
            self.cache_store.update_access(best_row["id"])
            return RoutingDecision(
                route=best_row["source"],
                source="cache",
                cache_hit=True,
                similarity=best_score,
                result=result,
            )

        return None

    @staticmethod
    def _classify(query: str) -> str:
        lowered = query.lower()
        if "http" in lowered or "latest" in lowered or "news" in lowered:
            return "web"
        if "project" in lowered or "status" in lowered or "deadline" in lowered:
            return "ananke"
        return "weaviate"
