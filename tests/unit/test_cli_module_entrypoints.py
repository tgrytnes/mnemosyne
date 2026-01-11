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


@pytest.mark.unit
@pytest.mark.parametrize(
    ("module", "expected"),
    [
        ("mnemosyne.cli.hermes", "Run a single delivery + reply poll cycle and exit."),
        ("mnemosyne.cli.scheduler", "Run a single scheduler cycle and exit."),
    ],
)
def test_cli_module_help_includes_options(module: str, expected: str) -> None:
    result = _run_module_help(module)

    assert result.returncode == 0, result.stderr
    assert expected in result.stdout
