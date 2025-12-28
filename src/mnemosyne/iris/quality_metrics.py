"""
Quality metrics orchestration for Mnemosyne.

Coordinates embedding quality, retrieval evaluation, and chunking quality
analysis to generate comprehensive quality reports.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
import weaviate
from weaviate.classes.query import MetadataQuery

from mnemosyne.iris.chunking_quality import ChunkData, ChunkingQualityAnalyzer
from mnemosyne.iris.embedding_quality import EmbeddingQualityAnalyzer
from mnemosyne.iris.retrieval_evaluation import GroundTruthDataset, RetrievalEvaluator


@dataclass
class QualityReport:
    """Complete quality report with all metrics."""

    timestamp: datetime
    collection_name: str
    num_chunks: int
    embedding_metrics: Optional[dict]
    retrieval_metrics: Optional[dict]
    chunking_metrics: Optional[dict]


class QualityMetricsOrchestrator:
    """
    Orchestrates quality analysis across all dimensions.

    Fetches data from Weaviate, runs analyses, generates reports.
    """

    def __init__(
        self,
        weaviate_client: weaviate.WeaviateClient,
        collection_name: str = "TheMuses",
    ):
        """
        Initialize orchestrator.

        Args:
            weaviate_client: Connected Weaviate client
            collection_name: Name of collection to analyze
        """
        self.client = weaviate_client
        self.collection_name = collection_name

    def fetch_chunks_with_vectors(
        self, limit: Optional[int] = None
    ) -> tuple[List[ChunkData], np.ndarray]:
        """
        Fetch chunks with embeddings from Weaviate.

        Args:
            limit: Max number of chunks to fetch (None = all)

        Returns:
            (chunks, embeddings_matrix)
        """
        collection = self.client.collections.get(self.collection_name)

        # Fetch objects with vectors
        if limit:
            response = collection.query.fetch_objects(
                limit=limit,
                include_vector=True,
                return_metadata=MetadataQuery(creation_time=True),
            )
        else:
            # Fetch all objects (may be slow for large collections)
            response = collection.query.fetch_objects(
                include_vector=True,
                return_metadata=MetadataQuery(creation_time=True),
            )

        chunks = []
        embeddings = []

        for obj in response.objects:
            # Extract properties
            props = obj.properties
            text = props.get("text", "")
            source_file = props.get("sourceFile", "")
            chunk_index = props.get("chunkIndex", 0)

            # Extract vector
            vector = obj.vector.get("default") if obj.vector else None

            if vector is not None:
                chunks.append(
                    ChunkData(
                        text=text,
                        chunk_id=str(obj.uuid),
                        source_file=source_file,
                        chunk_index=chunk_index,
                        embedding=np.array(vector),
                    )
                )
                embeddings.append(vector)

        embeddings_matrix = np.array(embeddings) if embeddings else np.array([])

        return chunks, embeddings_matrix

    def analyze_embedding_quality(
        self, embeddings: np.ndarray
    ) -> Optional[dict]:
        """
        Analyze embedding quality.

        Args:
            embeddings: Matrix of shape (n_samples, n_dimensions)

        Returns:
            Dict of metrics or None if insufficient data
        """
        if embeddings.size == 0 or embeddings.shape[0] < 10:
            return None

        analyzer = EmbeddingQualityAnalyzer(embeddings)
        metrics = analyzer.analyze()

        return {
            "avg_pairwise_similarity": metrics.avg_pairwise_similarity,
            "similarity_std": metrics.similarity_std,
            "vector_space_coverage": metrics.vector_space_coverage,
            "dimensionality_usage": metrics.dimensionality_usage,
            "embedding_collapse_detected": metrics.embedding_collapse_detected,
            "avg_vector_magnitude": metrics.avg_vector_magnitude,
            "magnitude_std": metrics.magnitude_std,
        }

    def analyze_chunking_quality(self, chunks: List[ChunkData]) -> Optional[dict]:
        """
        Analyze chunking quality.

        Args:
            chunks: List of ChunkData objects

        Returns:
            Dict of metrics or None if insufficient data
        """
        if not chunks:
            return None

        analyzer = ChunkingQualityAnalyzer(chunks)
        metrics = analyzer.analyze()

        return {
            "avg_chunk_size": metrics.avg_chunk_size,
            "chunk_size_std": metrics.chunk_size_std,
            "min_chunk_size": metrics.min_chunk_size,
            "max_chunk_size": metrics.max_chunk_size,
            "semantic_coherence": metrics.semantic_coherence,
            "boundary_quality": metrics.boundary_quality,
            "overlap_effectiveness": metrics.overlap_effectiveness,
        }

    def analyze_retrieval_quality(
        self, ground_truth_path: Optional[Path] = None
    ) -> Optional[dict]:
        """
        Analyze retrieval quality using ground truth dataset.

        Args:
            ground_truth_path: Path to ground truth JSON file

        Returns:
            Dict of metrics or None if ground truth unavailable
        """
        if ground_truth_path is None or not ground_truth_path.exists():
            return None

        # Load ground truth
        ground_truth = GroundTruthDataset(ground_truth_path)

        if len(ground_truth) == 0:
            return None

        # Create retrieval function
        def retrieve_docs(query: str) -> List[str]:
            """Query Weaviate and return ordered list of source files."""
            collection = self.client.collections.get(self.collection_name)

            # Semantic search
            response = collection.query.near_text(query=query, limit=20)

            # Extract source file paths
            docs = []
            for obj in response.objects:
                source_file = obj.properties.get("sourceFile", "")
                if source_file and source_file not in docs:
                    docs.append(source_file)

            return docs

        # Evaluate
        evaluator = RetrievalEvaluator(ground_truth)
        metrics = evaluator.evaluate(retrieve_docs, k_values=[5, 10, 20])

        return {
            "recall_at_5": metrics.recall_at_5,
            "recall_at_10": metrics.recall_at_10,
            "recall_at_20": metrics.recall_at_20,
            "ndcg_at_5": metrics.ndcg_at_5,
            "ndcg_at_10": metrics.ndcg_at_10,
            "ndcg_at_20": metrics.ndcg_at_20,
            "mrr": metrics.mrr,
            "num_queries": metrics.num_queries,
        }

    def generate_report(
        self,
        ground_truth_path: Optional[Path] = None,
        sample_size: Optional[int] = 1000,
    ) -> QualityReport:
        """
        Generate comprehensive quality report.

        Args:
            ground_truth_path: Optional path to ground truth dataset
            sample_size: Max chunks to analyze (None = all)

        Returns:
            QualityReport with all metrics
        """
        # Fetch data
        chunks, embeddings = self.fetch_chunks_with_vectors(limit=sample_size)

        # Analyze each dimension
        embedding_metrics = self.analyze_embedding_quality(embeddings)
        chunking_metrics = self.analyze_chunking_quality(chunks)
        retrieval_metrics = self.analyze_retrieval_quality(ground_truth_path)

        return QualityReport(
            timestamp=datetime.now(),
            collection_name=self.collection_name,
            num_chunks=len(chunks),
            embedding_metrics=embedding_metrics,
            retrieval_metrics=retrieval_metrics,
            chunking_metrics=chunking_metrics,
        )


class QualityReportFormatter:
    """Formats quality reports as Markdown or HTML."""

    @staticmethod
    def format_markdown(report: QualityReport) -> str:
        """
        Format report as Markdown.

        Args:
            report: QualityReport to format

        Returns:
            Markdown string
        """
        lines = [
            "# Mnemosyne Quality Report",
            f"",
            f"**Generated**: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Collection**: {report.collection_name}",
            f"**Chunks Analyzed**: {report.num_chunks}",
            f"",
        ]

        # Embedding quality
        if report.embedding_metrics:
            em = report.embedding_metrics
            lines.extend(
                [
                    "## Embedding Quality",
                    "",
                    f"- **Avg Pairwise Similarity**: {em['avg_pairwise_similarity']:.3f}",
                    f"- **Similarity Std Dev**: {em['similarity_std']:.3f}",
                    f"- **Vector Space Coverage**: {em['vector_space_coverage']:.1%}",
                    f"- **Dimensionality Usage**: {em['dimensionality_usage']:.1%}",
                    f"- **Embedding Collapse**: {'⚠️ YES' if em['embedding_collapse_detected'] else '✅ No'}",
                    f"- **Avg Vector Magnitude**: {em['avg_vector_magnitude']:.3f}",
                    "",
                ]
            )

        # Retrieval quality
        if report.retrieval_metrics:
            rm = report.retrieval_metrics
            lines.extend(
                [
                    "## Retrieval Performance",
                    "",
                    f"*Based on {rm['num_queries']} ground truth queries*",
                    "",
                    f"- **Recall@5**: {rm['recall_at_5']:.3f}",
                    f"- **Recall@10**: {rm['recall_at_10']:.3f}",
                    f"- **Recall@20**: {rm['recall_at_20']:.3f}",
                    f"- **NDCG@5**: {rm['ndcg_at_5']:.3f}",
                    f"- **NDCG@10**: {rm['ndcg_at_10']:.3f}",
                    f"- **NDCG@20**: {rm['ndcg_at_20']:.3f}",
                    f"- **MRR**: {rm['mrr']:.3f}",
                    "",
                ]
            )
        else:
            lines.extend(
                [
                    "## Retrieval Performance",
                    "",
                    "*No ground truth dataset provided - skipping retrieval evaluation*",
                    "",
                ]
            )

        # Chunking quality
        if report.chunking_metrics:
            cm = report.chunking_metrics
            lines.extend(
                [
                    "## Chunking Quality",
                    "",
                    f"- **Avg Chunk Size**: {cm['avg_chunk_size']:.0f} chars",
                    f"- **Chunk Size Std Dev**: {cm['chunk_size_std']:.0f} chars",
                    f"- **Min/Max Chunk Size**: {cm['min_chunk_size']} / {cm['max_chunk_size']} chars",
                    f"- **Boundary Quality**: {cm['boundary_quality']:.1%} at natural boundaries",
                ]
            )

            if cm["semantic_coherence"] is not None:
                lines.append(
                    f"- **Semantic Coherence**: {cm['semantic_coherence']:.3f}"
                )

            if cm["overlap_effectiveness"] is not None:
                lines.append(
                    f"- **Overlap Effectiveness**: {cm['overlap_effectiveness']:.1%}"
                )

            lines.append("")

        return "\n".join(lines)
