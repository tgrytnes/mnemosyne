"""
Unit tests for A/B comparison of chunking strategies.
"""

from scripts.compare_chunking_strategies import compare_strategies, generate_report


class TestChunkingABComparison:
    """Test strategy comparison metrics."""

    def test_hybrid_outperforms_recursive_in_toy_example(self):
        """Hybrid should score >= recursive on recall/NDCG for toy data."""
        queries = [
            ("alpha", [0]),
            ("beta", [1]),
        ]
        strategy_chunks = {
            "recursive": ["alpha beta", "misc"],
            "semantic": ["alpha", "beta"],
            "hybrid": ["alpha", "beta"],
        }

        results = compare_strategies(queries, strategy_chunks)

        assert results["hybrid"].recall_at_5 >= results["recursive"].recall_at_5
        assert results["hybrid"].ndcg_at_5 >= results["recursive"].ndcg_at_5

    def test_generate_report_contains_strategies(self):
        """Report should list all strategies in markdown table."""
        queries = [("alpha", [0])]
        strategy_chunks = {"recursive": ["alpha"], "semantic": ["alpha"]}
        results = compare_strategies(queries, strategy_chunks)

        report = generate_report(results)

        assert "| recursive |" in report
        assert "| semantic |" in report
