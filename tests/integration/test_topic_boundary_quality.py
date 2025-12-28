"""
Integration test for topic boundary quality with semantic chunking.
"""

import json

from mnemosyne.aletheia.semantic_chunker import SemanticChunker


def test_semantic_chunking_aligns_with_topic_boundaries(mocker):
    """Semantic boundaries should align with topic shifts."""
    text = "Topic A ends here.\n\nTopic B starts now."
    boundary_index = text.index("Topic B")

    mock_ollama = mocker.MagicMock()
    mock_ollama.generate.return_value = {"response": json.dumps({"boundaries": [boundary_index]})}

    chunker = SemanticChunker(ollama_client=mock_ollama, min_chunk_size=1)
    chunks = chunker.chunk(text, source_file="note.md")

    assert len(chunks) == 2
    assert "Topic A" in chunks[0].text
    assert "Topic B" in chunks[1].text
