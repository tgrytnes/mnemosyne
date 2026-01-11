"""
E2E test for Story 025: shadow gatekeeper approval flow.
Requires real services: filesystem + Weaviate + Ollama.
"""

import pytest
from mnemosyne.config.providers import ProviderConfig

from mnemosyne.aletheia.shadow_gatekeeper import ObsidianGatekeeper  # to be implemented
from mnemosyne.aletheia.shadow_janitor import Janitor  # to be implemented
from mnemosyne.aletheia.shadow_tagger import Tagger  # to be implemented
from mnemosyne.alexandria.weaviate_schema import WeaviateSchemaManager
from mnemosyne.providers.factory import create_llm_provider


@pytest.mark.e2e
@pytest.mark.weaviate
@pytest.mark.ollama
def test_shadow_gatekeeper_approval_flow(tmp_path, weaviate_client):
    """
    Flow:
    - Sync source -> shadow with normalization
    - Tag in shadow
    - Request approval -> approve -> sync back to source
    - Verify Weaviate chunks updated/deleted accordingly
    """
    source = tmp_path / "vault"
    shadow = tmp_path / "shadow"
    (source / "notes").mkdir(parents=True)
    src_file = source / "notes" / "project.md"
    src_file.write_text("Project idea draft.\nNeed review.\n")

    # Ensure collection exists
    WeaviateSchemaManager(weaviate_client).ensure_collection_exists("TheMuses")
    weaviate_client.collections.get("TheMuses")

    # 1) Sync to shadow
    Janitor(str(source), str(shadow)).sync_to_shadow()
    shadow_file = shadow / "notes" / "project.md"
    assert shadow_file.exists()

    # 2) Tag in shadow
    config = ProviderConfig(
        llm_provider="ollama", llm_model="qwen3:0.6b", ollama_base_url="http://localhost:11434"
    )
    llm_provider = create_llm_provider(config)
    tagger = Tagger(llm_provider)
    tags = tagger.tag_file(shadow_file)
    tagger.apply_tags_to_file(shadow_file, tags)

    # 3) Request approval and approve
    gatekeeper = ObsidianGatekeeper(str(source), str(shadow))
    gatekeeper.request_approval(str(shadow_file), {"tags_added": tags})
    assert gatekeeper.pending_approvals
    gatekeeper.approve_all()

    # 4) Sync back to source after approval
    Janitor(str(source), str(shadow)).sync_approved_changes_back()
    assert (source / "notes" / "project.md").exists()
    # Optionally verify tags propagated:
    updated_content = (source / "notes" / "project.md").read_text()
    for tag in tags:
        assert tag in updated_content
