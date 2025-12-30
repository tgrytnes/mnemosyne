# Story 023: Configurable Clustering Strategy

**As a** system architect
**I want** the ClusterManager to support multiple clustering algorithms (k-means, HDBSCAN, Agglomerative) with configurable parameters
**So that** I can experiment with different clustering approaches and select the optimal algorithm based on data characteristics and performance requirements

## Acceptance Criteria
- [ ] Strategy pattern implementation for clustering algorithms
- [ ] Support for 3+ clustering algorithms: k-means, HDBSCAN, Agglomerative
- [ ] Configuration via environment variables or config file
- [ ] Each algorithm has sensible defaults but allows parameter overrides
- [ ] Backward compatibility with existing k-means code
- [ ] Clustering metadata stored with algorithm name and parameters used
- [ ] CLI supports `--algorithm` flag to select clustering method
- [ ] All existing tests pass with default k-means configuration
- [ ] New integration tests validate each clustering algorithm
- [ ] Documentation for when to use each algorithm

## Technical Notes

### Current Problem

The `ClusterManager` in `src/mnemosyne/cli/cluster.py` is tightly coupled to MiniBatchKMeans:

```python
# Current implementation (hardcoded)
def run_kmeans_clustering(self, vectors: np.ndarray, n_clusters: int):
    kmeans = MiniBatchKMeans(
        n_clusters=n_clusters,
        random_state=42,
        batch_size=256,
        n_init="auto",
    )
    labels = kmeans.fit_predict(vectors)
    return labels, kmeans.cluster_centers_
```

**Issues:**
- No way to test HDBSCAN or other algorithms (needed for Story 022)
- Algorithm choice not documented in cluster metadata
- Can't switch algorithms without code changes
- Hard to A/B test different clustering approaches

### Proposed Architecture

**1. Strategy Pattern Implementation**

```python
# src/mnemosyne/argus/clustering/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ClusteringConfig:
    """Base configuration for clustering algorithms."""
    random_state: int = 42

@dataclass
class ClusteringResult:
    """Standardized result from any clustering algorithm."""
    labels: np.ndarray
    centroids: Optional[np.ndarray]  # None for HDBSCAN (auto clusters)
    n_clusters: int
    algorithm: str
    parameters: dict
    noise_points: int = 0  # For HDBSCAN


class ClusteringStrategy(ABC):
    """Abstract base class for clustering algorithms."""

    @abstractmethod
    def fit(self, vectors: np.ndarray, **kwargs) -> ClusteringResult:
        """Run clustering on vectors and return standardized result."""
        pass

    @abstractmethod
    def get_algorithm_name(self) -> str:
        """Return algorithm name for metadata."""
        pass
```

**2. Concrete Implementations**

```python
# src/mnemosyne/argus/clustering/kmeans_strategy.py
from sklearn.cluster import MiniBatchKMeans

@dataclass
class KMeansConfig(ClusteringConfig):
    """Configuration for k-means clustering."""
    n_clusters: int = 416
    batch_size: int = 256
    n_init: str = "auto"
    max_iter: int = 300


class KMeansStrategy(ClusteringStrategy):
    """MiniBatch K-Means clustering strategy."""

    def __init__(self, config: KMeansConfig):
        self.config = config

    def fit(self, vectors: np.ndarray, **kwargs) -> ClusteringResult:
        n_clusters = kwargs.get('n_clusters', self.config.n_clusters)

        kmeans = MiniBatchKMeans(
            n_clusters=n_clusters,
            random_state=self.config.random_state,
            batch_size=self.config.batch_size,
            n_init=self.config.n_init,
            max_iter=self.config.max_iter,
        )

        labels = kmeans.fit_predict(vectors)

        return ClusteringResult(
            labels=labels,
            centroids=kmeans.cluster_centers_,
            n_clusters=n_clusters,
            algorithm="kmeans",
            parameters={
                "n_clusters": n_clusters,
                "batch_size": self.config.batch_size,
                "n_init": self.config.n_init,
            }
        )

    def get_algorithm_name(self) -> str:
        return "kmeans"


# src/mnemosyne/argus/clustering/hdbscan_strategy.py
import hdbscan

@dataclass
class HDBSCANConfig(ClusteringConfig):
    """Configuration for HDBSCAN clustering."""
    min_cluster_size: int = 5
    min_samples: int = 3
    metric: str = "euclidean"
    cluster_selection_epsilon: float = 0.0


class HDBSCANStrategy(ClusteringStrategy):
    """HDBSCAN density-based clustering strategy."""

    def __init__(self, config: HDBSCANConfig):
        self.config = config

    def fit(self, vectors: np.ndarray, **kwargs) -> ClusteringResult:
        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=kwargs.get('min_cluster_size', self.config.min_cluster_size),
            min_samples=kwargs.get('min_samples', self.config.min_samples),
            metric=self.config.metric,
            cluster_selection_epsilon=self.config.cluster_selection_epsilon,
        )

        labels = clusterer.fit_predict(vectors)

        # HDBSCAN uses -1 for noise points
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        noise_points = np.sum(labels == -1)

        # Calculate centroids for non-noise clusters
        centroids = []
        for cluster_id in range(n_clusters):
            cluster_mask = labels == cluster_id
            centroid = vectors[cluster_mask].mean(axis=0)
            centroids.append(centroid)

        return ClusteringResult(
            labels=labels,
            centroids=np.array(centroids) if centroids else None,
            n_clusters=n_clusters,
            algorithm="hdbscan",
            parameters={
                "min_cluster_size": self.config.min_cluster_size,
                "min_samples": self.config.min_samples,
                "metric": self.config.metric,
            },
            noise_points=noise_points,
        )

    def get_algorithm_name(self) -> str:
        return "hdbscan"


# src/mnemosyne/argus/clustering/agglomerative_strategy.py
from sklearn.cluster import AgglomerativeClustering

@dataclass
class AgglomerativeConfig(ClusteringConfig):
    """Configuration for Agglomerative clustering."""
    n_clusters: int = 416
    linkage: str = "ward"
    affinity: str = "euclidean"


class AgglomerativeStrategy(ClusteringStrategy):
    """Agglomerative hierarchical clustering strategy."""

    def __init__(self, config: AgglomerativeConfig):
        self.config = config

    def fit(self, vectors: np.ndarray, **kwargs) -> ClusteringResult:
        n_clusters = kwargs.get('n_clusters', self.config.n_clusters)

        clusterer = AgglomerativeClustering(
            n_clusters=n_clusters,
            linkage=self.config.linkage,
            affinity=self.config.affinity,
        )

        labels = clusterer.fit_predict(vectors)

        # Calculate centroids
        centroids = []
        for cluster_id in range(n_clusters):
            cluster_mask = labels == cluster_id
            centroid = vectors[cluster_mask].mean(axis=0)
            centroids.append(centroid)

        return ClusteringResult(
            labels=labels,
            centroids=np.array(centroids),
            n_clusters=n_clusters,
            algorithm="agglomerative",
            parameters={
                "n_clusters": n_clusters,
                "linkage": self.config.linkage,
                "affinity": self.config.affinity,
            }
        )

    def get_algorithm_name(self) -> str:
        return "agglomerative"
```

**3. Factory Pattern for Strategy Selection**

```python
# src/mnemosyne/argus/clustering/factory.py
import os
from typing import Optional

class ClusteringStrategyFactory:
    """Factory for creating clustering strategies."""

    _strategies = {
        "kmeans": KMeansStrategy,
        "hdbscan": HDBSCANStrategy,
        "agglomerative": AgglomerativeStrategy,
    }

    @classmethod
    def create(cls, algorithm: Optional[str] = None, config: Optional[ClusteringConfig] = None) -> ClusteringStrategy:
        """Create clustering strategy from config or environment.

        Args:
            algorithm: Algorithm name (kmeans, hdbscan, agglomerative)
                      If None, reads from CLUSTERING_ALGORITHM env var
            config: Algorithm-specific configuration
                   If None, uses default config

        Returns:
            ClusteringStrategy instance

        Raises:
            ValueError: If algorithm not recognized
        """
        # Default to k-means for backward compatibility
        algorithm = algorithm or os.getenv("CLUSTERING_ALGORITHM", "kmeans")
        algorithm = algorithm.lower()

        if algorithm not in cls._strategies:
            raise ValueError(
                f"Unknown clustering algorithm: {algorithm}. "
                f"Supported: {list(cls._strategies.keys())}"
            )

        strategy_class = cls._strategies[algorithm]

        # Use default config if not provided
        if config is None:
            if algorithm == "kmeans":
                config = KMeansConfig()
            elif algorithm == "hdbscan":
                config = HDBSCANConfig()
            elif algorithm == "agglomerative":
                config = AgglomerativeConfig()

        return strategy_class(config)

    @classmethod
    def register(cls, name: str, strategy_class: type):
        """Register a new clustering strategy (for extensibility)."""
        cls._strategies[name] = strategy_class
```

**4. Refactored ClusterManager**

```python
# src/mnemosyne/cli/cluster.py (refactored)
from mnemosyne.argus.clustering.factory import ClusteringStrategyFactory
from mnemosyne.argus.clustering.base import ClusteringResult

class ClusterManager:
    """Handles the clustering process with configurable algorithms."""

    def __init__(
        self,
        client: weaviate.WeaviateClient,
        clustering_algorithm: Optional[str] = None
    ):
        self.client = client
        self.muses_collection = self.client.collections.get(TheMuses.collection_name)
        self.centroid_collection = self.client.collections.get(
            ClusterCentroidCollection.collection_name
        )

        # Create clustering strategy
        self.strategy = ClusteringStrategyFactory.create(clustering_algorithm)

    def fetch_all_vectors(self) -> tuple[np.ndarray, list[str]]:
        """Fetch all vectors and their UUIDs from TheMuses collection."""
        logger.info("Fetching all vectors from TheMuses collection...")
        vectors = []
        uuids = []

        query_result = self.muses_collection.iterator(include_vector=True)

        for item in query_result:
            vectors.append(item.vector["default"])
            uuids.append(str(item.uuid))

        logger.info(f"Fetched {len(vectors)} vectors.")
        return np.array(vectors), uuids

    def run_clustering(
        self,
        vectors: np.ndarray,
        **kwargs
    ) -> ClusteringResult:
        """Run clustering with configured algorithm.

        Args:
            vectors: Vector embeddings to cluster
            **kwargs: Algorithm-specific parameters (e.g., n_clusters for k-means)

        Returns:
            ClusteringResult with labels, centroids, and metadata
        """
        logger.info(f"Running {self.strategy.get_algorithm_name()} clustering...")
        result = self.strategy.fit(vectors, **kwargs)
        logger.info(f"Clustering complete: {result.n_clusters} clusters formed")

        if result.noise_points > 0:
            logger.info(f"  {result.noise_points} noise points detected")

        return result

    # Backward compatibility method
    def run_kmeans_clustering(
        self, vectors: np.ndarray, n_clusters: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Legacy method for backward compatibility.

        DEPRECATED: Use run_clustering() instead.
        """
        logger.warning("run_kmeans_clustering() is deprecated. Use run_clustering().")
        result = self.run_clustering(vectors, n_clusters=n_clusters)
        return result.labels, result.centroids

    def update_chunk_cluster_ids(self, uuids: list[str], labels: np.ndarray) -> None:
        """Update each chunk with its assigned cluster ID."""
        logger.info("Updating cluster IDs for all chunks...")

        for uuid_str, label in zip(uuids, labels):
            # HDBSCAN can produce -1 for noise points
            cluster_id = int(label) if label >= 0 else -1

            self.muses_collection.data.update(
                uuid=uuid_str,
                properties={"clusterId": cluster_id},
            )
        logger.info("Finished updating chunk cluster IDs.")

    def update_centroids(
        self,
        result: ClusteringResult
    ) -> None:
        """Calculate and store cluster centroids with algorithm metadata.

        Args:
            result: ClusteringResult containing centroids and metadata
        """
        logger.info("Calculating and storing cluster centroids...")

        # Clear existing centroids
        from weaviate.classes.query import Filter
        delete_result = self.centroid_collection.data.delete_many(
            where=Filter.by_property("clusterId").greater_or_equal(0)
        )
        logger.info(
            f"Deleted {delete_result.matches} existing centroids "
            f"(successful: {delete_result.successful}, failed: {delete_result.failed})"
        )

        # Insert new centroids with metadata
        import time
        from datetime import datetime

        centroids_to_insert = []
        for i in range(result.n_clusters):
            cluster_size = np.count_nonzero(result.labels == i)
            if cluster_size > 0:
                centroids_to_insert.append((i, result.centroids[i], cluster_size))

        logger.info(f"Inserting {len(centroids_to_insert)} new centroids...")

        with self.centroid_collection.batch.fixed_size(batch_size=100) as batch:
            for cluster_id, centroid_vec, size in centroids_to_insert:
                batch.add_object(
                    vector=centroid_vec.tolist(),
                    properties={
                        "clusterId": int(cluster_id),
                        "clusterSize": int(size),
                        "lastUpdated": datetime.utcnow().isoformat() + "Z",
                        "algorithm": result.algorithm,
                        "algorithmParams": str(result.parameters),  # Store as JSON string
                    },
                )

        # Verify insertion
        time.sleep(0.5)
        for attempt in range(3):
            verify = self.centroid_collection.query.fetch_objects(limit=1, include_vector=True)
            if len(verify.objects) > 0:
                logger.info(f"Verified {len(centroids_to_insert)} centroids stored successfully")
                break
            logger.warning(
                f"Verification attempt {attempt + 1}: No centroids found yet, retrying..."
            )
            time.sleep(0.5)

        logger.info("Finished storing cluster centroids.")


def run_clustering(n_clusters: int, algorithm: Optional[str] = None):
    """Main function to run the clustering process.

    Args:
        n_clusters: The number of clusters to create (for k-means/agglomerative)
        algorithm: Clustering algorithm to use (kmeans, hdbscan, agglomerative)
    """
    try:
        # Validate n_clusters
        if n_clusters < 1:
            logger.error(f"Invalid n_clusters: {n_clusters}. Must be >= 1.")
            sys.exit(1)

        config = ClusteringConfig()

        logger.info("=" * 60)
        logger.info("Starting Chunk Clustering")
        logger.info("=" * 60)
        logger.info(f"Weaviate: {config.weaviate_host}:{config.weaviate_port}")
        logger.info(f"Algorithm: {algorithm or os.getenv('CLUSTERING_ALGORITHM', 'kmeans')}")
        logger.info(f"Number of clusters: {n_clusters}")
        logger.info("=" * 60)

        client = weaviate.connect_to_local(
            host=config.weaviate_host,
            port=config.weaviate_port,
            grpc_port=config.weaviate_grpc_port,
        )

        # Ensure collections exist
        schema_manager = WeaviateSchemaManager(client)
        schema_manager.ensure_collection_exists(TheMuses.collection_name)
        schema_manager.ensure_collection_exists(ClusterCentroidCollection.collection_name)

        manager = ClusterManager(client, clustering_algorithm=algorithm)

        vectors, uuids = manager.fetch_all_vectors()
        if len(vectors) == 0:
            logger.warning("No vectors found in TheMuses collection. Aborting clustering.")
            client.close()
            return

        # Validate n_clusters against vector count
        if n_clusters > len(vectors):
            logger.warning(
                f"n_clusters ({n_clusters}) > vector count ({len(vectors)}). "
                f"Setting n_clusters = {len(vectors)}"
            )
            n_clusters = len(vectors)

        result = manager.run_clustering(vectors, n_clusters=n_clusters)
        manager.update_chunk_cluster_ids(uuids, result.labels)
        manager.update_centroids(result)

        logger.info("\n" + "=" * 60)
        logger.info("Clustering Complete!")
        logger.info(f"  Algorithm: {result.algorithm}")
        logger.info(f"  Clusters formed: {result.n_clusters}")
        if result.noise_points > 0:
            logger.info(f"  Noise points: {result.noise_points}")
        logger.info("=" * 60)

        client.close()

    except Exception as e:
        logger.error(f"Error during clustering: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
```

**5. Updated CLI**

```python
# src/mnemosyne/cli/cluster.py (main function)
def main():
    """Main CLI entry point for clustering."""
    parser = argparse.ArgumentParser(
        description="Mnemosyne - Chunk Clustering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 'run' command
    parser_run = subparsers.add_parser("run", help="Run clustering on TheMuses collection")
    parser_run.add_argument(
        "--n-clusters",
        type=int,
        default=416,
        help="The number of clusters to create (default: 416). Ignored for HDBSCAN.",
    )
    parser_run.add_argument(
        "--algorithm",
        type=str,
        choices=["kmeans", "hdbscan", "agglomerative"],
        default=None,
        help="Clustering algorithm to use. Default: kmeans (or CLUSTERING_ALGORITHM env var)",
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "run":
        run_clustering(args.n_clusters, args.algorithm)
```

### Configuration Examples

**Environment Variables:**
```bash
# Use HDBSCAN instead of k-means
export CLUSTERING_ALGORITHM=hdbscan

# Use Agglomerative clustering
export CLUSTERING_ALGORITHM=agglomerative
```

**CLI Usage:**
```bash
# K-means (default)
python -m mnemosyne.cli.cluster run --n-clusters 416

# HDBSCAN (auto-determines cluster count)
python -m mnemosyne.cli.cluster run --algorithm hdbscan

# Agglomerative with 200 clusters
python -m mnemosyne.cli.cluster run --algorithm agglomerative --n-clusters 200
```

### Algorithm Selection Guide

**K-Means (MiniBatch)**
- **When to use:** Known number of clusters, fast performance required
- **Pros:** Fast, deterministic, works well on spherical clusters
- **Cons:** Must specify k, sensitive to outliers, assumes equal-sized clusters
- **Best for:** Production default, large datasets (>10k vectors)

**HDBSCAN**
- **When to use:** Unknown cluster count, noisy data, varying cluster densities
- **Pros:** Auto-determines clusters, handles noise, finds arbitrary shapes
- **Cons:** Slower, more parameters to tune, may create too many small clusters
- **Best for:** Exploratory analysis, research vaults with diverse topics

**Agglomerative (Hierarchical)**
- **When to use:** Need hierarchical taxonomy, small-medium datasets
- **Pros:** Hierarchical structure, deterministic, intuitive dendrograms
- **Cons:** Slow (O(n³)), high memory usage, must specify k
- **Best for:** Story 003 (taxonomy generation), <5k vectors

### Schema Updates

Update `ClusterCentroidCollection` to store algorithm metadata:

```python
# src/mnemosyne/alexandria/weaviate_schema.py
class ClusterCentroidCollection:
    collection_name = "ClusterCentroid"

    properties = [
        Property(name="clusterId", data_type=DataType.INT),
        Property(name="clusterSize", data_type=DataType.INT),
        Property(name="lastUpdated", data_type=DataType.DATE),
        Property(name="algorithm", data_type=DataType.TEXT),  # NEW
        Property(name="algorithmParams", data_type=DataType.TEXT),  # NEW (JSON string)
    ]
```

### Migration Strategy

**Phase 1: Add new code (backward compatible)**
1. Create new `argus/clustering/` module with strategies
2. Keep existing `run_kmeans_clustering()` method (deprecated)
3. Add `run_clustering()` as preferred method
4. All new code uses `run_clustering()`

**Phase 2: Update tests**
1. Update E2E tests to use new `run_clustering()` API
2. Add tests for HDBSCAN and Agglomerative
3. Verify backward compatibility tests still pass

**Phase 3: Deprecate old API**
1. Mark `run_kmeans_clustering()` as deprecated
2. Update documentation
3. Plan removal for future version

### Testing Strategy

**Unit Tests:**
- Each strategy returns valid `ClusteringResult`
- Factory creates correct strategy from config
- Backward compatibility with old API

**Integration Tests:**
- K-means produces same results as before
- HDBSCAN handles noise points correctly
- Agglomerative creates hierarchy
- All algorithms update Weaviate correctly

**E2E Tests:**
- Full pipeline works with each algorithm
- Cluster representatives work with all algorithms
- Metadata synthesis works with all algorithms

## Affected Components

- **Argus**: New `clustering/` module with strategy implementations
- **Alexandria**: Schema update for ClusterCentroid (add algorithm metadata)
- **CLI**: Updated `cluster.py` with algorithm selection
- **Tests**: New integration tests for each algorithm

## Dependencies

- Story 001: Cluster Centroid Node (uses clustering results)
- Story 022: Quality Testing Matrix (will use this for benchmarking)

**External Dependencies:**
- `scikit-learn` (already installed) - k-means, Agglomerative
- `hdbscan` (new) - HDBSCAN algorithm
- `numpy`, `scipy` (already installed)

## Priority

**Medium** - Enables Story 022 benchmarking, improves flexibility

## Estimate

8 story points (5-7 days)
- Strategy pattern implementation: 2 days
- Three algorithm implementations: 2 days
- ClusterManager refactor: 1 day
- Schema migration: 0.5 day
- Testing (unit + integration): 1.5 days
- Documentation: 1 day

## Linear Labels

`phase-1`, `clustering`, `refactoring`, `argus`, `performance`, `enhancement`

## Related Stories

- Story 001: Cluster Centroid Node (consumer of clustering results)
- Story 022: Quality Testing Matrix (will benchmark all algorithms)
- Story 003: Automated Graph Taxonomy (may benefit from hierarchical clustering)

## Risks and Mitigations

**Risk 1: Breaking changes to existing code**
- Mitigation: Keep `run_kmeans_clustering()` for backward compatibility
- Fallback: Comprehensive integration tests before merge
- Validation: All existing E2E tests must pass

**Risk 2: HDBSCAN dependency installation issues on Pi 5**
- Mitigation: Test installation on Pi 5 early
- Fallback: Make HDBSCAN optional, only install for dev/testing
- Workaround: Compile from source if wheel unavailable

**Risk 3: Performance regression with abstraction layer**
- Mitigation: Benchmark before/after, strategy pattern is lightweight
- Fallback: If >10% slower, optimize hot paths
- Threshold: No more than 5% overhead acceptable

**Risk 4: Different algorithms produce incompatible cluster IDs**
- Mitigation: ClusteringResult standardizes interface
- Fallback: Store algorithm metadata with centroids
- Validation: Representatives node works with all algorithms

## Success Metrics

- [ ] All three algorithms (k-means, HDBSCAN, Agglomerative) work end-to-end
- [ ] Switching algorithms via env var or CLI flag works correctly
- [ ] No performance regression for default k-means path (<5% overhead)
- [ ] All existing tests pass with default configuration
- [ ] New integration tests pass for HDBSCAN and Agglomerative
- [ ] Story 022 can use factory to benchmark different algorithms
- [ ] Documentation clearly explains when to use each algorithm

## Future Enhancements (Not in Scope)

- Auto-select best algorithm based on data characteristics
- GPU-accelerated clustering (RAPIDS cuML)
- Incremental clustering (update clusters without full re-run)
- Hierarchical HDBSCAN for multi-level taxonomy
- Custom distance metrics (cosine, Manhattan)
- Cluster quality metrics (silhouette score, Davies-Bouldin index)

## Documentation Updates

**User Guide:**
- When to use each clustering algorithm
- How to configure via env vars or CLI
- Performance comparison table

**Developer Guide:**
- How to add a new clustering strategy
- ClusteringStrategy interface documentation
- Factory pattern explanation

**Migration Guide:**
- How to update code from `run_kmeans_clustering()` to `run_clustering()`
- Backward compatibility notes
