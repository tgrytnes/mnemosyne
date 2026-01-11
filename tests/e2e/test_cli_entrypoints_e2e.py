import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_module_help(module: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(repo_root / "src"), env.get("PYTHONPATH", "")]).strip(
        os.pathsep
    )

    return subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


@pytest.mark.e2e
@pytest.mark.weaviate
def test_scheduler_entrypoint_with_real_weaviate(weaviate_client, clean_weaviate_collection):
    import weaviate.classes as wvc

    collection = weaviate_client.collections.create(
        name="TestCollection",
        vector_config=wvc.config.Configure.Vectors.self_provided(),
        properties=[
            wvc.config.Property(name="text", data_type=wvc.config.DataType.TEXT),
        ],
    )
    collection.data.insert(
        properties={"text": "entrypoint smoke"},
        vector={"default": [0.0, 0.0, 0.0]},
    )

    response = collection.query.fetch_objects(limit=1)
    assert response.objects

    result = _run_module_help("mnemosyne.cli.scheduler")
    assert result.returncode == 0, result.stderr
    assert "Run a single scheduler cycle and exit." in result.stdout
