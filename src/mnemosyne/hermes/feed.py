"""
Discovery feed management for Story 013.

This implementation is intentionally simple/in-memory to satisfy current tests.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass
class DiscoveryItem:
    discovery_id: str
    title: str
    pattern_type: str
    confidence: float
    detected_at: str
    status: str
    clusters: list[str]
    description: str | None = None


@dataclass
class PaginatedResult:
    items: list[DiscoveryItem]
    total: int
    page: int
    per_page: int

    @property
    def total_pages(self) -> int:
        return max(1, -(-self.total // self.per_page))

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages


class DiscoveryFeedManager:
    def __init__(self):
        self._items: dict[str, DiscoveryItem] = {}

    def ingest(self, raw_items: Iterable[dict]) -> None:
        for raw in raw_items:
            item = DiscoveryItem(
                discovery_id=str(raw["discovery_id"]),
                title=raw["title"],
                pattern_type=raw["pattern_type"],
                confidence=raw.get("confidence", 0.0),
                detected_at=raw.get("detected_at", dt.datetime.utcnow().isoformat()),
                status=raw.get("status", "new"),
                clusters=list(raw.get("clusters", [])),
                description=raw.get("description"),
            )
            self._items[item.discovery_id] = item

    def list(self, filters: dict | None = None, page: int = 1, per_page: int = 10) -> PaginatedResult:
        filters = filters or {}
        items = list(self._items.values())
        type_filter = filters.get("type")
        status_filter = filters.get("status")
        if type_filter:
            items = [i for i in items if i.pattern_type == type_filter]
        if status_filter:
            items = [i for i in items if i.status == status_filter]
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page
        return PaginatedResult(items=items[start:end], total=total, page=page, per_page=per_page)

    def search(self, keyword: str, page: int = 1, per_page: int = 10) -> PaginatedResult:
        keyword_lower = keyword.lower()
        items = [
            i
            for i in self._items.values()
            if keyword_lower in i.title.lower()
            or (i.description and keyword_lower in i.description.lower())
        ]
        total = len(items)
        start = (page - 1) * per_page
        end = start + per_page
        return PaginatedResult(items=items[start:end], total=total, page=page, per_page=per_page)

    def view(self, discovery_id: str) -> DiscoveryItem:
        item = self._items[discovery_id]
        item.status = "reviewed"
        return item

    def get_status(self, discovery_id: str) -> str:
        return self._items[discovery_id].status

    def export_markdown(self, discovery_id: str, destination: Path) -> dict:
        item = self._items[discovery_id]
        content = f"# {item.title}\n\nid: {item.discovery_id}\npattern: {item.pattern_type}\n"
        destination.write_text(content)
        return {"path": str(destination), "content": content}

    def bulk_action(self, ids: list[str], action: str) -> None:
        for did in ids:
            if did not in self._items:
                continue
            if action == "dismiss":
                self._items[did].status = "dismissed"
            elif action == "archive":
                self._items[did].status = "archived"
            elif action == "reviewed":
                self._items[did].status = "reviewed"
