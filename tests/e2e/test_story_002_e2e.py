"""
E2E tests for Story 002 - Structured Metadata Synthesis with REAL Ollama.
"""

import time

import ollama
import pytest

from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
from mnemosyne.argus.cluster_metadata_synthesis import (
    ClusterData,
    ClusterMetadataSynthesizer,
)


@pytest.mark.e2e
@pytest.mark.postgres
def test_story_002_end_to_end_with_real_ollama(postgres_connection, test_config):
    """
    REAL E2E TEST: Generate cluster profiles with actual Ollama LLM.

    Tests the full pipeline:
    1. Create realistic cluster data
    2. Synthesize profiles with REAL Ollama (qwen3:0.6b with JSON mode)
    3. Validate LLM output quality
    4. Store in PostgreSQL
    5. Verify persistence
    """
    # Use REAL Ollama client
    ollama_client = ollama.Client(host=test_config["ollama_url"])

    # Setup repository
    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()

    # Real cluster data with meaningful content
    clusters = [
        ClusterData(
            cluster_id=f"cluster-{i}",
            representative_notes=[
                f"This is a research note about {topic}. "
                f"Key findings include {detail}. "
                f"The analysis shows significant insights into {topic} patterns."
            ],
            representative_note_ids=[f"note-{i}"],
            tags=["research", category],
        )
        for i, (topic, detail, category) in enumerate(
            [
                ("machine learning", "neural network architectures", "technology"),
                ("project management", "agile sprint planning", "business"),
                ("data science", "statistical hypothesis testing", "analytics"),
                ("knowledge graphs", "semantic relationships", "technology"),
                ("team collaboration", "remote work strategies", "business"),
            ]
        )
    ]

    synthesizer = ClusterMetadataSynthesizer(ollama_client)

    # Measure performance with real LLM
    start = time.monotonic()
    results = [synthesizer.synthesize(cluster) for cluster in clusters]
    elapsed = time.monotonic() - start

    # Real LLM might have occasional failures - check >80% success
    success_count = sum(1 for r in results if r.status == "success")
    success_rate = success_count / len(results)

    assert success_rate >= 0.80, (
        f"Only {success_count}/{len(results)} ({success_rate:.1%}) successful. "
        f"Expected >=80% with real LLM."
    )

    # Performance check with real LLM (5 clusters should complete reasonably fast)
    assert elapsed < 5 * 60, (
        f"Took {elapsed:.1f}s for {len(clusters)} clusters. " f"Expected <5 minutes with real LLM."
    )

    # Validate real LLM output quality
    for i, result in enumerate(results):
        if result.status == "success":
            profile = result.profile

            # Check theme summary is meaningful (not empty, reasonable length)
            assert profile.theme_summary, f"Cluster {i}: Empty theme summary"
            assert (
                len(profile.theme_summary) > 10
            ), f"Cluster {i}: Theme too short ({len(profile.theme_summary)} chars)"
            assert (
                len(profile.theme_summary) < 500
            ), f"Cluster {i}: Theme too long ({len(profile.theme_summary)} chars)"

            # Check confidence score is valid
            assert (
                0 <= profile.confidence_score <= 1
            ), f"Cluster {i}: Invalid confidence {profile.confidence_score}"

            # Check has some extracted data
            assert (
                profile.key_entities or profile.dominant_topics
            ), f"Cluster {i}: No entities or topics extracted"

            # Store in PostgreSQL
            repo.save(profile)

    # Verify persistence - fetch one back
    fetched = repo.get("cluster-0")
    assert fetched is not None, "Failed to retrieve saved profile"
    assert fetched.theme_summary, "Retrieved profile has no theme summary"
    assert fetched.confidence_score > 0, "Retrieved profile has no confidence"


@pytest.mark.e2e
@pytest.mark.postgres
@pytest.mark.parametrize(
    "cluster_content,expected_keywords",
    [
        (
            "Machine learning and deep neural networks for image classification. "
            "Convolutional networks and transfer learning techniques.",
            ["machine learning", "neural", "learning"],
        ),
        (
            "Project management using agile methodologies. "
            "Sprint planning, daily standups, and retrospectives.",
            ["project", "agile", "management"],
        ),
        (
            "Financial budgeting and expense tracking for personal finance. "
            "Investment strategies and portfolio diversification.",
            ["financial", "budget", "finance"],
        ),
    ],
)
def test_real_llm_identifies_themes(
    postgres_connection, test_config, cluster_content, expected_keywords
):
    """
    REAL E2E TEST: Validate LLM correctly identifies cluster themes.

    Tests that the real Ollama LLM:
    - Extracts relevant themes from content
    - Generates appropriate summaries
    - Identifies key entities and topics
    """
    ollama_client = ollama.Client(host=test_config["ollama_url"])

    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()

    synthesizer = ClusterMetadataSynthesizer(ollama_client)

    cluster = ClusterData(
        cluster_id="test-cluster",
        representative_notes=[cluster_content],
        representative_note_ids=["note-1"],
        tags=["test"],
    )

    result = synthesizer.synthesize(cluster)

    assert result.status == "success", f"Synthesis failed: {result.error}"

    # Check that theme summary contains at least one expected keyword
    theme_lower = result.profile.theme_summary.lower()
    found_keywords = [kw for kw in expected_keywords if kw in theme_lower]

    assert found_keywords, (
        f"Theme '{result.profile.theme_summary}' doesn't contain " f"any of {expected_keywords}"
    )

    # Check that profile has meaningful data
    assert (
        result.profile.key_entities or result.profile.dominant_topics
    ), "Profile has no entities or topics"

    # Save and verify
    repo.save(result.profile)
    fetched = repo.get("test-cluster")
    assert fetched.theme_summary == result.profile.theme_summary


@pytest.mark.e2e
@pytest.mark.postgres
def test_story_002_performance_target(postgres_connection, test_config):
    """
    REAL E2E TEST: Verify Story 002 acceptance criteria.

    Acceptance: Process 50 clusters in <= 5 minutes on RPi 5

    Note: This test uses 10 clusters for faster CI runtime.
    Scale to 50 for full acceptance validation.
    """
    ollama_client = ollama.Client(host=test_config["ollama_url"])

    repo = ClusterProfileRepository(postgres_connection)
    repo.ensure_table()

    # Create 10 realistic clusters (scale to 50 for full test)
    num_clusters = 10
    clusters = [
        ClusterData(
            cluster_id=f"perf-cluster-{i}",
            representative_notes=[
                f"Research note {i} about topic {i % 3}. " f"Contains analysis and findings."
            ],
            representative_note_ids=[f"note-{i}"],
            tags=["performance-test"],
        )
        for i in range(num_clusters)
    ]

    synthesizer = ClusterMetadataSynthesizer(ollama_client)

    start = time.monotonic()
    results = [synthesizer.synthesize(cluster) for cluster in clusters]
    elapsed = time.monotonic() - start

    success_count = sum(1 for r in results if r.status == "success")
    success_rate = success_count / len(results)

    # Acceptance: >= 95% success rate
    assert success_rate >= 0.95, f"Success rate {success_rate:.1%} below 95% threshold"

    # Performance target (scaled for 10 clusters)
    # 50 clusters in 5 min = 10 clusters in 1 min
    expected_time = 60  # 1 minute for 10 clusters
    assert (
        elapsed < expected_time
    ), f"Performance test failed: {elapsed:.1f}s > {expected_time}s for {num_clusters} clusters"

    # Save all successful profiles
    for result in results:
        if result.status == "success":
            repo.save(result.profile)
