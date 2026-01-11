"""
End-to-End tests for Story 020 - Hierarchical Structure Preservation.

These tests require REAL Weaviate and Ollama services running.
They will FAIL if services are not available - this is intentional!

Run these tests ONLY when validating the complete system:
    pytest tests/e2e/test_story_020_e2e.py -v

Prerequisites:
    - Weaviate running on localhost:8080
    - Ollama running with qwen3-embedding:0.6b model
"""

import pytest
import weaviate
from weaviate.classes.query import Filter

from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.iris.structure_quality import StructurePreservationAnalyzer


@pytest.mark.e2e
class TestStory020EndToEnd:
    """End-to-end validation tests for Story 020 with REAL services."""

    @pytest.fixture(scope="class")
    def weaviate_client(self):
        """Connect to REAL Weaviate instance - FAILS if not running."""
        try:
            client = weaviate.connect_to_local(
                host="localhost",
                port=8080,
            )
            yield client
            client.close()
        except Exception as e:
            pytest.fail(f"Weaviate connection failed: {e}. Start Weaviate first!")

    @pytest.fixture(scope="class")
    def embedding_provider(self):
        """Connect to REAL Ollama instance - FAILS if not running."""
        try:
            from mnemosyne.config.providers import ProviderConfig
            from mnemosyne.providers.factory import create_embedding_provider

            provider_config = ProviderConfig(embedding_provider="ollama")
            embedding_provider = create_embedding_provider(provider_config)
            # Verify model is available
            embedding_provider.embed(model="qwen3-embedding:0.6b", text="test")
            return embedding_provider
        except Exception as e:
            pytest.fail(
                f"Ollama connection failed: {e}. Start Ollama and pull qwen3-embedding:0.6b!"
            )

    @pytest.fixture(scope="class")
    def llm_provider(self):
        """Connect to REAL Ollama instance - FAILS if not running."""
        try:
            from mnemosyne.config.providers import ProviderConfig
            from mnemosyne.providers.factory import create_llm_provider

            provider_config = ProviderConfig(llm_provider="ollama")
            llm_provider = create_llm_provider(provider_config)
            return llm_provider
        except Exception as e:
            pytest.fail(f"Ollama connection failed: {e}. Start Ollama first!")

    @pytest.fixture
    def test_vault(self, tmp_path):
        """Create test vault with structured markdown files."""
        vault = tmp_path / "test_vault"
        vault.mkdir()

        # Create test document with clear heading structure
        doc1 = vault / "python_guide.md"
        doc1.write_text(
            """# Python Development Guide

Introduction to Python development best practices.

## Setup Instructions

Learn how to set up your development environment.

### Virtual Environments

Use venv or virtualenv to isolate dependencies. """
            + "More details about virtual environments. " * 30
            + """

### Package Management

Use pip or poetry for managing packages. """
            + "Package management best practices. " * 30
            + """

## Testing Strategies

Comprehensive testing is essential.

### Unit Testing

Test individual functions in isolation. """
            + "Unit testing guidelines. " * 30
            + """

### Integration Testing

Test component interactions. """
            + "Integration testing approaches. " * 30
        )

        return vault

    def test_real_weaviate_connection(self, weaviate_client):
        """REAL TEST: Verify Weaviate is accessible."""
        assert weaviate_client.is_ready()

    def test_real_provider_connection(self, embedding_provider, llm_provider):
        """REAL TEST: Verify Ollama is accessible."""
        # This should not raise an exception
        result = embedding_provider.embed(model="qwen3-embedding:0.6b", text="Test connection")
        assert isinstance(result, list)
        assert len(result) > 0

        # This should not raise an exception
        result = llm_provider.generate(model="qwen3:0.6b", prompt="test")
        assert "response" in result

    def test_real_ingestion_with_structure_metadata(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Ingest documents and verify heading metadata is stored in Weaviate."""
        # GIVEN: Real Obsidian vault
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        # WHEN: Ingesting vault
        stats = ingestor.ingest_vault()

        # THEN: Files were ingested
        assert stats["files_processed"] > 0
        assert stats["total_chunks"] > 0

        # AND: Verify heading metadata is in Weaviate
        collection = weaviate_client.collections.get("TheMuses")

        # Query chunks with heading metadata
        results = collection.query.fetch_objects(
            filters=Filter.by_property("headingPath").like("*Python*"), limit=10
        )

        chunks_with_headings = [obj for obj in results.objects if obj.properties.get("headingPath")]

        # CRITICAL: Must have chunks with heading metadata
        assert len(chunks_with_headings) > 0

        # Verify heading metadata fields exist and are populated
        for obj in chunks_with_headings:
            props = obj.properties
            assert "headingPath" in props
            assert "headingLevel" in props
            assert "sectionTitle" in props

            # Verify values are reasonable
            if props["headingPath"]:
                assert props["headingLevel"] > 0
                assert props["sectionTitle"]

    def test_real_structure_preservation_score(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify >95% structure preservation with real data."""
        # GIVEN: Real ingestion
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )
        ingestor.ingest_vault()

        # Define expected headings from test document
        expected_headings = [
            "# Python Development Guide",
            "## Setup Instructions",
            "### Virtual Environments",
            "### Package Management",
            "## Testing Strategies",
            "### Unit Testing",
            "### Integration Testing",
        ]

        # WHEN: Querying all chunks from Weaviate
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(
            filters=Filter.by_property("sourceFile").like("*python_guide.md"), limit=100
        )

        # Convert to format expected by analyzer
        chunks = [obj.properties for obj in results.objects]

        # THEN: Analyze structure preservation
        analyzer = StructurePreservationAnalyzer(chunks, expected_headings)
        metrics = analyzer.analyze()

        # CRITICAL: Must achieve >95% preservation
        assert metrics.preservation_score >= 0.95, (
            f"Structure preservation score {metrics.preservation_score:.1%} is below 95%! "
            f"Found {metrics.n_headings_found}/{metrics.n_headings_expected} headings."
        )
        assert metrics.heading_depth_accuracy >= 0.95

    def test_real_query_by_heading_path(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify we can query chunks by heading path."""
        # GIVEN: Real ingestion
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )
        ingestor.ingest_vault()

        # WHEN: Querying for specific section
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(
            filters=Filter.by_property("headingPath").like("*Testing Strategies*"), limit=10
        )

        # THEN: Should find chunks under that section
        assert len(results.objects) > 0

        for obj in results.objects:
            props = obj.properties
            assert "Testing Strategies" in props.get("headingPath", "")

    def test_real_nested_heading_queries(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify nested heading path queries work correctly."""
        # GIVEN: Real ingestion
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )
        ingestor.ingest_vault()

        collection = weaviate_client.collections.get("TheMuses")

        # WHEN: Querying for top-level section
        top_level_results = collection.query.fetch_objects(
            filters=Filter.by_property("headingPath").like("*Setup Instructions*"), limit=20
        )

        # THEN: Should find chunks under "Setup Instructions" and its subsections
        assert len(top_level_results.objects) > 0

        # WHEN: Querying for nested subsection
        nested_results = collection.query.fetch_objects(
            filters=Filter.by_property("headingPath").like("*Virtual Environments*"), limit=10
        )

        # THEN: Should find chunks specifically under "Virtual Environments"
        assert len(nested_results.objects) > 0

        # Verify nested paths contain parent hierarchy
        for obj in nested_results.objects:
            heading_path = obj.properties.get("headingPath", "")
            # Nested subsection should contain parent in path
            assert "Setup Instructions" in heading_path
            assert "Virtual Environments" in heading_path

        # WHEN: Querying by heading level (only top-level headings)
        level1_results = collection.query.fetch_objects(
            filters=Filter.by_property("headingLevel").equal(1), limit=10
        )

        # THEN: Should only find chunks directly under level 1 headings
        assert len(level1_results.objects) > 0
        for obj in level1_results.objects:
            assert obj.properties.get("headingLevel") == 1

    def test_real_cleanup(self, weaviate_client):
        """REAL TEST: Clean up test data from Weaviate."""
        # Delete test chunks
        collection = weaviate_client.collections.get("TheMuses")

        # Delete all chunks from test vault
        collection.data.delete_many(where=Filter.by_property("sourceFile").like("*/test_vault/*"))
