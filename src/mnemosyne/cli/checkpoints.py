"""CLI commands for checkpoint management."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

import click

from mnemosyne.argus.checkpointing import CheckpointCleanupJob, CheckpointStore


class CheckpointConfig:
    """Configuration for checkpoint CLI."""

    def __init__(self):
        self.db_path = os.getenv("CHECKPOINT_DB_PATH", "checkpoints.db")


def _format_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def list_checkpoints(db_path: str) -> int:
    with CheckpointStore(db_path) as store:
        items = store.list_checkpoints()
        for item in items:
            line = f"{item.query_id}\t{item.current_node}\t" f"{_format_timestamp(item.updated_at)}"
            print(line)
    return 0


def resume_checkpoint(db_path: str, query_id: str) -> int:
    with CheckpointStore(db_path) as store:
        state = store.load(query_id)
        if state is None:
            print("Checkpoint not found.", file=sys.stderr)
            return 1
        print(json.dumps(state.model_dump(mode="json"), indent=2))
    return 0


def delete_checkpoint(db_path: str, query_id: str) -> int:
    with CheckpointStore(db_path) as store:
        store.delete(query_id)
    return 0


def cleanup_checkpoints(db_path: str, max_age_days: int) -> int:
    with CheckpointStore(db_path) as store:
        removed = CheckpointCleanupJob(store=store, max_age_days=max_age_days).run()
        print(f"Removed {removed} checkpoints older than {max_age_days} days.")
    return 0


@click.group("checkpoints")
def checkpoints_cli():
    """Mnemosyne checkpoint utilities"""
    pass


@checkpoints_cli.command("list")
def list_cmd():
    """List checkpoints (latest per query)"""
    config = CheckpointConfig()
    sys.exit(list_checkpoints(config.db_path))


@checkpoints_cli.command("resume")
@click.argument("query_id")
def resume_cmd(query_id: str):
    """Load a checkpoint by query ID"""
    config = CheckpointConfig()
    sys.exit(resume_checkpoint(config.db_path, query_id))


@checkpoints_cli.command("delete")
@click.argument("query_id")
def delete_cmd(query_id: str):
    """Delete checkpoints by query ID"""
    config = CheckpointConfig()
    sys.exit(delete_checkpoint(config.db_path, query_id))


@checkpoints_cli.command("cleanup")
@click.option("--max-age-days", type=int, default=30)
def cleanup_cmd(max_age_days: int):
    """Delete old checkpoints"""
    config = CheckpointConfig()
    sys.exit(cleanup_checkpoints(config.db_path, max_age_days))


if __name__ == "__main__":
    checkpoints_cli()
