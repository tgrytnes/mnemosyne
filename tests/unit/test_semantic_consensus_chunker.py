from mnemosyne.aletheia.semantic_consensus_chunker import SemanticConsensusChunker
from mnemosyne.aletheia.text_chunker import TextChunk


def test_consensus_falls_back_on_semantic_error(mocker):
    semantic_chunker = mocker.MagicMock()
    semantic_chunker.chunk.side_effect = RuntimeError("LLM down")
    recursive_chunker = mocker.MagicMock()
    recursive_chunker.chunk.return_value = [
        TextChunk(text="fallback", index=0, source_file="note.md")
    ]

    chunker = SemanticConsensusChunker(
        semantic_chunker=semantic_chunker,
        recursive_chunker=recursive_chunker,
        min_chunk_size=1,
    )

    chunks = chunker.chunk("content", source_file="note.md")

    assert len(chunks) == 1
    assert chunks[0].text == "fallback"


def test_consensus_uses_overlap_boundaries(mocker):
    text = "one\n\ntwo\n\nthree"
    semantic_chunks = [
        TextChunk(text="one\n\n", index=0, source_file="note.md"),
        TextChunk(text="two\n\n", index=1, source_file="note.md"),
        TextChunk(text="three", index=2, source_file="note.md"),
    ]
    recursive_chunks = [
        TextChunk(text="one\n\n", index=0, source_file="note.md"),
        TextChunk(text="two\n\n", index=1, source_file="note.md"),
        TextChunk(text="three", index=2, source_file="note.md"),
    ]

    semantic_chunker = mocker.MagicMock()
    semantic_chunker.chunk.return_value = semantic_chunks
    recursive_chunker = mocker.MagicMock()
    recursive_chunker.chunk.return_value = recursive_chunks

    chunker = SemanticConsensusChunker(
        semantic_chunker=semantic_chunker,
        recursive_chunker=recursive_chunker,
        min_chunk_size=1,
    )

    chunks = chunker.chunk(text, source_file="note.md")

    assert [chunk.text for chunk in chunks] == ["one", "two", "three"]


def test_consensus_empty_uses_semantic(mocker):
    text = "alpha beta gamma"
    semantic_chunks = [
        TextChunk(text="alpha ", index=0, source_file="note.md"),
        TextChunk(text="beta ", index=1, source_file="note.md"),
        TextChunk(text="gamma", index=2, source_file="note.md"),
    ]
    recursive_chunks = [TextChunk(text=text, index=0, source_file="note.md")]

    semantic_chunker = mocker.MagicMock()
    semantic_chunker.chunk.return_value = semantic_chunks
    recursive_chunker = mocker.MagicMock()
    recursive_chunker.chunk.return_value = recursive_chunks

    chunker = SemanticConsensusChunker(
        semantic_chunker=semantic_chunker,
        recursive_chunker=recursive_chunker,
        min_chunk_size=1,
        boundary_tolerance=0,
    )

    chunks = chunker.chunk(text, source_file="note.md")

    assert [chunk.text for chunk in chunks] == [c.text for c in semantic_chunks]
