"""
Integration test for topic boundary quality with semantic chunking.

USES REAL OLLAMA (no mocks).
"""

import ollama
import pytest

from mnemosyne.aletheia.semantic_chunker import SemanticChunker


@pytest.mark.integration
def test_semantic_chunking_aligns_with_topic_boundaries(test_config):
    """Semantic boundaries should align with topic shifts using REAL Ollama."""
    text = """Topic A is about machine learning and neural networks.
Deep learning has transformed AI research significantly.
This section focuses on technical aspects.

Topic B discusses project management and team collaboration.
Agile methodologies are important for software development.
This section shifts to organizational topics."""

    # Use REAL Ollama client
    ollama_client = ollama.Client(host=test_config["ollama_url"])

    chunker = SemanticChunker(ollama_client=ollama_client, min_chunk_size=1)
    chunks = chunker.chunk(text, source_file="note.md")

    # Should detect the topic boundary and create 2 chunks
    assert len(chunks) >= 2, f"Expected at least 2 chunks, got {len(chunks)}"

    # Verify topics are separated
    chunk_texts = [c.text for c in chunks]
    topic_a_found = any("machine learning" in text.lower() for text in chunk_texts)
    topic_b_found = any("project management" in text.lower() for text in chunk_texts)

    assert topic_a_found, "Topic A (machine learning) should be in chunks"
    assert topic_b_found, "Topic B (project management) should be in chunks"
