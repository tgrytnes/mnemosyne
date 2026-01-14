"""Unit tests for semantic-cosine chunking."""

from mnemosyne.aletheia.semantic_cosine_chunker import SemanticCosineChunker
from mnemosyne.aletheia.text_chunker import TextChunker


class _DummyEmbeddingProvider:
    def __init__(self, vectors_by_text):
        self.vectors_by_text = vectors_by_text
        self.calls = []

    def embed(self, model: str, text: str):
        self.calls.append(text)
        return self.vectors_by_text[text]


def test_semantic_cosine_splits_on_similarity_drop():
    text = "Alpha one. Alpha two. Beta three."
    vectors = {
        "Alpha one.": [1.0, 0.0],
        "Alpha two.": [1.0, 0.0],
        "Beta three.": [0.0, 1.0],
    }
    embedding_provider = _DummyEmbeddingProvider(vectors)
    chunker = SemanticCosineChunker(
        embedding_provider=embedding_provider,
        fallback_chunker=TextChunker(chunk_size=100, chunk_overlap=0),
        similarity_threshold=0.5,
        min_chunk_size=1,
        max_chunk_size=200,
    )

    chunks = chunker.chunk(text, source_file="note.md")

    assert [chunk.text for chunk in chunks] == [
        "Alpha one. Alpha two.",
        "Beta three.",
    ]


def test_semantic_cosine_falls_back_on_embedding_failure():
    embedding_provider = _DummyEmbeddingProvider({})
    fallback = TextChunker(chunk_size=5, chunk_overlap=0)
    chunker = SemanticCosineChunker(
        embedding_provider=embedding_provider,
        fallback_chunker=fallback,
        similarity_threshold=0.5,
        min_chunk_size=1,
        max_chunk_size=200,
    )

    text = "One. Two. Three."
    chunks = chunker.chunk(text, source_file="note.md")
    fallback_chunks = fallback.chunk(text, source_file="note.md")

    assert [chunk.text for chunk in chunks] == [chunk.text for chunk in fallback_chunks]
