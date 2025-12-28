"""
Markdown cleaner for Obsidian vault content.

Removes Obsidian-specific syntax and noise to prepare content for embedding.
Based on Project Crystal's markdown cleaning approach.
"""

import re
from typing import Tuple

from mnemosyne.aletheia.structure_extractor import DocumentStructure, StructureExtractor


class ObsidianMarkdownCleaner:
    """
    Cleans Obsidian markdown files for embedding generation.

    Removes:
    - YAML frontmatter
    - Wiki-links [[...]]
    - Embeds ![[...]]
    - HTML tags
    - Obsidian metadata (property::value)
    - ChatGPT plugin blocks
    - Emoji markers
    - Extra whitespace
    """

    def __init__(self):
        """Initialize cleaner with structure extractor."""
        self.structure_extractor = StructureExtractor()

    def clean(self, markdown: str) -> str:
        """
        Clean markdown text for embedding.

        Args:
            markdown: Raw markdown text from Obsidian

        Returns:
            Cleaned text ready for chunking and embedding
        """
        if not markdown:
            return ""

        text = markdown

        # Remove YAML frontmatter (---)
        text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL | re.MULTILINE)

        # Remove ChatGPT plugin blocks (must be before general code block handling)
        text = re.sub(r"```chatgpt[^`]*```", "", text, flags=re.DOTALL)

        # Remove embeds ![[...]] (must be before wiki-links)
        text = re.sub(r"!\[\[([^\]]+)\]\]", "", text)

        # Convert wiki-links [[...]] to plain text
        # Handle both [[link]] and [[link|alias]] formats
        text = re.sub(
            r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]",
            lambda m: m.group(2) if m.group(2) else m.group(1),
            text,
        )

        # Remove HTML tags
        text = re.sub(r"<[^>]+>", "", text)

        # Remove Obsidian metadata (property::value)
        text = re.sub(r"\b\w+::[^\n]+", "", text)

        # Remove emoji markers
        text = re.sub(r"📌|🎯|💡|⚡", "", text)

        # Normalize whitespace
        # Replace multiple spaces with single space
        text = re.sub(r" +", " ", text)
        # Replace more than 2 newlines with 2 newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Strip leading/trailing whitespace
        text = text.strip()

        return text

    def clean_with_structure(self, markdown: str) -> Tuple[str, DocumentStructure]:
        """
        Clean markdown and extract document structure.

        Extracts structure from ORIGINAL markdown before cleaning,
        then cleans the text. This ensures heading positions and
        content are preserved before markdown syntax is removed.

        Args:
            markdown: Raw markdown text from Obsidian

        Returns:
            Tuple of (cleaned_text, document_structure)
        """
        # Step 1: Extract structure from ORIGINAL markdown (before cleaning)
        structure = self.structure_extractor.extract_structure(markdown)

        # Step 2: Clean the markdown
        cleaned_text = self.clean(markdown)

        return cleaned_text, structure
