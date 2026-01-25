from mnemosyne.aletheia.semantic_cosine_merge_chunker import SemanticCosineMergeChunker
from mnemosyne.aletheia.text_chunker import TextChunk


def test_semantic_cosine_merge_merges_similar_chunks(mocker):
    semantic_chunker = mocker.MagicMock()
    semantic_chunker.chunk.return_value = [
        TextChunk(text="alpha ", index=0, source_file="note.md"),
        TextChunk(text="alpha", index=1, source_file="note.md"),
    ]
    embedding_provider = mocker.MagicMock()
    embedding_provider.embed.return_value = [1.0, 0.0]

    chunker = SemanticCosineMergeChunker(
        semantic_chunker=semantic_chunker,
        embedding_provider=embedding_provider,
        similarity_threshold=0.9,
        min_chunk_size=1,
        max_chunk_size=100,
    )

    chunks = chunker.chunk("alpha alpha", source_file="note.md")

    assert len(chunks) == 1


def test_semantic_cosine_merge_uses_fallback_for_oversized_chunks(mocker):
    semantic_chunker = mocker.MagicMock()
    semantic_chunker.chunk.return_value = [
        TextChunk(text="123456", index=0, source_file="note.md"),
        TextChunk(text="7890", index=1, source_file="note.md"),
    ]
    embedding_provider = mocker.MagicMock()
    embedding_provider.embed.return_value = [1.0, 0.0]
    fallback_chunker = mocker.MagicMock()
    fallback_chunker.chunk.return_value = [TextChunk(text="small", index=0, source_file="note.md")]

    chunker = SemanticCosineMergeChunker(
        semantic_chunker=semantic_chunker,
        embedding_provider=embedding_provider,
        similarity_threshold=0.9,
        min_chunk_size=1,
        max_chunk_size=5,
        fallback_chunker=fallback_chunker,
    )

    chunks = chunker.chunk("1234567890", source_file="note.md")

    fallback_chunker.chunk.assert_called_once()
    assert any(chunk.text == "small" for chunk in chunks)
