"""Pydantic schema for cluster profiles."""

from datetime import datetime
from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ClusterProfile(BaseModel):
    """Structured cluster metadata generated from LLM output."""

    cluster_id: str = Field(min_length=1)
    theme_summary: str = Field(min_length=1)
    key_entities: List[str] = Field(default_factory=list)
    dominant_topics: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    representative_note_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
