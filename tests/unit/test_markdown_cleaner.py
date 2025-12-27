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
