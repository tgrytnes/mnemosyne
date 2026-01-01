"""
Unit tests for Story 025 Tagger: parsing and applying tags in shadow copy.
"""

from pathlib import Path

import pytest


class DummyTagger:
    """Minimal Tagger stub to exercise parsing/apply logic."""

    def __init__(self, client=None):
        from mnemosyne.aletheia.shadow_tagger import Tagger  # to be implemented

        self._tagger = Tagger(client)

    def tag_file(self, path: Path):
        return self._tagger.tag_file(path)

    def apply_tags_to_file(self, path: Path, tags):
        return self._tagger.apply_tags_to_file(path, tags)


def test_tag_file_parses_hash_lines(mocker, tmp_path: Path):
    file_path = tmp_path / "note.md"
    file_path.write_text("content")

    client = mocker.MagicMock()
    client.generate.return_value = {"response": "#needs_review\n#project_candidate"}

    tagger = DummyTagger(client)
    tags = tagger.tag_file(file_path)

    assert tags == ["#needs_review", "#project_candidate"]


def test_apply_tags_updates_frontmatter(tmp_path: Path):
    file_path = tmp_path / "note.md"
    file_path.write_text("---\ntags:\n  - #old\n---\nBody\n")

    tagger = DummyTagger()  # Tagger uses no client for apply
    tagger.apply_tags_to_file(file_path, ["#needs_review", "#new_tag"])

    content = file_path.read_text()
    assert "#old" in content
    assert "#needs_review" in content
    assert "#new_tag" in content
