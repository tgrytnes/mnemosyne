"""
Integration tests for Story 020 - Hierarchical Structure Preservation.

Tests the complete pipeline from markdown file to Weaviate storage with
heading metadata preserved throughout.

USES REAL OLLAMA AND WEAVIATE (no mocks).
"""

import ollama
import pytest

from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor


class TestStructurePreservationPipeline:
    """Integration tests for complete structure preservation pipeline."""

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_end_to_end_structure_preservation(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test complete pipeline preserves heading structure end-to-end with REAL services."""
        # GIVEN: A markdown file with hierarchical structure
        markdown_content = """# Python Testing Guide

Testing is essential for code quality.

## Unit Tests

Unit tests verify individual functions in isolation.

They should be fast and deterministic.

## Integration Tests

Integration tests verify components work together.

### Database Tests

These test database interactions and queries.

### API Tests

These test REST API endpoints.

## Best Practices

Always write tests first using TDD."""

        # Create temporary markdown file
        test_file = tmp_path / "testing.md"
        test_file.write_text(markdown_content)

        # Use REAL Ollama client
        ollama_client = ollama.Client(host=test_config["ollama_url"])

        # Create ingestor
        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            ollama_client=ollama_client,
        )

        # WHEN: Ingesting the file
        chunk_count = ingestor.ingest_file(str(test_file))

        # THEN: File is processed successfully
        assert chunk_count >= 1

        # AND: Chunks stored in Weaviate with heading metadata
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=100)
        chunks = [obj.properties for obj in results.objects]

        assert len(chunks) == chunk_count

        # Verify at least one chunk has heading metadata
        chunks_with_headings = [c for c in chunks if c.get("headingPath")]
        assert len(chunks_with_headings) > 0

        # Verify heading paths are hierarchical
        heading_paths = [c["headingPath"] for c in chunks_with_headings]
        assert any(">" in path for path in heading_paths)

        # Verify specific sections are captured
        section_titles = [c.get("sectionTitle", "") for c in chunks_with_headings]
        expected_sections = ["Python Testing Guide", "Unit Tests", "Integration Tests"]
        assert any(section in section_titles for section in expected_sections)

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_structure_extraction_before_cleaning(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test that structure is extracted BEFORE markdown cleaning."""
        # GIVEN: Markdown with wiki-links and headings
        markdown_content = """# Main Topic

Check out [[Related Note]] for more info.

## Subsection

See also [[Another Note|with alias]]."""

        test_file = tmp_path / "linked.md"
        test_file.write_text(markdown_content)

        # Use REAL Ollama client
        ollama_client = ollama.Client(host=test_config["ollama_url"])

        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            ollama_client=ollama_client,
        )

        # WHEN: Ingesting the file
        chunk_count = ingestor.ingest_file(str(test_file))

        # THEN: Chunks are created
        assert chunk_count >= 1

        # AND: Heading metadata is preserved (extracted before cleaning)
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=100)
        properties_list = [obj.properties for obj in results.objects]

        # At least one chunk should have heading metadata
        assert any(p.get("headingPath") for p in properties_list)

        # AND: Cleaned text should not have wiki-link syntax
        for props in properties_list:
            assert "[[" not in props["text"]
            assert "]]" not in props["text"]

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_chunks_assigned_to_correct_headings(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test chunks are assigned to their parent headings."""
        # GIVEN: Document with clear sections and enough content for multiple chunks
        markdown_content = (
            """# Main

Content under main heading. """
            + "More content. " * 100
            + """

## Section One

First section content here. """
            + "Additional content. " * 100
            + """

## Section Two

Second section content here. """
            + "Even more content. " * 100
        )

        test_file = tmp_path / "sections.md"
        test_file.write_text(markdown_content)

        # Use REAL Ollama client
        ollama_client = ollama.Client(host=test_config["ollama_url"])

        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            ollama_client=ollama_client,
        )

        # WHEN: Ingesting the file
        chunk_count = ingestor.ingest_file(str(test_file))

        # THEN: Multiple chunks created
        assert chunk_count >= 1

        # AND: Chunks have appropriate heading assignments
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=100)
        properties_list = [obj.properties for obj in results.objects]

        # Check that different chunks have different section titles
        section_titles = {p.get("sectionTitle", "") for p in properties_list}
        assert len(section_titles) > 1

        # Verify hierarchical paths exist
        heading_paths = [p.get("headingPath", "") for p in properties_list]
        assert any("Main" in path for path in heading_paths)

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_nested_heading_structure_preserved(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test deeply nested heading structures are preserved."""
        # GIVEN: Document with 3-level nesting and enough content
        markdown_content = (
            """# Level 1

Content at level 1. """
            + "More text. " * 50
            + """

## Level 2

Content at level 2. """
            + "Additional text. " * 50
            + """

### Level 3

Content at level 3 (deepest). """
            + "Even more text. " * 50
        )

        test_file = tmp_path / "nested.md"
        test_file.write_text(markdown_content)

        # Use REAL Ollama client
        ollama_client = ollama.Client(host=test_config["ollama_url"])

        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            ollama_client=ollama_client,
        )

        # WHEN: Ingesting the file
        chunk_count = ingestor.ingest_file(str(test_file))

        # THEN: Chunks created
        assert chunk_count >= 1

        # AND: At least one chunk has nested heading path
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=100)
        properties_list = [obj.properties for obj in results.objects]

        heading_paths = [p.get("headingPath", "") for p in properties_list]

        # Should have nested paths with ">"
        nested_paths = [path for path in heading_paths if ">" in path]
        assert len(nested_paths) > 0

        # Should have at least one 3-level path
        three_level_paths = [path for path in heading_paths if path.count(">") >= 2]
        assert len(three_level_paths) > 0

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_heading_levels_correctly_assigned(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test heading levels (0-6) are correctly assigned."""
        # GIVEN: Document with various heading levels
        markdown_content = """# H1

## H2

### H3

#### H4

##### H5

###### H6"""

        test_file = tmp_path / "levels.md"
        test_file.write_text(markdown_content)

        # Use REAL Ollama client
        ollama_client = ollama.Client(host=test_config["ollama_url"])

        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            ollama_client=ollama_client,
        )

        # WHEN: Ingesting the file
        chunk_count = ingestor.ingest_file(str(test_file))

        # THEN: Chunks created
        assert chunk_count >= 1

        # AND: Heading levels range from 1-6
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=100)
        properties_list = [obj.properties for obj in results.objects]

        heading_levels = {p.get("headingLevel", 0) for p in properties_list}

        # Should have levels between 1 and 6
        assert all(0 <= level <= 6 for level in heading_levels)
        # Should have at least some non-zero levels
        assert any(level > 0 for level in heading_levels)

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_document_without_headings(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test documents without headings get default metadata."""
        # GIVEN: Plain text without headings
        markdown_content = "Just plain content without any structure or headings."

        test_file = tmp_path / "plain.md"
        test_file.write_text(markdown_content)

        # Use REAL Ollama client
        ollama_client = ollama.Client(host=test_config["ollama_url"])

        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            ollama_client=ollama_client,
        )

        # WHEN: Ingesting the file
        chunk_count = ingestor.ingest_file(str(test_file))

        # THEN: Chunk created
        assert chunk_count == 1

        # AND: Has default heading metadata
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=1, include_vector=True)
        properties = results.objects[0].properties

        assert properties["headingPath"] == ""
        assert properties["headingLevel"] == 0
        assert properties["sectionTitle"] == ""

    @pytest.mark.integration
    @pytest.mark.weaviate
    def test_backward_compatibility_preserved(
        self, tmp_path, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Test that all original metadata fields are still present."""
        # GIVEN: Any markdown file
        markdown_content = "# Test\n\nContent here."

        test_file = tmp_path / "test.md"
        test_file.write_text(markdown_content)

        # Use REAL Ollama client
        ollama_client = ollama.Client(host=test_config["ollama_url"])

        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=weaviate_client,
            ollama_client=ollama_client,
        )

        # WHEN: Ingesting the file
        ingestor.ingest_file(str(test_file))

        # THEN: Original metadata fields still present
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(limit=1)
        properties = results.objects[0].properties

        # Story 000 fields (backward compatibility)
        assert "text" in properties
        assert "sourceFile" in properties
        assert "sourceType" in properties
        assert properties["sourceType"] == "obsidian"
        assert "chunkIndex" in properties
        assert "ingestedAt" in properties
        assert "fileModifiedAt" in properties

        # Story 020 fields (new)
        assert "headingPath" in properties
        assert "headingLevel" in properties
        assert "sectionTitle" in properties

        # Embedding verification is covered in test_embeddings_generated.
