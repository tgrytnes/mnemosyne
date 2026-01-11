"""
Integration tests for Weaviate operations
Requires Weaviate to be running (docker-compose up weaviate)
"""

import pytest


@pytest.mark.integration
@pytest.mark.weaviate
class TestWeaviateIngestion:
    """Test ingestion into Weaviate collections"""

    @pytest.fixture(scope="class")
    def embedding_provider(self, test_config):
        """Connect to REAL Ollama instance - FAILS if not running."""
        try:
            from mnemosyne.config.providers import ProviderConfig
            from mnemosyne.providers.factory import create_embedding_provider

            provider_config = ProviderConfig(
                embedding_provider="ollama", ollama_base_url=test_config["ollama_url"]
            )
            embedding_provider = create_embedding_provider(provider_config)
            # Verify model is available
            embedding_provider.embed(model="qwen3-embedding:0.6b", text="test")
            return embedding_provider
        except Exception as e:
            pytest.fail(
                f"Ollama connection failed: {e}. Start Ollama and pull qwen3-embedding:0.6b!"
            )

    def test_create_the_muses_collection(self, weaviate_client, clean_weaviate_collection):
        """Test creating TheMuses collection"""
        import weaviate.classes as wvc

        # Create collection
        weaviate_client.collections.create(
            name="TheMuses_Test",
            vector_config=wvc.config.Configure.Vectors.self_provided(),
            properties=[
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="sourceFile", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="sourceType", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="chunkIndex", data_type=wvc.config.DataType.INT),
            ],
        )

        assert weaviate_client.collections.exists("TheMuses_Test")

    def test_insert_obsidian_chunks(
        self, weaviate_client, clean_weaviate_collection, sample_chunks, embedding_provider
    ):
        """Test inserting Obsidian chunks into TheMuses"""
        import weaviate.classes as wvc

        # Create collection
        collection = weaviate_client.collections.create(
            name="TheMuses_Test",
            vector_config=wvc.config.Configure.Vectors.self_provided(),
            properties=[
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="sourceFile", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="sourceType", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="chunkIndex", data_type=wvc.config.DataType.INT),
            ],
        )

        # Insert chunks
        with collection.batch.dynamic() as batch:
            for chunk in sample_chunks:
                embedding = embedding_provider.embed(
                    model="qwen3-embedding:0.6b", text=chunk["text"]
                )
                batch.add_object(
                    properties={
                        "text": chunk["text"],
                        "sourceFile": chunk["source_file"],
                        "sourceType": "obsidian",
                        "chunkIndex": chunk["chunk_index"],
                    },
                    vector={"default": embedding},
                )

        # Verify insertion
        response = collection.query.fetch_objects(limit=10)
        assert len(response.objects) == len(sample_chunks)

    def test_query_by_source_type(
        self, weaviate_client, clean_weaviate_collection, sample_chunks, embedding_provider
    ):
        """Test filtering by sourceType"""
        import weaviate.classes as wvc

        collection = weaviate_client.collections.create(
            name="TheMuses_Test",
            vector_config=wvc.config.Configure.Vectors.self_provided(),
            properties=[
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="sourceFile", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="sourceType", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="chunkIndex", data_type=wvc.config.DataType.INT),
            ],
        )

        # Insert mixed data
        with collection.batch.dynamic() as batch:
            for chunk in sample_chunks:
                embedding = embedding_provider.embed(
                    model="qwen3-embedding:0.6b", text=chunk["text"]
                )
                batch.add_object(
                    properties={
                        "text": chunk["text"],
                        "sourceFile": chunk["source_file"],
                        "sourceType": "obsidian",
                        "chunkIndex": chunk["chunk_index"],
                    },
                    vector={"default": embedding},
                )

        # Query for obsidian only
        response = collection.query.fetch_objects(
            filters=wvc.query.Filter.by_property("sourceType").equal("obsidian"),
            limit=10,
        )

        assert len(response.objects) == len(sample_chunks)
        assert all(obj.properties["sourceType"] == "obsidian" for obj in response.objects)


@pytest.mark.integration
@pytest.mark.weaviate
class TestSemanticSearch:
    """Test semantic search operations"""

    @pytest.fixture(scope="class")
    def embedding_provider(self, test_config):
        """Connect to REAL Ollama instance - FAILS if not running."""
        try:
            from mnemosyne.config.providers import ProviderConfig
            from mnemosyne.providers.factory import create_embedding_provider

            provider_config = ProviderConfig(
                embedding_provider="ollama", ollama_base_url=test_config["ollama_url"]
            )
            embedding_provider = create_embedding_provider(provider_config)
            # Verify model is available
            embedding_provider.embed(model="qwen3-embedding:0.6b", text="test")
            return embedding_provider
        except Exception as e:
            pytest.fail(
                f"Ollama connection failed: {e}. Start Ollama and pull qwen3-embedding:0.6b!"
            )

    def test_near_text_search(self, weaviate_client, clean_weaviate_collection, embedding_provider):
        """Test semantic search with vector similarity"""
        import weaviate.classes as wvc

        collection = weaviate_client.collections.create(
            name="TestCollection",
            vector_config=wvc.config.Configure.Vectors.self_provided(),
            properties=[
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
            ],
        )

        # Insert test data
        test_docs = [
            "Docker Compose is a tool for multi-container applications",
            "Python is a programming language",
            "Kubernetes orchestrates Docker containers",
        ]

        with collection.batch.dynamic() as batch:
            for text in test_docs:
                embedding = embedding_provider.embed(model="qwen3-embedding:0.6b", text=text)
                batch.add_object(properties={"text": text}, vector={"default": embedding})

        # Query for Docker-related content
        query_embedding = embedding_provider.embed(
            model="qwen3-embedding:0.6b", text="Docker containers"
        )
        response = collection.query.near_vector(
            near_vector=query_embedding, limit=2, target_vector="default"
        )

        # Should return Docker-related docs first
        assert len(response.objects) == 2
        assert "Docker" in response.objects[0].properties["text"]


@pytest.mark.integration
@pytest.mark.weaviate
@pytest.mark.slow
def test_large_batch_insertion(weaviate_client, clean_weaviate_collection, test_config):
    """Test inserting large batch of documents"""
    import weaviate.classes as wvc

    from mnemosyne.config.providers import ProviderConfig
    from mnemosyne.providers.factory import create_embedding_provider

    provider_config = ProviderConfig(
        embedding_provider="ollama", ollama_base_url=test_config["ollama_url"]
    )
    embedding_provider = create_embedding_provider(provider_config)

    collection = weaviate_client.collections.create(
        name="TestCollection",
        vector_config=wvc.config.Configure.Vectors.self_provided(),
        properties=[
            wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
        ],
    )

    base_embedding = embedding_provider.embed(model="qwen3-embedding:0.6b", text="Test document")

    # Insert 1000 documents
    num_docs = 1000
    with collection.batch.dynamic() as batch:
        for i in range(num_docs):
            batch.add_object(
                properties={"text": f"Test document {i}"},
                vector={"default": base_embedding},
            )

    # Verify count
    response = collection.aggregate.over_all(total_count=True)
    assert response.total_count == num_docs
