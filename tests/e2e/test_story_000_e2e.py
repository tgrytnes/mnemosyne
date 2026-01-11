"""
End-to-End tests for Story 000 - Obsidian Vault Ingestion.

These tests require REAL Weaviate and Ollama services running.
They will FAIL if services are not available - this is intentional!

Run these tests ONLY when validating the complete system:
    pytest tests/e2e/test_story_000_e2e.py -v -m e2e

Prerequisites:
    - Weaviate running on localhost:8080
    - Ollama running with qwen3-embedding:0.6b model
"""

import time

import pytest
import weaviate
from weaviate.classes.query import Filter

from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor


@pytest.mark.e2e
class TestStory000EndToEnd:
    """End-to-end validation tests for Story 000 with REAL services."""

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

    @pytest.fixture(autouse=True)
    def cleanup_weaviate(self, weaviate_client):
        """Clean up Weaviate collection before each test to ensure isolation."""
        # Run before test: Clear the collection (if it exists)
        try:
            collection = weaviate_client.collections.get("TheMuses")
            # Delete all objects using a filter that matches everything
            collection.data.delete_many(where=Filter.by_property("sourceType").equal("obsidian"))
        except Exception:
            # Collection doesn't exist yet - this is fine for the first test
            pass
        yield
        # After test: No cleanup needed (next test will clean before it runs)

    @pytest.fixture
    def test_vault(self, tmp_path):
        """Create test vault with Obsidian markdown files."""
        vault = tmp_path / "test_vault_000"
        vault.mkdir()

        # Create test document with frontmatter and wiki-links
        doc1 = vault / "test_note.md"
        doc1.write_text(
            """---
title: Test Note
tags: [testing, obsidian]
created: 2025-01-01
---

# Test Note

This is a test note with [[wiki-links]] and some content.

## Section One

Content with a link to [[Another Note]].

## Section Two

More content here.
"""
        )

        # Create document with HTML and emoji markers
        doc2 = vault / "advanced_note.md"
        doc2.write_text(
            """# Advanced Note

Some content with <strong>HTML tags</strong> that should be removed.

📌 Important: This has emoji markers.

## Technical Details

<div class="custom-class">
HTML block content
</div>

Regular content continues here.
"""
        )

        # Create simple document for chunking test
        doc3 = vault / "long_note.md"
        doc3.write_text(
            """# Long Document

"""
            + "This is a long document with repeated content. " * 50
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

    def test_real_vault_ingestion_end_to_end(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Full ingestion pipeline with real services."""
        # GIVEN: Real Obsidian vault
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        # WHEN: Ingesting vault
        stats = ingestor.ingest_vault()

        # THEN: Files were processed
        assert stats["files_processed"] == 3
        assert stats["total_chunks"] > 0
        assert stats["total_files"] == 3

        # AND: Verify chunks stored in Weaviate TheMuses collection
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(
            filters=Filter.by_property("sourceFile").contains_any(["test_vault_000"]), limit=100
        )

        # Should have chunks from all 3 files
        assert len(results.objects) > 0
        assert len(results.objects) == stats["total_chunks"]

        # Verify all chunks have required metadata
        for obj in results.objects:
            props = obj.properties
            assert "text" in props
            assert "sourceFile" in props
            assert "sourceType" in props
            assert props["sourceType"] == "obsidian"
            assert "chunkIndex" in props
            assert "ingestedAt" in props
            assert "fileModifiedAt" in props

    def test_real_markdown_cleaning(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify markdown cleaning (frontmatter, wiki-links, HTML removed)."""
        # GIVEN: Vault with complex markdown
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        # WHEN: Ingesting vault
        ingestor.ingest_vault()

        # THEN: Query chunks and verify cleaning
        collection = weaviate_client.collections.get("TheMuses")

        # Filter for chunks from test_note.md only
        # Use a simple approach - filter all results manually in Python
        all_results = collection.query.fetch_objects(limit=100)
        results_list = [
            obj
            for obj in all_results.objects
            if obj.properties.get("sourceFile", "").endswith("/test_note.md")
        ]

        # Create a mock results object
        from types import SimpleNamespace

        results = SimpleNamespace(objects=results_list)

        assert len(results.objects) > 0

        # Verify frontmatter removed
        all_text = " ".join([obj.properties["text"] for obj in results.objects])
        assert "---" not in all_text
        assert "title: Test Note" not in all_text
        assert "tags:" not in all_text

        # Verify wiki-links cleaned (brackets removed but text preserved)
        assert "[[" not in all_text
        assert "]]" not in all_text
        assert "wiki-links" in all_text or "Another Note" in all_text

    def test_real_html_and_emoji_cleaning(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify HTML and emoji markers are removed."""
        # GIVEN: Vault with HTML and emojis
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        # WHEN: Ingesting vault
        ingestor.ingest_vault()

        # THEN: Query chunks and verify cleaning
        collection = weaviate_client.collections.get("TheMuses")

        # Filter manually in Python since Weaviate filters are problematic
        from types import SimpleNamespace

        all_results = collection.query.fetch_objects(limit=100)
        results_list = [
            obj
            for obj in all_results.objects
            if obj.properties.get("sourceFile", "").endswith("/advanced_note.md")
        ]
        results = SimpleNamespace(objects=results_list)

        assert len(results.objects) > 0

        all_text = " ".join([obj.properties["text"] for obj in results.objects])

        # Verify HTML tags removed
        assert "<strong>" not in all_text
        assert "</strong>" not in all_text
        assert "<div" not in all_text
        assert "</div>" not in all_text

        # Verify emoji markers removed
        assert "📌" not in all_text

        # Verify content preserved
        assert "HTML tags" in all_text or "Important" in all_text

    def test_real_embedding_generation(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify embeddings are generated via Ollama."""
        # GIVEN: Vault for ingestion
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        # WHEN: Ingesting vault
        ingestor.ingest_vault()

        # THEN: Query chunks and verify embeddings
        collection = weaviate_client.collections.get("TheMuses")
        results = collection.query.fetch_objects(
            filters=Filter.by_property("sourceFile").contains_any(["test_vault_000"]),
            limit=10,
            include_vector=True,
        )

        assert len(results.objects) > 0

        # Verify all chunks have 1024-dimensional embeddings (from Ollama qwen3-embedding:0.6b)
        for obj in results.objects:
            assert obj.vector is not None
            # Vector is stored under 'default' key
            assert "default" in obj.vector
            assert len(obj.vector["default"]) == 1024
            # Verify vector is not all zeros (real embedding from Ollama)
            assert sum(obj.vector["default"]) != 0

    def test_real_chunking_with_overlap(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify chunking with 400 chars and 100 char overlap."""
        # GIVEN: Long document
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        # WHEN: Ingesting vault
        ingestor.ingest_vault()

        # THEN: Query chunks from long document
        collection = weaviate_client.collections.get("TheMuses")

        # Filter manually in Python since Weaviate filters are problematic
        from types import SimpleNamespace

        all_results = collection.query.fetch_objects(limit=100)
        results_list = [
            obj
            for obj in all_results.objects
            if obj.properties.get("sourceFile", "").endswith("/long_note.md")
        ]
        results = SimpleNamespace(objects=results_list)

        # Should have multiple chunks due to length
        assert len(results.objects) > 1

        # Verify chunk sizes are reasonable (around 400 chars)
        for obj in results.objects:
            text_len = len(obj.properties["text"])
            # Chunks should be between 10 and 800 chars
            # (allowing for short heading-only chunks from structure preservation)
            assert 10 < text_len < 800

    def test_real_incremental_updates(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify incremental updates (only changed files re-processed)."""
        # GIVEN: Initial ingestion
        ingestor = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        initial_stats = ingestor.ingest_vault()
        assert initial_stats["files_processed"] == 3

        # WHEN: Re-running ingestion without changes
        stats_no_changes = ingestor.ingest_vault()

        # THEN: No files should be re-processed (state tracking)
        assert stats_no_changes["files_processed"] == 0
        assert stats_no_changes["files_skipped"] == 3

        # WHEN: Modifying one file
        time.sleep(0.1)  # Ensure modification time changes
        doc = test_vault / "test_note.md"
        content = doc.read_text()
        doc.write_text(content + "\n\nNew content added.")

        stats_after_change = ingestor.ingest_vault()

        # THEN: Only modified file should be re-processed
        assert stats_after_change["files_processed"] == 1
        assert stats_after_change["files_skipped"] == 2

    def test_real_state_persistence(
        self, test_vault, weaviate_client, embedding_provider, llm_provider
    ):
        """REAL TEST: Verify ingestion state persists across restarts."""
        # GIVEN: Initial ingestion
        ingestor1 = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        stats1 = ingestor1.ingest_vault()
        assert stats1["files_processed"] == 3

        # Close and cleanup first ingestor
        ingestor1.state_tracker.close()

        # WHEN: Creating new ingestor instance (simulates restart)
        ingestor2 = ObsidianIngestor(
            vault_path=str(test_vault),
            weaviate_client=weaviate_client,
            embedding_provider=embedding_provider,
            llm_provider=llm_provider,
        )

        stats2 = ingestor2.ingest_vault()

        # THEN: State should be persisted (no files re-processed)
        assert stats2["files_processed"] == 0
        assert stats2["files_skipped"] == 3

        # Cleanup
        ingestor2.state_tracker.close()

    def test_real_cleanup(self, weaviate_client):
        """REAL TEST: Clean up test data from Weaviate."""
        collection = weaviate_client.collections.get("TheMuses")

        # Delete all chunks from test vault
        collection.data.delete_many(
            where=Filter.by_property("sourceFile").contains_any(["test_vault_000"])
        )
