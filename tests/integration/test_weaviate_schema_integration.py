"""
Integration tests for WeaviateSchemaManager using real Weaviate.
"""

import pytest

from src.mnemosyne.alexandria.weaviate_schema import (
    Discoveries,
    TheMuses,
    WeaviateSchemaManager,
)


@pytest.mark.integration
def test_ensure_collection_exists_creates_themuses(weaviate_client):
    if weaviate_client.collections.exists("TheMuses"):
        weaviate_client.collections.delete("TheMuses")

    schema_manager = WeaviateSchemaManager(weaviate_client)
    schema_manager.ensure_collection_exists("TheMuses")

    assert weaviate_client.collections.exists("TheMuses")


@pytest.mark.integration
def test_get_collection_returns_collection(weaviate_client):
    schema_manager = WeaviateSchemaManager(weaviate_client)
    schema_manager.ensure_collection_exists("TheMuses")

    collection = schema_manager.get_collection("TheMuses")
    assert collection is not None


@pytest.mark.integration
def test_themuses_schema_properties_present(weaviate_client):
    schema_manager = WeaviateSchemaManager(weaviate_client)
    schema_manager.ensure_collection_exists("TheMuses")

    collection = weaviate_client.collections.get("TheMuses")
    properties = {prop.name for prop in collection.config.get().properties}

    expected = {prop["name"] for prop in TheMuses.properties}
    assert expected.issubset(properties)


@pytest.mark.integration
def test_ensure_collection_exists_creates_discoveries(weaviate_client):
    if weaviate_client.collections.exists("Discoveries"):
        weaviate_client.collections.delete("Discoveries")

    schema_manager = WeaviateSchemaManager(weaviate_client)
    schema_manager.ensure_collection_exists("Discoveries")

    assert weaviate_client.collections.exists("Discoveries")


@pytest.mark.integration
def test_discoveries_schema_properties_present(weaviate_client):
    schema_manager = WeaviateSchemaManager(weaviate_client)
    schema_manager.ensure_collection_exists("Discoveries")

    collection = weaviate_client.collections.get("Discoveries")
    properties = {prop.name for prop in collection.config.get().properties}

    expected = {prop["name"] for prop in Discoveries.properties}
    assert expected.issubset(properties)
