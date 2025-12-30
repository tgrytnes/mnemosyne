"""Structure preservation quality analysis."""

from dataclasses import dataclass


@dataclass
class StructurePreservationMetrics:
    """Container for structure preservation quality metrics."""

    preservation_score: float
    heading_depth_accuracy: float
    n_headings_found: int
    n_headings_expected: int


class StructurePreservationAnalyzer:
    """Analyzer for structure preservation quality metrics."""

    def __init__(self, chunks: list[dict], expected_headings: list[str]):
        """Initialize analyzer with chunks and expected headings.

        Args:
            chunks: List of chunk dictionaries with heading metadata
            expected_headings: List of heading strings that should be preserved
        """
        self.chunks = chunks
        self.expected_headings = expected_headings
        self.n_chunks = len(chunks)
        self.n_expected_headings = len(expected_headings)

    def compute_preservation_score(self) -> float:
        """Compute fraction of expected headings found in chunks.

        Returns:
            float: Fraction of expected headings preserved (0.0 to 1.0)
        """
        if not self.expected_headings:
            return 1.0  # No headings expected, trivially preserved

        # Extract all unique headings from chunks
        found_headings = set()
        for chunk in self.chunks:
            # Support both snake_case (Python) and camelCase (Weaviate)
            heading_path = chunk.get("headingPath") or chunk.get("heading_path")
            if heading_path:
                # Split path like "# Main > ## Section" into individual headings
                headings = [h.strip() for h in heading_path.split(">")]
                found_headings.update(headings)

        # Count how many expected headings were found
        expected_set = set(self.expected_headings)
        found_count = len(expected_set & found_headings)

        return found_count / len(expected_set)

    def compute_heading_depth_accuracy(self) -> float:
        """Compute accuracy of heading level assignments.

        Returns:
            float: Fraction of chunks with correct heading levels (0.0 to 1.0)
        """
        if not self.chunks:
            return 1.0

        correct_count = 0
        total_count = 0

        for chunk in self.chunks:
            # Support both snake_case (Python) and camelCase (Weaviate)
            heading_path = chunk.get("headingPath") or chunk.get("heading_path")
            heading_level = chunk.get("headingLevel") or chunk.get("heading_level", 0)

            if heading_path:
                # Count # symbols in the last heading of the path
                headings = [h.strip() for h in heading_path.split(">")]
                last_heading = headings[-1]
                expected_level = last_heading.count("#")

                total_count += 1
                if heading_level == expected_level:
                    correct_count += 1

        if total_count == 0:
            return 1.0  # No headings to check

        return correct_count / total_count

    def analyze(self) -> StructurePreservationMetrics:
        """Run all quality analyses and return comprehensive metrics.

        Returns:
            StructurePreservationMetrics: Complete structure quality metrics
        """
        preservation_score = self.compute_preservation_score()
        depth_accuracy = self.compute_heading_depth_accuracy()

        # Count how many headings were actually found
        found_headings = set()
        for chunk in self.chunks:
            # Support both snake_case (Python) and camelCase (Weaviate)
            heading_path = chunk.get("headingPath") or chunk.get("heading_path")
            if heading_path:
                headings = [h.strip() for h in heading_path.split(">")]
                found_headings.update(headings)

        return StructurePreservationMetrics(
            preservation_score=preservation_score,
            heading_depth_accuracy=depth_accuracy,
            n_headings_found=len(found_headings),
            n_headings_expected=self.n_expected_headings,
        )
