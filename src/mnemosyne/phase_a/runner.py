"""
Phase A experiment runner utilities.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

SUMMARY_KEYS = [
    "run_name",
    "run_id",
    "output_root",
    "chunking_strategy",
    "chunking_augmentation",
    "embedding_provider",
    "embedding_model",
    "llm_provider",
    "llm_model",
    "contextual_llm_provider",
    "contextual_llm_model",
    "contextual_max_doc_chars",
    "late_chunk_adapter",
    "late_chunk_embedding_model",
    "started_at",
    "completed_at",
    "duration_seconds",
    "file_count",
    "chunk_count",
    "cluster_count",
    "profile_count",
    "centroid_count",
]


@dataclass(frozen=True)
class PhaseARunConfig:
    name: str
    run_id: str
    output_root: str
    chunking_strategy: str
    chunking_augmentation: str
    embedding_provider: str
    embedding_model: str
    llm_provider: str
    llm_model: str
    contextual_llm_provider: str
    contextual_llm_model: str
    contextual_max_doc_chars: int
    late_chunk_adapter: str
    late_chunk_embedding_model: str


def load_phase_a_env(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        raise FileNotFoundError(f"Phase A env file not found: {env_path}")
    values = {key: value for key, value in dotenv_values(env_path).items() if value is not None}
    for key, value in os.environ.items():
        values.setdefault(key, value)
    return values


def build_run_plan(env: dict[str, str]) -> list[PhaseARunConfig]:
    run_names = _split_csv(env.get("PHASE_A_RUNS", ""))
    if not run_names:
        raise ValueError("PHASE_A_RUNS must be set in the Phase A env file.")

    defaults = {
        "OUTPUT_ROOT": env.get("PHASE_A_DEFAULT_OUTPUT_ROOT", "data/phase_a"),
        "CHUNKING_STRATEGY": env.get("PHASE_A_DEFAULT_CHUNKING_STRATEGY", "recursive"),
        "CHUNKING_AUGMENTATION": env.get("PHASE_A_DEFAULT_CHUNKING_AUGMENTATION", "none"),
        "EMBEDDING_PROVIDER": env.get("PHASE_A_DEFAULT_EMBEDDING_PROVIDER", "ollama"),
        "EMBEDDING_MODEL": env.get("PHASE_A_DEFAULT_EMBEDDING_MODEL", ""),
        "LLM_PROVIDER": env.get("PHASE_A_DEFAULT_LLM_PROVIDER", "ollama"),
        "LLM_MODEL": env.get("PHASE_A_DEFAULT_LLM_MODEL", ""),
        "CONTEXTUAL_LLM_PROVIDER": env.get("PHASE_A_DEFAULT_CONTEXTUAL_LLM_PROVIDER", ""),
        "CONTEXTUAL_LLM_MODEL": env.get("PHASE_A_DEFAULT_CONTEXTUAL_LLM_MODEL", ""),
        "CONTEXTUAL_MAX_DOC_CHARS": env.get("PHASE_A_DEFAULT_CONTEXTUAL_MAX_DOC_CHARS", "4000"),
        "LATE_CHUNK_ADAPTER": env.get("PHASE_A_DEFAULT_LATE_CHUNK_ADAPTER", "retrieval.passage"),
        "LATE_CHUNK_EMBEDDING_MODEL": env.get("PHASE_A_DEFAULT_LATE_CHUNK_EMBEDDING_MODEL", ""),
    }

    plan: list[PhaseARunConfig] = []
    for name in run_names:
        prefix = f"PHASE_A_RUN_{name}_"
        run_id = env.get(f"{prefix}RUN_ID", name)
        output_root = env.get(f"{prefix}OUTPUT_ROOT", defaults["OUTPUT_ROOT"])
        chunking_strategy = env.get(f"{prefix}CHUNKING_STRATEGY", defaults["CHUNKING_STRATEGY"])
        chunking_augmentation = env.get(
            f"{prefix}CHUNKING_AUGMENTATION", defaults["CHUNKING_AUGMENTATION"]
        )
        embedding_provider = env.get(f"{prefix}EMBEDDING_PROVIDER", defaults["EMBEDDING_PROVIDER"])
        embedding_model = env.get(f"{prefix}EMBEDDING_MODEL", defaults["EMBEDDING_MODEL"])
        llm_provider = env.get(f"{prefix}LLM_PROVIDER", defaults["LLM_PROVIDER"])
        llm_model = env.get(f"{prefix}LLM_MODEL", defaults["LLM_MODEL"])
        contextual_llm_provider = (
            env.get(f"{prefix}CONTEXTUAL_LLM_PROVIDER", defaults["CONTEXTUAL_LLM_PROVIDER"])
            or llm_provider
        )
        contextual_llm_model = env.get(
            f"{prefix}CONTEXTUAL_LLM_MODEL", defaults["CONTEXTUAL_LLM_MODEL"]
        )
        contextual_max_doc_chars = int(
            env.get(
                f"{prefix}CONTEXTUAL_MAX_DOC_CHARS",
                defaults["CONTEXTUAL_MAX_DOC_CHARS"],
            )
        )
        late_chunk_adapter = env.get(f"{prefix}LATE_CHUNK_ADAPTER", defaults["LATE_CHUNK_ADAPTER"])
        late_chunk_embedding_model = env.get(
            f"{prefix}LATE_CHUNK_EMBEDDING_MODEL", defaults["LATE_CHUNK_EMBEDDING_MODEL"]
        )

        plan.append(
            PhaseARunConfig(
                name=name,
                run_id=run_id,
                output_root=output_root,
                chunking_strategy=chunking_strategy,
                chunking_augmentation=chunking_augmentation,
                embedding_provider=embedding_provider,
                embedding_model=embedding_model,
                llm_provider=llm_provider,
                llm_model=llm_model,
                contextual_llm_provider=contextual_llm_provider,
                contextual_llm_model=contextual_llm_model,
                contextual_max_doc_chars=contextual_max_doc_chars,
                late_chunk_adapter=late_chunk_adapter,
                late_chunk_embedding_model=late_chunk_embedding_model,
            )
        )

    return plan


def build_run_summary(run: PhaseARunConfig, metrics: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "run_name": run.name,
        "run_id": run.run_id,
        "output_root": run.output_root,
        "chunking_strategy": run.chunking_strategy,
        "chunking_augmentation": run.chunking_augmentation,
        "embedding_provider": run.embedding_provider,
        "embedding_model": run.embedding_model,
        "llm_provider": run.llm_provider,
        "llm_model": run.llm_model,
        "contextual_llm_provider": run.contextual_llm_provider,
        "contextual_llm_model": run.contextual_llm_model,
        "contextual_max_doc_chars": run.contextual_max_doc_chars,
        "late_chunk_adapter": run.late_chunk_adapter,
        "late_chunk_embedding_model": run.late_chunk_embedding_model,
        "started_at": metrics.get("started_at"),
        "completed_at": metrics.get("completed_at"),
        "duration_seconds": metrics.get("duration_seconds"),
        "file_count": metrics.get("file_count"),
        "chunk_count": metrics.get("chunk_count"),
        "cluster_count": metrics.get("cluster_count"),
        "profile_count": metrics.get("profile_count"),
        "centroid_count": metrics.get("centroid_count"),
    }
    for key in SUMMARY_KEYS:
        summary.setdefault(key, None)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Phase A experiment matrix.")
    parser.add_argument(
        "--env-file",
        default=".env.phase_a.local",
        help="Path to Phase A env file (default: .env.phase_a.local)",
    )
    parser.add_argument(
        "--runs",
        default="",
        help="Comma-separated run names to execute (default: all in PHASE_A_RUNS).",
    )
    parser.add_argument(
        "--steps",
        default="",
        help="Comma-separated steps: sample,ingest,cluster,profile,export "
        "(default: PHASE_A_STEPS).",
    )
    parser.add_argument("--reset-between-runs", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    env_path = Path(args.env_file)
    env = load_phase_a_env(env_path)
    plan = build_run_plan(env)

    selected = _split_csv(args.runs)
    if selected:
        plan = [run for run in plan if run.name in selected]
        if not plan:
            logger.error("No matching runs found for: %s", ", ".join(selected))
            return 1

    steps = _split_csv(args.steps) or _split_csv(env.get("PHASE_A_STEPS", "ingest,cluster"))
    if not steps:
        logger.error("No steps provided. Set PHASE_A_STEPS or pass --steps.")
        return 1

    for run in plan:
        if args.reset_between_runs:
            _reset_between_runs(env, args.dry_run)
        _execute_run(run, env, steps, dry_run=args.dry_run)

    return 0


def _execute_run(
    run: PhaseARunConfig, env: dict[str, str], steps: list[str], dry_run: bool
) -> None:
    output_dir = Path(run.output_root) / run.run_id
    output_dir.mkdir(parents=True, exist_ok=True)

    run_env = _build_run_env(run, env, output_dir)
    _write_env_snapshot(output_dir, run_env)

    metrics: dict[str, Any] = {}
    started_at = datetime.now(UTC)
    metrics["started_at"] = started_at.isoformat()

    for step in steps:
        _run_step(step, run, env, run_env, output_dir, dry_run=dry_run)

    completed_at = datetime.now(UTC)
    metrics["completed_at"] = completed_at.isoformat()
    metrics["duration_seconds"] = (completed_at - started_at).total_seconds()

    metrics.update(_collect_metrics(run_env))

    summary = build_run_summary(run, metrics)
    _write_summary_files(output_dir, summary)


def _build_run_env(run: PhaseARunConfig, env: dict[str, str], output_dir: Path) -> dict[str, str]:
    run_env = os.environ.copy()
    run_env.update(env)

    run_env["CHUNKING_STRATEGY"] = run.chunking_strategy
    run_env["CHUNKING_AUGMENTATION"] = run.chunking_augmentation
    run_env["EMBEDDING_PROVIDER"] = run.embedding_provider
    run_env["LLM_PROVIDER"] = run.llm_provider
    run_env["CONTEXTUAL_LLM_PROVIDER"] = run.contextual_llm_provider
    run_env["CONTEXTUAL_LLM_MODEL"] = run.contextual_llm_model
    run_env["CONTEXTUAL_MAX_DOC_CHARS"] = str(run.contextual_max_doc_chars)
    run_env["LATE_CHUNK_ADAPTER"] = run.late_chunk_adapter
    run_env["LATE_CHUNK_EMBEDDING_MODEL"] = run.late_chunk_embedding_model

    if "INGESTION_STATE_DB" not in env:
        run_env["INGESTION_STATE_DB"] = str(output_dir / "ingestion_state.db")

    if run.embedding_provider == "fastapi" and run.embedding_model:
        run_env["FASTAPI_EMBEDDING_MODEL"] = run.embedding_model
    if run.embedding_provider == "ollama" and run.embedding_model:
        run_env["OLLAMA_EMBEDDING_MODEL"] = run.embedding_model

    if run.llm_provider == "fastapi" and run.llm_model:
        run_env["FASTAPI_LLM_MODEL"] = run.llm_model
    if run.llm_provider == "ollama" and run.llm_model:
        run_env["OLLAMA_LLM_MODEL"] = run.llm_model
    if run.llm_provider == "groq" and run.llm_model:
        run_env["GROQ_LLM_MODEL"] = run.llm_model

    run_env["PHASE_A_RUN_ID"] = run.run_id
    run_env["PHASE_A_RUN_NAME"] = run.name
    run_env["PHASE_A_OUTPUT_DIR"] = str(output_dir)
    return run_env


def _write_env_snapshot(output_dir: Path, run_env: dict[str, str]) -> None:
    snapshot = output_dir / "run_env.json"
    snapshot.write_text(json.dumps(run_env, indent=2, sort_keys=True), encoding="utf-8")


def _run_step(
    step: str,
    run: PhaseARunConfig,
    env: dict[str, str],
    run_env: dict[str, str],
    output_dir: Path,
    dry_run: bool,
) -> None:
    normalized = step.strip().lower()
    logger.info("Phase A run %s: step %s", run.name, normalized)

    if normalized == "sample":
        command = env.get("PHASE_A_SAMPLE_COMMAND", "").strip()
        _run_shell_command(command, run_env, dry_run, required=False)
        return
    if normalized == "ingest":
        _run_mnemosyne_cli(["ingest", "once"], run_env, dry_run)
        return
    if normalized == "cluster":
        n_clusters = env.get("PHASE_A_N_CLUSTERS", "20")
        _run_mnemosyne_cli(["cluster", "run", "--n-clusters", str(n_clusters)], run_env, dry_run)
        return
    if normalized == "profile":
        _run_mnemosyne_cli(["graph-taxonomy"], run_env, dry_run)
        return
    if normalized == "export":
        command = env.get("PHASE_A_EXPORT_COMMAND", "").strip()
        _run_shell_command(command, run_env, dry_run, required=False)
        return

    raise ValueError(f"Unknown step: {step}")


def _run_mnemosyne_cli(args: list[str], env: dict[str, str], dry_run: bool) -> None:
    command = [sys.executable, "-m", "mnemosyne.cli.main", *args]
    if dry_run:
        logger.info("Dry run: %s", " ".join(command))
        return
    subprocess.run(command, env=env, check=True)


def _run_shell_command(command: str, env: dict[str, str], dry_run: bool, required: bool) -> None:
    if not command:
        if required:
            raise ValueError("Required command missing from env.")
        logger.info("No command configured; skipping.")
        return
    if dry_run:
        logger.info("Dry run: %s", command)
        return
    subprocess.run(command, env=env, shell=True, check=True)


def _reset_between_runs(env: dict[str, str], dry_run: bool) -> None:
    env_name = env.get("PHASE_A_RESET_ENV", "dev")
    command = [
        sys.executable,
        "-m",
        "mnemosyne.cli.main",
        "ingest",
        "reset",
        "--env",
        env_name,
        "--vault",
        "--weaviate",
        "--postgres",
    ]
    if dry_run:
        logger.info("Dry run: %s", " ".join(command))
        return
    subprocess.run(command, env=env, check=True)


def _write_summary_files(output_dir: Path, summary: dict[str, Any]) -> None:
    json_path = output_dir / "summary.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")

    csv_path = output_dir / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_KEYS)
        writer.writeheader()
        writer.writerow({key: summary.get(key) for key in SUMMARY_KEYS})


def _collect_metrics(env: dict[str, str]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    vault_path = env.get("OBSIDIAN_VAULT_PATH")
    if vault_path:
        metrics["file_count"] = _count_markdown_files(Path(vault_path))

    weaviate_host = env.get("WEAVIATE_HTTP_HOST", "localhost")
    weaviate_port = int(env.get("WEAVIATE_HTTP_PORT", "8080"))
    weaviate_grpc_port = int(env.get("WEAVIATE_GRPC_PORT", "50051"))
    try:
        import weaviate

        client = weaviate.connect_to_local(
            host=weaviate_host, port=weaviate_port, grpc_port=weaviate_grpc_port
        )
        try:
            muses = client.collections.get("TheMuses")
            metrics["chunk_count"] = _count_collection(muses)
            centroids = client.collections.get("ClusterCentroid")
            metrics["centroid_count"] = _count_collection(centroids)
            metrics["cluster_count"] = metrics["centroid_count"]
        finally:
            client.close()
    except Exception as exc:
        logger.warning("Unable to collect Weaviate metrics: %s", exc)

    try:
        import psycopg2

        conn = psycopg2.connect(
            host=env.get("POSTGRES_HOST", "localhost"),
            port=int(env.get("POSTGRES_PORT", "5432")),
            dbname=env.get("POSTGRES_DB", "mnemosyne_dev"),
            user=env.get("POSTGRES_USER", "postgres"),
            password=env.get("POSTGRES_PASSWORD", ""),
        )
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM cluster_profiles")
                metrics["profile_count"] = cursor.fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Unable to collect Postgres metrics: %s", exc)

    return metrics


def _count_markdown_files(vault: Path) -> int:
    if not vault.exists():
        return 0
    count = 0
    for path in vault.rglob("*.md"):
        if ".obsidian" in path.parts:
            continue
        count += 1
    return count


def _count_collection(collection) -> int:
    try:
        result = collection.aggregate.over_all(total_count=True)
        return int(result.total_count or 0)
    except Exception:
        results = collection.query.fetch_objects(limit=1)
        return len(results.objects)


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
