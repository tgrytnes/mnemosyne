"""PostgreSQL repository for ClusterProfile records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from mnemosyne.alexandria.the_gates import ClusterProfile


@dataclass
class ClusterProfileRepository:
    """Repository for storing ClusterProfile records in The Ananke."""

    connection: Any

    def ensure_table(self) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cluster_profiles (
                id SERIAL PRIMARY KEY,
                cluster_id TEXT NOT NULL UNIQUE,
                theme_summary TEXT NOT NULL,
                key_entities TEXT[],
                dominant_topics TEXT[],
                tags TEXT[],
                confidence_score FLOAT,
                representative_note_ids TEXT[],
                created_at TIMESTAMP,
                metadata JSONB
            )
        """
        )
        self.connection.commit()

    def save(self, profile: ClusterProfile) -> None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO cluster_profiles (
                cluster_id,
                theme_summary,
                key_entities,
                dominant_topics,
                tags,
                confidence_score,
                representative_note_ids,
                created_at,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cluster_id) DO UPDATE SET
                theme_summary = EXCLUDED.theme_summary,
                key_entities = EXCLUDED.key_entities,
                dominant_topics = EXCLUDED.dominant_topics,
                tags = EXCLUDED.tags,
                confidence_score = EXCLUDED.confidence_score,
                representative_note_ids = EXCLUDED.representative_note_ids,
                created_at = EXCLUDED.created_at,
                metadata = EXCLUDED.metadata
        """,
            (
                profile.cluster_id,
                profile.theme_summary,
                profile.key_entities,
                profile.dominant_topics,
                profile.tags,
                profile.confidence_score,
                profile.representative_note_ids,
                profile.created_at,
                json.dumps(profile.metadata),
            ),
        )
        self.connection.commit()

    def get(self, cluster_id: str) -> ClusterProfile | None:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT
                cluster_id,
                theme_summary,
                key_entities,
                dominant_topics,
                tags,
                confidence_score,
                representative_note_ids,
                created_at,
                metadata
            FROM cluster_profiles
            WHERE cluster_id = %s
        """,
            (cluster_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        metadata = row[8] if row[8] is not None else {}
        return ClusterProfile(
            cluster_id=row[0],
            theme_summary=row[1],
            key_entities=row[2] or [],
            dominant_topics=row[3] or [],
            tags=row[4] or [],
            confidence_score=row[5] or 0.0,
            representative_note_ids=row[6] or [],
            created_at=row[7],
            metadata=metadata,
        )
