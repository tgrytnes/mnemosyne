"""
Integration tests for Weaviate operations
Requires Weaviate to be running (docker-compose up weaviate)
"""
import pytest
import weaviate
from datetime import datetime


@pytest.mark.integration
@pytest.mark.weaviate
class TestWeaviateIngestion:
    """Test ingestion into Weaviate collections"""

    def test_create_the_muses_collection(self, weaviate_client, clean_weaviate_collection):
        """Test creating TheMuses collection"""
        import weaviate.classes as wvc

        # Create collection
        collection = weaviate_client.collections.create(
            name="TheMuses_Test",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            properties=[
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="sourceFile", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="sourceType", data_type=wvc.config.DataType.TEXT),
                wvc.config.Property(name="chunkIndex", data_type=wvc.config.DataType.INT),
            ],
        )

        assert weaviate_client.collections.exists("TheMuses_Test")

    def test_insert_obsidian_chunks(self, weaviate_client, clean_weaviate_collection, sample_chunks):
        """Test inserting Obsidian chunks into TheMuses"""
        import weaviate.classes as wvc

        # Create collection
        collection = weaviate_client.collections.create(
            name="TheMuses_Test",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
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
                batch.add_object(
                    properties={
                        "text": chunk["text"],
                        "sourceFile": chunk["source_file"],
                        "sourceType": "obsidian",
                        "chunkIndex": chunk["chunk_index"],
                    },
                    vector=[0.1] * 1024,  # Mock embedding
                )

        # Verify insertion
        response = collection.query.fetch_objects(limit=10)
        assert len(response.objects) == len(sample_chunks)

    def test_query_by_source_type(self, weaviate_client, clean_weaviate_collection, sample_chunks):
        """Test filtering by sourceType"""
        import weaviate.classes as wvc

        collection = weaviate_client.collections.create(
            name="TheMuses_Test",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
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
                batch.add_object(
                    properties={
                        "text": chunk["text"],
                        "sourceFile": chunk["source_file"],
                        "sourceType": "obsidian",
                        "chunkIndex": chunk["chunk_index"],
                    },
                    vector=[0.1] * 1024,
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

    def test_near_text_search(self, weaviate_client, clean_weaviate_collection):
        """Test semantic search with vector similarity"""
        import weaviate.classes as wvc

        collection = weaviate_client.collections.create(
            name="TestCollection",
            vectorizer_config=wvc.config.Configure.Vectorizer.none(),
            properties=[
                wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
            ],
        )

        # Insert test data
        test_docs = [
            ("Docker Compose is a tool for multi-container applications", [0.8, 0.2] + [0.0] * 1022),
            ("Python is a programming language", [0.2, 0.8] + [0.0] * 1022),
            ("Kubernetes orchestrates Docker containers", [0.7, 0.3] + [0.0] * 1022),
        ]

        with collection.batch.dynamic() as batch:
            for text, vector in test_docs:
                batch.add_object(properties={"text": text}, vector=vector)

        # Query for Docker-related content
        response = collection.query.near_vector(
            near_vector=[0.8, 0.2] + [0.0] * 1022, limit=2
        )

        # Should return Docker-related docs first
        assert len(response.objects) == 2
        assert "Docker" in response.objects[0].properties["text"]


@pytest.mark.integration
@pytest.mark.weaviate
@pytest.mark.slow
def test_large_batch_insertion(weaviate_client, clean_weaviate_collection):
    """Test inserting large batch of documents"""
    import weaviate.classes as wvc

    collection = weaviate_client.collections.create(
        name="TestCollection",
        vectorizer_config=wvc.config.Configure.Vectorizer.none(),
        properties=[
            wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
        ],
    )

    # Insert 1000 documents
    num_docs = 1000
    with collection.batch.dynamic() as batch:
        for i in range(num_docs):
            batch.add_object(
                properties={"text": f"Test document {i}"},
                vector=[i / num_docs] * 1024,
            )

    # Verify count
    response = collection.aggregate.over_all(total_count=True)
    assert response.total_count == num_docs
