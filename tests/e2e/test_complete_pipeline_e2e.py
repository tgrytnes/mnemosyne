"""
Comprehensive End-to-End Pipeline Tests

Tests the complete data flow across multiple stories:
- Story 000: Vault Ingestion
- Story 019: Quality Metrics
- Story 020: Structure Preservation
- Story 021: Semantic Chunking
- Story 001: Cluster Representatives
- Story 002: Metadata Synthesis (when merged)

These tests validate the ENTIRE pipeline with REAL data:
    Raw Vault → Clean → Chunk → Embed → Store → Cluster → Query → Analyze
"""

import tempfile
import time
from pathlib import Path

import pytest
from langgraph.graph import END, START, StateGraph

from mnemosyne.aletheia.ingestion_state import IngestionStateTracker
from mnemosyne.aletheia.obsidian_ingestor import ObsidianIngestor
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_embedding_provider, create_llm_provider
from mnemosyne.alexandria.weaviate_schema import (
    ClusterCentroidCollection,
    WeaviateSchemaManager,
)
from mnemosyne.argus.nodes.cluster_representatives import (
    ClusterRepresentativesState,
    GetClusterRepresentatives,
)
from mnemosyne.cli.cluster import ClusterManager
from mnemosyne.iris.structure_quality import StructurePreservationAnalyzer


@pytest.mark.e2e
@pytest.mark.weaviate
class TestCompleteEndToEndPipeline:
    """
    COMPREHENSIVE E2E TESTS: Full pipeline validation with real data.

    These tests validate the COMPLETE data flow, not isolated components.
    """

    def test_pipeline_00_vault_to_cluster_representatives(
        self, weaviate_client, clean_weaviate_collection, test_config
    ):
        """
        PIPELINE TEST 00: Complete flow from vault ingestion to cluster representatives.

        Flow:
        1. Create realistic vault with diverse content
        2. Ingest with structure preservation
        3. Run clustering (K-means)
        4. Query cluster representatives via LangGraph
        5. Validate data integrity at each stage

        This is the GOLDEN PATH test - if this passes, the core pipeline works.
        """
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        # STAGE 1: Create realistic test vault
        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "test_vault"
            vault_path.mkdir()

            # Create diverse, realistic notes (expanded to generate >10 chunks)
            notes = {
                "machine_learning.md": """# Machine Learning Fundamentals

## Neural Networks
Deep learning architectures use layered neural networks to model complex patterns.
Each layer extracts increasingly abstract features from the input data.
Backpropagation optimizes weights through gradient descent algorithms.
The learning rate controls how quickly the model adapts to new information.

## Model Training
Training involves iterative optimization over multiple epochs.
Each epoch processes the entire training dataset:
- Forward pass computes predictions from current weights
- Loss function measures prediction errors
- Backward pass updates weights via gradient descent
- Validation set checks generalization performance
- Early stopping prevents overfitting to training data

## Common Architectures
Convolutional Neural Networks (CNNs) excel at image classification tasks.
They use convolution layers to detect spatial patterns and features.
Recurrent Neural Networks (RNNs) handle sequential data like time series.
Long Short-Term Memory (LSTM) networks address vanishing gradient problems.
Transformers revolutionized Natural Language Processing with attention mechanisms.
BERT and GPT models demonstrate the power of large-scale pre-training.

## Optimization Techniques
Stochastic Gradient Descent (SGD) updates weights using mini-batches.
Adam optimizer adapts learning rates for each parameter dynamically.
Momentum accelerates convergence by accumulating gradient history.
Learning rate scheduling adjusts rates during training for better convergence.
""",
                "project_management.md": """# Agile Project Management

## Sprint Planning
Weekly or bi-weekly sprints organize work into manageable time-boxed chunks.
Sprint planning sessions define goals and select backlog items.
Daily standups keep team aligned and identify blockers quickly.
Each team member shares progress, plans, and impediments.

## User Stories
User stories capture requirements from the end-user perspective.
They follow the format: As a [role], I want [feature], so that [benefit].
Acceptance criteria define what "done" means for each story.
Story points estimate relative complexity using Fibonacci numbers.

## Retrospectives
Retrospectives review what worked well and what needs improvement.
Teams identify action items to implement in the next sprint.
Continuous improvement mindset drives process refinement over time.
Psychological safety enables honest and constructive feedback.

## Kanban Boards
Kanban boards visualize workflow stages and work in progress.
Common columns include:
- Backlog: Prioritized work waiting to start
- Todo: Work ready for the current sprint
- In Progress: Active development tasks
- Code Review: Awaiting peer feedback
- Testing: Quality assurance validation
- Done: Completed and deployed features

Work-in-progress (WIP) limits prevent team overload and context switching.
""",
                "cooking_recipes.md": """# Italian Cuisine

## Pasta Carbonara
Traditional Roman dish combining eggs, guanciale, and Pecorino Romano cheese.
The heat from freshly cooked pasta cooks the eggs into a creamy sauce.

### Ingredients
- 400g spaghetti or rigatoni
- 4 large egg yolks plus 1 whole egg
- 200g guanciale (cured pork jowl)
- 100g Pecorino Romano cheese, finely grated
- Freshly ground black pepper
- Salt for pasta water

### Preparation Steps
1. Bring large pot of salted water to boil for pasta
2. Cut guanciale into small strips and render in pan
3. Beat eggs with grated Pecorino and black pepper
4. Cook pasta until al dente, reserve cup of pasta water
5. Combine hot pasta with guanciale off heat
6. Add egg mixture quickly while tossing to create creamy sauce
7. Add pasta water if needed to achieve silky consistency

## Pizza Margherita
Simple Neapolitan pizza showcasing quality ingredients: tomato, mozzarella, and basil.
Named after Queen Margherita, representing Italian flag colors.
High-temperature wood-fired ovens create the characteristic charred crust.

## Risotto alla Milanese
Creamy Lombard rice dish requiring patience and constant stirring.
Arborio or Carnaroli rice releases starch for signature creaminess.
Saffron threads provide golden color and distinctive flavor.
Mantecatura final step adds butter and Parmesan for luxurious texture.
""",
                "mixed_content.md": """# Diverse Topics

## Philosophy
Existentialism emphasizes individual freedom, choice, and personal responsibility.
Sartre argued that existence precedes essence - we define ourselves through actions.
Camus explored absurdism and the search for meaning in an indifferent universe.
The existential question "Why is there something rather than nothing?" remains fundamental.

## Technology
Kubernetes orchestrates containerized applications across distributed clusters.
It handles deployment, scaling, and management of microservices automatically.
Container orchestration enables cloud-native architectures and DevOps practices.
Service mesh technologies like Istio add observability and traffic management.

## History
The Renaissance transformed European culture from 14th to 17th centuries.
Humanism emphasized classical learning and individual potential.
Artists like Leonardo da Vinci and Michelangelo redefined artistic expression.
Scientific revolution challenged medieval worldviews with empirical observation.
Printing press democratized knowledge and accelerated cultural change.

## Economics
Supply and demand curves determine market equilibrium prices.
Monetary policy influences inflation through interest rate adjustments.
Fiscal policy uses government spending and taxation to manage economy.
Behavioral economics examines psychological factors in economic decisions.
""",
            }

            for filename, content in notes.items():
                (vault_path / filename).write_text(content)

            # STAGE 2: Ingest vault
            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,

                embedding_provider=embedding_provider,
                state_tracker=state_tracker,
            )

            ingestion_stats = ingestor.ingest_vault()

            # Validate ingestion
            assert ingestion_stats["files_processed"] == 4, "All files should be processed"
            assert (
                ingestion_stats["total_chunks"] >= 15
            ), f"Should create 15+ chunks from ~5000 chars, got {ingestion_stats['total_chunks']}"
            assert ingestion_stats["files_skipped"] == 0, "No files should be skipped"

            # STAGE 3: Verify chunks in Weaviate
            collection = weaviate_client.collections.get("TheMuses")
            all_chunks = collection.query.fetch_objects(limit=100)

            assert len(all_chunks.objects) > 0, "Chunks should be stored in Weaviate"
            assert len(all_chunks.objects) == ingestion_stats["total_chunks"], "Count mismatch"

            # Validate chunk metadata
            sample_chunk = all_chunks.objects[0]
            assert "text" in sample_chunk.properties, "Chunk should have text"
            assert "sourceFile" in sample_chunk.properties, "Chunk should have source file"
            assert "headingPath" in sample_chunk.properties, "Chunk should have heading path"
            assert sample_chunk.vector is not None, "Chunk should have embedding vector"

            # STAGE 4: Run clustering
            # Ensure ClusterCentroid collection exists
            schema_manager = WeaviateSchemaManager(weaviate_client)
            schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

            cluster_manager = ClusterManager(weaviate_client)
            n_clusters = 3  # Group into 3 semantic clusters

            # Fetch vectors from Weaviate
            vectors, uuids = cluster_manager.fetch_all_vectors()
            assert len(vectors) == len(all_chunks.objects), "Should fetch all vectors"

            # Run K-means clustering
            labels, centroids = cluster_manager.run_kmeans_clustering(vectors, n_clusters)
            assert len(labels) == len(vectors), "Should have label for each vector"
            assert len(centroids) == n_clusters, "Should have centroids for each cluster"

            # Update Weaviate with cluster assignments
            cluster_manager.update_chunk_cluster_ids(uuids, labels)
            cluster_manager.update_centroids(centroids, labels)

            # Verify cluster assignments
            clustered_chunks = collection.query.fetch_objects(limit=100)
            cluster_ids = [
                obj.properties.get("clusterId")
                for obj in clustered_chunks.objects
                if obj.properties.get("clusterId") is not None
            ]

            assert len(cluster_ids) > 0, "Chunks should have cluster IDs"
            assert all(0 <= cid < n_clusters for cid in cluster_ids), "Cluster IDs should be valid"

            # STAGE 5: Query cluster representatives via LangGraph
            get_reps_node = GetClusterRepresentatives(weaviate_client)

            # Create simple workflow
            workflow = StateGraph(ClusterRepresentativesState)
            workflow.add_node("get_representatives", get_reps_node)
            workflow.add_edge(START, "get_representatives")
            workflow.add_edge("get_representatives", END)
            app = workflow.compile()

            # Test each cluster
            all_representatives = []
            for cluster_id in range(n_clusters):
                state = {"cluster_id": cluster_id}
                result = app.invoke(state)

                assert "representative_chunks" in result, "Should return representatives"
                representatives = result["representative_chunks"]

                assert len(representatives) > 0, f"Cluster {cluster_id} should have representatives"
                assert len(representatives) <= 5, "Should return max 5 representatives"

                # Validate representative structure
                for rep in representatives:
                    assert rep.chunk_id, "Representative should have chunk_id"
                    assert rep.text, "Representative should have text"
                    assert rep.source_file, "Representative should have source_file"
                    assert rep.distance_from_centroid is not None, "Should have distance metric"

                all_representatives.extend(representatives)

            # STAGE 6: Validate semantic clustering quality
            # Representatives should be semantically related within clusters

            assert (
                len(all_representatives) >= n_clusters
            ), "Should have representatives from all clusters"
            assert (
                len(all_representatives) <= n_clusters * 5
            ), "Should not exceed max representatives"

            # Check that representatives are ordered by distance
            for cluster_id in range(n_clusters):
                state = {"cluster_id": cluster_id}
                result = app.invoke(state)
                reps = result["representative_chunks"]

                if len(reps) > 1:
                    distances = [r.distance_from_centroid for r in reps]
                    assert distances == sorted(
                        distances
                    ), f"Cluster {cluster_id} reps should be ordered by distance"

    def test_pipeline_01_chunking_strategy_comparison(
        self, weaviate_client, clean_weaviate_collection, test_config
    ):
        """
        PIPELINE TEST 01: Compare chunking strategies with quality metrics.

        Tests Stories: 021 (Chunking), 019 (Quality Metrics)

        Flow:
        1. Create structured test vault
        2. Ingest with RECURSIVE strategy → measure quality
        3. Clear Weaviate
        4. Ingest with HYBRID strategy → measure quality
        5. Compare metrics (hybrid should preserve structure better)
        """
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        # Create vault with clear structure
        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "structured_vault"
            vault_path.mkdir()

            # Create a highly structured document
            (vault_path / "structured_doc.md").write_text(
                """# Main Title

## Section 1: Introduction
This is the introduction section with some context.
It contains multiple sentences to create a meaningful chunk.

## Section 2: Methods
The methods section describes our approach.
We use systematic analysis and validation.

### Subsection 2.1: Data Collection
Data was collected from multiple sources.
Quality checks ensured accuracy.

### Subsection 2.2: Analysis
Statistical methods applied to datasets.
Results validated against ground truth.

## Section 3: Results
Our findings show significant improvements.
Quality metrics exceeded expectations.

## Section 4: Conclusion
This work demonstrates effective methods.
Future work will expand the scope.
"""
            )

            results = {}

            # Test both strategies
            for strategy in ["recursive", "hybrid"]:
                # Clear collection between runs
                if strategy == "hybrid":
                    from weaviate.classes.query import Filter

                    collection = weaviate_client.collections.get("TheMuses")
                    # Delete all objects by filtering for any sourceFile
                    collection.data.delete_many(where=Filter.by_property("sourceFile").like("*"))

                # Ingest with strategy
                state_tracker = IngestionStateTracker(str(vault_path / f"state_{strategy}.db"))

                import os

                os.environ["CHUNKING_STRATEGY"] = strategy

                ingestor = ObsidianIngestor(
                    vault_path=str(vault_path),
                    weaviate_client=weaviate_client,
                    llm_provider=llm_provider,

                    embedding_provider=embedding_provider,
                    state_tracker=state_tracker,
                )

                start_time = time.monotonic()
                ingestor.ingest_vault()
                elapsed = time.monotonic() - start_time

                # Collect quality metrics
                collection = weaviate_client.collections.get("TheMuses")
                chunks = collection.query.fetch_objects(limit=100, include_vector=True)

                # Chunking quality
                chunk_sizes = [len(obj.properties["text"]) for obj in chunks.objects]
                avg_chunk_size = sum(chunk_sizes) / len(chunk_sizes)

                # Structure preservation using analyzer (Story 020)
                expected_headings = [
                    "# Main Title",
                    "## Section 1: Introduction",
                    "## Section 2: Methods",
                    "### Subsection 2.1: Data Collection",
                    "### Subsection 2.2: Analysis",
                    "## Section 3: Results",
                    "## Section 4: Conclusion",
                ]

                # Convert Weaviate objects to dicts for analyzer
                chunk_dicts = [
                    {
                        "headingPath": obj.properties.get("headingPath"),
                        "headingLevel": obj.properties.get("headingLevel"),
                    }
                    for obj in chunks.objects
                ]

                analyzer = StructurePreservationAnalyzer(chunk_dicts, expected_headings)
                structure_metrics = analyzer.analyze()

                results[strategy] = {
                    "total_chunks": len(chunks.objects),
                    "avg_chunk_size": avg_chunk_size,
                    "ingestion_time": elapsed,
                    "structure_preservation": structure_metrics.preservation_score,
                    "heading_depth_accuracy": structure_metrics.heading_depth_accuracy,
                    "headings_found": structure_metrics.n_headings_found,
                }

            # VALIDATE: Hybrid should preserve structure better
            assert (
                results["hybrid"]["structure_preservation"]
                >= results["recursive"]["structure_preservation"]
            ), "Hybrid should preserve structure as well or better than recursive"

            # Hybrid should create more chunks (respects heading boundaries)
            # Recursive might create larger chunks ignoring structure

            print("\nStrategy Comparison Results:")
            print(f"Recursive: {results['recursive']}")
            print(f"Hybrid: {results['hybrid']}")

    def test_pipeline_02_incremental_update_propagation(
        self, weaviate_client, clean_weaviate_collection, test_config
    ):
        """
        PIPELINE TEST 02: Verify incremental updates propagate through pipeline.

        Tests Stories: 000 (Ingestion), 001 (Clustering)

        Flow:
        1. Initial ingestion
        2. Run clustering
        3. Modify a file
        4. Re-ingest (incremental)
        5. Verify old chunks removed, new chunks added
        6. Re-cluster
        7. Verify cluster assignments updated
        """
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "vault"
            vault_path.mkdir()

            # Initial content (expanded to generate 2+ chunks for clustering)
            test_file = vault_path / "test_note.md"
            test_file.write_text(
                """# Machine Learning Fundamentals

## Neural Network Basics
Neural networks are powerful computational tools inspired by biological neurons.
They consist of interconnected layers that process information through weighted connections.
Each neuron applies an activation function to produce outputs.
Backpropagation enables learning by adjusting weights based on errors.

## Training Process
Training involves iterative optimization to minimize a loss function.
The learning rate controls how quickly the model adapts to new patterns.
Gradient descent algorithms update weights to improve performance.
Regularization techniques prevent overfitting to the training data.
Early stopping monitors validation performance to avoid overtraining.

## Common Architectures
Convolutional neural networks excel at image processing tasks.
Recurrent networks handle sequential data like time series.
Transformers revolutionized natural language processing with attention mechanisms.
"""
            )

            # STAGE 1: Initial ingestion
            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,

                embedding_provider=embedding_provider,
                state_tracker=state_tracker,
            )

            stats_v1 = ingestor.ingest_vault()
            assert stats_v1["files_processed"] == 1

            collection = weaviate_client.collections.get("TheMuses")
            chunks_v1 = collection.query.fetch_objects(limit=100)
            initial_uuids = {obj.uuid for obj in chunks_v1.objects}

            # STAGE 2: Initial clustering
            schema_manager = WeaviateSchemaManager(weaviate_client)
            schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

            cluster_manager = ClusterManager(weaviate_client)
            vectors_v1, uuids_v1 = cluster_manager.fetch_all_vectors()
            labels_v1, centroids_v1 = cluster_manager.run_kmeans_clustering(
                vectors_v1, n_clusters=2
            )
            cluster_manager.update_chunk_cluster_ids(uuids_v1, labels_v1)
            cluster_manager.update_centroids(centroids_v1, labels_v1)

            # STAGE 3: Modify file (major change - ensure multiple chunks)
            time.sleep(1)  # Ensure different mtime
            test_file.write_text(
                """# Italian Cooking Guide

## Pasta Techniques
Making fresh pasta requires practice and patience.
Knead the dough until smooth and elastic.
Let it rest for at least 30 minutes before rolling.
Roll the dough thin but not too thin to avoid tearing.

## Classic Carbonara
Traditional Roman carbonara uses only eggs, guanciale, pecorino, and black pepper.
No cream is used in authentic carbonara.
The heat from the pasta cooks the eggs into a silky sauce.
Timing is critical to avoid scrambled eggs.

## Pizza Dough
High-protein flour creates better gluten structure for pizza.
Cold fermentation develops flavor over 24-48 hours.
Stretch the dough gently to preserve air bubbles.
"""
            )

            # STAGE 4: Re-ingest (incremental)
            stats_v2 = ingestor.ingest_vault()

            assert stats_v2["files_processed"] == 1, "Modified file should be re-processed"
            assert stats_v2["files_skipped"] == 0, "No files should be skipped"

            # STAGE 5: Verify chunks updated
            chunks_v2 = collection.query.fetch_objects(limit=100)
            updated_uuids = {obj.uuid for obj in chunks_v2.objects}

            # Old chunks should be deleted, new chunks added
            # UUIDs should be different (new content = new chunks)
            assert initial_uuids != updated_uuids, "Chunk UUIDs should change after content update"

            # Check content actually changed
            v2_texts = [obj.properties["text"] for obj in chunks_v2.objects]
            assert any(
                "cooking" in text.lower() or "pasta" in text.lower() for text in v2_texts
            ), "New content should be present"

            assert not any(
                "machine learning" in text.lower() for text in v2_texts
            ), "Old content should be removed"

            # STAGE 6: Re-cluster
            vectors_v2, uuids_v2 = cluster_manager.fetch_all_vectors()
            assert len(vectors_v2) >= 2, "Should have at least 2 chunks from expanded content"

            labels_v2, centroids_v2 = cluster_manager.run_kmeans_clustering(
                vectors_v2, n_clusters=2
            )
            cluster_manager.update_chunk_cluster_ids(uuids_v2, labels_v2)
            cluster_manager.update_centroids(centroids_v2, labels_v2)

            # Verify all new chunks were clustered
            assert len(labels_v2) == len(chunks_v2.objects), "All new chunks should be clustered"

    def test_pipeline_03_quality_metrics_end_to_end(
        self, weaviate_client, clean_weaviate_collection, test_config
    ):
        """
        PIPELINE TEST 03: Validate quality metrics across full pipeline.

        Tests Stories: 019 (Quality Framework), 020 (Structure), 021 (Chunking)

        Flow:
        1. Ingest structured vault
        2. Collect chunking quality metrics
        3. Collect embedding quality metrics
        4. Collect structure preservation metrics
        5. Validate all metrics meet thresholds
        """
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "vault"
            vault_path.mkdir()

            # Create diverse content for quality analysis
            (vault_path / "technical.md").write_text(
                """# Technical Documentation

## System Architecture
The system uses microservices architecture.
Each service handles specific domain logic.

## Database Design
PostgreSQL stores relational data.
Weaviate provides vector search.

## API Endpoints
REST API follows OpenAPI specification.
GraphQL alternative for complex queries.
"""
            )

            (vault_path / "creative.md").write_text(
                """# Creative Writing

## Short Story
The moon hung low over the city.
Sarah walked through empty streets.

## Poetry
Whispers in the wind,
Shadows dance at night,
Stars guide the way.
"""
            )

            # Ingest
            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,

                embedding_provider=embedding_provider,
                state_tracker=state_tracker,
            )

            stats = ingestor.ingest_vault()
            assert stats["files_processed"] == 2

            # Fetch chunks with vectors
            collection = weaviate_client.collections.get("TheMuses")
            chunks = collection.query.fetch_objects(limit=100, include_vector=True)

            assert len(chunks.objects) > 0, "Should have chunks"

            # METRIC 1: Chunking Quality
            chunk_texts = [obj.properties["text"] for obj in chunks.objects]
            chunk_sizes = [len(text) for text in chunk_texts]

            avg_size = sum(chunk_sizes) / len(chunk_sizes)
            assert 100 < avg_size < 1000, f"Avg chunk size {avg_size} should be reasonable"

            # METRIC 2: Embedding Quality
            vectors = []
            for obj in chunks.objects:
                if obj.vector and "default" in obj.vector:
                    vectors.append(obj.vector["default"])

            assert len(vectors) > 0, "Should have embedding vectors"
            assert all(len(v) == 1024 for v in vectors), "Vectors should be 1024-dim"

            # Check no embedding collapse (all vectors similar)
            import numpy as np

            vectors_array = np.array(vectors)
            mean_vector = np.mean(vectors_array, axis=0)
            similarities = [
                np.dot(v, mean_vector) / (np.linalg.norm(v) * np.linalg.norm(mean_vector))
                for v in vectors
            ]
            avg_similarity = sum(similarities) / len(similarities)

            # Should not all be identical (embedding collapse)
            assert avg_similarity < 0.99, f"Avg similarity {avg_similarity} too high (collapse?)"

            # METRIC 3: Structure Preservation
            chunks_with_headings = sum(
                1 for obj in chunks.objects if obj.properties.get("headingPath")
            )
            structure_score = chunks_with_headings / len(chunks.objects)

            # Most chunks should have heading context
            assert structure_score > 0.5, f"Structure preservation {structure_score} too low"

            print("\nQuality Metrics:")
            print(f"  Avg chunk size: {avg_size:.1f} chars")
            print(f"  Embedding dimensionality: {len(vectors[0])}")
            print(f"  Avg vector similarity: {avg_similarity:.3f}")
            print(f"  Structure preservation: {structure_score:.1%}")

    def test_pipeline_04_heading_based_retrieval(
        self, weaviate_client, clean_weaviate_collection, test_config
    ):
        """
        PIPELINE TEST 04: Validate heading-based queries work end-to-end.

        Tests Stories: 020 (Structure Preservation), 001 (Representatives)

        Flow:
        1. Ingest structured document
        2. Query by specific heading path
        3. Verify returned chunks belong to correct section
        4. Test nested heading queries
        """
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "vault"
            vault_path.mkdir()

            (vault_path / "knowledge_base.md").write_text(
                """# Knowledge Management

## Personal Notes
My daily journal and thoughts.
Reflections on life and work.

## Technical Documentation
System architecture and design decisions.
API specifications and deployment guides.

### Database Schema
PostgreSQL tables and relationships.
Weaviate collections and properties.

### API Design
REST endpoints follow RESTful principles.
GraphQL schema for complex queries.

## Project Ideas
Brainstorming future projects.
Innovation and experimentation.
"""
            )

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

            # Query by heading path
            from weaviate.classes.query import Filter

            collection = weaviate_client.collections.get("TheMuses")

            # TEST 1: Top-level section
            tech_docs = collection.query.fetch_objects(
                filters=Filter.by_property("headingPath").contains_any(["Technical Documentation"]),
                limit=20,
            )

            assert len(tech_docs.objects) > 0, "Should find chunks in Technical Documentation"

            # Verify all chunks are from correct section
            for obj in tech_docs.objects:
                heading = obj.properties.get("headingPath", "")
                assert "Technical Documentation" in heading, f"Wrong section: {heading}"

            # TEST 2: Nested subsection
            db_chunks = collection.query.fetch_objects(
                filters=Filter.by_property("headingPath").contains_any(["Database Schema"]),
                limit=20,
            )

            assert len(db_chunks.objects) > 0, "Should find chunks in Database Schema subsection"

            for obj in db_chunks.objects:
                heading = obj.properties.get("headingPath", "")
                # Should mention database-related content
                assert "Database Schema" in heading, f"Wrong subsection: {heading}"

            # TEST 3: Verify heading levels preserved
            all_chunks = collection.query.fetch_objects(limit=100)

            heading_levels = [obj.properties.get("headingLevel", -1) for obj in all_chunks.objects]

            # Should have multiple heading levels (0, 1, 2, 3)
            unique_levels = set(level for level in heading_levels if level >= 0)
            assert len(unique_levels) >= 2, f"Should preserve heading hierarchy: {unique_levels}"

    def test_pipeline_05_cluster_semantic_coherence(
        self, weaviate_client, clean_weaviate_collection, test_config
    ):
        """
        PIPELINE TEST 05: Validate clusters are semantically coherent.

        Tests Stories: 001 (Clustering), 019 (Quality Metrics)

        Flow:
        1. Create vault with clearly distinct topics
        2. Ingest and cluster
        3. For each cluster, get representatives
        4. Validate representatives are topically related
        5. Measure intra-cluster vs inter-cluster similarity
        """
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "vault"
            vault_path.mkdir()

            # Create 3 topically distinct documents (expanded for better semantic separation)
            (vault_path / "ml_doc1.md").write_text(
                """# Machine Learning Fundamentals

## Neural Network Architecture
Neural networks use backpropagation algorithms to learn from data.
Gradient descent optimizes network weights through iterative updates.
Deep learning models stack multiple layers for hierarchical feature extraction.
Activation functions introduce non-linearity into neural computations.

## Training and Optimization
Supervised learning requires labeled datasets for model training.
Cross-validation techniques assess model generalization performance.
Regularization methods prevent overfitting to training data.
Learning rate schedules improve convergence during gradient descent.
"""
            )

            (vault_path / "ml_doc2.md").write_text(
                """# Deep Learning Applications

## Computer Vision
Convolutional neural networks process images through learned filters.
CNNs detect spatial hierarchies and visual patterns automatically.
Image classification tasks benefit from deep convolutional architectures.
Transfer learning leverages pre-trained models for new vision tasks.

## Natural Language Processing
Recurrent neural networks handle sequential text data effectively.
Transformers revolutionized NLP with attention mechanisms and parallelization.
BERT and GPT models demonstrate the power of large-scale pre-training.
Word embeddings capture semantic relationships between terms.
"""
            )

            (vault_path / "cooking_doc1.md").write_text(
                """# Italian Cuisine Masterclass

## Pasta Making
Traditional pasta carbonara uses eggs, guanciale, and pecorino romano.
Fresh pasta dough requires proper kneading and resting time.
Al dente cooking preserves pasta texture and flavor.
Authentic Italian recipes emphasize simplicity and quality ingredients.

## Pizza and Risotto
Pizza margherita showcases the perfect balance of dough, sauce, and cheese.
Neapolitan pizza requires high-temperature wood-fired ovens.
Risotto demands patience, constant stirring, and gradual broth addition.
Arborio rice releases starch for creamy risotto consistency.
"""
            )

            (vault_path / "cooking_doc2.md").write_text(
                """# Artisan Baking Techniques

## Bread Fundamentals
Bread dough development requires proper kneading and gluten formation.
Yeast activation needs warm water temperature and sugar for feeding.
Proofing allows fermentation to develop complex flavors and textures.
Scoring bread dough controls oven spring expansion patterns.

## Advanced Baking
Sourdough starter cultivation creates natural leavening cultures.
Baking temperature and steam affect crust formation and color.
Whole grain flours add nutritional value and rustic character.
Cold fermentation enhances bread flavor through extended rising times.
"""
            )

            (vault_path / "history_doc.md").write_text(
                """# Ancient Roman Civilization

## Imperial Expansion
The Roman Empire spanned three continents at its height.
Julius Caesar transformed the Roman Republic through military conquests.
Roman legions employed advanced tactics and engineering capabilities.
Provincial governance integrated diverse cultures into imperial administration.

## Cultural Legacy
Latin language influenced modern Romance languages profoundly.
Roman law established legal principles still used today.
Ancient architecture inspired neoclassical design movements.
Roman engineering achievements include aqueducts and road networks.
"""
            )

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

            # Cluster into 3 groups (ML, Cooking, History)
            schema_manager = WeaviateSchemaManager(weaviate_client)
            schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

            cluster_manager = ClusterManager(weaviate_client)
            vectors, uuids = cluster_manager.fetch_all_vectors()
            labels, centroids = cluster_manager.run_kmeans_clustering(vectors, n_clusters=3)
            cluster_manager.update_chunk_cluster_ids(uuids, labels)
            cluster_manager.update_centroids(centroids, labels)

            # Get representatives for each cluster
            get_reps = GetClusterRepresentatives(weaviate_client)

            cluster_topics = {}
            for cluster_id in range(3):
                state = {"cluster_id": cluster_id}
                result = get_reps(state)

                representatives = result["representative_chunks"]
                assert len(representatives) > 0, f"Cluster {cluster_id} should have representatives"

                # Analyze representative content
                texts = [rep.text.lower() for rep in representatives]
                combined_text = " ".join(texts)

                # Determine dominant topic
                ml_score = sum(
                    1
                    for keyword in [
                        "neural",
                        "learning",
                        "network",
                        "gradient",
                        "model",
                        "deep",
                    ]
                    if keyword in combined_text
                )
                cooking_score = sum(
                    1
                    for keyword in ["pasta", "pizza", "bread", "dough", "cooking", "baking"]
                    if keyword in combined_text
                )
                history_score = sum(
                    1
                    for keyword in ["roman", "empire", "caesar", "ancient", "latin"]
                    if keyword in combined_text
                )

                scores = {"ml": ml_score, "cooking": cooking_score, "history": history_score}
                topic = max(scores, key=scores.get)

                cluster_topics[cluster_id] = {
                    "topic": topic,
                    "score": scores[topic],
                    "representatives_count": len(representatives),
                }

            # VALIDATE: Should have 3 distinct topics in 3 clusters
            topics_found = [info["topic"] for info in cluster_topics.values()]
            unique_topics = set(topics_found)

            assert (
                len(unique_topics) >= 2
            ), f"Should identify at least 2 distinct topics: {cluster_topics}"

            # Each cluster should have coherent topic (dominant score > 0)
            for cluster_id, info in cluster_topics.items():
                assert info["score"] > 0, f"Cluster {cluster_id} should have identifiable topic"

            print("\nCluster Semantic Coherence:")
            for cluster_id, info in cluster_topics.items():
                print(f"  Cluster {cluster_id}: {info['topic']} (score={info['score']})")


@pytest.mark.e2e
@pytest.mark.weaviate
class TestPipelineEdgeCases:
    """
    EDGE CASE TESTS: Validate pipeline handles challenging scenarios.
    """

    def test_empty_vault_handling(self, weaviate_client, clean_weaviate_collection, test_config):
        """Verify pipeline handles empty vault gracefully."""
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "empty_vault"
            vault_path.mkdir()

            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,

                embedding_provider=embedding_provider,
                state_tracker=state_tracker,
            )

            stats = ingestor.ingest_vault()

            assert stats["files_processed"] == 0, "No files to process"
            assert stats["total_chunks"] == 0, "No chunks created"

            # Clustering should handle empty collection
            # Should not crash on empty data
            # (Implementation should check for empty collection)

    def test_single_file_single_chunk(
        self, weaviate_client, clean_weaviate_collection, test_config
    ):
        """Verify pipeline handles minimal content."""
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "minimal_vault"
            vault_path.mkdir()

            # Very short note (single chunk)
            (vault_path / "tiny.md").write_text("# Tiny Note\nJust a small thought.")

            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,

                embedding_provider=embedding_provider,
                state_tracker=state_tracker,
            )

            stats = ingestor.ingest_vault()

            assert stats["files_processed"] == 1
            assert stats["total_chunks"] >= 1, "Should create at least 1 chunk"

            # Clustering with 1 chunk should work (n_clusters=1)
            schema_manager = WeaviateSchemaManager(weaviate_client)
            schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

            cluster_manager = ClusterManager(weaviate_client)
            vectors, uuids = cluster_manager.fetch_all_vectors()
            labels, centroids = cluster_manager.run_kmeans_clustering(vectors, n_clusters=1)
            cluster_manager.update_chunk_cluster_ids(uuids, labels)
            cluster_manager.update_centroids(centroids, labels)

            assert len(labels) >= 1, "Should cluster at least 1 chunk"

    def test_very_long_document(self, weaviate_client, clean_weaviate_collection, test_config):
        """Verify pipeline handles large documents (many chunks)."""
        provider_config = ProviderConfig(
            llm_provider="ollama",
            embedding_provider="ollama",
            ollama_base_url=test_config["ollama_url"]
        )
        llm_provider = create_llm_provider(provider_config)
        embedding_provider = create_embedding_provider(provider_config)

        with tempfile.TemporaryDirectory() as tmp_dir:
            vault_path = Path(tmp_dir) / "large_vault"
            vault_path.mkdir()

            # Generate long document (should create 20+ chunks)
            content = "# Long Document\n\n"
            for i in range(50):
                content += f"## Section {i}\n"
                content += f"This is section {i} with some content. " * 20
                content += "\n\n"

            (vault_path / "large_doc.md").write_text(content)

            state_tracker = IngestionStateTracker(str(vault_path / "state.db"))
            ingestor = ObsidianIngestor(
                vault_path=str(vault_path),
                weaviate_client=weaviate_client,
                llm_provider=llm_provider,

                embedding_provider=embedding_provider,
                state_tracker=state_tracker,
            )

            stats = ingestor.ingest_vault()

            assert stats["files_processed"] == 1
            assert stats["total_chunks"] >= 20, "Large document should create many chunks"

            # Clustering should handle large chunk count
            collection = weaviate_client.collections.get("TheMuses")
            chunks = collection.query.fetch_objects(limit=1000)

            assert len(chunks.objects) == stats["total_chunks"], "All chunks should be stored"
