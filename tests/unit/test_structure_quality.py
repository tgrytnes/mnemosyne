"""Unit tests for structure preservation quality analysis."""

import pytest

from mnemosyne.iris.structure_quality import StructurePreservationAnalyzer


class TestStructurePreservationAnalyzer:
    """Test suite for StructurePreservationAnalyzer."""

    def test_init_with_valid_data(self):
        """Test initialization with valid chunks and expected headings."""
        chunks = [
            {"heading_path": "# Main > ## Section", "heading_level": 2},
            {"heading_path": "# Main > ## Section > ### Subsection", "heading_level": 3},
        ]
        expected_headings = ["# Main", "## Section", "### Subsection"]

        analyzer = StructurePreservationAnalyzer(chunks, expected_headings)

        assert analyzer.n_chunks == 2
        assert analyzer.n_expected_headings == 3

    def test_compute_preservation_score_perfect(self):
        """Test preservation score with all headings preserved."""
        chunks = [
            {"heading_path": "# Main", "heading_level": 1},
            {"heading_path": "# Main > ## Section One", "heading_level": 2},
            {"heading_path": "# Main > ## Section Two", "heading_level": 2},
        ]
        expected_headings = ["# Main", "## Section One", "## Section Two"]

        analyzer = StructurePreservationAnalyzer(chunks, expected_headings)
        score = analyzer.compute_preservation_score()

        assert score == 1.0  # 100% preserved

    def test_compute_preservation_score_partial(self):
        """Test preservation score with some headings missing."""
        chunks = [
            {"heading_path": "# Main > ## Section One", "heading_level": 2},
            # Missing "## Section Two"
        ]
        expected_headings = ["# Main", "## Section One", "## Section Two"]

        analyzer = StructurePreservationAnalyzer(chunks, expected_headings)
        score = analyzer.compute_preservation_score()

        # Only 2 of 3 headings found
        assert score == pytest.approx(2 / 3)

    def test_compute_preservation_score_zero(self):
        """Test preservation score with no headings preserved."""
        chunks = [
            {"heading_path": None, "heading_level": 0},
            {"heading_path": None, "heading_level": 0},
        ]
        expected_headings = ["# Main", "## Section"]

        analyzer = StructurePreservationAnalyzer(chunks, expected_headings)
        score = analyzer.compute_preservation_score()

        assert score == 0.0

    def test_compute_heading_depth_accuracy(self):
        """Test that heading levels are correctly assigned."""
        chunks = [
            {"heading_path": "# Main", "heading_level": 1},
            {"heading_path": "# Main > ## Section", "heading_level": 2},
            {"heading_path": "# Main > ## Section > ### Subsection", "heading_level": 3},
        ]

        analyzer = StructurePreservationAnalyzer(chunks, [])
        accuracy = analyzer.compute_heading_depth_accuracy()

        assert accuracy == 1.0  # All levels correct

    def test_analyze_returns_all_metrics(self):
        """Test that analyze() returns complete metrics."""
        chunks = [
            {"heading_path": "# Main > ## Section", "heading_level": 2},
        ]
        expected_headings = ["# Main", "## Section"]

        analyzer = StructurePreservationAnalyzer(chunks, expected_headings)
        metrics = analyzer.analyze()

        # Check all fields are present
        assert hasattr(metrics, "preservation_score")
        assert hasattr(metrics, "heading_depth_accuracy")
        assert hasattr(metrics, "n_headings_found")
        assert hasattr(metrics, "n_headings_expected")

        # Check types
        assert isinstance(metrics.preservation_score, float)
        assert isinstance(metrics.heading_depth_accuracy, float)
        assert isinstance(metrics.n_headings_found, int)
        assert isinstance(metrics.n_headings_expected, int)
