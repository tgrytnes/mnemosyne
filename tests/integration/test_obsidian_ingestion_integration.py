"""
Integration tests for Obsidian vault ingestion.

Tests the complete pipeline with real Weaviate and Ollama services.
Requires Docker containers to be running.
"""

import os
from pathlib import Path

import pytest
import weaviate

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider


@pytest.mark.integration
class TestObsidianIngestionIntegration:
    """Integration tests for complete ingestion pipeline"""

    @pytest.fixture(scope="class")
    def weaviate_client(self):
        """Connect to Weaviate instance"""
        # Get connection details from environment
        host = os.getenv("WEAVIATE_HTTP_HOST", "localhost")
        port = os.getenv("WEAVIATE_HTTP_PORT", "8080")
        grpc_port = os.getenv("WEAVIATE_GRPC_PORT", "50051")

        # Connect to Weaviate
        client = weaviate.connect_to_local(
            host=host,
            port=int(port),
            grpc_port=int(grpc_port),
        )

        yield client

        # Cleanup: Close connection
        client.close()

    @pytest.fixture(scope="class")
    def provider_config(self):
        """Create provider configuration"""
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return ProviderConfig(
            llm_provider="ollama", embedding_provider="ollama", ollama_base_url=base_url
        )

    @pytest.fixture(scope="class")
    def llm_provider(self, provider_config):
        """Create LLM provider"""
        return create_llm_provider(provider_config)

    @pytest.fixture(scope="class")
    def embedding_provider(self, provider_config):
        """Create embedding provider"""
        return create_embedding_provider(provider_config)

    @pytest.fixture
    def test_vault(self, tmp_path):
        """Create temporary vault with test markdown files"""
        vault_path = tmp_path / "test_vault"
        vault_path.mkdir()

        # Create test markdown files
        (vault_path / "note1.md").write_text(
            """---
title: Python Testing
tags: [python, testing]
---

# Python Testing Best Practices

Testing is crucial for software quality. Use pytest for unit tests.

[[Related Note]] - See this for more info.

![[diagram.png]]

Key points:
- Write tests first (TDD)
- Use real services in integration tests
- Aim for high coverage
"""
        )

        (vault_path / "note2.md").write_text(
            """
# Machine Learning Basics

Machine learning is a subset of artificial intelligence.

Common algorithms:
1. Linear regression
2. Decision trees
3. Neural networks

📌 Important: Always validate your models!
"""
        )

        (vault_path / "subdir").mkdir()
        (vault_path / "subdir" / "note3.md").write_text(
            """
# Docker Containers

Docker enables consistent development environments.

Commands:
- docker build
- docker run
- docker compose
"""
        )

        return str(vault_path)

    @pytest.fixture
    def state_tracker(self, tmp_path):
        """Create temporary state tracker"""
        db_path = tmp_path / "test_state.db"
        return IngestionStateTracker(str(db_path))

    @pytest.fixture
    def ingestor(
        self, test_vault, weaviate_client, llm_provider, embedding_provider, state_tracker
    ):
        """Create ingestor with real services"""
        return ObsidianIngestor(
            vault_path=test_vault,
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            state_tracker=state_tracker,
        )

    @pytest.fixture(autouse=True)
    def cleanup_weaviate(self, weaviate_client):
        """Clean up TheMuses collection after each test"""
        yield
        # Delete collection after test
        try:
            weaviate_client.collections.delete("TheMuses")
        except Exception:
            pass  # Collection might not exist

    def test_weaviate_connection(self, weaviate_client):
        """Should connect to Weaviate successfully"""
        # GIVEN/WHEN: Client connected
        # THEN: Client is ready
        assert weaviate_client.is_ready()

    def test_ollama_connection(self, llm_provider):
        """Should connect to Ollama successfully"""
        # GIVEN/WHEN: LLM provider
        # THEN: Can generate completion
        response = llm_provider.generate("Say hello")
        assert response is not None

    def test_ollama_embedding_model_available(self, embedding_provider):
        """Should have embedding model available"""
        # GIVEN: Embedding provider
        # WHEN: Generating embedding
        embedding = embedding_provider.embed("test text")

        # THEN: Embedding is generated with correct dimension
        assert embedding is not None
        assert len(embedding) == 1024  # qwen3-embedding dimension

    def test_create_weaviate_collection(self, weaviate_client):
        """Should create TheMuses collection"""
        # GIVEN: Weaviate client
        schema_manager = WeaviateSchemaManager(weaviate_client)

        # WHEN: Creating collection
        schema_manager.ensure_collection_exists("TheMuses")

        # THEN: Collection exists
        assert weaviate_client.collections.exists("TheMuses")

    def test_ingest_single_file_end_to_end(self, ingestor, test_vault):
        """Should ingest single file through complete pipeline"""
        # GIVEN: Test file
        file_path = Path(test_vault) / "note1.md"

        # WHEN: Ingesting file
        chunk_count = ingestor.ingest_file(str(file_path))

        # THEN: Chunks created and stored
        assert chunk_count > 0
        print(f"Created {chunk_count} chunks")

    def test_chunks_stored_in_weaviate(self, ingestor, weaviate_client, test_vault):
        """Should store chunks in Weaviate with embeddings"""
        # GIVEN: Test file
        file_path = Path(test_vault) / "note1.md"

        # WHEN: Ingesting file
        ingestor.ingest_file(str(file_path))

        # THEN: Chunks are in Weaviate
        collection = weaviate_client.collections.get("TheMuses")

        # Query all objects
        result = collection.query.fetch_objects(limit=100)

        assert len(result.objects) > 0
        print(f"Found {len(result.objects)} chunks in Weaviate")

        # Verify chunk properties
        chunk = result.objects[0]
        assert chunk.properties["text"] is not None
        assert chunk.properties["sourceFile"] == str(file_path)
        assert chunk.properties["sourceType"] == "obsidian"
        assert chunk.properties["chunkIndex"] >= 0

    def test_embeddings_generated(self, ingestor, weaviate_client, test_vault):
        """Should generate and store embeddings"""
        # GIVEN: Test file
        file_path = Path(test_vault) / "note1.md"

        # WHEN: Ingesting file
        ingestor.ingest_file(str(file_path))

        # THEN: Objects have vectors
        collection = weaviate_client.collections.get("TheMuses")
        result = collection.query.fetch_objects(include_vector=True, limit=1)

        assert len(result.objects) > 0
        chunk = result.objects[0]

        # Verify vector exists and has correct dimensions
        assert chunk.vector is not None
        # Weaviate returns vector as dict with 'default' key
        vector = chunk.vector["default"] if isinstance(chunk.vector, dict) else chunk.vector
        assert len(vector) == 1024  # qwen3-embedding dimension

    def test_ingest_entire_vault(self, ingestor):
        """Should ingest all files in vault"""
        # GIVEN: Vault with multiple files
        # WHEN: Ingesting vault
        stats = ingestor.ingest_vault()

        # THEN: All files processed
        assert stats["files_processed"] == 3
        assert stats["total_chunks"] > 0
        print(f"Ingestion stats: {stats}")

    def test_incremental_ingestion(self, ingestor, test_vault, state_tracker):
        """Should only re-ingest modified files"""
        # GIVEN: Vault already ingested
        stats1 = ingestor.ingest_vault()
        files_processed_first = stats1["files_processed"]

        # WHEN: Re-ingesting without changes
        stats2 = ingestor.ingest_vault()

        # THEN: No files re-processed
        assert stats2["files_processed"] == 0
        assert stats2["files_skipped"] == files_processed_first

        # WHEN: Modifying one file
        file_path = Path(test_vault) / "note1.md"
        file_path.write_text("Modified content")

        stats3 = ingestor.ingest_vault()

        # THEN: Only modified file re-processed
        assert stats3["files_processed"] == 1

    def test_semantic_search_works(self, ingestor, weaviate_client, test_vault):
        """Should enable semantic search on ingested content"""
        # GIVEN: Vault ingested
        ingestor.ingest_vault()

        # WHEN: Searching for "testing"
        collection = weaviate_client.collections.get("TheMuses")

        # Generate query embedding
        query_text = "software testing practices"
        query_embedding = ingestor._generate_embedding(query_text)

        # Search by vector
        result = collection.query.near_vector(
            near_vector=query_embedding, limit=3, target_vector="default"
        )

        # THEN: Finds relevant chunks
        assert len(result.objects) > 0

        # Should find testing-related content
        top_result = result.objects[0]
        assert (
            "test" in top_result.properties["text"].lower()
            or "python" in top_result.properties["text"].lower()
        )

        print(f"Top result: {top_result.properties['text'][:100]}...")

    def test_markdown_cleaning_applied(self, ingestor, weaviate_client, test_vault):
        """Should clean Obsidian syntax before storing"""
        # GIVEN: File with Obsidian syntax
        # WHEN: Ingesting
        ingestor.ingest_vault()

        # THEN: Stored chunks don't have Obsidian syntax
        collection = weaviate_client.collections.get("TheMuses")
        result = collection.query.fetch_objects(limit=100)

        for chunk in result.objects:
            text = chunk.properties["text"]
            # Should not contain wiki-links or embeds
            assert "[[" not in text
            assert "![[" not in text
            # YAML frontmatter should be removed
            assert "---" not in text or text.count("---") < 2

    def test_state_tracking_persists(
        self, test_vault, weaviate_client, llm_provider, embedding_provider, tmp_path
    ):
        """Should persist ingestion state across restarts"""
        # GIVEN: State tracker with persistent database
        db_path = tmp_path / "persistent_state.db"

        # First ingestor instance
        tracker1 = IngestionStateTracker(str(db_path))
        ingestor1 = ObsidianIngestor(
            vault_path=test_vault,
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            state_tracker=tracker1,
        )

        # WHEN: Ingesting vault
        stats1 = ingestor1.ingest_vault()

        # Create new ingestor with same database
        tracker2 = IngestionStateTracker(str(db_path))
        ingestor2 = ObsidianIngestor(
            vault_path=test_vault,
            weaviate_client=weaviate_client,
            llm_provider=llm_provider,
            embedding_provider=embedding_provider,
            state_tracker=tracker2,
        )

        # WHEN: Re-ingesting
        stats2 = ingestor2.ingest_vault()

        # THEN: State persisted, no re-ingestion
        assert stats2["files_skipped"] == stats1["files_processed"]
        assert stats2["files_processed"] == 0

    def test_chunk_metadata_complete(self, ingestor, weaviate_client, test_vault):
        """Should store all required metadata"""
        # GIVEN: Vault ingested
        ingestor.ingest_vault()

        # WHEN: Retrieving chunks
        collection = weaviate_client.collections.get("TheMuses")
        result = collection.query.fetch_objects(limit=1)

        # THEN: All metadata fields present
        chunk = result.objects[0]
        properties = chunk.properties

        required_fields = [
            "text",
            "sourceFile",
            "sourceType",
            "chunkIndex",
            "ingestedAt",
        ]

        for field in required_fields:
            assert field in properties, f"Missing required field: {field}"
