"""
Integration test for Story 025: deletion hygiene removes chunks from Weaviate.
Requires Weaviate running.
"""

import pytest


@pytest.mark.integration
@pytest.mark.weaviate
def test_deletion_removes_weaviate_chunks(tmp_path, weaviate_client):
    from mnemosyne.aletheia.shadow_janitor import Janitor  # to be implemented
    from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager

    source = tmp_path / "vault"
    shadow = tmp_path / "shadow"
    source.mkdir()
    file_path = source / "note.md"
    file_path.write_text("Hello world")

    # Seed a chunk in Weaviate with source path
    WeaviateSchemaManager(weaviate_client).ensure_collection_exists("TheMuses")
    collection = weaviate_client.collections.get("TheMuses")
    collection.data.insert(
        properties={"text": "Hello world", "sourceFile": str(file_path), "sourceFileId": "abc"},
        vector={"default": [0.0] * 1024},
    )

    janitor = Janitor(str(source), str(shadow))
    janitor.sync_to_shadow()

    # Delete the source file and resync
    file_path.unlink()
    janitor.sync_to_shadow()

    objs = collection.query.fetch_objects(limit=10)
    assert all(obj.properties.get("sourceFile") != str(file_path) for obj in objs.objects)
