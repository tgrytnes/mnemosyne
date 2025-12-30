#!/usr/bin/env python3
"""
Build a local, machine-readable story index for VS Code and automation.

Usage:
  .venv/bin/python scripts/build_story_index.py
  .venv/bin/python scripts/build_story_index.py --no-linear
  .venv/bin/python scripts/build_story_index.py --output user-stories/stories.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import requests
    from dotenv import load_dotenv
except ImportError:  # Optional when running without Linear sync
    requests = None
    load_dotenv = None

LINEAR_API_URL = "https://api.linear.app/graphql"


@dataclass(frozen=True)
class Story:
    number: int
    title: str
    short_title: str
    file_path: str
    phase: str | None
    phase_slug: str | None
    user_story: dict[str, str] | None
    acceptance_criteria: list[dict[str, Any]]
    priority: dict[str, str] | None
    estimate: dict[str, Any] | None
    linear_labels: list[str]
    related_stories: list[int]


def normalize_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


def extract_section(content: str, header: str) -> str:
    pattern = rf"## {re.escape(header)}\s*\n(.+?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


def extract_title(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def extract_user_story(content: str) -> dict[str, str] | None:
    match = re.search(
        r"\*\*As a\*\*\s+(.+?)\n\*\*I want\*\*\s+(.+?)\n\*\*So that\*\*\s+(.+)",
        content,
        re.DOTALL,
    )
    if not match:
        return None
    return {
        "as_a": normalize_whitespace(match.group(1)),
        "i_want": normalize_whitespace(match.group(2)),
        "so_that": normalize_whitespace(match.group(3)),
    }


def parse_acceptance_criteria(content: str) -> list[dict[str, Any]]:
    section = extract_section(content, "Acceptance Criteria")
    if not section:
        return []

    items = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("-"):
            continue
        checkbox_match = re.match(r"- \[(?P<state>[ xX])\]\s+(?P<text>.+)", line)
        if checkbox_match:
            checked = checkbox_match.group("state").lower() == "x"
            text = checkbox_match.group("text").strip()
        else:
            checked = False
            text = line.lstrip("-").strip()
        if text:
            items.append({"text": text, "checked": checked})
    return items


def parse_priority(content: str) -> dict[str, str] | None:
    section = extract_section(content, "Priority")
    if not section:
        return None
    first_line = section.splitlines()[0].strip()
    if not first_line:
        return None
    level_match = re.search(r"\*\*(.+?)\*\*", first_line)
    level = level_match.group(1).strip() if level_match else None
    return {"raw": first_line, "level": level} if level else {"raw": first_line}


def parse_estimate(content: str) -> dict[str, Any] | None:
    section = extract_section(content, "Estimate")
    if not section:
        return None
    first_line = section.splitlines()[0].strip()
    if not first_line:
        return None
    points_match = re.match(r"(\d+)\s+story points", first_line)
    points = int(points_match.group(1)) if points_match else None
    estimate = {"raw": first_line}
    if points is not None:
        estimate["story_points"] = points
    return estimate


def parse_linear_labels(content: str) -> list[str]:
    section = extract_section(content, "Linear Labels")
    if not section:
        return []
    labels = [label.strip() for label in re.findall(r"`([^`]+)`", section)]
    if not labels:
        labels = [label.strip() for label in section.split(",") if label.strip()]
    return labels


def parse_related_stories(content: str, story_number: int) -> list[int]:
    related = [int(value) for value in re.findall(r"Story (\d+)", content)]
    return [value for value in related if value != story_number]


def parse_phase(file_path: Path) -> tuple[str | None, str | None]:
    for part in file_path.parts:
        if part.startswith("phase-"):
            match = re.match(r"phase-(\d+)", part)
            if match:
                return f"Phase {match.group(1)}", part
    return None, None


def load_stories(project_root: Path) -> list[Story]:
    stories = []
    for path in sorted(project_root.glob("user-stories/**/story-*.md")):
        match = re.search(r"story-(\d+)", path.name)
        if not match:
            continue
        number = int(match.group(1))
        content = path.read_text(encoding="utf-8")
        title = extract_title(content, path.stem)
        short_title = re.sub(r"^Story\s+\d+\s*:\s*", "", title, flags=re.IGNORECASE).strip()
        phase, phase_slug = parse_phase(path)
        story = Story(
            number=number,
            title=title,
            short_title=short_title,
            file_path=str(path.relative_to(project_root)),
            phase=phase,
            phase_slug=phase_slug,
            user_story=extract_user_story(content),
            acceptance_criteria=parse_acceptance_criteria(content),
            priority=parse_priority(content),
            estimate=parse_estimate(content),
            linear_labels=parse_linear_labels(content),
            related_stories=parse_related_stories(content, number),
        )
        stories.append(story)
    return sorted(stories, key=lambda item: item.number)


def fetch_linear_story_map(team_hint: str | None) -> dict[int, dict[str, str]]:
    if requests is None or load_dotenv is None:
        raise RuntimeError("requests/python-dotenv not installed; install to use Linear sync")

    load_dotenv(dotenv_path=Path(".env"), override=False)
    api_key = os.getenv("LINEAR_API_KEY")
    if not api_key:
        return {}

    headers = {"Authorization": api_key, "Content-Type": "application/json"}

    def graphql(query: str, variables: dict | None = None) -> dict:
        response = requests.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables or {}},
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise RuntimeError(data["errors"])
        return data["data"]

    team_query = """
    query {
        teams {
            nodes { id name }
        }
    }
    """
    teams = graphql(team_query)["teams"]["nodes"]
    if not teams:
        return {}

    team = None
    if team_hint:
        team = next(
            (item for item in teams if item["id"] == team_hint or item["name"] == team_hint),
            None,
        )
        if team is None:
            raise RuntimeError(f"Team '{team_hint}' not found in Linear workspace")
    else:
        team = next((item for item in teams if item["name"] == "Project_Mnemosyne"), teams[0])

    issues_query = """
    query($teamId: String!) {
        team(id: $teamId) {
            issues {
                nodes {
                    id
                    identifier
                    title
                    url
                    state { name type }
                }
            }
        }
    }
    """
    issues = graphql(issues_query, {"teamId": team["id"]})["team"]["issues"]["nodes"]

    story_map: dict[int, dict[str, str]] = {}
    for issue in issues:
        match = re.match(r"Story\s+(\d+):", issue["title"])
        if not match:
            continue
        number = int(match.group(1))
        story_map[number] = {
            "id": issue["id"],
            "identifier": issue["identifier"],
            "title": issue["title"],
            "url": issue["url"],
            "state": issue["state"]["name"],
            "state_type": issue["state"]["type"],
        }
    return story_map


def story_to_dict(story: Story, linear_map: dict[int, dict[str, str]]) -> dict[str, Any]:
    data = {
        "number": story.number,
        "id": f"{story.number:03d}",
        "title": story.title,
        "short_title": story.short_title,
        "phase": story.phase,
        "phase_slug": story.phase_slug,
        "file_path": story.file_path,
        "user_story": story.user_story,
        "acceptance_criteria": story.acceptance_criteria,
        "priority": story.priority,
        "estimate": story.estimate,
        "linear_labels": story.linear_labels,
        "related_stories": story.related_stories,
    }
    linear_info = linear_map.get(story.number)
    if linear_info:
        data["linear"] = linear_info
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local story index.")
    parser.add_argument(
        "--output",
        default="user-stories/stories.json",
        help="Output JSON path (default: user-stories/stories.json)",
    )
    parser.add_argument("--team", help="Linear team id or name")
    parser.add_argument("--no-linear", action="store_true", help="Skip Linear status lookup")
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent
    stories = load_stories(project_root)
    if not stories:
        print("No stories found under user-stories/")
        return 1

    linear_map: dict[int, dict[str, str]] = {}
    if not args.no_linear:
        try:
            linear_map = fetch_linear_story_map(args.team)
        except RuntimeError as exc:
            print(f"Linear lookup skipped: {exc}")

    index = {
        "stories": [story_to_dict(story, linear_map) for story in stories],
    }

    output_path = project_root / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
