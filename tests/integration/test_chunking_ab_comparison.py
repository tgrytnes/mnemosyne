"""
Integration test for A/B comparison using Story 019 quality metrics.
"""

import numpy as np

from scripts.compare_chunking_strategies import compare_strategies, generate_report


def test_ab_comparison_with_quality_metrics():
    """Compare strategies and include quality metrics in the report."""
    queries = [("alpha", [0]), ("beta", [1])]
    strategy_chunks = {
        "recursive": ["alpha beta.", "misc."],
        "semantic": ["alpha.", "beta."],
        "hybrid": ["alpha.", "beta."],
    }
    vectors = {
        "recursive": np.eye(2).tolist(),
        "semantic": np.eye(2).tolist(),
        "hybrid": np.eye(2).tolist(),
    }

    results = compare_strategies(queries, strategy_chunks, strategy_vectors=vectors)
    report = generate_report(results)

    assert "Boundary Quality" in report
    assert results["semantic"].boundary_quality >= 0.0
    assert results["semantic"].semantic_coherence >= 0.0
