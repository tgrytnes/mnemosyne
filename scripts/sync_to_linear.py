#!/usr/bin/env python3
"""
Sync local user story definitions into Linear.

This script reads user story markdown files and ensures Linear issues are
created or updated to match the local titles, descriptions, and labels.

Usage:
    .venv/bin/python scripts/sync_to_linear.py
"""

from __future__ import annotations

import argparse
import os
import re
from dataclasses import dataclass
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_API_URL = "https://api.linear.app/graphql"

LABEL_MAP = {
    "phase-0": "Phase 0",
    "phase-1": "Phase 1",
    "phase-2": "Phase 2",
    "phase-3": "Phase 3",
    "phase-4": "Phase 4",
    "phase-5": "Phase 5",
    "aletheia": "Aletheia",
    "alexandria": "Alexandria",
    "argus": "Argus",
    "iris": "Iris",
    "hermes": "Hermes",
    "prometheus": "Prometheus",
}

LABEL_COLORS = {
    "Phase 0": "#FF6B6B",
    "Phase 1": "#4ECDC4",
    "Phase 2": "#45B7D1",
    "Phase 3": "#96CEB4",
    "Phase 4": "#FFEAA7",
    "Phase 5": "#DFE6E9",
    "Aletheia": "#A8E6CF",
    "Alexandria": "#FFD3B6",
    "Argus": "#FFAAA5",
    "Iris": "#AA9CFF",
    "Hermes": "#90DBF4",
    "Prometheus": "#D1C4E9",
}


@dataclass(frozen=True)
class Story:
    number: int
    title: str
    short_title: str
    description: str
    labels: list[str]
    related_stories: list[int]
    file_path: str
    normalized_title: str


def normalize_title(title: str) -> str:
    cleaned = re.sub(r"^Story\s+\d+\s*:\s*", "", title, flags=re.IGNORECASE)
    cleaned = cleaned.strip().lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return " ".join(cleaned.split())


def extract_title(content: str, fallback: str) -> str:
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else fallback


def extract_user_story(content: str) -> str:
    match = re.search(
        r"\*\*As a\*\*\s+(.+?)\n\*\*I want\*\*\s+(.+?)\n\*\*So that\*\*\s+(.+)",
        content,
        re.DOTALL,
    )
    if not match:
        return ""
    return (
        f"**As a** {match.group(1).strip()}\n"
        f"**I want** {match.group(2).strip()}\n"
        f"**So that** {match.group(3).strip()}\n\n"
    )


def extract_section(content: str, header: str) -> str:
    pattern = rf"## {re.escape(header)}\s*\n(.+?)(?=\n##|\Z)"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


def build_description(content: str) -> str:
    user_story = extract_user_story(content)
    acceptance_criteria = extract_section(content, "Acceptance Criteria")
    technical_notes = extract_section(content, "Technical Notes")

    description = user_story
    if acceptance_criteria:
        description += "## Acceptance Criteria\n" + acceptance_criteria + "\n\n"
    if technical_notes:
        description += "## Technical Notes\n" + technical_notes[:2000] + "\n"

    return description.strip()


def extract_labels(content: str) -> list[str]:
    labels_section = extract_section(content, "Linear Labels")
    if not labels_section:
        return []

    labels = [label.strip() for label in re.findall(r"`([^`]+)`", labels_section)]
    if not labels:
        labels = [label.strip() for label in labels_section.split(",") if label.strip()]

    mapped_labels = []
    for label in labels:
        key = label.lower()
        mapped_labels.append(LABEL_MAP.get(key, label))

    seen = set()
    unique_labels = []
    for label in mapped_labels:
        if label in seen:
            continue
        seen.add(label)
        unique_labels.append(label)

    return unique_labels


def extract_related_stories(content: str, story_number: int) -> list[int]:
    related = [int(value) for value in re.findall(r"Story (\d+)", content)]
    return [value for value in related if value != story_number]


def parse_story_file(file_path: Path) -> Story | None:
    match = re.search(r"story-(\d+)", file_path.name)
    if not match:
        return None

    number = int(match.group(1))
    content = file_path.read_text(encoding="utf-8")
    title = extract_title(content, file_path.stem)
    short_title = re.sub(r"^Story\s+\d+\s*:\s*", "", title, flags=re.IGNORECASE).strip()

    description = build_description(content)
    labels = extract_labels(content)
    related = extract_related_stories(content, number)
    normalized_title = normalize_title(short_title)

    return Story(
        number=number,
        title=title,
        short_title=short_title,
        description=description,
        labels=labels,
        related_stories=related,
        file_path=str(file_path),
        normalized_title=normalized_title,
    )


def load_stories(project_root: Path) -> list[Story]:
    stories = []
    for file_path in sorted(project_root.glob("user-stories/**/story-*.md")):
        story = parse_story_file(file_path)
        if story:
            stories.append(story)
    return stories


class LinearSyncer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        self.team_id = None
        self.label_ids: dict[str, str] = {}

    def graphql_query(self, query: str, variables: dict | None = None) -> dict:
        response = requests.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables or {}},
            headers=self.headers,
        )
        response.raise_for_status()
        data = response.json()
        if "errors" in data:
            raise RuntimeError(f"GraphQL Error: {data['errors']}")
        return data["data"]

    def get_team_id(self, team_hint: str | None) -> str:
        query = """
        query {
            teams {
                nodes {
                    id
                    name
                }
            }
        }
        """
        data = self.graphql_query(query)
        teams = data["teams"]["nodes"]

        if not teams:
            raise RuntimeError("No teams found in workspace")

        if team_hint:
            for team in teams:
                if team_hint in (team["id"], team["name"]):
                    self.team_id = team["id"]
                    print(f"Selected team: {team['name']}")
                    return self.team_id
            raise RuntimeError(f"Team '{team_hint}' not found in Linear workspace")

        if len(teams) == 1:
            self.team_id = teams[0]["id"]
            print(f"Selected team: {teams[0]['name']}")
            return self.team_id

        print("Available teams:")
        for idx, team in enumerate(teams, 1):
            print(f"  {idx}. {team['name']} ({team['id']})")

        try:
            choice = input(f"Select team (1-{len(teams)}) [1]: ").strip() or "1"
        except EOFError:
            choice = "1"

        team_idx = int(choice) - 1
        self.team_id = teams[team_idx]["id"]
        print(f"Selected team: {teams[team_idx]['name']}")
        return self.team_id

    def load_labels(self):
        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                labels {
                    nodes {
                        id
                        name
                    }
                }
            }
        }
        """
        data = self.graphql_query(query, {"teamId": self.team_id})
        self.label_ids = {label["name"]: label["id"] for label in data["team"]["labels"]["nodes"]}

    def create_label(self, name: str) -> str:
        color = LABEL_COLORS.get(name, "#4E5AEC")
        mutation = """
        mutation($teamId: String!, $name: String!, $color: String!) {
            issueLabelCreate(input: {
                teamId: $teamId,
                name: $name,
                color: $color
            }) {
                issueLabel {
                    id
                    name
                }
            }
        }
        """
        data = self.graphql_query(
            mutation,
            {"teamId": self.team_id, "name": name, "color": color},
        )
        label_id = data["issueLabelCreate"]["issueLabel"]["id"]
        self.label_ids[name] = label_id
        return label_id

    def ensure_label_ids(self, labels: list[str]) -> list[str]:
        ids = []
        for label in labels:
            label_id = self.label_ids.get(label)
            if not label_id:
                label_id = self.create_label(label)
            ids.append(label_id)
        return ids

    def fetch_story_issues(self) -> list[dict]:
        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                issues {
                    nodes {
                        id
                        identifier
                        title
                        description
                        labels {
                            nodes {
                                id
                                name
                            }
                        }
                    }
                }
            }
        }
        """
        data = self.graphql_query(query, {"teamId": self.team_id})
        issues = data["team"]["issues"]["nodes"]

        story_issues = []
        for issue in issues:
            if re.match(r"Story\s+\d+:", issue["title"]):
                story_issues.append(issue)
        return story_issues

    def create_issue(self, title: str, description: str, label_ids: list[str]) -> dict:
        mutation = """
        mutation($teamId: String!, $title: String!, $description: String!, $labelIds: [String!]) {
            issueCreate(input: {
                teamId: $teamId,
                title: $title,
                description: $description,
                labelIds: $labelIds
            }) {
                issue {
                    id
                    identifier
                    title
                }
            }
        }
        """
        data = self.graphql_query(
            mutation,
            {
                "teamId": self.team_id,
                "title": title,
                "description": description,
                "labelIds": label_ids,
            },
        )
        return data["issueCreate"]["issue"]

    def update_issue(self, issue_id: str, title: str, description: str, label_ids: list[str]):
        mutation = """
        mutation($id: String!, $title: String!, $description: String!, $labelIds: [String!]) {
            issueUpdate(id: $id, input: {
                title: $title,
                description: $description,
                labelIds: $labelIds
            }) {
                issue {
                    id
                    identifier
                    title
                }
            }
        }
        """
        self.graphql_query(
            mutation,
            {
                "id": issue_id,
                "title": title,
                "description": description,
                "labelIds": label_ids,
            },
        )


def build_issue_title(story: Story) -> str:
    return f"Story {story.number:03d}: {story.short_title}"


def issue_needs_update(issue: dict, title: str, description: str, label_names: list[str]) -> bool:
    if issue["title"] != title:
        return True
    if (issue.get("description") or "").strip() != description.strip():
        return True

    existing_labels = {label["name"] for label in issue["labels"]["nodes"]}
    return set(label_names) != existing_labels


def sync_stories(syncer: LinearSyncer, stories: list[Story]) -> int:
    existing_issues = syncer.fetch_story_issues()
    existing_by_number = {}
    existing_by_title = {}

    for issue in existing_issues:
        match = re.match(r"Story\s+(\d+):", issue["title"])
        if match:
            existing_by_number[int(match.group(1))] = issue
        short_title = re.sub(r"^Story\s+\d+\s*:\s*", "", issue["title"], flags=re.IGNORECASE)
        normalized = normalize_title(short_title)
        existing_by_title.setdefault(normalized, []).append(issue)

    used_issue_ids = set()
    created = 0
    updated = 0
    renumbered = 0

    for story in stories:
        issue = None
        renumber = False

        if story.number in existing_by_number:
            issue = existing_by_number[story.number]
        else:
            matches = existing_by_title.get(story.normalized_title, [])
            matches = [candidate for candidate in matches if candidate["id"] not in used_issue_ids]
            if len(matches) == 1:
                issue = matches[0]
                renumber = True

        issue_title = build_issue_title(story)
        label_ids = syncer.ensure_label_ids(story.labels)

        if issue:
            used_issue_ids.add(issue["id"])
            if issue_needs_update(issue, issue_title, story.description, story.labels):
                syncer.update_issue(issue["id"], issue_title, story.description, label_ids)
                updated += 1
                if renumber:
                    renumbered += 1
                print(f"Updated {issue['identifier']} -> {issue_title}")
            else:
                print(f"Up-to-date: {issue['identifier']} -> {issue_title}")
            continue

        new_issue = syncer.create_issue(issue_title, story.description, label_ids)
        created += 1
        print(f"Created {new_issue['identifier']} -> {issue_title}")

    print(f"\nSync complete: {created} created, {updated} updated ({renumbered} renumbered).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync local stories to Linear.")
    parser.add_argument("--team", help="Linear team id or name")
    args = parser.parse_args()

    if not LINEAR_API_KEY:
        print("Error: LINEAR_API_KEY not found in environment.")
        return 1

    project_root = Path(__file__).parent.parent
    stories = load_stories(project_root)
    if not stories:
        print("No story files found under user-stories/")
        return 1

    syncer = LinearSyncer(LINEAR_API_KEY)
    syncer.get_team_id(args.team)
    syncer.load_labels()

    return sync_stories(syncer, stories)


if __name__ == "__main__":
    raise SystemExit(main())
