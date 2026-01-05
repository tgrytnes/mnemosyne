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
                cluster_id TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'muses',
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
        cursor.execute(
            "ALTER TABLE cluster_profiles ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'muses'"
        )
        cursor.execute("UPDATE cluster_profiles SET source = 'muses' WHERE source IS NULL")
        cursor.execute("ALTER TABLE cluster_profiles ALTER COLUMN source SET NOT NULL")
        cursor.execute(
            "ALTER TABLE cluster_profiles DROP CONSTRAINT IF EXISTS cluster_profiles_cluster_id_key"
        )
        cursor.execute("DROP INDEX IF EXISTS idx_cluster_profiles_cluster_id")
        cursor.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_cluster_profiles_cluster_id_source
            ON cluster_profiles(cluster_id, source)
            """
        )
        self.connection.commit()

    def save(self, profile: ClusterProfile, source: str | None = None) -> None:
        profile_source = source or "muses"
        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO cluster_profiles (
                cluster_id,
                source,
                theme_summary,
                key_entities,
                dominant_topics,
                tags,
                confidence_score,
                representative_note_ids,
                created_at,
                metadata
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cluster_id, source) DO UPDATE SET
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
                profile_source,
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

    def get(self, cluster_id: str, source: str | None = None) -> ClusterProfile | None:
        profile_source = source or "muses"
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT
                cluster_id,
                source,
                theme_summary,
                key_entities,
                dominant_topics,
                tags,
                confidence_score,
                representative_note_ids,
                created_at,
                metadata
            FROM cluster_profiles
            WHERE cluster_id = %s AND source = %s
        """,
            (cluster_id, profile_source),
        )
        row = cursor.fetchone()
        if not row:
            return None

        metadata = row[9] if row[9] is not None else {}
        metadata = {**metadata, "source": row[1]}
        return ClusterProfile(
            cluster_id=row[0],
            theme_summary=row[2],
            key_entities=row[3] or [],
            dominant_topics=row[4] or [],
            tags=row[5] or [],
            confidence_score=row[6] or 0.0,
            representative_note_ids=row[7] or [],
            created_at=row[8],
            metadata=metadata,
        )
