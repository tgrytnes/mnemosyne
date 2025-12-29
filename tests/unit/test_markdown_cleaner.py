"""
Unit tests for markdown cleaning functionality.

Tests the ObsidianMarkdownCleaner class which removes:
- YAML frontmatter
- Wiki-links
- Embeds
- HTML tags
- Obsidian metadata
- ChatGPT plugin blocks
- Emoji markers
"""

import pytest

from mnemosyne.aletheia.structure_extractor import DocumentStructure
from src.mnemosyne.aletheia.markdown_cleaner import ObsidianMarkdownCleaner


class TestObsidianMarkdownCleaner:
    """Test markdown cleaning for Obsidian vault ingestion"""

    @pytest.fixture
    def cleaner(self):
        """Create a markdown cleaner instance"""
        return ObsidianMarkdownCleaner()

    def test_remove_yaml_frontmatter(self, cleaner):
        """Should remove YAML frontmatter from document"""
        # GIVEN: Markdown with YAML frontmatter
        markdown = """---
title: My Note
tags: [python, testing]
created: 2024-01-01
---

This is the actual content."""

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: Frontmatter is removed, content remains
        assert "---" not in result
        assert "title:" not in result
        assert "tags:" not in result
        assert "This is the actual content." in result

    def test_remove_wiki_links(self, cleaner):
        """Should convert wiki-links to plain text"""
        # GIVEN: Markdown with wiki-links
        markdown = "Check out [[My Other Note]] and [[Another Note|with alias]]"

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: Wiki-link syntax removed, text preserved
        assert "[[" not in result
        assert "]]" not in result
        assert "My Other Note" in result
        assert "with alias" in result

    def test_remove_embeds(self, cleaner):
        """Should remove image/file embeds"""
        # GIVEN: Markdown with embeds
        markdown = "Here is an image: ![[screenshot.png]] and text"

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: Embed is completely removed
        assert "![[" not in result
        assert "screenshot.png" not in result
        assert "Here is an image:" in result
        assert "and text" in result

    def test_remove_html_tags(self, cleaner):
        """Should remove HTML tags"""
        # GIVEN: Markdown with HTML
        markdown = "This is <span class='highlight'>highlighted</span> text"

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: HTML tags removed, text preserved
        assert "<span" not in result
        assert "</span>" not in result
        assert "highlighted" in result
        assert "This is highlighted text" in result

    def test_remove_obsidian_metadata(self, cleaner):
        """Should remove Obsidian metadata syntax"""
        # GIVEN: Markdown with metadata
        markdown = "Created:: 2024-01-01\nStatus:: active\n\nRegular content"

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: Metadata syntax removed
        assert "Created::" not in result
        assert "Status::" not in result
        assert "Regular content" in result

    def test_remove_chatgpt_blocks(self, cleaner):
        """Should remove ChatGPT plugin code blocks"""
        # GIVEN: Markdown with ChatGPT blocks
        markdown = """Before

```chatgpt
role:: user
What is Python?
```

After"""

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: ChatGPT block removed
        assert "```chatgpt" not in result
        assert "role::" not in result
        assert "Before" in result
        assert "After" in result

    def test_remove_emoji_markers(self, cleaner):
        """Should remove common emoji markers"""
        # GIVEN: Markdown with emoji markers
        markdown = "📌 Important point\n🎯 Goal: Learn Python\n💡 Idea here"

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: Emojis removed, text preserved
        assert "📌" not in result
        assert "🎯" not in result
        assert "💡" not in result
        assert "Important point" in result
        assert "Goal: Learn Python" in result

    def test_normalize_whitespace(self, cleaner):
        """Should normalize multiple spaces and newlines"""
        # GIVEN: Markdown with extra whitespace
        markdown = "This  has   multiple    spaces\n\n\n\nand many newlines"

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: Whitespace normalized to single spaces
        assert "  " not in result  # No double spaces
        assert "\n\n\n" not in result  # No triple newlines
        assert "This has multiple spaces" in result

    def test_clean_complex_document(self, cleaner):
        """Should handle a complex real-world document"""
        # GIVEN: Complex markdown document
        markdown = """---
title: Python Testing
tags: [python, pytest, tdd]
---

# Python Testing Guide

📌 **Important**: Testing is crucial!

Check out [[Unit Testing]] and [[Integration Testing|testing strategies]].

Here's a diagram:
![[test_pyramid.png]]

<div class="callout">
This is a callout
</div>

Status:: in-progress
Created:: 2024-01-01

```chatgpt
role:: user
Explain pytest
```

The actual content about testing."""

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: All noise removed, content preserved
        assert "---" not in result
        assert "tags:" not in result
        assert "📌" not in result
        assert "[[" not in result
        assert "![[" not in result
        assert "<div" not in result
        assert "Status::" not in result
        assert "```chatgpt" not in result
        assert "Python Testing Guide" in result
        assert "Testing is crucial" in result
        assert "The actual content about testing" in result

    def test_empty_string(self, cleaner):
        """Should handle empty string"""
        # GIVEN: Empty string
        markdown = ""

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: Returns empty string
        assert result == ""

    def test_already_clean_markdown(self, cleaner):
        """Should not modify clean markdown"""
        # GIVEN: Already clean markdown
        markdown = "This is clean markdown. It has sentences. Nothing to remove."

        # WHEN: Cleaning the markdown
        result = cleaner.clean(markdown)

        # THEN: Content unchanged (except whitespace normalization)
        assert "This is clean markdown" in result
        assert "Nothing to remove" in result


class TestObsidianMarkdownCleanerWithStructure:
    """Test markdown cleaning with structure extraction (Story 020)"""

    @pytest.fixture
    def cleaner(self):
        """Create a markdown cleaner instance"""
        return ObsidianMarkdownCleaner()

    def test_clean_with_structure_returns_tuple(self, cleaner):
        """Should return tuple of (cleaned_text, structure)"""
        # GIVEN: Markdown with headings
        markdown = """# Main Heading

Some content here.

## Section One

More content."""

        # WHEN: Cleaning with structure extraction
        result = cleaner.clean_with_structure(markdown)

        # THEN: Returns tuple of (cleaned_text, DocumentStructure)
        assert isinstance(result, tuple)
        assert len(result) == 2
        cleaned_text, structure = result
        assert isinstance(cleaned_text, str)
        assert isinstance(structure, DocumentStructure)

    def test_clean_with_structure_extracts_before_cleaning(self, cleaner):
        """Should extract structure from ORIGINAL markdown before cleaning"""
        # GIVEN: Markdown with headings and wiki-links
        markdown = """# Main Heading

Content with [[wiki-link]].

## Section One

More content."""

        # WHEN: Cleaning with structure extraction
        cleaned_text, structure = cleaner.clean_with_structure(markdown)

        # THEN: Structure preserves original headings
        assert structure.root.title == "Main Heading"
        assert structure.root.level == 1
        assert len(structure.root.children) == 1
        assert structure.root.children[0].title == "Section One"

        # AND: Cleaned text has wiki-links removed
        assert "[[" not in cleaned_text
        assert "wiki-link" in cleaned_text

    def test_clean_with_structure_preserves_heading_positions(self, cleaner):
        """Should preserve heading positions from original document"""
        # GIVEN: Markdown with headings
        markdown = """# Main

Content.

## Section

More content."""

        # WHEN: Cleaning with structure extraction
        cleaned_text, structure = cleaner.clean_with_structure(markdown)

        # THEN: Heading positions are from original markdown
        assert structure.root.start_pos == 0
        assert structure.root.children[0].start_pos > 0

    def test_clean_with_structure_handles_no_headings(self, cleaner):
        """Should handle documents without headings"""
        # GIVEN: Markdown without headings
        markdown = "Just plain text without any headings."

        # WHEN: Cleaning with structure extraction
        cleaned_text, structure = cleaner.clean_with_structure(markdown)

        # THEN: Structure has empty root node
        assert structure.root.level == 0
        assert structure.root.title == ""
        assert len(structure.root.children) == 0

        # AND: Text is still cleaned
        assert cleaned_text == "Just plain text without any headings."

    def test_clean_with_structure_handles_complex_document(self, cleaner):
        """Should handle complex document with frontmatter, headings, and noise"""
        # GIVEN: Complex markdown
        markdown = """---
title: Test Note
---

# Main Heading

📌 Important: Check [[Other Note]]

## Section One

Content here.

### Subsection

![[image.png]]

## Section Two

More content."""

        # WHEN: Cleaning with structure extraction
        cleaned_text, structure = cleaner.clean_with_structure(markdown)

        # THEN: Structure extracted from original
        assert structure.root.title == "Main Heading"
        assert len(structure.root.children) == 2
        assert structure.root.children[0].title == "Section One"
        assert structure.root.children[0].children[0].title == "Subsection"

        # AND: Cleaned text has all noise removed
        assert "---" not in cleaned_text
        assert "📌" not in cleaned_text
        assert "[[" not in cleaned_text
        assert "![[" not in cleaned_text
        assert "Important: Check Other Note" in cleaned_text
