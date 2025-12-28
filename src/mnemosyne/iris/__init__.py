"""Iris - Quality Analysis and Metrics Package."""

# Story 020 additions
from mnemosyne.iris.structure_quality import (
    StructurePreservationAnalyzer,
    StructurePreservationMetrics,
)

# Story 019 modules (will be available after merge)
try:
    from mnemosyne.iris.chunking_quality import (
        ChunkingQualityAnalyzer,
        ChunkingQualityMetrics,
    )
    from mnemosyne.iris.embedding_quality import (
        EmbeddingQualityAnalyzer,
        EmbeddingQualityMetrics,
    )
    from mnemosyne.iris.retrieval_evaluation import (
        GroundTruthDataset,
        GroundTruthQuery,
        RetrievalEvaluator,
    )

    __all__ = [
        "ChunkingQualityAnalyzer",
        "ChunkingQualityMetrics",
        "EmbeddingQualityAnalyzer",
        "EmbeddingQualityMetrics",
        "GroundTruthDataset",
        "GroundTruthQuery",
        "RetrievalEvaluator",
        "StructurePreservationAnalyzer",
        "StructurePreservationMetrics",
    ]
except ImportError:
    # Story 019 modules not yet available (on feature branch)
    __all__ = [
        "StructurePreservationAnalyzer",
        "StructurePreservationMetrics",
    ]
