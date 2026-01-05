"""
E2E performance benchmark for hybrid chunking with REAL Ollama and Weaviate.
"""

import os
import time

import ollama
import pytest

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor


@pytest.mark.e2e
@pytest.mark.weaviate
def test_hybrid_ingestion_under_time_limit(
    tmp_path, weaviate_client, clean_weaviate_collection, test_config
):
    """
    REAL E2E TEST: Hybrid ingestion with actual Ollama LLM calls.
    Should complete under the configured time limit.
    """
    file_count = int(os.getenv("E2E_HYBRID_INGEST_FILE_COUNT", "50"))
    max_minutes = float(os.getenv("E2E_HYBRID_INGEST_MAX_MINUTES", "30"))
    progress_every = int(os.getenv("INGEST_PROGRESS_EVERY", "10"))

    # Create test files with meaningful content for semantic chunking
    for i in range(file_count):
        content = f"""# Note {i}

## Introduction
This is test note number {i} with multiple sections to test semantic chunking.
The content is meaningful enough for the LLM to detect topic boundaries.

## Main Topic
Here we discuss the main topic of note {i}.
This section contains the primary information.

## Conclusion
Final thoughts on note {i}.
"""
        (tmp_path / f"note-{i}.md").write_text(content)

    # Use REAL Ollama client
    ollama_client = ollama.Client(host=test_config["ollama_url"])

    # Use REAL Weaviate client
    state_tracker = IngestionStateTracker(str(tmp_path / "ingestion_state.db"))

    ingestor = ObsidianIngestor(
        vault_path=str(tmp_path),
        weaviate_client=weaviate_client,
        ollama_client=ollama_client,
        state_tracker=state_tracker,
        chunking_strategy="hybrid",
        section_semantic_min_length=100,  # Realistic threshold
        semantic_min_chunk_size=50,
        progress_every=progress_every,
    )

    start = time.monotonic()
    stats = ingestor.ingest_vault()
    elapsed = time.monotonic() - start

    assert stats["files_processed"] == file_count
    assert stats["total_chunks"] >= file_count  # Should create at least one chunk per file
    assert elapsed < max_minutes * 60


@pytest.mark.e2e
@pytest.mark.weaviate
@pytest.mark.parametrize(
    "filename,text,keywords,expected_min_chunks",
    [
        (
            "semantic_boundary_1.md",
            """Topic A is about machine learning and neural networks.
Deep learning has transformed AI research significantly.
This section focuses on technical aspects.

Topic B discusses project management and team collaboration.
Agile methodologies are important for software development.
This section shifts to organizational topics.
""",
            ["machine learning", "project management"],
            2,
        ),
        (
            "semantic_boundary_2.md",
            """Gardening tips: compost improves soil quality and water retention.
Mulching suppresses weeds and stabilizes moisture.

Cybersecurity basics include using MFA and rotating passwords.
Phishing awareness helps avoid credential theft.
""",
            ["compost", "cybersecurity"],
            2,
        ),
        (
            "semantic_boundary_3.md",
            """Financial budgeting starts with tracking income and fixed expenses.
Saving goals are easier with automated transfers.

Fitness training includes strength sessions and cardio intervals.
Recovery days reduce injury risk and improve performance.
""",
            ["budgeting", "fitness"],
            2,
        ),
        (
            "semantic_boundary_4.md",
            """Product roadmap: define customer problems and prioritize initiatives.
Quarterly goals align teams and clarify scope.

Legal compliance: document data handling and retention policies.
Audits ensure adherence to regulations.

Customer support: response SLAs and knowledge bases improve satisfaction.
""",
            ["roadmap", "compliance", "support"],
            3,
        ),
    ],
)
def test_semantic_chunking_detects_topic_shift(
    tmp_path,
    weaviate_client,
    clean_weaviate_collection,
    test_config,
    filename,
    text,
    keywords,
    expected_min_chunks,
):
    """
    REAL E2E TEST: Semantic chunking should split at clear topic shifts.
    """
    note_path = tmp_path / filename
    note_path.write_text(text)

    ollama_client = ollama.Client(host=test_config["ollama_url"])
    state_tracker = IngestionStateTracker(str(tmp_path / f"{filename}.db"))

    ingestor = ObsidianIngestor(
        vault_path=str(tmp_path),
        weaviate_client=weaviate_client,
        ollama_client=ollama_client,
        state_tracker=state_tracker,
        chunking_strategy="semantic",
        semantic_min_chunk_size=1,
        semantic_max_chunk_size=1000,
    )

    ingestor.ingest_file(str(note_path))

    collection = weaviate_client.collections.get("TheMuses")
    results = collection.query.fetch_objects(limit=50)
    chunks = [
        obj.properties["text"]
        for obj in results.objects
        if obj.properties.get("sourceFile", "").endswith(f"/{filename}")
    ]

    assert (
        len(chunks) >= expected_min_chunks
    ), f"Expected at least {expected_min_chunks} chunks, got {len(chunks)}"

    chunk_texts = [text.lower() for text in chunks]
    for keyword in keywords:
        assert any(keyword in text for text in chunk_texts), f"Missing keyword: {keyword}"
