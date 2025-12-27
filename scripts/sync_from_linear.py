#!/usr/bin/env python3
"""
Sync status from Linear to local IMPLEMENTATION_PLAN.md

This script fetches issue status from Linear and updates checkboxes
in IMPLEMENTATION_PLAN.md to reflect current progress.

Usage:
    python scripts/sync_from_linear.py
    python scripts/sync_from_linear.py --show-status  # Just show, don't update
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv
import argparse

# Load environment variables from .env
load_dotenv()

LINEAR_API_KEY = os.getenv("LINEAR_API_KEY")
LINEAR_API_URL = "https://api.linear.app/graphql"

# Story number to Linear issue mapping (from import)
STORY_TO_LINEAR = {
    0: "PRO-5",
    1: "PRO-6",
    2: "PRO-7",
    3: "PRO-8",
    # Phase 1 stories (note: different numbering)
    # Add more as needed
}


class LinearSyncer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": api_key,
            "Content-Type": "application/json",
        }
        self.team_id = None
        self.issue_status = {}

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
        """Get team ID"""
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

        # Auto-select first team
        self.team_id = teams[0]["id"]
        print(f"📋 Team: {teams[0]['name']}\n")
        return self.team_id

    def fetch_all_issues(self) -> Dict[str, Dict]:
        """Fetch all Mnemosyne issues from Linear"""
        query = """
        query($teamId: String!) {
            team(id: $teamId) {
                issues {
                    nodes {
                        id
                        identifier
                        title
                        state {
                            name
                            type
                        }
                        completedAt
                        createdAt
                        labels {
                            nodes {
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

        # Filter to only Mnemosyne story issues
        story_issues = {}
        for issue in issues:
            # Look for issues starting with "Story XXX:"
            match = re.search(r'Story (\d+):', issue['title'])
            if match:
                story_num = int(match.group(1))
                story_issues[story_num] = {
                    "identifier": issue["identifier"],
                    "title": issue["title"],
                    "state": issue["state"]["name"],
                    "state_type": issue["state"]["type"],  # started, completed, canceled
                    "completed": issue["completedAt"] is not None,
                    "labels": [label["name"] for label in issue["labels"]["nodes"]],
                }

        return story_issues

    def get_status_emoji(self, issue_info: Dict) -> str:
        """Get emoji based on Linear state"""
        state_type = issue_info["state_type"]

        if state_type == "completed":
            return "✅"
        elif state_type == "started":
            return "🔄"
        elif state_type == "canceled":
            return "❌"
        else:  # backlog, triage, todo
            return "⬜"

    def show_status_summary(self, issues: Dict[str, Dict]):
        """Display status summary"""
        print("📊 Mnemosyne Project Status\n")
        print("=" * 80)

        # Group by phase
        phases = {
            "Phase 0": list(range(0, 4)),
            "Phase 1": [1, 2, 3],  # Phase 1 stories (cluster, metadata, taxonomy)
            "Phase 2": [4, 5, 6],
            "Phase 3": [7, 8, 9],
            "Phase 4": [10, 11, 12, 13, 14, 15, 16],
            "Phase 5": [17, 18],
        }

        for phase_name, story_numbers in phases.items():
            phase_issues = {num: issues[num] for num in story_numbers if num in issues}

            if not phase_issues:
                continue

            total = len(phase_issues)
            completed = sum(1 for i in phase_issues.values() if i["state_type"] == "completed")
            in_progress = sum(1 for i in phase_issues.values() if i["state_type"] == "started")

            print(f"\n{phase_name}: {completed}/{total} completed, {in_progress} in progress")
            print("-" * 80)

            for story_num in sorted(phase_issues.keys()):
                issue = phase_issues[story_num]
                emoji = self.get_status_emoji(issue)
                state = issue["state"]
                identifier = issue["identifier"]
                title = issue["title"].split(":")[1].strip() if ":" in issue["title"] else issue["title"]

                # Truncate title if too long
                if len(title) > 50:
                    title = title[:47] + "..."

                print(f"  {emoji} [{identifier}] Story {story_num:03d}: {title}")
                print(f"      Status: {state}")

        print("\n" + "=" * 80)

        # Overall stats
        all_completed = sum(1 for i in issues.values() if i["state_type"] == "completed")
        all_in_progress = sum(1 for i in issues.values() if i["state_type"] == "started")
        all_total = len(issues)

        print(f"\n📈 Overall Progress: {all_completed}/{all_total} completed ({all_completed/all_total*100:.1f}%)")
        print(f"🔄 In Progress: {all_in_progress}")
        print(f"⬜ Not Started: {all_total - all_completed - all_in_progress}\n")

    def update_implementation_plan(self, issues: Dict[str, Dict], plan_path: Path):
        """Update IMPLEMENTATION_PLAN.md with Linear status"""

        if not plan_path.exists():
            print(f"❌ Error: {plan_path} not found")
            return

        content = plan_path.read_text()
        original_content = content

        # Update story checkboxes based on Linear status
        for story_num, issue_info in issues.items():
            completed = issue_info["state_type"] == "completed"
            checkbox = "[x]" if completed else "[ ]"

            # Find story header pattern in IMPLEMENTATION_PLAN.md
            # Pattern: - [ ] Story XXX: Title
            pattern = rf'- \[ \] (Story {story_num:03d}:.*?)$'
            replacement = rf'- {checkbox} \1'

            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        # Check if anything changed
        if content == original_content:
            print("ℹ️  No changes needed - IMPLEMENTATION_PLAN.md is up to date")
            return

        # Backup original
        backup_path = plan_path.parent / f"{plan_path.name}.backup"
        backup_path.write_text(original_content)
        print(f"💾 Backed up original to: {backup_path}")

        # Write updated content
        plan_path.write_text(content)
        print(f"✅ Updated {plan_path}")

        # Count changes
        changes = sum(1 for s in issues.values() if s["state_type"] == "completed")
        print(f"📝 Marked {changes} stories as completed")


def main():
    parser = argparse.ArgumentParser(description="Sync Linear status to IMPLEMENTATION_PLAN.md")
    parser.add_argument("--show-status", action="store_true", help="Show status summary only, don't update files")
    args = parser.parse_args()

    if not LINEAR_API_KEY:
        print("❌ Error: LINEAR_API_KEY not found in environment")
        print("\nMake sure you have LINEAR_API_KEY in your .env file")
        sys.exit(1)

    project_root = Path(__file__).parent.parent
    plan_path = project_root / "IMPLEMENTATION_PLAN.md"

    syncer = LinearSyncer(LINEAR_API_KEY)

    try:
        print("🔄 Syncing from Linear...\n")

        # Get team
        syncer.get_team_id()

        # Fetch all issues
        print("📥 Fetching issues from Linear...")
        issues = syncer.fetch_all_issues()
        print(f"✓ Found {len(issues)} Mnemosyne stories\n")

        # Show status summary
        syncer.show_status_summary(issues)

        # Update local file unless --show-status
        if not args.show_status:
            print("\n📝 Updating IMPLEMENTATION_PLAN.md...")
            syncer.update_implementation_plan(issues, plan_path)
        else:
            print("\nℹ️  Run without --show-status to update IMPLEMENTATION_PLAN.md")

    except KeyboardInterrupt:
        print("\n\n⚠ Sync cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
