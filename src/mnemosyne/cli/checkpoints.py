"""CLI commands for checkpoint management."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

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
            line = (
                f"{item.query_id}\t{item.current_node}\t"
                f"{_format_timestamp(item.updated_at)}"
            )
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Mnemosyne checkpoint utilities")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("list", help="List checkpoints (latest per query)")

    resume_parser = subparsers.add_parser("resume", help="Load a checkpoint by query ID")
    resume_parser.add_argument("query_id", help="Query ID to resume")

    delete_parser = subparsers.add_parser("delete", help="Delete checkpoints by query ID")
    delete_parser.add_argument("query_id", help="Query ID to delete")

    cleanup_parser = subparsers.add_parser("cleanup", help="Delete old checkpoints")
    cleanup_parser.add_argument("--max-age-days", type=int, default=30)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = CheckpointConfig()

    if args.command == "list":
        sys.exit(list_checkpoints(config.db_path))
    if args.command == "resume":
        sys.exit(resume_checkpoint(config.db_path, args.query_id))
    if args.command == "delete":
        sys.exit(delete_checkpoint(config.db_path, args.query_id))
    if args.command == "cleanup":
        sys.exit(cleanup_checkpoints(config.db_path, args.max_age_days))


if __name__ == "__main__":
    main()
