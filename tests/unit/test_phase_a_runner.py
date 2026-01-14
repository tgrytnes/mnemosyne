"""
Unit tests for Phase A runner configuration and summary output.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

from mnemosyne.phase_a.runner import (
    SUMMARY_KEYS,
    PhaseARunConfig,
    _collect_metrics,
    build_run_plan,
    build_run_summary,
    load_phase_a_env,
)


def _write_env(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_build_run_plan_applies_defaults_and_overrides(tmp_path: Path):
    env_file = tmp_path / ".env.phase_a.local"
    _write_env(
        env_file,
        "\n".join(
            [
                "PHASE_A_RUNS=baseline,late",
                "PHASE_A_DEFAULT_OUTPUT_ROOT=data/phase_a",
                "PHASE_A_DEFAULT_CHUNKING_STRATEGY=recursive",
                "PHASE_A_DEFAULT_CHUNKING_AUGMENTATION=none",
                "PHASE_A_DEFAULT_EMBEDDING_PROVIDER=fastapi",
                "PHASE_A_DEFAULT_EMBEDDING_MODEL=jinaai/jina-embeddings-v3",
                "PHASE_A_DEFAULT_LLM_PROVIDER=fastapi",
                "PHASE_A_DEFAULT_LLM_MODEL=smart",
                "PHASE_A_RUN_baseline_RUN_ID=baseline_test",
                "PHASE_A_RUN_late_RUN_ID=late_test",
                "PHASE_A_RUN_late_CHUNKING_AUGMENTATION=late",
                "PHASE_A_RUN_late_LATE_CHUNK_ADAPTER=retrieval.passage",
            ]
        ),
    )

    env = load_phase_a_env(env_file)
    plan = build_run_plan(env)

    assert [run.name for run in plan] == ["baseline", "late"]

    baseline, late = plan
    assert baseline.run_id == "baseline_test"
    assert baseline.chunking_strategy == "recursive"
    assert baseline.chunking_augmentation == "none"
    assert baseline.embedding_provider == "fastapi"
    assert baseline.llm_model == "smart"

    assert late.chunking_augmentation == "late"
    assert late.late_chunk_adapter == "retrieval.passage"


def test_summary_schema_is_stable():
    run = PhaseARunConfig(
        name="baseline",
        run_id="baseline_001",
        output_root="data/phase_a",
        chunking_strategy="recursive",
        chunking_augmentation="none",
        embedding_provider="fastapi",
        embedding_model="jinaai/jina-embeddings-v3",
        llm_provider="fastapi",
        llm_model="smart",
        contextual_llm_provider="fastapi",
        contextual_llm_model="Qwen3_4B",
        contextual_max_doc_chars=2000,
        late_chunk_adapter="retrieval.passage",
        late_chunk_embedding_model="",
    )
    metrics = {
        "started_at": "2026-01-12T12:00:00Z",
        "completed_at": "2026-01-12T12:01:00Z",
        "duration_seconds": 60.0,
        "file_count": 10,
        "chunk_count": 100,
        "cluster_count": 10,
        "profile_count": 10,
        "centroid_count": 10,
    }

    summary = build_run_summary(run, metrics)

    assert set(summary.keys()) == set(SUMMARY_KEYS)
    assert summary["run_id"] == "baseline_001"
    assert summary["chunk_count"] == 100


def test_collect_metrics_uses_grpc_port(monkeypatch):
    called = {}

    class FakeAggregateResult:
        total_count = 1

    class FakeAggregate:
        def over_all(self, total_count: bool = True):
            return FakeAggregateResult()

    class FakeCollection:
        aggregate = FakeAggregate()

    class FakeCollections:
        def get(self, name: str):
            return FakeCollection()

    class FakeClient:
        collections = FakeCollections()

        def close(self):
            return None

    def connect_to_local(host, port, grpc_port=None, **kwargs):
        called["host"] = host
        called["port"] = port
        called["grpc_port"] = grpc_port
        return FakeClient()

    fake_weaviate = SimpleNamespace(connect_to_local=connect_to_local)
    monkeypatch.setitem(sys.modules, "weaviate", fake_weaviate)

    env = {
        "WEAVIATE_HTTP_HOST": "localhost",
        "WEAVIATE_HTTP_PORT": "8082",
        "WEAVIATE_GRPC_PORT": "50062",
    }
    _collect_metrics(env)

    assert called["grpc_port"] == 50062
