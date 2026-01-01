"""
Unit tests for Story 025: Janitor shadow sync and normalization.
"""

import tempfile
from pathlib import Path

import pytest

from mnemosyne.aletheia import text_chunker  # for side effects of package init


class DummyJanitor:
    """Minimal Janitor stub to exercise normalize logic without full implementation."""

    def normalize_file(self, file_path: str) -> str:
        from mnemosyne.aletheia.shadow_janitor import Janitor  # to be implemented

        return Janitor("", "").normalize_file(file_path)

    def sync_to_shadow(self, source: Path, shadow: Path):
        from mnemosyne.aletheia.shadow_janitor import Janitor  # to be implemented

        janitor = Janitor(str(source), str(shadow))
        janitor.sync_to_shadow()


@pytest.fixture
def sample_md(tmp_path: Path) -> Path:
    path = tmp_path / "note.md"
    path.write_text("Line 1\r\nLine 2   \n\n\nLine    3\n    code   block\n")
    return path


def test_normalize_file_trims_and_preserves_code_blocks(sample_md: Path):
    janitor = DummyJanitor()
    normalized = janitor.normalize_file(str(sample_md))

    assert "Line 1\nLine 2\n\nLine 3\n    code   block" == normalized


def test_sync_to_shadow_copies_structure_and_normalized_content(tmp_path: Path):
    source = tmp_path / "vault"
    shadow = tmp_path / "shadow"
    (source / "a/b").mkdir(parents=True)
    src_file = source / "a/b/note.md"
    src_file.write_text("Hello   world  \n\nLine 2\r\n")

    DummyJanitor().sync_to_shadow(source, shadow)

    shadow_file = shadow / "a/b/note.md"
    assert shadow_file.exists()
    assert shadow_file.read_text() == "Hello world\n\nLine 2"
