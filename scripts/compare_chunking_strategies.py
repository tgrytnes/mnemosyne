"""
Compare chunking strategies with simple retrieval metrics.
"""

import argparse
from collections.abc import Callable
from dataclasses import dataclass

from mnemosyne.iris.retrieval_evaluation import RetrievalEvaluator


@dataclass
class StrategyMetrics:
    """Metrics for a single strategy."""

    recall_at_5: float
    ndcg_at_5: float
    boundary_quality: float
    semantic_coherence: float


def default_retriever(query: str, chunks: list[str]) -> list[int]:
    """
    Rank chunks by keyword overlap with the query.
    """
    query_terms = {term.lower() for term in query.split()}
    scored = []
    for idx, chunk in enumerate(chunks):
        chunk_terms = {term.lower().strip(".,") for term in chunk.split()}
        score = len(query_terms & chunk_terms)
        scored.append((score, idx))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [idx for _, idx in scored]


def compare_strategies(
    queries: list[tuple[str, list[int]]],
    strategy_chunks: dict[str, list[str]],
    retriever: Callable[[str, list[str]], list[int]] | None = None,
    strategy_vectors: dict[str, list[list[float]]] | None = None,
) -> dict[str, StrategyMetrics]:
    """
    Compare strategies using Recall@5 and NDCG@5.

    Args:
        queries: List of tuples (query, relevant_chunk_ids)
        strategy_chunks: Mapping of strategy name to list of chunk texts
        retriever: Optional custom retriever (defaults to keyword overlap)
    """
    retriever = retriever or default_retriever
    evaluator = RetrievalEvaluator()
    results: dict[str, StrategyMetrics] = {}

    for strategy, chunks in strategy_chunks.items():
        recalls = []
        ndcgs = []
        for query, relevant in queries:
            ranked_ids = retriever(query, chunks)
            recalls.append(evaluator.recall_at_k(ranked_ids, relevant, k=5))
            ndcgs.append(evaluator.ndcg_at_k(ranked_ids, relevant, k=5))

        if strategy_vectors and strategy in strategy_vectors:
            import numpy as np

            from mnemosyne.iris.chunking_quality import ChunkingQualityAnalyzer

            vectors = np.array(strategy_vectors[strategy])
            analyzer = ChunkingQualityAnalyzer(chunks, vectors)
            metrics = analyzer.analyze()
            boundary_quality = metrics.boundary_quality
            semantic_coherence = metrics.semantic_coherence
        else:
            boundary_quality = 0.0
            semantic_coherence = 0.0

        results[strategy] = StrategyMetrics(
            recall_at_5=sum(recalls) / len(recalls),
            ndcg_at_5=sum(ndcgs) / len(ndcgs),
            boundary_quality=boundary_quality,
            semantic_coherence=semantic_coherence,
        )

    return results


def generate_report(results: dict[str, StrategyMetrics]) -> str:
    """Generate a simple markdown report for comparison results."""
    lines = [
        "| Strategy | Recall@5 | NDCG@5 | Boundary Quality | Semantic Coherence |",
        "|---|---|---|---|---|",
    ]
    for strategy, metrics in results.items():
        lines.append(
            f"| {strategy} | {metrics.recall_at_5:.2f} | {metrics.ndcg_at_5:.2f} | "
            f"{metrics.boundary_quality:.2f} | {metrics.semantic_coherence:.2f} |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare chunking strategies.")
    parser.add_argument("--print-example", action="store_true", help="Print example output")
    args = parser.parse_args()

    if args.print_example:
        queries = [("alpha", [0]), ("beta", [1])]
        chunks = {"recursive": ["alpha content", "beta content"]}
        results = compare_strategies(queries, chunks)
        for strategy, metrics in results.items():
            print(f"{strategy}: recall@5={metrics.recall_at_5:.2f}, ndcg@5={metrics.ndcg_at_5:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
