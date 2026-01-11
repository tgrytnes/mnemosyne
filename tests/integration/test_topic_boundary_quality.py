"""
Integration test for topic boundary quality with semantic chunking.

USES REAL OLLAMA (no mocks).
"""

import pytest

from mnemosyne.aletheia.semantic_chunker import SemanticChunker
from mnemosyne.config.providers import ProviderConfig
from mnemosyne.providers.factory import create_llm_provider


@pytest.mark.integration
@pytest.mark.parametrize(
    "text,keywords,expected_min_chunks",
    [
        (
            """Topic A is about machine learning and neural networks.
Deep learning has transformed AI research significantly.
This section focuses on technical aspects.

Topic B discusses project management and team collaboration.
Agile methodologies are important for software development.
This section shifts to organizational topics.""",
            ["machine learning", "project management"],
            2,
        ),
        (
            """Cooking basics: boil pasta until al dente and season the water.
Sauce prep focuses on tomatoes, garlic, and olive oil.

Travel planning covers flights, hotels, and local transit passes.
Packing checklists reduce stress and help avoid overpacking.""",
            ["pasta", "travel"],
            2,
        ),
        (
            """Financial budgeting starts with tracking income and fixed expenses.
Saving goals are easier with automated transfers.

Fitness training includes strength sessions and cardio intervals.
Recovery days reduce injury risk and improve performance.""",
            ["budgeting", "fitness"],
            2,
        ),
        (
            """Gardening tips: compost improves soil quality and water retention.
Mulching suppresses weeds and stabilizes moisture.

Cybersecurity basics include using MFA and rotating passwords.
Phishing awareness helps avoid credential theft.""",
            ["compost", "cybersecurity"],
            2,
        ),
        (
            """Product roadmap: define customer problems and prioritize initiatives.
Quarterly goals align teams and clarify scope.

Legal compliance: document data handling and retention policies.
Audits ensure adherence to regulations.

Customer support: response SLAs and knowledge bases improve satisfaction.""",
            ["roadmap", "compliance", "support"],
            3,
        ),
    ],
)
def test_semantic_chunking_aligns_with_topic_boundaries(
    test_config, text, keywords, expected_min_chunks
):
    """Semantic boundaries should align with topic shifts using REAL Ollama."""
    provider_config = ProviderConfig(
        llm_provider="ollama", ollama_base_url=test_config["ollama_url"]
    )
    llm_provider = create_llm_provider(provider_config)

    chunker = SemanticChunker(llm_provider=llm_provider, min_chunk_size=1)
    chunks = chunker.chunk(text, source_file="note.md")

    assert (
        len(chunks) >= expected_min_chunks
    ), f"Expected at least {expected_min_chunks} chunks, got {len(chunks)}"

    chunk_texts = [c.text.lower() for c in chunks]
    for keyword in keywords:
        assert any(keyword in text for text in chunk_texts), f"Missing keyword: {keyword}"
