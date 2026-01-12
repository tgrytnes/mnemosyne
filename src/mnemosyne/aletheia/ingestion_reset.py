"""
Reset utilities for ingestion state and data.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

logger = logging.getLogger(__name__)


@dataclass
class ResetEnvironment:
    ingestion_state_db: Path
    email_state_path: Path
    pdf_state_path: Path
    weaviate_http_host: str
    weaviate_http_port: int
    weaviate_grpc_port: int
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str
    data_root: Path | None = None


@dataclass
class ResetOptions:
    env: str
    vault: bool = False
    email: bool = False
    pdf: bool = False
    weaviate: bool = False
    postgres: bool = False
    weaviate_collections: list[str] = field(default_factory=list)
    postgres_tables: list[str] = field(default_factory=list)
    dry_run: bool = False
    force: bool = False


@dataclass
class ResetAction:
    action: str
    target: str
    details: dict[str, Any] = field(default_factory=dict)


def validate_reset_options(options: ResetOptions) -> None:
    if options.postgres_tables and not options.postgres:
        raise ValueError("--postgres is required when --postgres-table is set")
    if options.weaviate_collections and not options.weaviate:
        raise ValueError("--weaviate is required when --weaviate-collection is set")
    if options.env in {"staging", "prod"} and not options.force and not options.dry_run:
        raise ValueError("--force is required for staging/prod resets")
    if not any(
        [
            options.vault,
            options.email,
            options.pdf,
            options.weaviate_collections,
            options.postgres_tables,
        ]
    ):
        raise ValueError("No reset targets specified")


def build_reset_plan(options: ResetOptions, env: ResetEnvironment) -> list[ResetAction]:
    plan: list[ResetAction] = []

    if options.vault:
        plan.append(ResetAction("delete_file", str(env.ingestion_state_db)))
        if options.weaviate:
            plan.append(ResetAction("delete_weaviate_collection", "TheMuses"))
            plan.append(ResetAction("delete_weaviate_collection", "ClusterCentroid"))

    if options.email:
        plan.append(ResetAction("delete_file", str(env.email_state_path)))
        if options.weaviate:
            plan.append(
                ResetAction(
                    "delete_weaviate_filter",
                    "TheLethe",
                    details={"property": "type", "value": "email"},
                )
            )
            plan.append(ResetAction("delete_weaviate_collection", "ClusterCentroidLethe"))

    if options.pdf:
        plan.append(ResetAction("delete_file", str(env.pdf_state_path)))
        if options.weaviate:
            plan.append(
                ResetAction(
                    "delete_weaviate_filter",
                    "TheLethe",
                    details={"property": "type", "value": "pdf"},
                )
            )
            plan.append(ResetAction("delete_weaviate_collection", "ClusterCentroidLethe"))

    if options.weaviate and options.weaviate_collections:
        for name in options.weaviate_collections:
            plan.append(ResetAction("delete_weaviate_collection", name))

    if options.postgres and options.postgres_tables:
        for name in options.postgres_tables:
            plan.append(ResetAction("truncate_postgres", name))

    return plan


def build_reset_environment(env_name: str) -> ResetEnvironment:
    env_values = _load_env_values(env_name)
    data_root = Path(env_values["DATA_ROOT"]) if env_values.get("DATA_ROOT") else None
    state_root = data_root / "ingestion_state" if data_root else None

    ingestion_state_db = _resolve_state_path(
        env_values.get("INGESTION_STATE_DB", "/state/ingestion_state.db"),
        state_root,
    )
    email_state_path = _resolve_state_path(
        env_values.get("EMAIL_INGESTION_STATE_PATH", "/state/email_ingestion_state.json"),
        state_root,
    )
    pdf_state_path = _resolve_state_path(
        env_values.get("PDF_INGESTION_STATE_PATH", "/state/pdf_ingestion_state.json"),
        state_root,
    )

    weaviate_host, weaviate_port, weaviate_grpc_port = _resolve_weaviate_settings(env_values)
    postgres_host, postgres_port = _resolve_postgres_settings(env_values)

    return ResetEnvironment(
        ingestion_state_db=ingestion_state_db,
        email_state_path=email_state_path,
        pdf_state_path=pdf_state_path,
        weaviate_http_host=weaviate_host,
        weaviate_http_port=weaviate_port,
        weaviate_grpc_port=weaviate_grpc_port,
        postgres_host=postgres_host,
        postgres_port=postgres_port,
        postgres_db=env_values.get("POSTGRES_DB", "mnemosyne"),
        postgres_user=env_values.get("POSTGRES_USER", "postgres"),
        postgres_password=env_values.get("POSTGRES_PASSWORD", ""),
        data_root=data_root,
    )


def apply_reset_plan(plan: list[ResetAction], env: ResetEnvironment) -> None:
    weaviate_client = None
    postgres_conn = None
    for action in plan:
        if action.action == "delete_file":
            _delete_file(Path(action.target))
            continue

        if action.action.startswith("delete_weaviate"):
            if weaviate_client is None:
                weaviate_client = _connect_weaviate(env)
            if action.action == "delete_weaviate_collection":
                _delete_weaviate_collection(weaviate_client, action.target)
            elif action.action == "delete_weaviate_filter":
                _delete_weaviate_filter(
                    weaviate_client,
                    action.target,
                    action.details.get("property"),
                    action.details.get("value"),
                )
            continue

        if action.action == "truncate_postgres":
            if postgres_conn is None:
                postgres_conn = _connect_postgres(env)
            _truncate_postgres_table(postgres_conn, action.target)
            continue

    if postgres_conn:
        postgres_conn.close()
    if weaviate_client:
        weaviate_client.close()


def _delete_file(path: Path) -> None:
    if path.exists():
        path.unlink()
        logger.info("Deleted file: %s", path)
    else:
        logger.info("File not found: %s", path)


def _connect_weaviate(env: ResetEnvironment):
    import weaviate

    client = weaviate.connect_to_custom(
        http_host=env.weaviate_http_host,
        http_port=env.weaviate_http_port,
        http_secure=False,
        grpc_host=env.weaviate_http_host,
        grpc_port=env.weaviate_grpc_port,
        grpc_secure=False,
    )
    if not client.is_ready():
        raise RuntimeError("Weaviate is not ready")
    return client


def _delete_weaviate_collection(client, name: str) -> None:
    if client.collections.exists(name):
        client.collections.delete(name)
        logger.info("Deleted collection: %s", name)
    else:
        logger.info("Collection not found: %s", name)


def _delete_weaviate_filter(client, collection_name: str, prop: str | None, value: str | None):
    if not prop or value is None:
        raise ValueError("Weaviate filter requires property and value")
    if not client.collections.exists(collection_name):
        logger.info("Collection not found: %s", collection_name)
        return
    from weaviate.classes.query import Filter

    collection = client.collections.get(collection_name)
    delete_result = collection.data.delete_many(where=Filter.by_property(prop).equal(value))
    logger.info(
        "Deleted %s objects from %s where %s=%s (successful: %s, failed: %s)",
        delete_result.matches,
        collection_name,
        prop,
        value,
        delete_result.successful,
        delete_result.failed,
    )


def _connect_postgres(env: ResetEnvironment):
    import psycopg2

    return psycopg2.connect(
        host=env.postgres_host,
        port=env.postgres_port,
        dbname=env.postgres_db,
        user=env.postgres_user,
        password=env.postgres_password,
    )


def _truncate_postgres_table(conn, table_name: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    with conn.cursor() as cursor:
        cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
    conn.commit()
    logger.info("Truncated table: %s", table_name)


def _resolve_state_path(raw_path: str, state_root: Path | None) -> Path:
    path = Path(raw_path)
    if state_root and path.is_absolute():
        raw = str(path)
        if raw.startswith("/state"):
            suffix = raw.removeprefix("/state").lstrip("/")
            return state_root / suffix
    return path


def _load_env_values(env_name: str) -> dict[str, str]:
    repo_root = Path.cwd()
    base_path = repo_root / f".env.{env_name}"
    local_path = repo_root / f".env.{env_name}.local"

    values = {}
    values.update(_coerce_env(dotenv_values(base_path)))
    values.update(_coerce_env(dotenv_values(local_path)))
    for key, value in os.environ.items():
        values.setdefault(key, value)
    return values


def _coerce_env(values: dict[str, str | None]) -> dict[str, str]:
    return {key: value for key, value in values.items() if value is not None}


def _resolve_weaviate_settings(env_values: dict[str, str]) -> tuple[str, int, int]:
    host_port = _env_int(env_values, "WEAVIATE_HOST_PORT", None)
    grpc_host_port = _env_int(env_values, "WEAVIATE_GRPC_HOST_PORT", None)

    host = env_values.get("WEAVIATE_HTTP_HOST", "localhost")
    http_port = _env_int(env_values, "WEAVIATE_HTTP_PORT", 8080)
    grpc_port = _env_int(env_values, "WEAVIATE_GRPC_PORT", 50051)

    if host_port is not None:
        host = "localhost"
        http_port = host_port
    if grpc_host_port is not None:
        grpc_port = grpc_host_port
    return host, http_port, grpc_port


def _resolve_postgres_settings(env_values: dict[str, str]) -> tuple[str, int]:
    host_port = _env_int(env_values, "POSTGRES_HOST_PORT", None)
    host = env_values.get("POSTGRES_HOST", "localhost")
    port = _env_int(env_values, "POSTGRES_PORT", 5432)
    if host_port is not None:
        host = "localhost"
        port = host_port
    return host, port


def _env_int(env_values: dict[str, str], key: str, default: int | None) -> int | None:
    raw = env_values.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{key} must be an integer") from exc
