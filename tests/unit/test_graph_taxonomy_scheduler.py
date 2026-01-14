from unittest.mock import MagicMock


def test_run_graph_taxonomy_task_uses_llm_provider(monkeypatch):
    import mnemosyne.cli.scheduler as scheduler

    fake_provider = MagicMock()
    monkeypatch.setattr(
        scheduler,
        "ProviderConfig",
        MagicMock(from_env=MagicMock(return_value=MagicMock())),
    )
    monkeypatch.setattr(
        scheduler,
        "create_llm_provider",
        MagicMock(return_value=fake_provider),
    )

    weaviate_client = MagicMock()
    monkeypatch.setattr(
        scheduler.weaviate,
        "connect_to_local",
        MagicMock(return_value=weaviate_client),
    )
    postgres_conn = MagicMock()
    monkeypatch.setattr(
        scheduler.psycopg2,
        "connect",
        MagicMock(return_value=postgres_conn),
    )
    neo4j_driver = MagicMock()
    monkeypatch.setattr(
        scheduler.GraphDatabase,
        "driver",
        MagicMock(return_value=neo4j_driver),
    )

    bootstrapper = MagicMock()
    monkeypatch.setattr(scheduler, "ClusterProfileBootstrapper", bootstrapper)

    pipeline_instance = MagicMock()
    pipeline_instance.build_graph.return_value = {"nodes": [], "edges": []}
    monkeypatch.setattr(
        scheduler,
        "GraphTaxonomyPipeline",
        MagicMock(return_value=pipeline_instance),
    )

    scheduler.run_graph_taxonomy_task()

    _, kwargs = bootstrapper.call_args
    assert "llm_provider" in kwargs
    assert kwargs["llm_provider"] is fake_provider
