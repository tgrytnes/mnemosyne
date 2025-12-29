"""
Integration tests for cluster metadata synthesis with REAL Ollama and Weaviate.
"""

import ollama
import pytest

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.argus.cluster_metadata_synthesis import (
    ClusterData,
    ClusterMetadataSynthesizer,
)


@pytest.mark.integration
@pytest.mark.postgres
def test_synthesis_and_storage_with_real_ollama(postgres_connection, test_config):
    """
    REAL INTEGRATION TEST: Synthesize cluster profile with actual Ollama LLM.

    Tests:
    - Real Ollama LLM generates valid JSON
    - Profile meets Pydantic schema
    - PostgreSQL storage and retrieval works
    """
    # Use REAL Ollama client
    ollama_client = ollama.Client(
        host=test_config["ollama_url"],
        timeout=test_config["ollama_timeout"],
    )

    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()

    synthesizer = ClusterMetadataSynthesizer(ollama_client)

    # Realistic cluster data
    cluster = ClusterData(
        cluster_id="integration-cluster-99",
        representative_notes=[
            "This cluster focuses on knowledge management and personal note-taking systems. "
            "Key topics include Zettelkasten methodology, linking strategies, and semantic search. "
            "The notes discuss building a second brain and knowledge graphs."
        ],
        representative_note_ids=["note-10", "note-11"],
        tags=["research", "knowledge-management"],
    )

    # Synthesize with REAL LLM
    result = synthesizer.synthesize(cluster)

    # Validate result
    assert result.status == "success", f"Synthesis failed: {result.error}"
    assert result.profile is not None

    # Validate profile content
    profile = result.profile
    assert profile.cluster_id == "integration-cluster-99"
    assert profile.theme_summary  # Not empty
    assert len(profile.theme_summary) > 10  # Meaningful content

    # Confidence should be reasonable
    assert 0 <= profile.confidence_score <= 1

    # Should extract some entities or topics
    assert profile.key_entities or profile.dominant_topics

    # Save to PostgreSQL
    repo.save(profile)

    # Verify persistence
    fetched = repo.get("integration-cluster-99")
    assert fetched is not None
    assert fetched.theme_summary == profile.theme_summary
    assert fetched.confidence_score == profile.confidence_score
    assert fetched.key_entities == profile.key_entities


@pytest.mark.integration
@pytest.mark.weaviate
@pytest.mark.postgres
def test_cluster_synthesis_from_real_weaviate_data(
    weaviate_client, clean_weaviate_collection, postgres_connection, test_config
):
    """
    REAL INTEGRATION TEST: Fetch cluster from Weaviate, synthesize with Ollama.

    Full pipeline test:
    1. Ingest real notes to Weaviate
    2. Fetch chunks for a cluster
    3. Synthesize profile with real Ollama
    4. Store in PostgreSQL
    """
    import tempfile
    from pathlib import Path

    import ollama

    from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
    from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor

    # STEP 1: Create test vault and ingest to Weaviate

    with tempfile.TemporaryDirectory() as tmp_dir:
        vault_path = Path(tmp_dir) / "test_vault"
        vault_path.mkdir()

        # Create realistic notes
        notes = [
            (
                "ml_basics.md",
                """# Machine Learning Basics
Neural networks and deep learning fundamentals.
Key concepts: backpropagation, gradient descent, activation functions.
""",
            ),
            (
                "ml_advanced.md",
                """# Advanced ML Topics
Transfer learning and model optimization.
Techniques for improving model performance.
""",
            ),
            (
                "project_mgmt.md",
                """# Project Management
Agile methodologies and sprint planning.
Team coordination and task management.
""",
            ),
        ]

        for filename, content in notes:
            (vault_path / filename).write_text(content)

        # Ingest to Weaviate
        ollama_client = ollama.Client(
            host=test_config["ollama_url"],
            timeout=test_config["ollama_timeout"],
        )
        state_tracker = IngestionStateTracker(str(vault_path / "state.db"))

        ingestor = ObsidianIngestor(
            vault_path=str(vault_path),
            weaviate_client=weaviate_client,
            ollama_client=ollama_client,
            state_tracker=state_tracker,
        )

        stats = ingestor.ingest_vault()
        assert stats["files_processed"] == 3

    # STEP 2: Fetch chunks from Weaviate (simulating Story 001 cluster)
    collection = weaviate_client.collections.get("TheMuses")

    # Get all chunks
    all_results = collection.query.fetch_objects(limit=100)
    assert len(all_results.objects) > 0, "No chunks in Weaviate"

    # Get chunks for ML topic (first 2 notes)
    ml_chunks = [
        obj for obj in all_results.objects if "ml_" in obj.properties.get("sourceFile", "").lower()
    ]
    assert len(ml_chunks) >= 2, "Not enough ML chunks"

    # Extract text content
    representative_notes = [chunk.properties["text"] for chunk in ml_chunks[:2]]
    representative_ids = [str(chunk.uuid) for chunk in ml_chunks[:2]]

    # STEP 3: Create cluster data from Weaviate chunks
    cluster = ClusterData(
        cluster_id="weaviate-cluster-ml",
        representative_notes=representative_notes,
        representative_note_ids=representative_ids,
        tags=["machine-learning"],
    )

    # STEP 4: Synthesize with REAL Ollama
    synthesizer = ClusterMetadataSynthesizer(ollama_client)
    result = synthesizer.synthesize(cluster)

    assert result.status == "success", f"Synthesis failed: {result.error}"

    # STEP 5: Validate profile extracted ML theme
    profile = result.profile
    theme_lower = profile.theme_summary.lower()

    # Should recognize ML content
    ml_keywords = ["machine", "learning", "neural", "model"]
    found = any(kw in theme_lower for kw in ml_keywords)
    assert found, f"Theme '{profile.theme_summary}' doesn't mention ML concepts"

    # STEP 6: Save to PostgreSQL and verify
    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()
    repo.save(profile)

    fetched = repo.get("weaviate-cluster-ml")
    assert fetched is not None
    assert fetched.cluster_id == "weaviate-cluster-ml"


@pytest.mark.integration
@pytest.mark.parametrize(
    "note_content,expected_topic_keywords",
    [
        (
            "Deep learning with PyTorch and TensorFlow. "
            "Training convolutional neural networks for computer vision.",
            ["deep learning", "neural", "pytorch", "vision"],
        ),
        (
            "Agile development with Scrum framework. " "Daily standups and sprint retrospectives.",
            ["agile", "scrum", "sprint"],
        ),
        (
            "SQL database optimization and query performance. "
            "Indexing strategies and normalization.",
            ["sql", "database", "query"],
        ),
    ],
)
def test_real_llm_topic_extraction(
    postgres_connection, test_config, note_content, expected_topic_keywords
):
    """
    REAL INTEGRATION TEST: Validate LLM extracts correct topics from content.

    Parametrized test ensures LLM works across different content types.
    """
    ollama_client = ollama.Client(
        host=test_config["ollama_url"],
        timeout=test_config["ollama_timeout"],
    )

    synthesizer = ClusterMetadataSynthesizer(ollama_client)

    cluster = ClusterData(
        cluster_id=f"topic-test-{hash(note_content) % 10000}",
        representative_notes=[note_content],
        representative_note_ids=["test-note"],
        tags=["test"],
    )

    result = synthesizer.synthesize(cluster)

    assert result.status == "success", f"Failed: {result.error}"

    # Check theme or topics contain expected keywords
    profile = result.profile
    all_text = (
        profile.theme_summary.lower()
        + " ".join(profile.dominant_topics).lower()
        + " ".join(profile.key_entities).lower()
    )

    # Should find at least one keyword
    found_keywords = [kw for kw in expected_topic_keywords if kw in all_text]
    assert found_keywords, (
        f"Profile doesn't contain any of {expected_topic_keywords}. "
        f"Theme: '{profile.theme_summary}', "
        f"Topics: {profile.dominant_topics}, "
        f"Entities: {profile.key_entities}"
    )


@pytest.mark.integration
def test_error_handling_with_real_llm(test_config):
    """
    REAL INTEGRATION TEST: Validate error handling with real LLM.

    Tests retry logic when LLM gives malformed responses.
    Note: This might pass if Ollama always returns valid JSON.
    """
    ollama_client = ollama.Client(
        host=test_config["ollama_url"],
        timeout=test_config["ollama_timeout"],
    )

    synthesizer = ClusterMetadataSynthesizer(
        ollama_client,
        max_retries=2,  # Allow retries
    )

    # Empty cluster might cause LLM to produce invalid output
    cluster = ClusterData(
        cluster_id="empty-cluster",
        representative_notes=[""],  # Empty content
        representative_note_ids=[],
        tags=[],
    )

    result = synthesizer.synthesize(cluster)

    # Should either succeed or fail gracefully
    assert result.status in ["success", "failed"]

    if result.status == "failed":
        assert result.error  # Has error message
        assert result.profile is None
    else:
        assert result.profile is not None
