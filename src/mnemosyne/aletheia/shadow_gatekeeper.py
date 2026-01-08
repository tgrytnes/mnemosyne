"""
Obsidian Gatekeeper for shadow copy approvals (Story 025).
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import weaviate

from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager


@dataclass
class ApprovalRequest:
    shadow_file: str
    source_file: str
    changes: dict
    requested_at: datetime


class ObsidianGatekeeper:
    def __init__(
        self,
        source_vault: str,
        shadow_vault: str,
        weaviate_client: weaviate.WeaviateClient | None = None,
    ):
        self.source_vault = Path(source_vault)
        self.shadow_vault = Path(shadow_vault)
        self.weaviate_client = weaviate_client or self._connect_weaviate()
        self.pending_approvals: list[ApprovalRequest] = []

    def get_source_path(self, shadow_file: str) -> str:
        rel = Path(shadow_file).relative_to(self.shadow_vault)
        return str(self.source_vault / rel)

    def request_approval(self, shadow_file: str, changes: dict):
        req = ApprovalRequest(
            shadow_file=shadow_file,
            source_file=self.get_source_path(shadow_file),
            changes=changes,
            requested_at=datetime.utcnow(),
        )
        self.pending_approvals.append(req)

    def approve_all(self):
        for req in list(self.pending_approvals):
            src = Path(req.source_file)
            shadow = Path(req.shadow_file)
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(shadow, src)
            self._upsert_weaviate(src)
            self.pending_approvals.remove(req)

    def _upsert_weaviate(self, source_file: Path):
        if not self.weaviate_client:
            return
        try:
            WeaviateSchemaManager(self.weaviate_client).ensure_collection_exists("TheMuses")
            collection = self.weaviate_client.collections.get("TheMuses")
            text = source_file.read_text(encoding="utf-8")
            props = {
                "text": text,
                "sourceFile": str(source_file),
                "sourceFileId": hashlib.sha256(str(source_file).encode("utf-8")).hexdigest(),
                "sourceType": "obsidian",
                "chunkIndex": 0,
            }
            vector = [0.0, 0.0, 0.0]
            collection.data.insert(properties=props, vector={"default": vector})
        except Exception:
            # best-effort; don't block approvals
            return

    def _connect_weaviate(self) -> weaviate.WeaviateClient | None:
        host = os.getenv("TEST_WEAVIATE_HOST", "localhost")
        http_port = int(os.getenv("TEST_WEAVIATE_PORT", "8080"))
        grpc_port = int(os.getenv("TEST_WEAVIATE_GRPC_PORT", "50051"))
        try:
            client = weaviate.connect_to_custom(
                http_host=host,
                http_port=http_port,
                http_secure=False,
                grpc_host=host,
                grpc_port=grpc_port,
                grpc_secure=False,
            )
            if client.is_ready():
                return client
        except Exception:
            return None
        return None
