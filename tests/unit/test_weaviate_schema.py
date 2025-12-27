"""
Unit tests for Weaviate schema management.

Tests the WeaviateSchemaManager class which creates and manages
the TheMuses collection schema for Obsidian vault embeddings.
"""

import pytest
from src.mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager, TheMuses


class TestWeaviateSchemaManager:
    """Test Weaviate schema creation and management"""

    @pytest.fixture
    def mock_client(self, mocker):
        """Create a mock Weaviate client"""
        return mocker.MagicMock()

    @pytest.fixture
    def schema_manager(self, mock_client):
        """Create schema manager with mock client"""
        return WeaviateSchemaManager(mock_client)

    def test_themuses_collection_name(self):
        """Should use correct collection name"""
        # GIVEN/WHEN: TheMuses schema class
        # THEN: Collection name is TheMuses
        assert TheMuses.collection_name == "TheMuses"

    def test_themuses_description(self):
        """Should have clear description of purpose"""
        # GIVEN/WHEN: TheMuses schema
        # THEN: Description indicates core knowledge only
        description = TheMuses.description
        assert "core knowledge" in description.lower() or "obsidian" in description.lower()
        assert description is not None

    def test_themuses_has_text_property(self):
        """Should have text property for chunk content"""
        # GIVEN/WHEN: TheMuses properties
        properties = TheMuses.properties

        # THEN: Has text property
        text_prop = next((p for p in properties if p["name"] == "text"), None)
        assert text_prop is not None
        assert text_prop["dataType"] == ["text"]

    def test_themuses_has_source_file_property(self):
        """Should track source file path"""
        # GIVEN/WHEN: TheMuses properties
        properties = TheMuses.properties

        # THEN: Has sourceFile property
        source_prop = next((p for p in properties if p["name"] == "sourceFile"), None)
        assert source_prop is not None
        assert source_prop["dataType"] == ["text"]

    def test_themuses_has_source_type_property(self):
        """Should have sourceType property (always 'obsidian')"""
        # GIVEN/WHEN: TheMuses properties
        properties = TheMuses.properties

        # THEN: Has sourceType property
        type_prop = next((p for p in properties if p["name"] == "sourceType"), None)
        assert type_prop is not None
        assert type_prop["dataType"] == ["text"]

    def test_themuses_has_chunk_index_property(self):
        """Should track position in source file"""
        # GIVEN/WHEN: TheMuses properties
        properties = TheMuses.properties

        # THEN: Has chunkIndex property as integer
        index_prop = next((p for p in properties if p["name"] == "chunkIndex"), None)
        assert index_prop is not None
        assert index_prop["dataType"] == ["int"]

    def test_themuses_has_ingested_at_property(self):
        """Should track when chunk was ingested"""
        # GIVEN/WHEN: TheMuses properties
        properties = TheMuses.properties

        # THEN: Has ingestedAt timestamp
        ingested_prop = next((p for p in properties if p["name"] == "ingestedAt"), None)
        assert ingested_prop is not None
        assert ingested_prop["dataType"] == ["date"]

    def test_themuses_has_file_modified_at_property(self):
        """Should track source file modification time"""
        # GIVEN/WHEN: TheMuses properties
        properties = TheMuses.properties

        # THEN: Has fileModifiedAt timestamp
        modified_prop = next((p for p in properties if p["name"] == "fileModifiedAt"), None)
        assert modified_prop is not None
        assert modified_prop["dataType"] == ["date"]

    def test_themuses_vectorizer_is_none(self):
        """Should use manual vectorization (Ollama)"""
        # GIVEN/WHEN: TheMuses vectorizer config
        # THEN: Vectorizer is none (we provide vectors via Ollama)
        assert TheMuses.vectorizer == "none"

    def test_create_collection_if_not_exists(self, schema_manager, mock_client):
        """Should create collection if it doesn't exist"""
        # GIVEN: Collection doesn't exist
        mock_client.collections.exists.return_value = False

        # WHEN: Ensuring collection exists
        schema_manager.ensure_collection_exists("TheMuses")

        # THEN: Creates the collection
        mock_client.collections.create.assert_called_once()

    def test_skip_creation_if_exists(self, schema_manager, mock_client):
        """Should skip creation if collection already exists"""
        # GIVEN: Collection already exists
        mock_client.collections.exists.return_value = True

        # WHEN: Ensuring collection exists
        schema_manager.ensure_collection_exists("TheMuses")

        # THEN: Does not attempt to create
        mock_client.collections.create.assert_not_called()

    def test_get_collection(self, schema_manager, mock_client, mocker):
        """Should retrieve existing collection"""
        # GIVEN: Mock collection
        mock_collection = mocker.MagicMock()
        mock_client.collections.get.return_value = mock_collection

        # WHEN: Getting collection
        collection = schema_manager.get_collection("TheMuses")

        # THEN: Returns the collection
        assert collection == mock_collection
        mock_client.collections.get.assert_called_once_with("TheMuses")

    def test_themuses_all_properties_have_descriptions(self):
        """Should document all properties"""
        # GIVEN/WHEN: TheMuses properties
        properties = TheMuses.properties

        # THEN: Every property has a description
        for prop in properties:
            assert "description" in prop
            assert len(prop["description"]) > 0

    def test_themuses_schema_completeness(self):
        """Should have all required properties for vault ingestion"""
        # GIVEN/WHEN: TheMuses properties
        property_names = [p["name"] for p in TheMuses.properties]

        # THEN: Has all essential properties
        required_properties = [
            "text",
            "sourceFile",
            "sourceType",
            "chunkIndex",
            "ingestedAt",
            "fileModifiedAt",
        ]
        for prop_name in required_properties:
            assert prop_name in property_names, f"Missing required property: {prop_name}"

    def test_create_collection_with_correct_schema(self, schema_manager, mock_client):
        """Should create collection with TheMuses schema"""
        # GIVEN: Collection doesn't exist
        mock_client.collections.exists.return_value = False

        # WHEN: Creating TheMuses collection
        schema_manager.ensure_collection_exists("TheMuses")

        # THEN: Creates collection with correct properties
        call_args = mock_client.collections.create.call_args
        assert call_args is not None
        # Verify collection name is passed
        assert "TheMuses" in str(call_args)
