"""
Weaviate schema definitions for Mnemosyne collections.

Defines the TheMuses collection schema for Obsidian vault embeddings.
This is separate from TheLethe (emails/PDFs) to enable efficient clustering
on curated knowledge only.
"""

from typing import List, Dict, Any
import weaviate
from weaviate.classes.config import Property, DataType, Configure


class TheMuses:
    """
    Schema for The Muses collection - Core Knowledge Database.

    Contains ONLY Obsidian vault content (curated knowledge).
    Designed for clustering, pattern detection, and semantic analysis.

    NOT for emails/PDFs - those go in TheLethe collection.
    """

    collection_name = "TheMuses"

    description = (
        "Core knowledge database containing Obsidian vault embeddings. "
        "Curated, high-quality content only. Used for clustering and pattern detection. "
        "NOT for email/PDF archive."
    )

    vectorizer = "none"  # We provide vectors via Ollama

    properties = [
        {
            "name": "text",
            "dataType": ["text"],
            "description": "Cleaned chunk text ready for semantic search",
        },
        {
            "name": "sourceFile",
            "dataType": ["text"],
            "description": "Original Obsidian file path (absolute)",
        },
        {
            "name": "sourceType",
            "dataType": ["text"],
            "description": "Always 'obsidian' for TheMuses collection",
        },
        {
            "name": "chunkIndex",
            "dataType": ["int"],
            "description": "Position in source file (0-indexed)",
        },
        {
            "name": "ingestedAt",
            "dataType": ["date"],
            "description": "Timestamp when chunk was ingested",
        },
        {
            "name": "fileModifiedAt",
            "dataType": ["date"],
            "description": "Last modified time of source file",
        },
    ]


class WeaviateSchemaManager:
    """
    Manages Weaviate collection schemas.

    Handles creation and validation of Mnemosyne collections.
    """

    def __init__(self, client: weaviate.WeaviateClient):
        """
        Initialize schema manager.

        Args:
            client: Connected Weaviate client
        """
        self.client = client

    def ensure_collection_exists(self, collection_name: str) -> None:
        """
        Create collection if it doesn't exist.

        Args:
            collection_name: Name of collection to ensure exists
        """
        # Check if collection already exists
        if self.client.collections.exists(collection_name):
            return

        # Get schema for this collection
        if collection_name == "TheMuses":
            self._create_themuses_collection()
        else:
            raise ValueError(f"Unknown collection: {collection_name}")

    def _create_themuses_collection(self) -> None:
        """Create TheMuses collection with proper schema"""
        # Convert property definitions to Weaviate Property objects
        properties = [
            Property(
                name=prop["name"],
                data_type=self._map_datatype(prop["dataType"][0]),
                description=prop.get("description", ""),
            )
            for prop in TheMuses.properties
        ]

        # Create collection
        self.client.collections.create(
            name=TheMuses.collection_name,
            description=TheMuses.description,
            vectorizer_config=Configure.Vectorizer.none(),  # Manual vectors via Ollama
            properties=properties,
        )

    def _map_datatype(self, datatype_str: str) -> DataType:
        """
        Map string datatype to Weaviate DataType enum.

        Args:
            datatype_str: String representation of datatype

        Returns:
            Weaviate DataType enum value
        """
        mapping = {
            "text": DataType.TEXT,
            "int": DataType.INT,
            "date": DataType.DATE,
            "number": DataType.NUMBER,
            "boolean": DataType.BOOL,
        }
        return mapping.get(datatype_str.lower(), DataType.TEXT)

    def get_collection(self, collection_name: str):
        """
        Get existing collection.

        Args:
            collection_name: Name of collection to retrieve

        Returns:
            Weaviate collection object
        """
        return self.client.collections.get(collection_name)
