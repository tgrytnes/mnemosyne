"""
Retrieval quality evaluation for Mnemosyne.

Provides metrics to evaluate semantic search quality:
- Recall@k (what % of relevant docs are in top k results?)
- NDCG@k (Normalized Discounted Cumulative Gain - ranking quality)
- MRR (Mean Reciprocal Rank - position of first relevant result)
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


@dataclass
class GroundTruthQuery:
    """Single query with known relevant documents."""

    query: str
    relevant_docs: List[str]  # File paths or chunk IDs
    query_id: str


@dataclass
class RetrievalMetrics:
    """Container for retrieval quality metrics."""

    recall_at_5: float
    recall_at_10: float
    recall_at_20: float
    ndcg_at_5: float
    ndcg_at_10: float
    ndcg_at_20: float
    mrr: float  # Mean Reciprocal Rank
    num_queries: int


class GroundTruthDataset:
    """
    Loads and manages ground truth query-document pairs.

    Format (JSON):
    {
        "queries": [
            {
                "id": "q001",
                "query": "What did I learn about Python testing?",
                "relevant_docs": ["notes/python_testing.md", "projects/test_automation.md"]
            },
            ...
        ]
    }
    """

    def __init__(self, dataset_path: Path):
        """Load ground truth dataset from JSON file."""
        self.dataset_path = dataset_path
        self.queries: List[GroundTruthQuery] = []
        self._load()

    def _load(self):
        """Load queries from JSON file."""
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"Ground truth dataset not found: {self.dataset_path}"
            )

        with open(self.dataset_path) as f:
            data = json.load(f)

        for q in data.get("queries", []):
            self.queries.append(
                GroundTruthQuery(
                    query_id=q["id"],
                    query=q["query"],
                    relevant_docs=q["relevant_docs"],
                )
            )

    def __len__(self) -> int:
        """Return number of queries in dataset."""
        return len(self.queries)

    def __iter__(self):
        """Iterate over queries."""
        return iter(self.queries)


class RetrievalEvaluator:
    """
    Evaluates retrieval quality using ground truth queries.

    Computes standard IR metrics: Recall@k, NDCG@k, MRR.
    """

    def __init__(self, ground_truth: GroundTruthDataset):
        """Initialize with ground truth dataset."""
        self.ground_truth = ground_truth

    def recall_at_k(
        self, retrieved_docs: List[str], relevant_docs: List[str], k: int
    ) -> float:
        """
        Compute Recall@k for a single query.

        Recall@k = (# relevant docs in top k) / (# total relevant docs)

        Args:
            retrieved_docs: Ordered list of retrieved document IDs
            relevant_docs: List of relevant document IDs
            k: Cutoff rank

        Returns:
            Recall@k score (0.0 to 1.0)
        """
        if not relevant_docs:
            return 0.0

        top_k = set(retrieved_docs[:k])
        relevant_set = set(relevant_docs)

        hits = len(top_k.intersection(relevant_set))
        return hits / len(relevant_set)

    def ndcg_at_k(
        self, retrieved_docs: List[str], relevant_docs: List[str], k: int
    ) -> float:
        """
        Compute NDCG@k (Normalized Discounted Cumulative Gain).

        NDCG measures ranking quality - rewards relevant docs ranked higher.

        Args:
            retrieved_docs: Ordered list of retrieved document IDs
            relevant_docs: List of relevant document IDs
            k: Cutoff rank

        Returns:
            NDCG@k score (0.0 to 1.0)
        """
        if not relevant_docs:
            return 0.0

        relevant_set = set(relevant_docs)
        top_k = retrieved_docs[:k]

        # Compute DCG (Discounted Cumulative Gain)
        dcg = 0.0
        for i, doc in enumerate(top_k):
            if doc in relevant_set:
                # Binary relevance: 1 if relevant, 0 otherwise
                # Discount by log2(rank + 2) -> positions 1, 2, 3... have gains 1.0, 0.63, 0.5...
                dcg += 1.0 / np.log2(i + 2)

        # Compute IDCG (Ideal DCG - if all relevant docs were ranked first)
        idcg = 0.0
        for i in range(min(len(relevant_docs), k)):
            idcg += 1.0 / np.log2(i + 2)

        if idcg == 0:
            return 0.0

        return dcg / idcg

    def reciprocal_rank(
        self, retrieved_docs: List[str], relevant_docs: List[str]
    ) -> float:
        """
        Compute Reciprocal Rank for a single query.

        RR = 1 / (rank of first relevant document)

        Args:
            retrieved_docs: Ordered list of retrieved document IDs
            relevant_docs: List of relevant document IDs

        Returns:
            Reciprocal rank (0.0 to 1.0)
        """
        relevant_set = set(relevant_docs)

        for i, doc in enumerate(retrieved_docs):
            if doc in relevant_set:
                return 1.0 / (i + 1)  # Rank is 1-indexed

        return 0.0  # No relevant document found

    def evaluate(
        self, retrieval_function: callable, k_values: List[int] = [5, 10, 20]
    ) -> RetrievalMetrics:
        """
        Run full retrieval evaluation on ground truth dataset.

        Args:
            retrieval_function: Function that takes a query string and returns
                              list of retrieved document IDs (ordered by relevance)
            k_values: List of k values for Recall@k and NDCG@k

        Returns:
            RetrievalMetrics with averaged metrics across all queries
        """
        recalls = {k: [] for k in k_values}
        ndcgs = {k: [] for k in k_values}
        rrs = []

        for gt_query in self.ground_truth:
            # Get retrieval results
            retrieved_docs = retrieval_function(gt_query.query)

            # Compute metrics for this query
            for k in k_values:
                recall = self.recall_at_k(retrieved_docs, gt_query.relevant_docs, k)
                ndcg = self.ndcg_at_k(retrieved_docs, gt_query.relevant_docs, k)
                recalls[k].append(recall)
                ndcgs[k].append(ndcg)

            rr = self.reciprocal_rank(retrieved_docs, gt_query.relevant_docs)
            rrs.append(rr)

        # Average across all queries
        return RetrievalMetrics(
            recall_at_5=float(np.mean(recalls.get(5, [0.0]))),
            recall_at_10=float(np.mean(recalls.get(10, [0.0]))),
            recall_at_20=float(np.mean(recalls.get(20, [0.0]))),
            ndcg_at_5=float(np.mean(ndcgs.get(5, [0.0]))),
            ndcg_at_10=float(np.mean(ndcgs.get(10, [0.0]))),
            ndcg_at_20=float(np.mean(ndcgs.get(20, [0.0]))),
            mrr=float(np.mean(rrs)),
            num_queries=len(self.ground_truth),
        )


def create_sample_ground_truth(output_path: Path) -> None:
    """
    Create a sample ground truth dataset for testing.

    Args:
        output_path: Where to save the JSON file
    """
    sample_data = {
        "queries": [
            {
                "id": "q001",
                "query": "Python testing best practices",
                "relevant_docs": [
                    "reference/python_best_practices.md",
                    "projects/machine_learning_experiments.md",
                ],
            },
            {
                "id": "q002",
                "query": "Mnemosyne project architecture",
                "relevant_docs": ["projects/mnemosyne_design.md"],
            },
            {
                "id": "q003",
                "query": "Smart home automation ideas",
                "relevant_docs": ["projects/smart_home_automation.md"],
            },
        ]
    }

    with open(output_path, "w") as f:
        json.dump(sample_data, f, indent=2)
