"""
Simple in-memory discovery feed manager for Story 013 unit tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass
class DiscoveryItem:
    discovery_id: str
    title: str
    pattern_type: str
    confidence: float
    detected_at: str
    status: str
    clusters: List[str]


@dataclass
class Page:
    items: List[DiscoveryItem]
    total: int
    page: int
    per_page: int


class DiscoveryFeedManager:
    """In-memory feed manager used for tests."""

    def __init__(self):
        self._items: dict[str, DiscoveryItem] = {}

    def ingest(self, discoveries: Iterable[dict]) -> None:
        for d in discoveries:
            item = DiscoveryItem(
                discovery_id=d["discovery_id"],
                title=d["title"],
                pattern_type=d["pattern_type"],
                confidence=d.get("confidence", 0.0),
                detected_at=d.get("detected_at", ""),
                status=d.get("status", "new"),
                clusters=d.get("clusters", []),
            )
            self._items[item.discovery_id] = item

    def list(self, filters: Optional[dict] = None, page: int = 1, per_page: int = 10) -> Page:
        filters = filters or {}
        filtered = [
            item
            for item in self._items.values()
            if (filters.get("type") is None or item.pattern_type == filters.get("type"))
            and (filters.get("status") is None or item.status == filters.get("status"))
        ]
        total = len(filtered)
        start = (page - 1) * per_page
        end = start + per_page
        return Page(items=filtered[start:end], total=total, page=page, per_page=per_page)

    def search(self, keyword: str, page: int = 1, per_page: int = 10) -> Page:
        keyword_lower = keyword.lower()
        filtered = [item for item in self._items.values() if keyword_lower in item.title.lower()]
        total = len(filtered)
        start = (page - 1) * per_page
        end = start + per_page
        return Page(items=filtered[start:end], total=total, page=page, per_page=per_page)

    def view(self, discovery_id: str) -> DiscoveryItem:
        item = self._items[discovery_id]
        item.status = "reviewed"
        return item

    def get_status(self, discovery_id: str) -> str:
        return self._items[discovery_id].status

    def export_markdown(self, discovery_id: str, destination: Path) -> dict:
        item = self._items[discovery_id]
        destination = Path(destination)
        content = (
            f"# {item.title}\n\n"
            f"- ID: {item.discovery_id}\n"
            f"- Pattern: {item.pattern_type}\n"
            f"- Status: {item.status}\n"
            f"- Clusters: {', '.join(item.clusters)}\n"
        )
        destination.write_text(content)
        return {"path": str(destination)}

    def bulk_action(self, ids: List[str], action: str) -> None:
        if action == "dismiss":
            for discovery_id in ids:
                if discovery_id in self._items:
                    self._items[discovery_id].status = "dismissed"
