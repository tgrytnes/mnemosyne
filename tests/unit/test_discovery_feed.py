"""Unit tests for Story 013: discovery feed management (filters, pagination, export)."""


def _sample_discoveries():
    return [
        {
            "discovery_id": "disc-001",
            "title": "Home lab project",
            "pattern_type": "project_candidate",
            "confidence": 0.9,
            "detected_at": "2024-01-02T09:00:00Z",
            "status": "new",
            "clusters": ["cluster-a"],
        },
        {
            "discovery_id": "disc-002",
            "title": "Docker + Home Automation link",
            "pattern_type": "weak_link",
            "confidence": 0.65,
            "detected_at": "2024-01-02T10:00:00Z",
            "status": "new",
            "clusters": ["cluster-a", "cluster-b"],
        },
        {
            "discovery_id": "disc-003",
            "title": "Contradiction: keto vs carb cycling",
            "pattern_type": "contradiction",
            "confidence": 0.8,
            "detected_at": "2024-01-01T08:00:00Z",
            "status": "dismissed",
            "clusters": ["cluster-c", "cluster-d"],
        },
    ]


def test_feed_filters_and_pagination():
    from mnemosyne.hermes.feed import DiscoveryFeedManager

    feed = DiscoveryFeedManager()
    feed.ingest(_sample_discoveries())

    page = feed.list(filters={"type": "weak_link", "status": "new"}, page=1, per_page=1)
    assert page.total == 1
    assert len(page.items) == 1
    assert page.items[0].discovery_id == "disc-002"

    search = feed.search(keyword="home", page=1, per_page=10)
    assert {item.discovery_id for item in search.items} == {"disc-001", "disc-002"}


def test_detail_marks_reviewed_and_export_markdown(tmp_path):
    from mnemosyne.hermes.feed import DiscoveryFeedManager

    feed = DiscoveryFeedManager()
    feed.ingest(_sample_discoveries())

    detail = feed.view("disc-001")
    assert detail.discovery_id == "disc-001"
    assert feed.get_status("disc-001") == "reviewed"

    md_path = tmp_path / "disc-001.md"
    exported = feed.export_markdown("disc-001", destination=md_path)
    assert md_path.exists()
    content = md_path.read_text()
    assert "disc-001" in content
    assert "Home lab project" in content
    assert exported["path"] == str(md_path)


def test_bulk_actions_are_idempotent():
    from mnemosyne.hermes.feed import DiscoveryFeedManager

    feed = DiscoveryFeedManager()
    feed.ingest(_sample_discoveries())

    feed.bulk_action(ids=["disc-001", "disc-002"], action="dismiss")
    assert feed.get_status("disc-001") == "dismissed"
    assert feed.get_status("disc-002") == "dismissed"

    # Repeat should be idempotent
    feed.bulk_action(ids=["disc-001"], action="dismiss")
    assert feed.get_status("disc-001") == "dismissed"
