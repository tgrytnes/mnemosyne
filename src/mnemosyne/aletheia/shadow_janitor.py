"""
Shadow vault janitor for Story 025.
"""

from __future__ import annotations

import os
import re
import shutil
from glob import glob
from pathlib import Path


class Janitor:
    def __init__(self, source_vault: str, shadow_vault: str, weaviate_client=None):
        self.source_vault = Path(source_vault)
        self.shadow_vault = Path(shadow_vault)
        self.weaviate_client = weaviate_client

    def normalize_file(self, file_path: str) -> str:
        content = Path(file_path).read_text(encoding="utf-8")
        content = content.replace("\r\n", "\n")
        lines = content.split("\n")
        normalized_lines = []
        for line in lines:
            line = line.rstrip()
            if not line.startswith("    ") and not line.startswith("\t"):
                line = re.sub(r" {2,}", " ", line)
            normalized_lines.append(line)
        content = "\n".join(normalized_lines)
        content = re.sub(r"\n{3,}", "\n\n", content)
        return content.strip()

    def sync_to_shadow(self):
        # Copy and normalize from source -> shadow
        for file_path in glob(str(self.source_vault / "**" / "*.md"), recursive=True):
            src = Path(file_path)
            rel = src.relative_to(self.source_vault)
            dst = self.shadow_vault / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            cleaned = self.normalize_file(str(src))
            dst.write_text(cleaned, encoding="utf-8")

        # Remove files deleted from source
        for shadow_file in self.shadow_vault.glob("**/*.md"):
            rel = shadow_file.relative_to(self.shadow_vault)
            src_equiv = self.source_vault / rel
            if not src_equiv.exists():
                shadow_file.unlink()
                self._remove_weaviate_chunks_for(str(src_equiv))

    def _remove_weaviate_chunks_for(self, source_path: str):
        if not self.weaviate_client:
            return
        try:
            collection = self.weaviate_client.collections.get("TheMuses")
            result = collection.query.fetch_objects(
                filters=self.weaviate_client.collections.filter.by_property(
                    "sourceFile", "==", source_path
                ),
                limit=100,
            )
            for obj in result.objects:
                collection.data.delete_by_id(obj.uuid)
        except Exception:
            # best effort cleanup
            return
