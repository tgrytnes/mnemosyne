#!/usr/bin/env python3
"""
Import Mnemosyne user stories into Linear

This script reads all user story markdown files and creates Linear issues
with proper labels, descriptions, and relationships.

Requirements:
    pip install requests python-dotenv

Usage:
    1. Get your Linear API key from: https://linear.app/settings/api
    2. Add to .env: LINEAR_API_KEY=lin_api_xxx
    3. Run: python scripts/import_to_linear.py
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_API_URL = "https://api.linear.app/graphql"

# Story metadata
STORY_FILES = [
    # Phase 0: Ingestion & Hygiene (Week 1-2)
    ("user-stories/phase-0-ingestion-hygiene/story-000-obsidian-vault-ingestion.md", "Phase 0", 1),
    ("user-stories/phase-0-ingestion-hygiene/story-001-email-archive-ingestion.md", "Phase 0", 1),
    ("user-stories/phase-0-ingestion-hygiene/story-002-shadow-copy-hygiene.md", "Phase 0", 1),
    ("user-stories/phase-0-ingestion-hygiene/story-003-pdf-ocr-ingestion.md", "Phase 0", 2),

    # Phase 1: Semantic Extraction (Week 3-4)
    ("user-stories/phase-1-semantic-extraction/story-001-cluster-centroid-node.md", "Phase 1", 3),
    ("user-stories/phase-1-semantic-extraction/story-002-structured-metadata-synthesis.md", "Phase 1", 3),
    ("user-stories/phase-1-semantic-extraction/story-003-automated-graph-taxonomy.md", "Phase 1", 4),

    # Phase 2: Efficiency Engine (Week 5-6)
    ("user-stories/phase-2-efficiency-engine/story-004-checkpointed-knowledge.md", "Phase 2", 5),
    ("user-stories/phase-2-efficiency-engine/story-005-semantic-routing.md", "Phase 2", 5),
    ("user-stories/phase-2-efficiency-engine/story-006-delta-sync-node.md", "Phase 2", 6),

    # Phase 3: Showcase (Week 7)
    ("user-stories/phase-3-showcase/story-007-multi-turn-reasoning-loop.md", "Phase 3", 7),
    ("user-stories/phase-3-showcase/story-008-traceable-showcase.md", "Phase 3", 7),
    ("user-stories/phase-3-showcase/story-009-actionable-synthesis.md", "Phase 3", 7),

    # Phase 4: Latent Scout (Week 8-10)
    ("user-stories/phase-4-latent-scout/story-010-autonomous-pattern-detection.md", "Phase 4", 8),
    ("user-stories/phase-4-latent-scout/story-011-radar-vector-exploration.md", "Phase 4", 8),
    ("user-stories/phase-4-latent-scout/story-012-proactive-insight-notifications.md", "Phase 4", 9),
    ("user-stories/phase-4-latent-scout/story-013-discovery-feed-management.md", "Phase 4", 9),
    ("user-stories/phase-4-latent-scout/story-014-sql-project-gatekeeper.md", "Phase 4", 9),
    ("user-stories/phase-4-latent-scout/story-015-monitor-agent.md", "Phase 4", 10),
    ("user-stories/phase-4-latent-scout/story-016-project-manager-agent.md", "Phase 4", 10),

    # Phase 5: Vault Curation (Future)
    ("user-stories/phase-5-vault-curation/story-017-vault-curator-agent.md", "Phase 5", None),
    ("user-stories/phase-5-vault-curation/story-018-vault-editor-agent.md", "Phase 5", None),
]


class LinearImporter:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        self.team_id = None
        self.label_ids = {}
        self.created_issues = {}  # story_number -> issue_id

    def graphql_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """Execute GraphQL query against Linear API"""
        response = requests.post(
            LINEAR_API_URL,
            json={"query": query, "variables": variables or {}},
            headers=self.headers,
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            raise Exception(f"GraphQL Error: {data['errors']}")

        return data["data"]

    def get_team_id(self) -> str:
        """Get the first team ID from the workspace"""
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
            raise Exception("No teams found in workspace")

        # Let user choose team
        print("\n📋 Available teams:")
        for i, team in enumerate(teams, 1):
            print(f"  {i}. {team['name']} (ID: {team['id']})")

        # Auto-select if only one team, otherwise ask
        if len(teams) == 1:
            choice = "1"
            print(f"\nAuto-selecting only team: {teams[0]['name']}")
        else:
            try:
                choice = input(f"\nSelect team (1-{len(teams)}) [1]: ").strip() or "1"
            except EOFError:
                choice = "1"
                print("\nAuto-selecting first team (non-interactive mode)")

        team_idx = int(choice) - 1

        self.team_id = teams[team_idx]["id"]
        print(f"✓ Selected team: {teams[team_idx]['name']}\n")
        return self.team_id

    def create_label(self, name: str, color: str = "#4E5AEC") -> str:
        """Create or get label ID"""
        # Try to find existing label first
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

        for label in data["team"]["labels"]["nodes"]:
            if label["name"] == name:
                return label["id"]

        # Create new label
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
        data = self.graphql_query(mutation, {
            "teamId": self.team_id,
            "name": name,
            "color": color,
        })
        return data["issueLabelCreate"]["issueLabel"]["id"]

    def parse_story_file(self, file_path: Path) -> Dict:
        """Parse user story markdown file"""
        content = file_path.read_text()

        # Extract story number from filename
        story_match = re.search(r'story-(\d+)', file_path.name)
        story_number = int(story_match.group(1)) if story_match else None

        # Extract title (first line with #)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else file_path.stem

        # Extract user story (As a... I want... So that...)
        user_story_match = re.search(
            r'\*\*As a\*\*\s+(.+?)\n\*\*I want\*\*\s+(.+?)\n\*\*So that\*\*\s+(.+)',
            content,
            re.DOTALL
        )

        user_story = ""
        if user_story_match:
            user_story = f"**As a** {user_story_match.group(1).strip()}\n"
            user_story += f"**I want** {user_story_match.group(2).strip()}\n"
            user_story += f"**So that** {user_story_match.group(3).strip()}\n\n"

        # Extract acceptance criteria
        ac_match = re.search(r'## Acceptance Criteria\s*\n((?:- \[ \].+\n?)+)', content, re.MULTILINE)
        acceptance_criteria = ""
        if ac_match:
            acceptance_criteria = "## Acceptance Criteria\n" + ac_match.group(1)

        # Extract technical notes section
        tech_notes_match = re.search(
            r'## Technical Notes(.+?)(?=##|\Z)',
            content,
            re.DOTALL
        )
        technical_notes = tech_notes_match.group(0) if tech_notes_match else ""

        # Build description
        description = user_story
        if acceptance_criteria:
            description += "\n" + acceptance_criteria
        if technical_notes:
            description += "\n" + technical_notes[:2000]  # Limit length

        # Extract dependencies/related stories
        related_match = re.findall(r'Story (\d+)', content)
        related_stories = [int(s) for s in related_match if int(s) != story_number]

        return {
            "number": story_number,
            "title": title,
            "description": description,
            "related_stories": related_stories,
            "file_path": str(file_path),
        }

    def create_issue(
        self,
        title: str,
        description: str,
        label_ids: List[str],
        story_number: int,
    ) -> str:
        """Create Linear issue"""
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
                    url
                }
            }
        }
        """

        data = self.graphql_query(mutation, {
            "teamId": self.team_id,
            "title": title,
            "description": description,
            "labelIds": label_ids,
        })

        issue = data["issueCreate"]["issue"]
        self.created_issues[story_number] = issue["id"]

        return issue

    def link_issues(self, issue_id: str, related_issue_ids: List[str]):
        """Create relations between issues"""
        for related_id in related_issue_ids:
            mutation = """
            mutation($issueId: String!, $relatedIssueId: String!) {
                issueRelationCreate(input: {
                    issueId: $issueId,
                    relatedIssueId: $relatedIssueId,
                    type: "related"
                }) {
                    issueRelation {
                        id
                    }
                }
            }
            """
            try:
                self.graphql_query(mutation, {
                    "issueId": issue_id,
                    "relatedIssueId": related_id,
                })
            except Exception as e:
                print(f"  ⚠ Failed to link issues: {e}")

    def import_stories(self, project_root: Path):
        """Import all user stories"""
        print("🚀 Starting Mnemosyne Linear Import\n")

        # Get team
        self.get_team_id()

        # Create phase labels
        print("📌 Creating labels...")
        phase_colors = {
            "Phase 0": "#FF6B6B",  # Red
            "Phase 1": "#4ECDC4",  # Teal
            "Phase 2": "#45B7D1",  # Blue
            "Phase 3": "#96CEB4",  # Green
            "Phase 4": "#FFEAA7",  # Yellow
            "Phase 5": "#DFE6E9",  # Gray
        }

        for phase, color in phase_colors.items():
            label_id = self.create_label(phase, color)
            self.label_ids[phase] = label_id
            print(f"  ✓ {phase}")

        # Create component labels
        component_labels = {
            "Aletheia": "#A8E6CF",  # Light green
            "Alexandria": "#FFD3B6",  # Light orange
            "Argus": "#FFAAA5",  # Light red
            "Iris": "#AA9CFF",  # Light purple
            "Hermes": "#90DBF4",  # Light blue
        }

        for component, color in component_labels.items():
            label_id = self.create_label(component, color)
            self.label_ids[component] = label_id
            print(f"  ✓ {component}")

        print()

        # Parse and create issues
        print("📝 Creating issues...\n")
        parsed_stories = []

        for story_file, phase, week in STORY_FILES:
            file_path = project_root / story_file

            if not file_path.exists():
                print(f"  ⚠ Skipping {story_file} (not found)")
                continue

            # Parse story
            story_data = self.parse_story_file(file_path)
            story_data["phase"] = phase
            story_data["week"] = week
            parsed_stories.append(story_data)

            # Determine labels
            labels = [self.label_ids[phase]]

            # Add component labels based on title/content
            title_lower = story_data["title"].lower()
            if "ingest" in title_lower or "vault" in title_lower:
                labels.append(self.label_ids["Aletheia"])
            if "gatekeeper" in title_lower or "shadow" in title_lower:
                labels.append(self.label_ids["Alexandria"])
            if "scout" in title_lower or "pattern" in title_lower or "discovery" in title_lower:
                labels.append(self.label_ids["Argus"])
            if "routing" in title_lower or "query" in title_lower:
                labels.append(self.label_ids["Iris"])
            if "telegram" in title_lower or "manager" in title_lower or "notification" in title_lower:
                labels.append(self.label_ids["Hermes"])

            # Create issue
            issue = self.create_issue(
                title=f"Story {story_data['number']:03d}: {story_data['title'].split(':')[-1].strip()}",
                description=story_data["description"],
                label_ids=labels,
                story_number=story_data["number"],
            )

            week_str = f"Week {week}" if week else "Future"
            print(f"  ✓ {issue['identifier']}: {story_data['title'][:60]} ({phase}, {week_str})")
            print(f"    {issue['url']}")

        # Link related stories
        print("\n🔗 Linking related stories...")
        for story_data in parsed_stories:
            if story_data["related_stories"]:
                issue_id = self.created_issues[story_data["number"]]
                related_ids = [
                    self.created_issues[num]
                    for num in story_data["related_stories"]
                    if num in self.created_issues
                ]
                if related_ids:
                    self.link_issues(issue_id, related_ids)
                    print(f"  ✓ Story {story_data['number']:03d} → {story_data['related_stories']}")

        print(f"\n✅ Successfully imported {len(parsed_stories)} user stories to Linear!")


def main():
    if not LINEAR_API_KEY:
        print("❌ Error: LINEAR_API_KEY not found in environment")
        print("\nTo get your API key:")
        print("  1. Go to: https://linear.app/settings/api")
        print("  2. Create new API key")
        print("  3. Add to .env file: LINEAR_API_KEY=lin_api_xxx")
        print("  4. Run this script again")
        sys.exit(1)

    project_root = Path(__file__).parent.parent
    importer = LinearImporter(LINEAR_API_KEY)

    try:
        importer.import_stories(project_root)
    except KeyboardInterrupt:
        print("\n\n⚠ Import cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
