"""
Unit tests for discovery identity derivation.
"""

from mnemosyne.argus.scout.radar import discovery_identity


def test_discovery_identity_uses_label_for_candidate_key():
    job_key = "private_projects"
    _, candidate_key, discovery_id = discovery_identity(
        job_key,
        ["c1"],
        candidate_label="House Painting",
    )

    assert candidate_key == "house_painting"
    assert discovery_id == f"{job_key}:{candidate_key}"


def test_discovery_identity_hashes_cluster_ids_when_label_missing():
    job_key = "private_projects"
    cluster_ids = ["c2", "c1"]
    _, candidate_key_a, discovery_id_a = discovery_identity(job_key, cluster_ids)
    _, candidate_key_b, discovery_id_b = discovery_identity(job_key, list(reversed(cluster_ids)))

    assert candidate_key_a == candidate_key_b
    assert discovery_id_a == discovery_id_b
    assert candidate_key_a != "c1-c2"
    assert candidate_key_a != "c2-c1"
