"""Bootstrap cluster profiles when a source has no profiles."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.argus.delta_sync import DeltaSyncNode

logger = logging.getLogger(__name__)


@dataclass
class ClusterProfileBootstrapper:
    """Ensure cluster profiles exist for a source before graph taxonomy runs."""

    weaviate_client: object
    postgres_connection: object
    ollama_client: object
    profile_source: str
    centroid_collection_name: str
    chunk_collection_name: str
    text_property: str
    source_property: str
    heading_property: str | None
    chunk_index_property: str

    def ensure_profiles(self, cluster_ids: list[str] | None = None) -> int:
        repo = ClusterProfileRepository(self.postgres_connection)
        repo.ensure_table()

        if repo.has_profiles(self.profile_source):
            logger.info(
                "Cluster profiles already exist for source '%s'; skipping bootstrap.",
                self.profile_source,
            )
            return 0

        if not cluster_ids:
            logger.info(
                "No cluster IDs available for source '%s'; skipping bootstrap.",
                self.profile_source,
            )
            return 0

        logger.info(
            "Bootstrapping cluster profiles for source '%s' (%s clusters)...",
            self.profile_source,
            len(cluster_ids),
        )

        node = DeltaSyncNode(
            weaviate_client=self.weaviate_client,
            postgres_connection=self.postgres_connection,
            ollama_client=self.ollama_client,
            graph_pipeline=None,
            cache_store=None,
            centroid_collection_name=self.centroid_collection_name,
            chunk_collection_name=self.chunk_collection_name,
            text_property=self.text_property,
            source_property=self.source_property,
            heading_property=self.heading_property,
            chunk_index_property=self.chunk_index_property,
            profile_source=self.profile_source,
        )

        stats = node.run_once()
        logger.info(
            "Cluster profile bootstrap completed for source '%s': %s profiles updated.",
            self.profile_source,
            stats.profile_updates,
        )
        return stats.profile_updates
