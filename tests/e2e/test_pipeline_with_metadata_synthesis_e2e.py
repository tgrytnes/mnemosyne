"""
Advanced End-to-End Pipeline Tests with Metadata Synthesis

These tests validate the COMPLETE pipeline including Story 002:
    Vault → Clean → Chunk → Embed → Store → Cluster → Representatives → Metadata Synthesis

PREREQUISITE: Story 002 must be merged for these tests to run.
"""

import tempfile
import time
from pathlib import Path

import ollama
import pytest

# These imports will only work after Story 002 is merged
try:
    from mnemosyne.alexandria.cluster_profile_repository import ClusterProfileRepository
    from mnemosyne.argus.cluster_metadata_synthesis import (
        ClusterData,
        ClusterMetadataSynthesizer,
    )

    STORY_002_AVAILABLE = True
except ImportError:
    STORY_002_AVAILABLE = False

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.argus.nodes.cluster_representatives import GetClusterRepresentatives
from mnemosyne.cli.cluster import ClusterManager


@pytest.mark.e2e
@pytest.mark.weaviate
@pytest.mark.postgres
@pytest.mark.skipif(not STORY_002_AVAILABLE, reason="Story 002 not yet merged")
class TestCompletePipelineWithMetadataSynthesis:
    """
    ADVANCED E2E TESTS: Full pipeline including metadata synthesis.

    These tests validate the ENTIRE system:
    - Story 000: Vault Ingestion
    - Story 020: Structure Preservation
    - Story 021: Semantic Chunking
    - Story 001: Cluster Representatives
    - Story 002: Metadata Synthesis (LLM-generated cluster profiles)
    """

    def test_pipeline_full_vault_to_cluster_profiles(
        self, weaviate_client, clean_weaviate_collection, postgres_connection, test_config
    ):
        """
        COMPLETE PIPELINE: Vault → Ingestion → Clustering → Representatives → Metadata Synthesis.

        This is the ULTIMATE E2E test - validates the entire system works together.

        Flow:
        1. Create realistic multi-topic vault
        2. Ingest with hybrid chunking
        3. Cluster into semantic groups
        4. Get representatives for each cluster
        5. Synthesize cluster profiles with LLM
        6. Store profiles in PostgreSQL
        7. Validate profile quality and accuracy
        """
        ollama_client = ollama.Client(
            host=test_config["ollama_url"],
            timeout=test_config["ollama_timeout"],
        )

        # Setup profile repository
        repo = ClusterProfileRepository(postgres_connection)
        repo.ensure_table()

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "realistic_vault"
            vault_path.mkdir()

            # Create realistic vault with distinct knowledge domains
            vault_notes = {
                "ml_fundamentals.md": """# Machine Learning Fundamentals

## Neural Networks
Neural networks are computational models inspired by biological neurons.
They consist of layers of interconnected nodes that process information.

### Backpropagation
Training uses backpropagation to compute gradients.
Weights are updated through gradient descent optimization.

### Activation Functions
ReLU, sigmoid, and tanh are common activation functions.
They introduce non-linearity into the network.

## Deep Learning
Deep learning uses multi-layer neural networks.
CNNs excel at computer vision tasks.
RNNs and transformers handle sequential data.
""",
                "ml_applications.md": """# Machine Learning Applications

## Computer Vision
Image classification identifies objects in photos.
Object detection locates items with bounding boxes.

## Natural Language Processing
Transformers revolutionized language understanding.
BERT and GPT enable semantic comprehension.

## Recommender Systems
Collaborative filtering suggests items based on user behavior.
Content-based filtering uses item features.
""",
                "project_management_agile.md": """# Agile Project Management

## Scrum Framework
Scrum organizes work into time-boxed sprints.
Daily standups keep team synchronized.

### Sprint Planning
Team commits to deliverables for the sprint.
Estimation uses story points or ideal days.

### Retrospectives
Reflect on process improvements.
Identify what worked and what needs change.

## Kanban Method
Visualize workflow with board columns.
Limit work in progress to prevent bottlenecks.
Continuous delivery without fixed iterations.
""",
                "project_management_tools.md": """# Project Management Tools

## Issue Tracking
Jira for enterprise teams.
Linear for modern software development.
GitHub Issues for open source.

## Documentation
Confluence for knowledge bases.
Notion for flexible workspaces.
Obsidian for linked thinking.

## Communication
Slack for team chat.
Discord for community building.
Teams for corporate environments.
""",
                "cooking_italian.md": """# Italian Cuisine

## Pasta Dishes
Carbonara uses eggs, guanciale, and pecorino.
Amatriciana features tomato and guanciale.
Cacio e pepe is simple: pasta, cheese, pepper.

## Pizza
Neapolitan pizza has strict DOC requirements.
Thin crust, high heat, minimal toppings.
Margherita showcases simplicity.

## Risotto
Arborio rice creates creamy texture.
Constant stirring releases starch.
Add stock gradually for best results.
""",
                "cooking_baking.md": """# Baking Fundamentals

## Bread Making
Yeast requires warm water for activation.
Kneading develops gluten structure.
Proofing allows dough to rise.

### Sourdough
Wild yeast and bacteria ferment dough.
Starter culture must be fed regularly.
Long fermentation develops complex flavor.

## Pastry
Butter creates flaky layers in croissants.
Cold ingredients prevent gluten development.
Lamination requires precision and patience.
""",
            }

            for filename, content in vault_notes.items():
                (vault_path / filename).write_text(content)

            # STAGE 1: Ingest vault with hybrid chunking
            import os

            os.environ["CHUNKING_STRATEGY"] = "hybrid"

            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                ollama_client=ollama_client,
                state_tracker=state_tracker,
            )

            print("\n=== STAGE 1: Ingesting vault ===")
            start_time = time.monotonic()
            stats = ingestor.ingest_vault()
            ingestion_time = time.monotonic() - start_time

            print(f"Files processed: {stats['files_processed']}")
            print(f"Total chunks: {stats['total_chunks']}")
            print(f"Ingestion time: {ingestion_time:.2f}s")

            assert stats["files_processed"] == 6, "All files should be ingested"
            assert stats["total_chunks"] > 20, "Should create substantial chunks"

            # STAGE 2: Run clustering (3 semantic groups: ML, PM, Cooking)
            print("\n=== STAGE 2: Clustering chunks ===")
            cluster_manager = ClusterManager(weaviate_client)
            n_clusters = 3

            cluster_result = cluster_manager.run_kmeans_clustering(n_clusters=n_clusters)

            print(f"Chunks clustered: {cluster_result['chunks_clustered']}")
            print(f"Clusters created: {cluster_result['n_clusters']}")
            print(f"Centroids stored: {cluster_result['centroids_stored']}")

            assert cluster_result["n_clusters"] == n_clusters
            assert cluster_result["chunks_clustered"] == stats["total_chunks"]

            # STAGE 3: Get representatives for each cluster
            print("\n=== STAGE 3: Getting cluster representatives ===")
            get_reps = GetClusterRepresentatives(weaviate_client)

            cluster_representatives = {}
            for cluster_id in range(n_clusters):
                state = {"cluster_id": cluster_id}
                result = get_reps(state)

                reps = result["representative_chunks"]
                cluster_representatives[cluster_id] = reps

                print(
                    f"Cluster {cluster_id}: {len(reps)} representatives "
                    f"(avg distance: {sum(r.distance_from_centroid for r in reps)/len(reps):.3f})"
                )

                assert len(reps) > 0, f"Cluster {cluster_id} should have representatives"

            # STAGE 4: Synthesize metadata profiles with REAL LLM
            print("\n=== STAGE 4: Synthesizing cluster profiles ===")
            synthesizer = ClusterMetadataSynthesizer(ollama_client)

            profiles = {}
            for cluster_id, representatives in cluster_representatives.items():
                # Create ClusterData from representatives
                cluster_data = ClusterData(
                    cluster_id=f"cluster-{cluster_id}",
                    representative_notes=[rep.text for rep in representatives],
                    representative_note_ids=[rep.chunk_id for rep in representatives],
                    tags=[],
                )

                # Synthesize profile with REAL LLM
                result = synthesizer.synthesize(cluster_data)

                assert (
                    result.status == "success"
                ), f"Cluster {cluster_id} synthesis failed: {result.error}"

                profile = result.profile
                profiles[cluster_id] = profile

                print(f"\nCluster {cluster_id} Profile:")
                print(f"  Theme: {profile.theme_summary[:80]}...")
                print(f"  Key Entities: {profile.key_entities[:5]}")
                print(f"  Topics: {profile.dominant_topics[:5]}")
                print(f"  Confidence: {profile.confidence_score:.2f}")

                # Validate profile quality
                assert profile.theme_summary, "Should have theme summary"
                assert len(profile.theme_summary) > 10, "Theme should be meaningful"
                assert 0 <= profile.confidence_score <= 1, "Confidence should be valid"

                # STAGE 5: Store in PostgreSQL
                repo.save(profile)

            # STAGE 6: Validate semantic coherence of profiles
            print("\n=== STAGE 6: Validating semantic coherence ===")

            # Analyze profile themes to determine topics
            profile_topics = {}
            for cluster_id, profile in profiles.items():
                theme_lower = profile.theme_summary.lower()
                entities_lower = " ".join(profile.key_entities).lower()
                topics_lower = " ".join(profile.dominant_topics).lower()
                all_text = f"{theme_lower} {entities_lower} {topics_lower}"

                # Score by topic
                ml_keywords = [
                    "machine",
                    "learning",
                    "neural",
                    "network",
                    "model",
                    "deep",
                    "training",
                ]
                pm_keywords = [
                    "project",
                    "agile",
                    "scrum",
                    "kanban",
                    "sprint",
                    "management",
                    "team",
                ]
                cooking_keywords = [
                    "pasta",
                    "pizza",
                    "bread",
                    "cooking",
                    "recipe",
                    "baking",
                    "dough",
                ]

                scores = {
                    "ML": sum(1 for kw in ml_keywords if kw in all_text),
                    "PM": sum(1 for kw in pm_keywords if kw in all_text),
                    "Cooking": sum(1 for kw in cooking_keywords if kw in all_text),
                }

                topic = max(scores, key=scores.get) if max(scores.values()) > 0 else "Mixed"
                profile_topics[cluster_id] = {"topic": topic, "scores": scores}

                print(f"Cluster {cluster_id}: {topic} (scores: {scores})")

            # Should identify at least 2 distinct topics
            topics_found = {info["topic"] for info in profile_topics.values()}
            assert len(topics_found) >= 2, f"Should identify multiple topics: {profile_topics}"

            # STAGE 7: Verify persistence and retrieval
            print("\n=== STAGE 7: Verifying persistence ===")
            for cluster_id, original_profile in profiles.items():
                fetched = repo.get(f"cluster-{cluster_id}")

                assert fetched is not None, f"Should retrieve cluster-{cluster_id}"
                assert fetched.theme_summary == original_profile.theme_summary
                assert fetched.confidence_score == original_profile.confidence_score
                assert fetched.key_entities == original_profile.key_entities

            print("\n=== PIPELINE TEST COMPLETE ===")
            print("Successfully validated full pipeline:")
            print(f"  - {stats['files_processed']} files ingested")
            print(f"  - {stats['total_chunks']} chunks created")
            print(f"  - {n_clusters} clusters formed")
            print(f"  - {n_clusters} profiles synthesized")
            print(f"  - {len(topics_found)} distinct topics identified")

    def test_pipeline_metadata_synthesis_quality_validation(
        self, weaviate_client, clean_weaviate_collection, postgres_connection, test_config
    ):
        """
        QUALITY VALIDATION: Verify synthesized metadata is actually useful.

        Flow:
        1. Create vault with known ground truth topics
        2. Run full pipeline
        3. Validate synthesized themes match expected topics
        4. Check key entities are relevant
        5. Verify confidence scores correlate with cluster quality
        """
        ollama_client = ollama.Client(
            host=test_config["ollama_url"],
            timeout=test_config["ollama_timeout"],
        )

        repo = ClusterProfileRepository(postgres_connection)
        repo.ensure_table()

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "ground_truth_vault"
            vault_path.mkdir()

            # Create highly coherent, single-topic documents
            # This should result in high-quality clusters with clear themes

            # TOPIC 1: Python Programming (highly coherent)
            for i in range(3):
                (vault_path / f"python_{i}.md").write_text(
                    f"""# Python Programming {i}

## Functions and Classes
Python functions use def keyword.
Classes enable object-oriented programming.
Decorators modify function behavior.

## Data Structures
Lists are mutable sequences.
Dictionaries store key-value pairs.
Sets contain unique elements.

## Libraries
NumPy for numerical computing.
Pandas for data analysis.
Matplotlib for visualization.
"""
                )

            # TOPIC 2: Mediterranean Food (highly coherent)
            for i in range(3):
                (vault_path / f"mediterranean_{i}.md").write_text(
                    f"""# Mediterranean Cuisine {i}

## Greek Dishes
Greek salad with feta and olives.
Moussaka layers eggplant and meat.
Tzatziki sauce uses yogurt and cucumber.

## Spanish Tapas
Patatas bravas are fried potatoes.
Gambas al ajillo features garlic shrimp.
Pan con tomate is simple and delicious.

## Middle Eastern
Hummus and falafel are chickpea-based.
Tabbouleh salad uses parsley and bulgur.
Shawarma wraps spiced meat.
"""
                )

            # Ingest
            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                ollama_client=ollama_client,
                state_tracker=state_tracker,
            )

            ingestor.ingest_vault()

            # Cluster (2 clear groups)
            cluster_manager = ClusterManager(weaviate_client)
            cluster_manager.run_kmeans_clustering(n_clusters=2)

            # Get representatives and synthesize
            synthesizer = ClusterMetadataSynthesizer(ollama_client)
            get_reps = GetClusterRepresentatives(weaviate_client)

            for cluster_id in range(2):
                state = {"cluster_id": cluster_id}
                result = get_reps(state)
                reps = result["representative_chunks"]

                cluster_data = ClusterData(
                    cluster_id=f"quality-cluster-{cluster_id}",
                    representative_notes=[rep.text for rep in reps],
                    representative_note_ids=[rep.chunk_id for rep in reps],
                    tags=[],
                )

                synthesis_result = synthesizer.synthesize(cluster_data)
                assert synthesis_result.status == "success"

                profile = synthesis_result.profile

                # QUALITY VALIDATION
                theme = profile.theme_summary.lower()
                entities = " ".join(profile.key_entities).lower()

                # Should identify Python OR Food topic clearly
                is_python = any(
                    kw in theme or kw in entities
                    for kw in ["python", "function", "class", "library", "numpy", "pandas"]
                )
                is_food = any(
                    kw in theme or kw in entities
                    for kw in [
                        "food",
                        "cuisine",
                        "dish",
                        "greek",
                        "mediterranean",
                        "recipe",
                    ]
                )

                assert is_python or is_food, (
                    "Cluster "
                    f"{cluster_id} should identify clear topic.\n"
                    f"Theme: {profile.theme_summary}\n"
                    f"Entities: {profile.key_entities}"
                )

                # Coherent clusters should have higher confidence
                assert (
                    profile.confidence_score >= 0.5
                ), f"Coherent cluster should have decent confidence: {profile.confidence_score}"

                print(f"\nCluster {cluster_id} Quality Validation:")
                print(f"  Theme: {profile.theme_summary}")
                print(f"  Entities: {profile.key_entities}")
                print(f"  Confidence: {profile.confidence_score:.2f}")
                topic_label = "Python" if is_python else "Food" if is_food else "Unknown"
                print(f"  Topic detected: {topic_label}")

    def test_pipeline_handles_mixed_quality_clusters(
        self, weaviate_client, clean_weaviate_collection, postgres_connection, test_config
    ):
        """
        ROBUSTNESS TEST: Verify pipeline handles both good and bad clusters.

        Flow:
        1. Create vault with mixed content (some coherent, some scattered)
        2. Cluster (will create some tight, some loose clusters)
        3. Synthesize metadata for all clusters
        4. Validate system handles low-quality clusters gracefully
        """
        ollama_client = ollama.Client(
            host=test_config["ollama_url"],
            timeout=test_config["ollama_timeout"],
        )

        repo = ClusterProfileRepository(postgres_connection)
        repo.ensure_table()

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "mixed_quality_vault"
            vault_path.mkdir()

            # Coherent content (ML topic)
            (vault_path / "ml_coherent.md").write_text(
                """# Machine Learning
Neural networks and deep learning.
Supervised and unsupervised learning.
Model training and evaluation.
"""
            )

            # Scattered random notes (will form low-quality cluster)
            (vault_path / "random_1.md").write_text("# Todo\nBuy milk. Call dentist. Fix bug.")
            (vault_path / "random_2.md").write_text(
                "# Thoughts\nWeather nice today. Project deadline approaching."
            )
            (vault_path / "random_3.md").write_text(
                "# Notes\nMeeting at 3pm. Remember to email Sarah."
            )

            # Another coherent topic (cooking)
            (vault_path / "cooking_coherent.md").write_text(
                """# Recipes
Italian pasta and pizza.
French sauces and pastries.
Asian stir-fry techniques.
"""
            )

            # Ingest and cluster
            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                ollama_client=ollama_client,
                state_tracker=state_tracker,
            )

            ingestor.ingest_vault()

            cluster_manager = ClusterManager(weaviate_client)
            cluster_manager.run_kmeans_clustering(n_clusters=3)

            # Synthesize for all clusters
            synthesizer = ClusterMetadataSynthesizer(ollama_client)
            get_reps = GetClusterRepresentatives(weaviate_client)

            profiles = []
            for cluster_id in range(3):
                state = {"cluster_id": cluster_id}
                result = get_reps(state)
                reps = result["representative_chunks"]

                if len(reps) == 0:
                    continue

                cluster_data = ClusterData(
                    cluster_id=f"mixed-cluster-{cluster_id}",
                    representative_notes=[rep.text for rep in reps],
                    representative_note_ids=[rep.chunk_id for rep in reps],
                    tags=[],
                )

                synthesis_result = synthesizer.synthesize(cluster_data)

                # System should handle synthesis even for poor clusters
                # May succeed or fail, but shouldn't crash
                if synthesis_result.status == "success":
                    profile = synthesis_result.profile
                    profiles.append((cluster_id, profile, "success"))

                    print(f"\nCluster {cluster_id} (Success):")
                    print(f"  Theme: {profile.theme_summary[:60]}...")
                    print(f"  Confidence: {profile.confidence_score:.2f}")
                else:
                    profiles.append((cluster_id, None, "failed"))
                    print(f"\nCluster {cluster_id} (Failed): {synthesis_result.error}")

            # Should handle at least some clusters successfully
            successful = [p for p in profiles if p[2] == "success"]
            assert len(successful) > 0, "At least some clusters should synthesize successfully"

            print("\nMixed Quality Results:")
            print(f"  Total clusters: {len(profiles)}")
            print(f"  Successful: {len(successful)}")
            print(f"  Failed: {len([p for p in profiles if p[2] == 'failed'])}")


# Mark entire module as requiring Story 002
pytestmark = pytest.mark.skipif(
    not STORY_002_AVAILABLE,
    reason="Story 002 (Metadata Synthesis) must be merged to run these tests",
)
