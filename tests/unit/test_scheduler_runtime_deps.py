"""Unit tests for scheduler runtime dependencies."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.unit
def test_scheduler_imports_with_runtime_deps() -> None:
    try:
        importlib.import_module("mnemosyne.cli.scheduler")
    except ModuleNotFoundError as exc:
        pytest.fail("Scheduler import failed due to missing runtime dependency: " f"{exc}")
