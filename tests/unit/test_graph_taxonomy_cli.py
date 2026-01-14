from unittest.mock import MagicMock


def test_graph_taxonomy_cli_uses_llm_provider(monkeypatch):
    import mnemosyne.cli.graph_taxonomy as graph_taxonomy

    fake_provider = MagicMock()
    monkeypatch.setattr(
        graph_taxonomy,
        "ProviderConfig",
        MagicMock(from_env=MagicMock(return_value=MagicMock())),
    )
    monkeypatch.setattr(
        graph_taxonomy,
        "create_llm_provider",
        MagicMock(return_value=fake_provider),
    )

    weaviate_client = MagicMock()
    monkeypatch.setattr(
        graph_taxonomy.weaviate,
        "connect_to_local",
        MagicMock(return_value=weaviate_client),
    )
    postgres_conn = MagicMock()
    monkeypatch.setattr(
        graph_taxonomy.psycopg2,
        "connect",
        MagicMock(return_value=postgres_conn),
    )
    neo4j_driver = MagicMock()
    monkeypatch.setattr(
        graph_taxonomy.GraphDatabase,
        "driver",
        MagicMock(return_value=neo4j_driver),
    )
    bootstrapper = MagicMock()
    monkeypatch.setattr(graph_taxonomy, "ClusterProfileBootstrapper", bootstrapper)

    pipeline_instance = MagicMock()
    pipeline_instance.build_graph.return_value = {"nodes": [], "edges": []}
    monkeypatch.setattr(
        graph_taxonomy,
        "GraphTaxonomyPipeline",
        MagicMock(return_value=pipeline_instance),
    )

    graph_taxonomy.run_graph_taxonomy()

    _, kwargs = bootstrapper.call_args
    assert "llm_provider" in kwargs
    assert kwargs["llm_provider"] is fake_provider
