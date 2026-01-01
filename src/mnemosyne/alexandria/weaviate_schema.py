"""
Weaviate schema definitions for Mnemosyne collections.

Defines the TheMuses collection schema for Obsidian vault embeddings.
This is separate from TheLethe (emails/PDFs) to enable efficient clustering
on curated knowledge only.
"""

import weaviate
from weaviate.classes.config import Configure, DataType, Property, Tokenization


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
            "name": "sourceFileId",
            "dataType": ["text"],
            "description": "Stable hash of sourceFile for exact-match deletes",
            "tokenization": Tokenization.FIELD,
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
        {
            "name": "headingPath",
            "dataType": ["text"],
            "description": "Full heading path (e.g., '# Main > ## Section > ### Subsection')",
        },
        {
            "name": "headingLevel",
            "dataType": ["int"],
            "description": "Heading level: 0 (no heading), 1-6 (# to ######)",
        },
        {
            "name": "sectionTitle",
            "dataType": ["text"],
            "description": "Immediate parent heading title",
        },
        {
            "name": "clusterId",
            "dataType": ["int"],
            "description": "ID of the cluster this chunk belongs to",
        },
    ]


class ClusterCentroidCollection:
    """
    Schema for ClusterCentroid collection.

    Stores the calculated centroid for each cluster.
    """

    collection_name = "ClusterCentroid"

    description = "Stores the calculated centroid vector and metadata for each cluster."

    vectorizer = "none"  # We provide vectors

    properties = [
        {
            "name": "clusterId",
            "dataType": ["int"],
            "description": "The ID of the cluster.",
        },
        {
            "name": "clusterSize",
            "dataType": ["int"],
            "description": "Number of items in the cluster.",
        },
        {
            "name": "lastUpdated",
            "dataType": ["date"],
            "description": "Timestamp when the centroid was last calculated.",
        },
    ]


class TheLethe:
    """
    Schema for TheLethe collection (email/PDF archive).
    """

    collection_name = "TheLethe"

    description = "Archive of emails/PDFs with cleaned text and embeddings."

    vectorizer = "none"  # manual vectors via embedder

    properties = [
        {
            "name": "subject",
            "dataType": ["text"],
            "description": "Email subject",
        },
        {
            "name": "body",
            "dataType": ["text"],
            "description": "Cleaned email body",
        },
        {
            "name": "sender",
            "dataType": ["text"],
            "description": "Sender address",
        },
        {
            "name": "date",
            "dataType": ["text"],
            "description": "Date string",
        },
        {
            "name": "clusterId",
            "dataType": ["int"],
            "description": "Assigned cluster id",
        },
        {
            "name": "keywords",
            "dataType": ["text[]"],
            "description": "Extracted keywords",
        },
        {
            "name": "type",
            "dataType": ["text"],
            "description": "Artifact type",
        },
        {
            "name": "messageId",
            "dataType": ["text"],
            "description": "Stable message identifier",
        },
        {
            "name": "sourcePath",
            "dataType": ["text"],
            "description": "Original file/source path",
        },
        {
            "name": "documentType",
            "dataType": ["text"],
            "description": "Document type (pdf/email/etc.)",
        },
        {
            "name": "pageNumber",
            "dataType": ["int"],
            "description": "Page number for PDF chunks",
        },
        {
            "name": "creationDate",
            "dataType": ["text"],
            "description": "Creation date from metadata",
        },
    ]

<<<<<<< HEAD
class TheLethe:
    """
    Schema for TheLethe collection (email/PDF archive).
    """

    collection_name = "TheLethe"

    description = "Archive of emails/PDFs with cleaned text and embeddings."

    vectorizer = "none"  # manual vectors via embedder

    properties = [
        {
            "name": "subject",
            "dataType": ["text"],
            "description": "Email subject",
        },
        {
            "name": "body",
            "dataType": ["text"],
            "description": "Cleaned email body",
        },
        {
            "name": "sender",
            "dataType": ["text"],
            "description": "Sender address",
        },
        {
            "name": "date",
            "dataType": ["text"],
            "description": "Date string",
        },
        {
            "name": "clusterId",
            "dataType": ["int"],
            "description": "Assigned cluster id",
        },
        {
            "name": "keywords",
            "dataType": ["text[]"],
            "description": "Extracted keywords",
        },
        {
            "name": "type",
            "dataType": ["text"],
            "description": "Artifact type",
        },
        {
            "name": "messageId",
            "dataType": ["text"],
            "description": "Stable message identifier",
        },
        {
            "name": "sourcePath",
            "dataType": ["text"],
            "description": "Original file/source path",
        },
        {
            "name": "documentType",
            "dataType": ["text"],
            "description": "Document type (pdf/email/etc.)",
        },
        {
            "name": "pageNumber",
            "dataType": ["int"],
            "description": "Page number for PDF chunks",
        },
        {
            "name": "creationDate",
            "dataType": ["text"],
            "description": "Creation date from metadata",
        },
    ]

class Discoveries:
    """
    Schema for Scout discoveries stored in latent space.
    """

    collection_name = "Discoveries"

    description = "Latent-space discoveries detected by Scout."

    vectorizer = "none"

    properties = [
        {
            "name": "patternType",
            "dataType": ["text"],
            "description": "Type of pattern detected (e.g., project_candidate)",
            "tokenization": Tokenization.FIELD,
        },
        {
            "name": "clusterIds",
            "dataType": ["text[]"],
            "description": "Cluster IDs associated with this discovery",
        },
        {
            "name": "confidenceScore",
            "dataType": ["number"],
            "description": "Confidence score for the detection",
        },
        {
            "name": "detectedAt",
            "dataType": ["date"],
            "description": "Timestamp when the pattern was detected",
        },
        {
            "name": "signals",
            "dataType": ["text"],
            "description": "JSON-encoded signals and scoring metadata",
        },
        {
            "name": "runId",
            "dataType": ["text"],
            "description": "Scout run identifier",
        },
        {
            "name": "clustersAnalyzed",
            "dataType": ["int"],
            "description": "Number of clusters analyzed in the run",
        },
        {
            "name": "errors",
            "dataType": ["text"],
            "description": "JSON-encoded error list for the run",
        },
        {
            "name": "dryRun",
            "dataType": ["boolean"],
            "description": "Whether the run was executed in dry-run mode",
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
        elif collection_name == TheLethe.collection_name:
            self._create_thelethe_collection()
        elif collection_name == ClusterCentroidCollection.collection_name:
            self._create_clustercentroid_collection()
        elif collection_name == Discoveries.collection_name:
            self._create_discoveries_collection()
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
                tokenization=prop.get("tokenization"),
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

    def _create_thelethe_collection(self) -> None:
        """Create TheLethe collection with proper schema"""
        properties = [
            Property(
                name=prop["name"],
                data_type=self._map_datatype(prop["dataType"][0]),
                description=prop.get("description", ""),
            )
            for prop in TheLethe.properties
        ]

        self.client.collections.create(
            name=TheLethe.collection_name,
            description=TheLethe.description,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=properties,
        )

    def _create_clustercentroid_collection(self) -> None:
        """Create ClusterCentroid collection with proper schema"""
        properties = [
            Property(
                name=prop["name"],
                data_type=self._map_datatype(prop["dataType"][0]),
                description=prop.get("description", ""),
            )
            for prop in ClusterCentroidCollection.properties
        ]

        self.client.collections.create(
            name=ClusterCentroidCollection.collection_name,
            description=ClusterCentroidCollection.description,
            vectorizer_config=Configure.Vectorizer.none(),
            properties=properties,
        )

    def _create_discoveries_collection(self) -> None:
        """Create Discoveries collection with proper schema"""
        properties = [
            Property(
                name=prop["name"],
                data_type=self._map_datatype(prop["dataType"][0]),
                description=prop.get("description", ""),
                tokenization=prop.get("tokenization"),
            )
            for prop in Discoveries.properties
        ]

        self.client.collections.create(
            name=Discoveries.collection_name,
            description=Discoveries.description,
            vectorizer_config=Configure.Vectorizer.none(),
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
            "text[]": getattr(DataType, "TEXT_ARRAY", DataType.TEXT),
            "int": DataType.INT,
            "int[]": getattr(DataType, "INT_ARRAY", DataType.INT),
            "date": DataType.DATE,
            "date[]": getattr(DataType, "DATE_ARRAY", DataType.DATE),
            "number": DataType.NUMBER,
            "number[]": getattr(DataType, "NUMBER_ARRAY", DataType.NUMBER),
            "boolean": DataType.BOOL,
            "boolean[]": getattr(DataType, "BOOL_ARRAY", DataType.BOOL),
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
