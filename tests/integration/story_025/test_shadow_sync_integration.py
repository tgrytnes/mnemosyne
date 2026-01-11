"""Integration test for Story 025: shadow sync + tagging with real services."""

from pathlib import Path

import pytest
from mnemosyne.config.providers import ProviderConfig

from mnemosyne.providers.factory import create_llm_provider


@pytest.mark.integration
@pytest.mark.ollama
def test_shadow_sync_and_tagging_with_real_ollama(tmp_path: Path):
    from mnemosyne.aletheia.shadow_janitor import Janitor  # to be implemented
    from mnemosyne.aletheia.shadow_tagger import Tagger  # to be implemented

    source = tmp_path / "vault"
    shadow = tmp_path / "shadow"
    (source / "notes").mkdir(parents=True)
    src_file = source / "notes" / "note.md"
    src_file.write_text("This is a draft note about a project.\nTODO: refine idea.")

    Janitor(str(source), str(shadow)).sync_to_shadow()

    shadow_file = shadow / "notes" / "note.md"
    assert shadow_file.exists()
    assert "draft note about a project." in shadow_file.read_text()

    config = ProviderConfig(
        llm_provider="ollama", llm_model="qwen3:0.6b", ollama_base_url="http://localhost:11434"
    )
    llm_provider = create_llm_provider(config)
    tagger = Tagger(llm_provider)
    tags = tagger.tag_file(shadow_file)
    tagger.apply_tags_to_file(shadow_file, tags)

    content = shadow_file.read_text()
    assert "#needs_review" in content or "#project_candidate" in content
