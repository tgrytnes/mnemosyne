"""Retrieval evaluation using ground truth datasets."""

import json
from dataclasses import dataclass
from pathlib import Path


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

    pass
