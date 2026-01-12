"""
Unit tests for ingestion reset planning and validation.
"""

from pathlib import Path

import pytest

from mnemosyne.aletheia.ingestion_reset import (
    ResetEnvironment,
    ResetOptions,
    build_reset_plan,
    validate_reset_options,
)


def _env(tmp_path: Path) -> ResetEnvironment:
    return ResetEnvironment(
        ingestion_state_db=tmp_path / "ingestion_state.db",
        email_state_path=tmp_path / "email_ingestion_state.json",
        pdf_state_path=tmp_path / "pdf_ingestion_state.json",
        weaviate_http_host="localhost",
        weaviate_http_port=8080,
        weaviate_grpc_port=50051,
        postgres_host="localhost",
        postgres_port=5432,
        postgres_db="mnemosyne",
        postgres_user="mnemosyne_user",
        postgres_password="password",
    )


def _has_action(plan, action: str, target: str, **details) -> bool:
    for item in plan:
        if item.action != action or item.target != target:
            continue
        if all(item.details.get(key) == value for key, value in details.items()):
            return True
    return False


def test_build_reset_plan_vault_weaviate(tmp_path: Path):
    env = _env(tmp_path)
    options = ResetOptions(env="dev", vault=True, weaviate=True)

    plan = build_reset_plan(options, env)

    assert _has_action(plan, "delete_file", str(env.ingestion_state_db))
    assert _has_action(plan, "delete_weaviate_collection", "TheMuses")
    assert _has_action(plan, "delete_weaviate_collection", "ClusterCentroid")


def test_build_reset_plan_email_pdf_filters(tmp_path: Path):
    env = _env(tmp_path)
    options = ResetOptions(env="dev", email=True, pdf=True, weaviate=True)

    plan = build_reset_plan(options, env)

    assert _has_action(plan, "delete_file", str(env.email_state_path))
    assert _has_action(plan, "delete_file", str(env.pdf_state_path))
    assert _has_action(
        plan,
        "delete_weaviate_filter",
        "TheLethe",
        property="type",
        value="email",
    )
    assert _has_action(
        plan,
        "delete_weaviate_filter",
        "TheLethe",
        property="type",
        value="pdf",
    )


def test_build_reset_plan_explicit_collections(tmp_path: Path):
    env = _env(tmp_path)
    options = ResetOptions(
        env="dev",
        weaviate=True,
        weaviate_collections=["Discoveries"],
    )

    plan = build_reset_plan(options, env)

    assert _has_action(plan, "delete_weaviate_collection", "Discoveries")


def test_build_reset_plan_postgres_tables(tmp_path: Path):
    env = _env(tmp_path)
    options = ResetOptions(
        env="dev",
        postgres=True,
        postgres_tables=["cluster_profiles", "cluster_sync_state"],
    )

    plan = build_reset_plan(options, env)

    assert _has_action(plan, "truncate_postgres", "cluster_profiles")
    assert _has_action(plan, "truncate_postgres", "cluster_sync_state")


def test_validate_requires_force_for_prod():
    options = ResetOptions(env="prod", vault=True)

    with pytest.raises(ValueError, match="--force"):
        validate_reset_options(options)


def test_validate_allows_dry_run_without_force():
    options = ResetOptions(env="staging", vault=True, dry_run=True)

    validate_reset_options(options)


def test_validate_requires_postgres_flag_for_tables():
    options = ResetOptions(env="dev", postgres_tables=["cluster_profiles"])

    with pytest.raises(ValueError, match="--postgres"):
        validate_reset_options(options)
