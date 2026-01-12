"""
JSON-backed ingestion state for PDF ingestion.
"""

from __future__ import annotations

import json
from pathlib import Path


class PDFIngestionState:
    """Tracks ingested PDF file metadata in a JSON file."""

    def __init__(self, state_path: Path):
        self.state_path = Path(state_path)
        self._entries: dict[str, dict[str, float | int]] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        entries = payload.get("files", {})
        if isinstance(entries, dict):
            for path, meta in entries.items():
                if not isinstance(meta, dict):
                    continue
                mtime = meta.get("mtime")
                size = meta.get("size")
                if isinstance(mtime, (int, float)) and isinstance(size, (int, float)):
                    self._entries[str(path)] = {"mtime": float(mtime), "size": int(size)}

    def is_ingested(self, file_path: str, *, mtime: float, size: int) -> bool:
        meta = self._entries.get(str(file_path))
        if not meta:
            return False
        return meta.get("mtime") == float(mtime) and meta.get("size") == int(size)

    def mark_ingested(self, file_path: str, *, mtime: float, size: int) -> None:
        self._entries[str(file_path)] = {"mtime": float(mtime), "size": int(size)}

    def save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"files": self._entries}
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
