"""Retrieval evaluation using ground truth datasets."""

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class GroundTruthQuery:
    """A single query with relevant documents."""

    query_id: str
    query: str
    relevant_docs: list[str]


class GroundTruthDataset:
    """Dataset of ground truth query-document pairs."""

    def __init__(self, file_path: Path):
        """Load ground truth from JSON file.

        Args:
            file_path: Path to ground truth JSON file

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Ground truth file not found: {file_path}")

        with open(file_path) as f:
            data = json.load(f)

        self.queries = [
            GroundTruthQuery(
                query_id=q["id"],
                query=q["query"],
                relevant_docs=q["relevant_docs"],
            )
            for q in data["queries"]
        ]

    def __len__(self) -> int:
        """Return number of queries."""
        return len(self.queries)


class RetrievalEvaluator:
    """Evaluator for retrieval performance metrics."""

    def recall_at_k(
        self, retrieved_docs: list[str], relevant_docs: list[str], k: int
    ) -> float:
        """Calculate Recall@k metric.

        Args:
            retrieved_docs: List of retrieved document IDs
            relevant_docs: List of relevant document IDs
            k: Number of top results to consider

        Returns:
            float: Recall@k (fraction of relevant docs found in top k)
        """
        if not relevant_docs:
            return 0.0

        # Only consider top k retrieved documents
        top_k = retrieved_docs[:k]

        # Count how many relevant docs are in top k
        found = len(set(top_k) & set(relevant_docs))

        # Return fraction of relevant docs found
        return found / len(relevant_docs)

    def ndcg_at_k(
        self, retrieved_docs: list[str], relevant_docs: list[str], k: int
    ) -> float:
        """Calculate Normalized Discounted Cumulative Gain (NDCG@k).

        Args:
            retrieved_docs: List of retrieved document IDs (in ranked order)
            relevant_docs: List of relevant document IDs
            k: Number of top results to consider

        Returns:
            float: NDCG@k score (0.0 to 1.0, higher is better)
        """
        if not relevant_docs:
            return 0.0

        # Convert to sets for fast lookup
        relevant_set = set(relevant_docs)

        # Calculate DCG@k
        dcg = 0.0
        for i, doc in enumerate(retrieved_docs[:k], start=1):
            if doc in relevant_set:
                # Relevance = 1 if relevant, 0 otherwise
                # DCG formula: sum(rel_i / log2(i + 1))
                dcg += 1.0 / np.log2(i + 1)

        # Calculate ideal DCG@k (all relevant docs at top)
        idcg = 0.0
        for i in range(1, min(len(relevant_docs), k) + 1):
            idcg += 1.0 / np.log2(i + 1)

        # Avoid division by zero
        if idcg == 0.0:
            return 0.0

        # Return normalized DCG
        return dcg / idcg

    def reciprocal_rank(
        self, retrieved_docs: list[str], relevant_docs: list[str]
    ) -> float:
        """Calculate Reciprocal Rank (RR) - used for Mean Reciprocal Rank (MRR).

        Args:
            retrieved_docs: List of retrieved document IDs (in ranked order)
            relevant_docs: List of relevant document IDs

        Returns:
            float: Reciprocal rank (1/rank of first relevant doc, or 0 if none found)
        """
        if not relevant_docs:
            return 0.0

        # Convert to set for fast lookup
        relevant_set = set(relevant_docs)

        # Find position of first relevant document
        for i, doc in enumerate(retrieved_docs, start=1):
            if doc in relevant_set:
                return 1.0 / i

        # No relevant docs found
        return 0.0
