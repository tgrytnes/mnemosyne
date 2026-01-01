"""
Unit tests for Obsidian Project Markdown Serialization/Parsing (Story 016)

Tests the bidirectional conversion between SQL project records and Obsidian
markdown files with YAML frontmatter.

TDD Approach: These tests are written BEFORE implementation (RED phase).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


# ==============================================================================
# Test Fixtures
# ==============================================================================

@pytest.fixture
def sample_project_dict():
    """Sample project data from SQL"""
    return {
        'id': 42,
        'title': 'Implement Dark Mode Toggle',
        'description': 'Add a dark mode toggle to the application settings page',
        'discovered_by': 'latent_scout',
        'discovery_id': 'disco_20260101_001',
        'cluster_ids': ['cluster_theme_001', 'cluster_ui_002'],
        'confidence_score': 0.89,
        'status': 'active',
        'importance': 5,
        'urgency': 4,
        'deadline': datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        'work_estimate': 20,
        'pressure_score': 1.25,
        'verified_by_user': True,
        'created_at': datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        'updated_at': datetime(2026, 1, 1, 14, 30, 0, tzinfo=timezone.utc),
        'obsidian_file_path': 'Projects/Implement-dark-mode-toggle.md',
        'last_synced_to_obsidian': datetime(2026, 1, 1, 14, 30, 0, tzinfo=timezone.utc),
        'last_synced_from_obsidian': None,
    }


@pytest.fixture
def expected_markdown():
    """Expected markdown output for sample project"""
    return """---
id: 42
title: Implement Dark Mode Toggle
discovered_by: latent_scout
discovery_id: disco_20260101_001
cluster_ids:
  - cluster_theme_001
  - cluster_ui_002
confidence_score: 0.89
status: active
importance: 5
urgency: 4
deadline: 2026-12-31T23:59:59+00:00
work_estimate: 20
pressure_score: 1.25
verified_by_user: true
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T14:30:00+00:00
---

# Implement Dark Mode Toggle

Add a dark mode toggle to the application settings page

## Metadata

- **Status**: active
- **Importance**: 5/5
- **Urgency**: 4/5
- **Deadline**: 2026-12-31
- **Work Estimate**: 20 hours
- **Pressure Score**: 1.25

## Discovery Info

- **Discovered by**: latent_scout
- **Discovery ID**: disco_20260101_001
- **Confidence**: 89%
- **Verified**: Yes

## Timestamps

- **Created**: 2026-01-01 10:00:00 UTC
- **Updated**: 2026-01-01 14:30:00 UTC
"""


# ==============================================================================
# Markdown Serialization Tests
# ==============================================================================

class TestMarkdownSerialization:
    """Test SQL project dict → Obsidian markdown conversion"""

    def test_serialize_complete_project(self, sample_project_dict, expected_markdown):
        """Test serializing a complete project to markdown"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import serialize_project

        markdown = serialize_project(sample_project_dict)

        assert markdown == expected_markdown

    def test_serialize_minimal_project(self):
        """Test serializing a minimal project (only required fields)"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import serialize_project

        minimal_project = {
            'id': 1,
            'title': 'Minimal Project',
            'description': 'Basic description',
            'discovered_by': 'latent_scout',
            'discovery_id': 'disco_001',
            'cluster_ids': ['cluster_1'],
            'confidence_score': 0.75,
            'status': 'candidate',
            'created_at': datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            'updated_at': datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        }

        markdown = serialize_project(minimal_project)

        # Should have frontmatter
        assert '---' in markdown
        assert 'id: 1' in markdown
        assert 'title: Minimal Project' in markdown

        # Should have body
        assert '# Minimal Project' in markdown
        assert 'Basic description' in markdown

        # Optional fields should not appear when None
        assert 'importance:' not in markdown
        assert 'urgency:' not in markdown
        assert 'deadline:' not in markdown

    def test_serialize_with_null_optional_fields(self):
        """Test that None values for optional fields are handled correctly"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import serialize_project

        project = {
            'id': 2,
            'title': 'Test Project',
            'description': 'Test',
            'discovered_by': 'test',
            'discovery_id': 'disco_002',
            'cluster_ids': ['c1'],
            'confidence_score': 0.80,
            'status': 'candidate',
            'importance': None,  # NULL
            'urgency': None,  # NULL
            'deadline': None,  # NULL
            'work_estimate': None,  # NULL
            'pressure_score': None,  # NULL
            'created_at': datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            'updated_at': datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        }

        markdown = serialize_project(project)

        # None values should be omitted from frontmatter
        assert 'importance:' not in markdown or 'importance: null' not in markdown
        assert 'urgency:' not in markdown or 'urgency: null' not in markdown

    def test_serialize_escapes_special_yaml_characters(self):
        """Test that special YAML characters in strings are properly escaped"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import serialize_project

        project = {
            'id': 3,
            'title': 'Project: With Special Characters',
            'description': 'Contains: colons, "quotes", and #hashtags',
            'discovered_by': 'test',
            'discovery_id': 'disco_003',
            'cluster_ids': ['c1'],
            'confidence_score': 0.80,
            'status': 'active',
            'created_at': datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            'updated_at': datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
        }

        markdown = serialize_project(project)

        # Special characters should be properly quoted in YAML
        assert 'title:' in markdown
        # YAML should handle the string correctly (either quoted or escaped)
        assert 'Project: With Special Characters' in markdown or '"Project: With Special Characters"' in markdown

    def test_serialize_formats_datetimes_iso(self):
        """Test that datetime fields are formatted as ISO 8601 strings"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import serialize_project

        project = {
            'id': 4,
            'title': 'Test',
            'description': 'Test',
            'discovered_by': 'test',
            'discovery_id': 'disco_004',
            'cluster_ids': ['c1'],
            'confidence_score': 0.80,
            'status': 'active',
            'deadline': datetime(2026, 6, 15, 12, 30, 45, tzinfo=timezone.utc),
            'created_at': datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            'updated_at': datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc),
        }

        markdown = serialize_project(project)

        # Datetimes should be ISO 8601 format
        assert '2026-06-15T12:30:45+00:00' in markdown  # deadline
        assert '2026-01-01T10:00:00+00:00' in markdown  # created_at
        assert '2026-01-01T11:00:00+00:00' in markdown  # updated_at


# ==============================================================================
# Markdown Parsing Tests
# ==============================================================================

class TestMarkdownParsing:
    """Test Obsidian markdown → SQL project dict conversion"""

    def test_parse_complete_markdown(self, expected_markdown):
        """Test parsing a complete Obsidian markdown file"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import parse_project_markdown

        project = parse_project_markdown(expected_markdown)

        assert project['id'] == 42
        assert project['title'] == 'Implement Dark Mode Toggle'
        assert project['description'] == 'Add a dark mode toggle to the application settings page'
        assert project['status'] == 'active'
        assert project['importance'] == 5
        assert project['urgency'] == 4
        assert project['work_estimate'] == 20
        assert project['pressure_score'] == 1.25
        assert project['confidence_score'] == 0.89
        assert project['discovered_by'] == 'latent_scout'
        assert project['discovery_id'] == 'disco_20260101_001'
        assert project['cluster_ids'] == ['cluster_theme_001', 'cluster_ui_002']

    def test_parse_minimal_markdown(self):
        """Test parsing markdown with only required fields"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import parse_project_markdown

        minimal_md = """---
id: 1
title: Minimal Project
discovered_by: test
discovery_id: disco_001
cluster_ids:
  - c1
confidence_score: 0.75
status: candidate
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T10:00:00+00:00
---

# Minimal Project

Basic description
"""

        project = parse_project_markdown(minimal_md)

        assert project['id'] == 1
        assert project['title'] == 'Minimal Project'
        assert project['description'] == 'Basic description'

        # Optional fields should be None
        assert project.get('importance') is None
        assert project.get('urgency') is None
        assert project.get('deadline') is None

    def test_parse_extracts_description_from_body(self):
        """Test that description is extracted from markdown body (after title)"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import parse_project_markdown

        markdown = """---
id: 5
title: Test Project
status: active
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T10:00:00+00:00
discovered_by: test
discovery_id: disco_005
cluster_ids: [c1]
confidence_score: 0.8
---

# Test Project

This is the project description.
It can span multiple paragraphs.

## Metadata
More content here
"""

        project = parse_project_markdown(markdown)

        # Description should be extracted from the body (between title and first ## header)
        expected_desc = "This is the project description.\nIt can span multiple paragraphs."
        assert expected_desc in project['description'] or project['description'].strip() == expected_desc.strip()

    def test_parse_converts_iso_datetimes(self):
        """Test that ISO datetime strings are converted to datetime objects"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import parse_project_markdown

        markdown = """---
id: 6
title: Test
status: active
deadline: 2026-12-31T23:59:59+00:00
created_at: 2026-01-01T10:00:00+00:00
updated_at: 2026-01-01T11:00:00+00:00
discovered_by: test
discovery_id: disco_006
cluster_ids: [c1]
confidence_score: 0.8
---

# Test
Description
"""

        project = parse_project_markdown(markdown)

        assert isinstance(project['deadline'], datetime)
        assert project['deadline'].year == 2026
        assert project['deadline'].month == 12
        assert project['deadline'].day == 31

        assert isinstance(project['created_at'], datetime)
        assert isinstance(project['updated_at'], datetime)

    def test_parse_handles_missing_frontmatter(self):
        """Test that files without frontmatter raise an error"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import parse_project_markdown

        markdown_without_frontmatter = """
# Some Project

This has no frontmatter
"""

        with pytest.raises(ValueError, match="No YAML frontmatter found"):
            parse_project_markdown(markdown_without_frontmatter)

    def test_parse_handles_invalid_yaml(self):
        """Test that invalid YAML in frontmatter raises an error"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import parse_project_markdown

        invalid_yaml = """---
id: 7
title: Test
this is: invalid: yaml:
---

# Test
"""

        with pytest.raises(ValueError, match="Invalid YAML"):
            parse_project_markdown(invalid_yaml)


# ==============================================================================
# Roundtrip Tests
# ==============================================================================

class TestMarkdownRoundtrip:
    """Test that serialize → parse → serialize produces identical results"""

    def test_roundtrip_preserves_data(self, sample_project_dict):
        """Test that roundtrip conversion preserves all data"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import serialize_project, parse_project_markdown

        # Serialize to markdown
        markdown = serialize_project(sample_project_dict)

        # Parse back to dict
        parsed = parse_project_markdown(markdown)

        # Compare key fields (exclude sync timestamps which may not roundtrip)
        assert parsed['id'] == sample_project_dict['id']
        assert parsed['title'] == sample_project_dict['title']
        assert parsed['description'] == sample_project_dict['description']
        assert parsed['status'] == sample_project_dict['status']
        assert parsed['importance'] == sample_project_dict['importance']
        assert parsed['urgency'] == sample_project_dict['urgency']
        assert parsed['work_estimate'] == sample_project_dict['work_estimate']

    def test_roundtrip_markdown_stability(self, sample_project_dict):
        """Test that serialize → parse → serialize produces same markdown"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import serialize_project, parse_project_markdown

        # First serialization
        markdown1 = serialize_project(sample_project_dict)

        # Parse and re-serialize
        parsed = parse_project_markdown(markdown1)
        markdown2 = serialize_project(parsed)

        # Should produce identical markdown (or at least semantically equivalent)
        # Note: YAML ordering might differ, so we check key content
        assert '# Implement Dark Mode Toggle' in markdown2
        assert 'importance: 5' in markdown2
        assert 'urgency: 4' in markdown2


# ==============================================================================
# File Path Generation Tests
# ==============================================================================

class TestFilePathGeneration:
    """Test generating Obsidian file paths from project titles"""

    def test_sanitize_title_for_filename(self):
        """Test that project titles are sanitized for use in file paths"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import sanitize_title_for_filename

        # Regular title
        assert sanitize_title_for_filename('My Project') == 'My-project'

        # Special characters
        assert sanitize_title_for_filename('Project: With / Slashes') == 'Project-With-Slashes'

        # Multiple spaces
        assert sanitize_title_for_filename('Project  With   Spaces') == 'Project-With-Spaces'

        # Leading/trailing spaces
        assert sanitize_title_for_filename('  Spaces  ') == 'Spaces'

        # Unicode characters
        assert sanitize_title_for_filename('Café Project') == 'Café-project'

        # Long titles should be truncated
        long_title = 'A' * 200
        sanitized = sanitize_title_for_filename(long_title)
        assert len(sanitized) <= 100  # Reasonable filename length

    def test_generate_obsidian_path(self):
        """Test generating full Obsidian file path"""
        from mnemosyne.aletheia.obsidian_sync.project_markdown import generate_obsidian_path

        # Simple title
        path = generate_obsidian_path('My Project', project_id=42)
        assert path == 'Projects/My-project.md'

        # With special characters
        path = generate_obsidian_path('Fix: Bug in API', project_id=100)
        assert path == 'Projects/Fix-Bug-in-API.md'

        # Should include project_id if title collision risk
        path1 = generate_obsidian_path('Same Title', project_id=1)
        path2 = generate_obsidian_path('Same Title', project_id=2)
        # Paths should be based on title, but we track by ID to handle renames
        assert 'Same-title.md' in path1.lower()
