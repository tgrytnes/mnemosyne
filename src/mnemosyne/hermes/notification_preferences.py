"""Notification preference model for Hermes."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NotificationPreferences(BaseModel):
    user_id: str = Field(min_length=1)
    enabled: bool = True
    quiet_start_hour: int = Field(default=22, ge=0, le=23)
    quiet_end_hour: int = Field(default=8, ge=0, le=23)
    max_daily_notifications: int = Field(default=3, ge=1)

    notify_emerging_themes: bool = True
    notify_orphaned_clusters: bool = False
    notify_contradictions: bool = True
    notify_project_candidates: bool = True
    notify_weak_links: bool = True

    min_confidence_emerging: float = Field(default=0.7, ge=0.0, le=1.0)
    min_confidence_contradiction: float = Field(default=0.8, ge=0.0, le=1.0)
    min_confidence_project: float = Field(default=0.75, ge=0.0, le=1.0)
    min_confidence_weak_link: float = Field(default=0.6, ge=0.0, le=1.0)

    batch_mode: Literal["immediate", "daily_digest", "weekly_digest"] = "daily_digest"
    digest_time: int = Field(default=9, ge=0, le=23)

    @property
    def quiet_hours(self) -> tuple[int, int]:
        return (self.quiet_start_hour, self.quiet_end_hour)
