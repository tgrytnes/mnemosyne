"""
Unit tests for clustering config env overrides.
"""

from mnemosyne.cli.cluster import ClusteringConfig


def test_cluster_config_reads_per_collection_counts(monkeypatch):
    monkeypatch.setenv("N_CLUSTERS", "50")
    monkeypatch.setenv("N_CLUSTERS_MUSES", "12")
    monkeypatch.setenv("N_CLUSTERS_LETHE", "34")

    config = ClusteringConfig()

    assert config.n_clusters_default == 50
    assert config.n_clusters_muses == 12
    assert config.n_clusters_lethe == 34


def test_cluster_config_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("N_CLUSTERS", "50")
    monkeypatch.delenv("N_CLUSTERS_MUSES", raising=False)
    monkeypatch.delenv("N_CLUSTERS_LETHE", raising=False)

    config = ClusteringConfig()

    assert config.n_clusters_muses == 50
    assert config.n_clusters_lethe == 50
