"""
JSON-backed ingestion state for raw email ingestion.
"""

from __future__ import annotations

import json
from pathlib import Path


class EmailIngestionState:
    """Tracks ingested email unique IDs in a JSON file."""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self._ingested_ids: set[str] = set()
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        ids = payload.get("ingested_ids", [])
        if isinstance(ids, list):
            self._ingested_ids.update(str(value) for value in ids)

    def is_ingested(self, unique_id: str) -> bool:
        return unique_id in self._ingested_ids

    def mark_ingested(self, unique_id: str) -> None:
        if unique_id:
            self._ingested_ids.add(unique_id)

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"ingested_ids": sorted(self._ingested_ids)}
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
