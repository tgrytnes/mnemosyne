"""
Integration tests for chunking strategies in the ingestion pipeline.
"""

import pytest

from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.aletheia.ingestion_state import IngestionStateTracker


def _make_vault(tmp_path):
    note = "# Title\n\nTopic A detail.\n\n## Section\n\nTopic B detail."
    (tmp_path / "note.md").write_text(note)
    return note


def _collect_properties(mock_weaviate):
    calls = mock_weaviate.collections.get.return_value.data.insert.call_args_list
    return [call.kwargs["properties"] for call in calls]


@pytest.mark.integration
def test_end_to_end_chunking_pipeline_strategies(tmp_path, mocker):
    """Ingest same vault with all strategies and compare metadata/boundaries."""
    text = _make_vault(tmp_path)

    mock_weaviate = mocker.MagicMock()
    mock_ollama = mocker.MagicMock()
    mock_ollama.embeddings.return_value = {"embedding": [0.1] * 1024}
    mock_ollama.generate.return_value = {
        "response": f'{{"boundaries": [{text.index("Topic B")} ]}}'
    }

    mocker.patch(
        "mnemosyne.aletheia.obsidian_ingestor.WeaviateSchemaManager.ensure_collection_exists",
        return_value=None,
    )

    results = {}
    for strategy in ("recursive", "semantic", "hybrid"):
        mock_weaviate.reset_mock()
        state_tracker = IngestionStateTracker(str(tmp_path / f"{strategy}.db"))
        ingestor = ObsidianIngestor(
            vault_path=str(tmp_path),
            weaviate_client=mock_weaviate,
            ollama_client=mock_ollama,
            state_tracker=state_tracker,
            chunking_strategy=strategy,
            chunk_size=1000,
            chunk_overlap=0,
            semantic_min_chunk_size=1,
            section_semantic_min_length=1,
        )
        ingestor.ingest_vault()
        results[strategy] = _collect_properties(mock_weaviate)

    # Semantic chunks should not carry heading metadata.
    assert all(prop["headingPath"] == "" for prop in results["semantic"])

    # Recursive and hybrid should include heading metadata.
    assert any(prop["headingPath"] for prop in results["recursive"])
    assert all(prop["headingPath"] for prop in results["hybrid"])

    # Semantic and hybrid should split at topic boundary, recursive should be 1 chunk.
    assert len(results["recursive"]) == 1
    assert len(results["semantic"]) == 2
    assert len(results["hybrid"]) == 2
