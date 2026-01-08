import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mnemosyne.alexandria.weaviate_schema import Discoveries, WeaviateSchemaManager

pytestmark = [pytest.mark.integration, pytest.mark.weaviate, pytest.mark.postgres]


def _run_monitor_cli(args: list[str], env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.update(env_overrides)
    env["PYTHONPATH"] = os.pathsep.join([str(repo_root / "src"), env.get("PYTHONPATH", "")]).strip(
        os.pathsep
    )

    return subprocess.run(
        [sys.executable, "-m", "mnemosyne.cli.monitor", *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_monitor_cli_help_displays_correctly():
    result = _run_monitor_cli(["--help"], {})
    assert result.returncode == 0
    assert "run" in result.stdout


def test_monitor_cli_run_creates_proposal(
    test_config,
    weaviate_client,
    postgres_connection,
    ananke_test_db,
):
    if weaviate_client.collections.exists(Discoveries.collection_name):
        weaviate_client.collections.delete(Discoveries.collection_name)

    WeaviateSchemaManager(weaviate_client).ensure_collection_exists(Discoveries.collection_name)
    collection = weaviate_client.collections.get(Discoveries.collection_name)

    discovery_id = "private_projects:house_painting"
    collection.data.insert(
        properties={
            "patternType": "project_candidate",
            "clusterIds": ["c1"],
            "confidenceScore": 0.82,
            "detectedAt": datetime.now(UTC),
            "discoveryId": discovery_id,
            "discoveryJobKey": "private_projects",
            "candidateKey": "house_painting",
        },
        vector={"default": [0.1, 0.2]},
    )

    env = {
        "WEAVIATE_HTTP_HOST": test_config["weaviate_http_host"],
        "WEAVIATE_HTTP_PORT": str(test_config["weaviate_http_port"]),
        "WEAVIATE_GRPC_PORT": str(test_config["weaviate_grpc_port"]),
        "POSTGRES_HOST": test_config["postgres_host"],
        "POSTGRES_PORT": str(test_config["postgres_port"]),
        "POSTGRES_DB": test_config["postgres_db"],
        "POSTGRES_USER": test_config["postgres_user"],
        "POSTGRES_PASSWORD": test_config["postgres_password"],
        "MONITOR_CONFIDENCE_THRESHOLD": "0.7",
        "MONITOR_SCAN_LIMIT": "10",
    }

    result = _run_monitor_cli(["run"], env)
    assert result.returncode == 0, result.stderr

    with postgres_connection.cursor() as cursor:
        cursor.execute(
            "SELECT discovery_id, status FROM proposal_queue WHERE discovery_id = %s",
            (discovery_id,),
        )
        row = cursor.fetchone()

    assert row is not None
    assert row[0] == discovery_id
    assert row[1] == "pending"
