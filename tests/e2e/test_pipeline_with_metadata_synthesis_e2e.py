"""
Advanced End-to-End Pipeline Tests with Metadata Synthesis

These tests validate the COMPLETE pipeline including Story 002:
    Vault → Clean → Chunk → Embed → Store → Cluster → Representatives → Metadata Synthesis

PREREQUISITE: Story 002 must be merged for these tests to run.
"""

import tempfile
import time
from pathlib import Path

import pytest

from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider

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
        self,
        weaviate_client,
        clean_weaviate_collection,
        postgres_connection,
        test_config,
        monkeypatch,
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
        config = ProviderConfig(
            llm_provider="ollama",
            ollama_llm_model="qwen3:0.6b",
            embedding_provider="ollama",
            ollama_embedding_model="nomic-embed-text:latest",
            ollama_base_url=test_config["ollama_url"],
        )
        llm_provider = create_llm_provider(config)
        embedding_provider = create_embedding_provider(config)

        # Setup profile repository
        repo = ClusterProfileRepository(postgres_connection)
        repo.ensure_table()

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "realistic_vault"
            vault_path.mkdir()

            # Create realistic vault with distinct knowledge domains (expanded to >20 chunks)
            vault_notes = {
                "ml_fundamentals.md": """# Machine Learning Fundamentals

## Neural Network Architecture
Neural networks are computational models inspired by biological neurons in the brain.
They consist of interconnected layers of nodes that process and transform information.
Each connection has an associated weight that determines signal strength.
The network learns by adjusting these weights through training algorithms.

### Backpropagation Algorithm
Training neural networks uses backpropagation to compute error gradients efficiently.
Gradients flow backward through the network from output to input layers.
Weights are updated iteratively through gradient descent optimization methods.
The learning rate parameter controls how quickly the network adapts to new patterns.
Momentum techniques accelerate convergence and escape local minima.

### Activation Functions
Activation functions introduce non-linearity into neural network computations.
ReLU (Rectified Linear Unit) is computationally efficient and reduces vanishing gradients.
Sigmoid and tanh functions squash outputs to bounded ranges for classification.
Modern architectures often use variants like Leaky ReLU or ELU for improved performance.
Choosing appropriate activation functions significantly impacts model training dynamics.

## Deep Learning Architectures
Deep learning leverages multi-layer neural networks for hierarchical feature extraction.
Convolutional Neural Networks (CNNs) excel at computer vision and image processing tasks.
Recurrent Neural Networks (RNNs) handle sequential data like time series or text.
Transformers revolutionized NLP with attention mechanisms that capture long-range dependencies.
Modern architectures combine multiple techniques for state-of-the-art performance.
""",
                "ml_applications.md": """# Machine Learning Applications

## Computer Vision
Image classification assigns categorical labels to visual input automatically.
Object detection identifies and localizes multiple items within images using bounding boxes.
Semantic segmentation classifies each pixel for detailed scene understanding.
Transfer learning leverages pre-trained models like ResNet or VGG for new vision tasks.
Data augmentation techniques improve model robustness to variations in lighting and perspective.

## Natural Language Processing
Transformer architectures revolutionized language understanding with self-attention mechanisms.
BERT (Bidirectional Encoder Representations from Transformers) enables contextual word embeddings.
GPT models demonstrate impressive text generation capabilities through large-scale pre-training.
Named entity recognition extracts structured information from unstructured text documents.
Machine translation systems achieve near-human performance for many language pairs.

## Recommender Systems
Collaborative filtering suggests items based on patterns in user behavior and preferences.
Content-based filtering uses item features and attributes for personalized recommendations.
Hybrid approaches combine multiple techniques for improved accuracy and coverage.
Matrix factorization techniques decompose user-item interaction matrices efficiently.
Deep learning models capture complex non-linear patterns in recommendation scenarios.
""",
                "project_management_agile.md": """# Agile Project Management

## Scrum Framework Fundamentals
Scrum organizes software development work into time-boxed sprints typically lasting 2-4 weeks.
Cross-functional teams collaborate closely to deliver potentially shippable product increments.
Daily standup meetings keep team members synchronized and identify impediments quickly.
The product owner prioritizes backlog items based on business value and stakeholder needs.
Sprint reviews demonstrate completed work and gather feedback from stakeholders.

### Sprint Planning Process
Sprint planning sessions define goals and select work items from the prioritized product backlog.
Team members estimate effort using story points based on relative complexity and uncertainty.
Capacity planning ensures the team commits to achievable goals for the upcoming sprint.
Tasks are broken down into smaller units to enable better tracking and coordination.
Definition of Done criteria ensure consistent quality standards across all deliverables.

### Retrospective Meetings
Retrospectives provide dedicated time for teams to reflect on process improvements.
Team members identify what worked well and should be continued in future sprints.
Action items address specific pain points and impediments to team effectiveness.
Psychological safety enables honest and constructive feedback for continuous improvement.
Regular retrospectives foster a culture of learning and adaptation within the team.

## Kanban Methodology
Kanban visualizes workflow stages using board columns to track work items in progress.
Work-in-progress (WIP) limits prevent context switching and reduce multitasking overhead.
Continuous delivery enables teams to ship features without fixed iteration boundaries.
Explicit policies define when work items can move between different workflow stages.
Cumulative flow diagrams help identify bottlenecks and optimize throughput over time.
""",
                "project_management_tools.md": """# Project Management Tools and Platforms

## Issue Tracking Systems
Jira provides comprehensive issue tracking features for enterprise software development teams.
Linear offers a modern, streamlined interface optimized for fast-moving product teams.
GitHub Issues integrates seamlessly with code repositories for open source project coordination.
Customizable workflows adapt to diverse team processes and organizational requirements.
Advanced filtering and search capabilities enable efficient backlog management at scale.

## Documentation Platforms
Confluence serves as a centralized knowledge base for technical and business documentation.
Notion provides flexible workspaces combining databases, wikis, and project management features.
Obsidian enables linked thinking through bidirectional connections between markdown notes.
Version control integration ensures documentation stays synchronized with code changes.
Collaborative editing features enable real-time teamwork on shared documents.

## Communication and Collaboration
Slack facilitates asynchronous team communication through organized channels and threads.
Discord supports community building with voice channels and customizable role permissions.
Microsoft Teams integrates deeply with Office 365 for corporate enterprise environments.
Screen sharing and video conferencing enable remote pair programming and code reviews.
Integration ecosystems connect communication tools with development workflows seamlessly.
""",
                "cooking_italian.md": """# Italian Cuisine Traditions

## Classic Pasta Dishes
Traditional carbonara combines eggs, guanciale (cured pork jowl), and pecorino romano cheese.
Amatriciana sauce features tomatoes, guanciale, and pecorino for a rich savory flavor profile.
Cacio e pepe demonstrates Italian minimalism: pasta, pecorino cheese, and black pepper only.
Pasta alle vongole pairs spaghetti with fresh clams, garlic, white wine, and parsley.
Regional variations showcase local ingredients and centuries of culinary tradition.

## Pizza Making Techniques
Neapolitan pizza follows strict DOC (Denominazione di Origine Controllata) requirements.
High-temperature wood-fired ovens reach 900°F for rapid cooking that creates signature char.
Thin crust with puffy cornicione (rim) results from proper dough fermentation and stretching.
Margherita pizza showcases simplicity with tomato sauce, mozzarella, and fresh basil leaves.
San Marzano tomatoes from volcanic soil near Mount Vesuvius provide ideal flavor and acidity.

## Risotto Preparation
Arborio rice with high starch content creates the creamy texture of authentic risotto.
Constant stirring during cooking releases starch gradually for optimal consistency.
Hot stock added gradually in small increments allows controlled absorption and even cooking.
Mantecatura (vigorous stirring with butter and cheese) creates luxurious final texture.
Proper timing achieves al dente rice with flowing but not soupy overall consistency.
""",
                "cooking_baking.md": """# Artisan Baking Fundamentals

## Bread Making Techniques
Bread dough requires proper gluten development through kneading or extended fermentation time.
Yeast activation needs warm water (105-115°F) and sugar for optimal metabolic activity.
Bulk fermentation allows flavor compounds to develop and dough structure to strengthen.
Proofing (final rise) gives shaped loaves volume before baking in a hot oven.
Steam during initial baking creates crispy crusts through gelatinization of surface starches.

### Sourdough Cultivation
Wild yeast and lactic acid bacteria naturally ferment sourdough starter cultures.
Regular feeding maintains starter vitality with consistent ratios of flour and water.
Long cold fermentation (12-48 hours) develops complex flavor profiles and digestibility.
Proper hydration levels (65-85%) significantly impact final crumb structure and texture.
Scoring patterns control expansion direction and create distinctive visual appearances.

## Pastry and Lamination
Butter creates flaky layers in croissants and puff pastry through lamination technique.
Cold ingredients prevent premature gluten development that would toughen delicate pastries.
Multiple folding iterations create hundreds of thin alternating layers of dough and butter.
Precision temperature control maintains butter plasticity without melting or breaking.
Proper resting periods between folds allow gluten to relax for easier rolling and shaping.
""",
            }

            for filename, content in vault_notes.items():
                (vault_path / filename).write_text(content)

            # STAGE 1: Ingest vault with hybrid chunking
            monkeypatch.setenv("CHUNKING_STRATEGY", "hybrid")

            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,
                embedding_provider=embedding_provider,
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

            # Ensure ClusterCentroid collection exists
            from mnemosyne.alexandria.weaviate_schema import (
                ClusterCentroidCollection,
                WeaviateSchemaManager,
            )

            schema_manager = WeaviateSchemaManager(weaviate_client)
            schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

            cluster_manager = ClusterManager(weaviate_client)
            n_clusters = 3

            # 4-step clustering process
            vectors, uuids = cluster_manager.fetch_all_vectors()
            labels, centroids = cluster_manager.run_kmeans_clustering(vectors, n_clusters)
            cluster_manager.update_chunk_cluster_ids(uuids, labels)
            cluster_manager.update_centroids(centroids, labels)

            print(f"Chunks clustered: {len(uuids)}")
            print(f"Clusters created: {n_clusters}")
            print(f"Centroids stored: {len(centroids)}")

            assert len(centroids) == n_clusters
            assert len(uuids) == stats["total_chunks"]

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
            synthesizer = ClusterMetadataSynthesizer(llm_provider)

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
        config = ProviderConfig(
            llm_provider="ollama",
            ollama_llm_model="qwen3:0.6b",
            embedding_provider="ollama",
            ollama_embedding_model="nomic-embed-text:latest",
            ollama_base_url=test_config["ollama_url"],
        )
        llm_provider = create_llm_provider(config)
        embedding_provider = create_embedding_provider(config)

        repo = ClusterProfileRepository(postgres_connection)
        repo.ensure_table()

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "ground_truth_vault"
            vault_path.mkdir()

            # Create highly coherent, single-topic documents
            # This should result in high-quality clusters with clear themes

            # TOPIC 1: Python Programming (highly coherent)
            for i in range(3):
                (vault_path / f"python_{i}.md").write_text(f"""# Python Programming {i}

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
""")

            # TOPIC 2: Mediterranean Food (highly coherent)
            for i in range(3):
                (vault_path / f"mediterranean_{i}.md").write_text(f"""# Mediterranean Cuisine {i}

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
""")

            # Ingest
            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,
                embedding_provider=embedding_provider,
                state_tracker=state_tracker,
            )

            ingestor.ingest_vault()

            # Cluster (2 clear groups)
            # Ensure ClusterCentroid collection exists
            from mnemosyne.alexandria.weaviate_schema import (
                ClusterCentroidCollection,
                WeaviateSchemaManager,
            )

            schema_manager = WeaviateSchemaManager(weaviate_client)
            schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

            cluster_manager = ClusterManager(weaviate_client)
            vectors, uuids = cluster_manager.fetch_all_vectors()
            labels, centroids = cluster_manager.run_kmeans_clustering(vectors, n_clusters=2)
            cluster_manager.update_chunk_cluster_ids(uuids, labels)
            cluster_manager.update_centroids(centroids, labels)

            # Get representatives and synthesize
            synthesizer = ClusterMetadataSynthesizer(llm_provider)
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
                    f"Cluster {cluster_id} should identify clear topic.\n"
                    f"Theme: {profile.theme_summary}\nEntities: {profile.key_entities}"
                )

                # Coherent clusters should have higher confidence
                assert (
                    profile.confidence_score >= 0.5
                ), f"Coherent cluster should have decent confidence: {profile.confidence_score}"

                print(f"\nCluster {cluster_id} Quality Validation:")
                print(f"  Theme: {profile.theme_summary}")
                print(f"  Entities: {profile.key_entities}")
                print(f"  Confidence: {profile.confidence_score:.2f}")
                topic = "Python" if is_python else "Food" if is_food else "Unknown"
                print(f"  Topic detected: {topic}")

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
        config = ProviderConfig(
            llm_provider="ollama",
            ollama_llm_model="qwen3:0.6b",
            embedding_provider="ollama",
            ollama_embedding_model="nomic-embed-text:latest",
            ollama_base_url=test_config["ollama_url"],
        )
        llm_provider = create_llm_provider(config)
        embedding_provider = create_embedding_provider(config)

        repo = ClusterProfileRepository(postgres_connection)
        repo.ensure_table()

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "mixed_quality_vault"
            vault_path.mkdir()

            # Coherent content (ML topic)
            (vault_path / "ml_coherent.md").write_text("""# Machine Learning
Neural networks and deep learning.
Supervised and unsupervised learning.
Model training and evaluation.
""")

            # Scattered random notes (will form low-quality cluster)
            (vault_path / "random_1.md").write_text("# Todo\nBuy milk. Call dentist. Fix bug.")
            (vault_path / "random_2.md").write_text(
                "# Thoughts\nWeather nice today. Project deadline approaching."
            )
            (vault_path / "random_3.md").write_text(
                "# Notes\nMeeting at 3pm. Remember to email Sarah."
            )

            # Another coherent topic (cooking)
            (vault_path / "cooking_coherent.md").write_text("""# Recipes
Italian pasta and pizza.
French sauces and pastries.
Asian stir-fry techniques.
""")

            # Ingest and cluster
            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,
                embedding_provider=embedding_provider,
                state_tracker=state_tracker,
            )

            ingestor.ingest_vault()

            # Ensure ClusterCentroid collection exists
            from mnemosyne.alexandria.weaviate_schema import (
                ClusterCentroidCollection,
                WeaviateSchemaManager,
            )

            schema_manager = WeaviateSchemaManager(weaviate_client)
            schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

            cluster_manager = ClusterManager(weaviate_client)
            vectors, uuids = cluster_manager.fetch_all_vectors()
            labels, centroids = cluster_manager.run_kmeans_clustering(vectors, n_clusters=3)
            cluster_manager.update_chunk_cluster_ids(uuids, labels)
            cluster_manager.update_centroids(centroids, labels)

            # Synthesize for all clusters
            synthesizer = ClusterMetadataSynthesizer(llm_provider)
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
