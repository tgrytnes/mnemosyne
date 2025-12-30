"""FastAPI app for checkpoint management."""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from mnemosyne.argus.checkpointing import (
    CheckpointCleanupJob,
    CheckpointStore,
    ResearchState,
)


class CheckpointSummary(BaseModel):
    query_id: str
    current_node: str
    updated_at: datetime


class CleanupResponse(BaseModel):
    removed: int


def create_app(checkpoint_db_path: str | None = None) -> FastAPI:
    db_path = checkpoint_db_path or os.getenv("CHECKPOINT_DB_PATH", "checkpoints.db")
    store = CheckpointStore(db_path)

    app = FastAPI(title="Mnemosyne Checkpoint API")

    @app.on_event("shutdown")
    def _shutdown_store() -> None:
        store.close()

    @app.get("/checkpoints", response_model=list[CheckpointSummary])
    def list_checkpoints() -> list[CheckpointSummary]:
        return [
            CheckpointSummary(
                query_id=info.query_id,
                current_node=info.current_node,
                updated_at=info.updated_at,
            )
            for info in store.list_checkpoints()
        ]

    @app.get("/checkpoints/{query_id}", response_model=ResearchState)
    def get_checkpoint(query_id: str) -> ResearchState:
        state = store.load(query_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        return state

    @app.delete("/checkpoints/{query_id}")
    def delete_checkpoint(query_id: str) -> dict[str, bool]:
        store.delete(query_id)
        return {"deleted": True}

    @app.post("/checkpoints/cleanup", response_model=CleanupResponse)
    def cleanup_checkpoints(
        max_age_days: int = Query(30, ge=1, le=3650),
    ) -> CleanupResponse:
        job = CheckpointCleanupJob(store=store, max_age_days=max_age_days)
        removed = job.run()
        return CleanupResponse(removed=removed)

    return app
