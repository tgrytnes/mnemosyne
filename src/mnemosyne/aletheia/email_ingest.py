"""Email ingestion into Weaviate (The Lethe) for Story 024."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager
from mnemosyne.aletheia.email_cleaner import clean_email_body, contains_mojibake, truncate_body


@dataclass
class EmailIngestConfig:
    tsv_path: Path
    max_chars: int = 8000
    min_body_chars: int = 20
    collection_name: str = "TheLethe"
    dedup: bool = True


@dataclass
class IngestSummary:
    total_loaded: int
    total_stored: int
    duplicates: int
    rejected: int


class EmailIngestor:
    def __init__(
        self,
        config: EmailIngestConfig,
        weaviate_client,
        embedder: Callable[[str], list[float]],
    ) -> None:
        self.config = config
        self.client = weaviate_client
        self.embedder = embedder
        WeaviateSchemaManager(self.client).ensure_collection_exists(config.collection_name)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        collection = self.client.collections.get(self.config.collection_name)
        try:
            existing = {p.name for p in collection.config.get().properties}
        except Exception:
            existing = set()
        needed = {
            "subject": "text",
            "body": "text",
            "sender": "text",
            "date": "text",
            "clusterId": "int",
            "keywords": "text[]",
            "type": "text",
            "messageId": "text",
            "sourcePath": "text",
        }
        from weaviate.classes.config import DataType, Property

        for name, dtype in needed.items():
            if name in existing:
                continue
            dt = DataType.TEXT
            if dtype == "int":
                dt = DataType.INT
            if dtype == "text[]":
                dt = getattr(DataType, "TEXT_ARRAY", DataType.TEXT)
            collection.config.add_property(Property(name=name, data_type=dt))

    def run(self) -> IngestSummary:
        collection = self.client.collections.get(self.config.collection_name)
        seen_ids: set[str] = set()
        total_loaded = 0
        total_stored = 0
        duplicates = 0
        rejected = 0

        for email in self._load_tsv(self.config.tsv_path):
            total_loaded += 1
            if contains_mojibake(email["body"]):
                rejected += 1
                continue
            body = truncate_body(email["body"], max_chars=self.config.max_chars)
            if len(body.strip()) < self.config.min_body_chars:
                rejected += 1
                continue

            msg_id = email.get("message_id") or ""
            stable = msg_id or hashlib.sha256(f"{email['subject']}{body}".encode("utf-8")).hexdigest()
            if self.config.dedup and stable in seen_ids:
                duplicates += 1
                continue
            seen_ids.add(stable)

            vec = self.embedder(body)
            props = {
                "subject": email["subject"],
                "body": body,
                "sender": email.get("sender"),
                "date": email.get("date"),
                "clusterId": -1,
                "keywords": [],
                "type": "unknown",
                "messageId": msg_id or stable,
                "sourcePath": email.get("source") or "",
            }
            collection.data.insert(properties=props, vector=vec)
            total_stored += 1

        return IngestSummary(
            total_loaded=total_loaded,
            total_stored=total_stored,
            duplicates=duplicates,
            rejected=rejected,
        )

    def cluster_and_label(self) -> list[dict]:
        collection = self.client.collections.get(self.config.collection_name)
        objs = collection.query.fetch_objects(limit=100)
        if not objs.objects:
            return []
        return [{"id": obj.uuid, "keywords": []} for obj in objs.objects]

    def _load_tsv(self, path: Path) -> Iterable[dict]:
        with path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                subject = row.get("subject", "") or ""
                body_raw = row.get("body", "") or ""
                source = row.get("source", "") or ""
                message_id = row.get("message_id", "") or ""
                date = row.get("date", "") or ""
                cleaned_body = clean_email_body(body_raw)
                yield {
                    "subject": subject,
                    "body": cleaned_body,
                    "source": source,
                    "message_id": message_id,
                    "date": date,
                }
