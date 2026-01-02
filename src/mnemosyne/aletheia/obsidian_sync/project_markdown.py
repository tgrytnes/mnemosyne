"""
Obsidian Project Markdown Serialization/Parsing (Story 016)

Bidirectional conversion between SQL project records and Obsidian markdown files
with YAML frontmatter.

This module handles:
- Serializing SQL project dicts to Obsidian markdown (SQL → Obsidian)
- Parsing Obsidian markdown back to SQL project dicts (Obsidian → SQL)
- File path generation from project titles
- Roundtrip data preservation
"""

import re
from datetime import datetime
from typing import Any

import yaml


# Custom YAML representer to output ISO datetime strings without quotes
def _datetime_representer(dumper, data):
    """Represent datetime as unquoted ISO string in YAML"""
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="")


# Register the custom representer for strings (to avoid quoting ISO datetimes)
yaml.add_representer(str, _datetime_representer)


# ==============================================================================
# Serialization (SQL → Obsidian Markdown)
# ==============================================================================


def serialize_project(project: dict[str, Any]) -> str:
    """
    Serialize a SQL project dict to Obsidian markdown with YAML frontmatter.

    Args:
        project: Project dict from The Ananke (PostgreSQL)

    Returns:
        Markdown string with YAML frontmatter

    Example:
        ```python
        project = {
            'id': 42,
            'title': 'Implement Dark Mode',
            'description': 'Add dark mode toggle',
            'status': 'active',
            'importance': 5,
            'urgency': 4,
            # ... more fields ...
        }
        markdown = serialize_project(project)
        ```
    """
    # Build frontmatter dict in specific order (matches test expectations)
    # Order: id, title, discovered_by, discovery_id, cluster_ids, confidence_score,
    # status, importance, urgency, deadline, work_estimate, pressure_score,
    # verified_by_user, created_at, updated_at
    frontmatter = {}

    # Required fields (always include)
    frontmatter["id"] = project["id"]
    frontmatter["title"] = project["title"]
    frontmatter["discovered_by"] = project["discovered_by"]
    frontmatter["discovery_id"] = project["discovery_id"]
    frontmatter["cluster_ids"] = project["cluster_ids"]
    frontmatter["confidence_score"] = project["confidence_score"]
    frontmatter["status"] = project["status"]

    # Optional fields (only include if not None)
    _add_optional_field(frontmatter, project, "importance")
    _add_optional_field(frontmatter, project, "urgency")
    _add_optional_field(frontmatter, project, "deadline", formatter=_format_datetime)
    _add_optional_field(frontmatter, project, "work_estimate")
    _add_optional_field(frontmatter, project, "pressure_score")
    _add_optional_field(frontmatter, project, "verified_by_user")

    # Timestamps (always include, format as ISO 8601)
    frontmatter["created_at"] = _format_datetime(project["created_at"])
    frontmatter["updated_at"] = _format_datetime(project["updated_at"])

    # Serialize frontmatter to YAML with proper indentation
    yaml_str = yaml.dump(
        frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False, indent=2
    )

    # Build markdown body
    title = project["title"]
    description = project.get("description", "")

    body_parts = [
        f"# {title}",
        "",
        description,
        "",
    ]

    # Add Metadata section if we have optional fields
    if any(
        project.get(f) is not None
        for f in ["importance", "urgency", "deadline", "work_estimate", "pressure_score"]
    ):
        body_parts.append("## Metadata")
        body_parts.append("")

        if project.get("status"):
            body_parts.append(f"- **Status**: {project['status']}")

        if project.get("importance") is not None:
            body_parts.append(f"- **Importance**: {project['importance']}/5")

        if project.get("urgency") is not None:
            body_parts.append(f"- **Urgency**: {project['urgency']}/5")

        if project.get("deadline"):
            deadline_date = project["deadline"]
            if isinstance(deadline_date, datetime):
                deadline_str = deadline_date.strftime("%Y-%m-%d")
            else:
                deadline_str = str(deadline_date)
            body_parts.append(f"- **Deadline**: {deadline_str}")

        if project.get("work_estimate") is not None:
            body_parts.append(f"- **Work Estimate**: {project['work_estimate']} hours")

        if project.get("pressure_score") is not None:
            body_parts.append(f"- **Pressure Score**: {project['pressure_score']}")

        body_parts.append("")

    # Add Discovery Info section
    body_parts.append("## Discovery Info")
    body_parts.append("")
    body_parts.append(f"- **Discovered by**: {project['discovered_by']}")
    body_parts.append(f"- **Discovery ID**: {project['discovery_id']}")

    confidence_pct = int(project["confidence_score"] * 100)
    body_parts.append(f"- **Confidence**: {confidence_pct}%")

    if project.get("verified_by_user") is not None:
        verified_str = "Yes" if project["verified_by_user"] else "No"
        body_parts.append(f"- **Verified**: {verified_str}")

    body_parts.append("")

    # Add Timestamps section
    body_parts.append("## Timestamps")
    body_parts.append("")

    created_str = _format_datetime_display(project["created_at"])
    updated_str = _format_datetime_display(project["updated_at"])

    body_parts.append(f"- **Created**: {created_str}")
    body_parts.append(f"- **Updated**: {updated_str}")
    body_parts.append("")

    body = "\n".join(body_parts)

    # Combine frontmatter and body
    markdown = f"---\n{yaml_str}---\n\n{body}"

    return markdown


def _add_optional_field(
    frontmatter: dict[str, Any], project: dict[str, Any], field_name: str, formatter=None
):
    """Add optional field to frontmatter if not None"""
    value = project.get(field_name)
    if value is not None:
        if formatter:
            value = formatter(value)
        frontmatter[field_name] = value


def _format_datetime(dt: datetime | None) -> str | None:
    """Format datetime as ISO 8601 string"""
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def _format_datetime_display(dt: datetime | None) -> str:
    """Format datetime for human-readable display"""
    if dt is None:
        return "N/A"
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    return str(dt)


# ==============================================================================
# Parsing (Obsidian Markdown → SQL Dict)
# ==============================================================================


def parse_project_markdown(markdown: str) -> dict[str, Any]:
    """
    Parse Obsidian markdown with YAML frontmatter back to SQL project dict.

    Args:
        markdown: Markdown string with YAML frontmatter

    Returns:
        Project dict suitable for SQL updates

    Raises:
        ValueError: If frontmatter is missing or invalid

    Example:
        ```python
        markdown = '''---
        id: 42
        title: Test
        ---
        # Test
        Description
        '''
        project = parse_project_markdown(markdown)
        # project['id'] == 42
        ```
    """
    # Extract frontmatter
    frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", markdown, re.DOTALL)

    if not frontmatter_match:
        raise ValueError("No YAML frontmatter found in markdown")

    frontmatter_str = frontmatter_match.group(1)

    # Parse YAML
    try:
        frontmatter = yaml.safe_load(frontmatter_str)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in frontmatter: {e}")

    if not isinstance(frontmatter, dict):
        raise ValueError("Frontmatter must be a YAML dict")

    # Extract description from body (text after title, before first ## header)
    body = markdown[frontmatter_match.end() :]

    # Find title line (starts with # )
    title_match = re.search(r"^# (.+)$", body, re.MULTILINE)

    if title_match:
        # Extract everything between title and first ## header
        after_title = body[title_match.end() :].strip()

        # Find first ## header
        section_match = re.search(r"^## ", after_title, re.MULTILINE)

        if section_match:
            description = after_title[: section_match.start()].strip()
        else:
            # No sections, take everything after title
            description = after_title
    else:
        # No title found, use empty description
        description = ""

    # Build project dict
    project = {
        "id": frontmatter["id"],
        "title": frontmatter["title"],
        "description": description,
        "discovered_by": frontmatter["discovered_by"],
        "discovery_id": frontmatter["discovery_id"],
        "cluster_ids": frontmatter["cluster_ids"],
        "confidence_score": frontmatter["confidence_score"],
        "status": frontmatter["status"],
        "created_at": _parse_datetime(frontmatter["created_at"]),
        "updated_at": _parse_datetime(frontmatter["updated_at"]),
    }

    # Optional fields
    _add_optional_parsed_field(project, frontmatter, "importance")
    _add_optional_parsed_field(project, frontmatter, "urgency")
    _add_optional_parsed_field(project, frontmatter, "deadline", parser=_parse_datetime)
    _add_optional_parsed_field(project, frontmatter, "work_estimate")
    _add_optional_parsed_field(project, frontmatter, "pressure_score")
    _add_optional_parsed_field(project, frontmatter, "verified_by_user")

    return project


def _add_optional_parsed_field(
    project: dict[str, Any], frontmatter: dict[str, Any], field_name: str, parser=None
):
    """Add optional field from frontmatter to project dict"""
    if field_name in frontmatter:
        value = frontmatter[field_name]
        if parser:
            value = parser(value)
        project[field_name] = value
    else:
        project[field_name] = None


def _parse_datetime(dt_str: str | datetime | None) -> datetime | None:
    """Parse ISO 8601 datetime string to datetime object"""
    if dt_str is None:
        return None

    if isinstance(dt_str, datetime):
        return dt_str

    # Parse ISO 8601 string
    # Handle formats like: 2026-12-31T23:59:59+00:00
    try:
        return datetime.fromisoformat(dt_str)
    except (ValueError, AttributeError):
        return None


# ==============================================================================
# File Path Generation
# ==============================================================================


def sanitize_title_for_filename(title: str, max_length: int = 100) -> str:
    """
    Sanitize project title for use in file path.

    Args:
        title: Project title
        max_length: Maximum filename length (default 100)

    Returns:
        Sanitized filename-safe string

    Example:
        >>> sanitize_title_for_filename('My Project')
        'My-project'
        >>> sanitize_title_for_filename('Project: With / Slashes')
        'Project-With-Slashes'
    """
    # Remove leading/trailing whitespace
    title = title.strip()

    # Replace multiple spaces with single space
    title = re.sub(r"\s+", " ", title)

    # Split on spaces to get original words
    original_words = title.split(" ")

    # Process each word: remove special chars, apply title case to each word
    processed_words = []
    for i, word in enumerate(original_words):
        # Remove special characters from this word
        cleaned = re.sub(r"[^\w]", "", word, flags=re.UNICODE)

        if not cleaned:
            continue

        # Apply title case with special handling
        if word.islower() and len(word) <= 3:
            # Keep short lowercase words lowercase (articles, prepositions like 'in', 'the', 'of')
            cleaned = cleaned.lower()
        elif word.isupper() and len(cleaned) > 1:
            # Keep all-caps acronyms as-is (like 'API', 'HTTP')
            cleaned = cleaned.upper()
        elif i == 0:
            # First word: always capitalize first letter
            cleaned = (
                cleaned[0].upper() + cleaned[1:].lower() if len(cleaned) > 1 else cleaned.upper()
            )
        else:
            # Other words: apply title case (capitalize first letter)
            cleaned = (
                cleaned[0].upper() + cleaned[1:].lower() if len(cleaned) > 1 else cleaned.upper()
            )

        processed_words.append(cleaned)

    # Join with hyphens
    title = "-".join(processed_words)

    # Truncate to max length
    if len(title) > max_length:
        title = title[:max_length].rstrip("-")

    return title


def generate_obsidian_path(title: str, project_id: int, projects_folder: str = "Projects") -> str:
    """
    Generate Obsidian file path from project title.

    Args:
        title: Project title
        project_id: Project ID (for tracking, not used in filename)
        projects_folder: Folder name for projects (default "Projects")

    Returns:
        Relative file path within Obsidian vault

    Example:
        >>> generate_obsidian_path('My Project', 42)
        'Projects/My-project.md'
    """
    filename = sanitize_title_for_filename(title)
    return f"{projects_folder}/{filename}.md"
