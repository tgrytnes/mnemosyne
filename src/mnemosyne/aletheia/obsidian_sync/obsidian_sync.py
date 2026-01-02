"""
Obsidian Bidirectional Sync Manager (Story 016)

Manages bidirectional synchronization between The Ananke (PostgreSQL) and
Obsidian markdown files.

This module handles:
- SQL → Obsidian sync: Writing project updates to markdown files
- Obsidian → SQL sync: Reading markdown edits back to database
- Conflict detection and resolution
- Sync cooldown to prevent rapid successive syncs
"""

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from .project_markdown import (
    serialize_project,
    parse_project_markdown,
    generate_obsidian_path,
)


class ObsidianSyncManager:
    """
    Manages bidirectional synchronization between SQL and Obsidian.

    Example:
        ```python
        sync_manager = ObsidianSyncManager(
            db_conn=db_connection,
            vault_path="/path/to/ObsidianVault"
        )

        # Sync project to Obsidian
        result = sync_manager.sync_project_to_obsidian(project)

        # Sync Obsidian changes back to SQL
        result = sync_manager.sync_obsidian_file_to_sql(file_path)
        ```
    """

    def __init__(
        self,
        db_conn,
        vault_path: str,
        projects_folder: str = "Projects",
        sync_cooldown_seconds: int = 30,
        conflict_strategy: str = "sql_wins",
        dry_run: bool = False,
        gatekeeper=None,
    ):
        """
        Initialize Obsidian Sync Manager.

        Args:
            db_conn: Database connection (psycopg2 connection)
            vault_path: Path to Obsidian vault root
            projects_folder: Folder name for projects (default "Projects")
            sync_cooldown_seconds: Minimum seconds between syncs (default 30)
            conflict_strategy: How to resolve conflicts - "sql_wins", "obsidian_wins", or "manual"
            dry_run: If True, don't actually write files (for testing)
            gatekeeper: SQL Gatekeeper instance for database updates
        """
        self._db = db_conn
        self.vault_path = vault_path
        self.projects_folder = projects_folder
        self.sync_cooldown = sync_cooldown_seconds
        self.conflict_strategy = conflict_strategy
        self.dry_run = dry_run
        self._gatekeeper = gatekeeper

        # Ensure Projects folder exists
        projects_path = Path(vault_path) / projects_folder
        if not dry_run:
            projects_path.mkdir(parents=True, exist_ok=True)

    # ==========================================================================
    # SQL → Obsidian Sync
    # ==========================================================================

    def sync_project_to_obsidian(
        self, project: dict[str, Any], force: bool = False
    ) -> dict[str, Any]:
        """
        Sync a project from SQL to Obsidian markdown file.

        Args:
            project: Project dict from SQL
            force: If True, bypass cooldown check

        Returns:
            Dict with sync result: {'action': 'created'|'updated'|'skipped', 'file_path': '...'}
        """
        # Check cooldown
        if not force and self._should_skip_sync(project):
            return {
                "action": "skipped",
                "reason": "recently_synced",
                "project_id": project["id"],
            }

        # Generate file path
        if project.get("obsidian_file_path"):
            file_path = Path(project["obsidian_file_path"])
        else:
            relative_path = generate_obsidian_path(
                project["title"], project["id"], self.projects_folder
            )
            file_path = Path(self.vault_path) / relative_path

        # Serialize to markdown
        markdown = serialize_project(project)

        # Determine action
        action = "updated" if file_path.exists() else "created"

        # Dry run mode
        if self.dry_run:
            would_action = "would_create" if action == "created" else "would_update"
            return {
                "action": would_action,
                "file_path": str(file_path),
                "project_id": project["id"],
            }

        # Preserve custom sections if file exists
        if file_path.exists():
            markdown = self._preserve_custom_sections(file_path, markdown)

        # Write file
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(markdown, encoding="utf-8")

        # Update SQL with file path and sync timestamp
        self._update_obsidian_sync_timestamp(project["id"], str(file_path), direction="to_obsidian")

        return {
            "action": action,
            "file_path": str(file_path),
            "project_id": project["id"],
        }

    def sync_all_projects_to_obsidian(self, projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Sync multiple projects to Obsidian.

        Args:
            projects: List of project dicts from SQL

        Returns:
            List of sync results
        """
        results = []
        for project in projects:
            result = self.sync_project_to_obsidian(project)
            results.append(result)
        return results

    def _should_skip_sync(self, project: dict[str, Any]) -> bool:
        """Check if project was synced recently (within cooldown period)"""
        last_synced = project.get("last_synced_to_obsidian")
        if not last_synced:
            return False

        now = datetime.now(timezone.utc)
        time_since_sync = (now - last_synced).total_seconds()

        return time_since_sync < self.sync_cooldown

    def _preserve_custom_sections(self, file_path: Path, new_markdown: str) -> str:
        """
        Preserve user-added custom sections when updating markdown.

        Extracts custom sections (headers not in our standard set) from
        existing file and appends them to new markdown.
        """
        try:
            existing_content = file_path.read_text(encoding="utf-8")
        except Exception:
            return new_markdown

        # Standard sections we manage
        standard_sections = {"Metadata", "Discovery Info", "Timestamps"}

        # Extract custom sections from existing file
        custom_sections = []
        lines = existing_content.split("\n")
        in_custom_section = False
        current_section = []

        for line in lines:
            if line.startswith("## "):
                # Found a section header
                section_name = line[3:].strip()

                # If previous section was custom, save it
                if in_custom_section and current_section:
                    custom_sections.append("\n".join(current_section))

                # Check if this is a custom section
                if section_name not in standard_sections:
                    in_custom_section = True
                    current_section = [line]
                else:
                    in_custom_section = False
                    current_section = []
            elif in_custom_section:
                current_section.append(line)

        # Save last section if custom
        if in_custom_section and current_section:
            custom_sections.append("\n".join(current_section))

        # Append custom sections to new markdown
        if custom_sections:
            new_markdown = new_markdown.rstrip() + "\n\n" + "\n\n".join(custom_sections)

        return new_markdown

    def _update_obsidian_sync_timestamp(self, project_id: int, file_path: str, direction: str):
        """Update sync timestamp in SQL"""
        now = datetime.now(timezone.utc)

        if direction == "to_obsidian":
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    UPDATE projects
                    SET obsidian_file_path = %s,
                        last_synced_to_obsidian = %s
                    WHERE id = %s
                    """,
                    (file_path, now, project_id),
                )
                self._db.commit()
        elif direction == "from_obsidian":
            with self._db.cursor() as cur:
                cur.execute(
                    """
                    UPDATE projects
                    SET last_synced_from_obsidian = %s
                    WHERE id = %s
                    """,
                    (now, project_id),
                )
                self._db.commit()

    # ==========================================================================
    # Obsidian → SQL Sync
    # ==========================================================================

    def sync_obsidian_file_to_sql(self, file_path: str) -> dict[str, Any]:
        """
        Sync Obsidian markdown file changes back to SQL.

        Args:
            file_path: Path to Obsidian markdown file

        Returns:
            Dict with sync result
        """
        # Parse markdown
        markdown = Path(file_path).read_text(encoding="utf-8")
        project = parse_project_markdown(markdown)

        # Validate project exists in SQL
        project_id = project["id"]
        if not self._project_exists(project_id):
            raise ValueError(f"Project with id {project_id} not found in database")

        # Check for conflicts
        conflict = self.detect_conflict(file_path)
        if conflict:
            conflict_result = self._handle_conflict(conflict, project, file_path)
            # If conflict was resolved by sql_wins or requires manual resolution, return
            if conflict_result is not None:
                return conflict_result
            # If obsidian_wins (returns None), continue with the sync

        # Extract only whitelisted fields for update
        allowed_fields = {
            "importance",
            "urgency",
            "deadline",
            "description",
            "status",
            "work_estimate",
        }

        updates = {
            key: value
            for key, value in project.items()
            if key in allowed_fields and value is not None
        }

        # Use gatekeeper if available
        if self._gatekeeper:
            self._gatekeeper.update_project_direct(project_id, updates, user_initiated=True)
        else:
            # Direct SQL update (fallback)
            self._update_project_direct(project_id, updates)

        # Update sync timestamp
        self._update_obsidian_sync_timestamp(project_id, file_path, direction="from_obsidian")

        return {"action": "updated", "project_id": project_id, "file_path": file_path}

    def sync_all_obsidian_files(self) -> list[dict[str, Any]]:
        """
        Sync all Obsidian markdown files in Projects folder to SQL.

        Returns:
            List of sync results
        """
        projects_path = Path(self.vault_path) / self.projects_folder
        results = []

        for file_path in projects_path.glob("*.md"):
            try:
                result = self.sync_obsidian_file_to_sql(str(file_path))
                results.append(result)
            except Exception as e:
                results.append(
                    {
                        "action": "error",
                        "file_path": str(file_path),
                        "error": str(e),
                    }
                )

        return results

    def _project_exists(self, project_id: int) -> bool:
        """Check if project exists in database"""
        with self._db.cursor() as cur:
            cur.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
            return cur.fetchone() is not None

    def _update_project_direct(self, project_id: int, updates: dict[str, Any]):
        """Direct SQL update (fallback when no gatekeeper)"""
        if not updates:
            return

        # Build SET clause
        set_parts = [f"{key} = %s" for key in updates.keys()]
        values = list(updates.values())
        values.append(project_id)

        with self._db.cursor() as cur:
            cur.execute(
                f"""
                UPDATE projects
                SET {', '.join(set_parts)}
                WHERE id = %s
                """,
                tuple(values),
            )
            self._db.commit()

    # ==========================================================================
    # Conflict Detection
    # ==========================================================================

    def detect_conflict(self, file_path: str) -> Optional[dict[str, Any]]:
        """
        Detect if there's a conflict between SQL and Obsidian versions.

        A conflict occurs when:
        - Both SQL and Obsidian were modified since last sync
        - SQL was updated after the last Obsidian→SQL sync
        - Obsidian file was modified after the last SQL→Obsidian sync

        Args:
            file_path: Path to Obsidian file

        Returns:
            Conflict dict if conflict detected, None otherwise
        """
        # Get file modification time
        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path), tz=timezone.utc)

        # Parse project ID from file
        markdown = Path(file_path).read_text(encoding="utf-8")
        project = parse_project_markdown(markdown)
        project_id = project["id"]

        # Get SQL timestamps
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, updated_at, last_synced_from_obsidian
                FROM projects
                WHERE id = %s
                """,
                (project_id,),
            )
            row = cur.fetchone()

        if not row:
            return None

        sql_updated_at = row[2]
        last_synced_from_obsidian = row[3]

        # Check if both were modified since last sync
        if last_synced_from_obsidian:
            sql_modified_after_sync = sql_updated_at and sql_updated_at > last_synced_from_obsidian
            obsidian_modified_after_sync = file_mtime > last_synced_from_obsidian

            if sql_modified_after_sync and obsidian_modified_after_sync:
                return {
                    "type": "both_modified",
                    "project_id": project_id,
                    "sql_updated_at": sql_updated_at,
                    "obsidian_modified_at": file_mtime,
                    "last_synced_from_obsidian": last_synced_from_obsidian,
                }

        return None

    def _handle_conflict(
        self, conflict: dict[str, Any], project: dict[str, Any], file_path: str
    ) -> dict[str, Any]:
        """Handle sync conflict based on configured strategy"""
        if self.conflict_strategy == "sql_wins":
            # Overwrite Obsidian with SQL version
            # Fetch latest from SQL
            sql_project = self._fetch_project_from_sql(conflict["project_id"])
            self.sync_project_to_obsidian(sql_project, force=True)

            return {
                "action": "conflict_resolved",
                "strategy": "sql_wins",
                "project_id": conflict["project_id"],
            }

        elif self.conflict_strategy == "obsidian_wins":
            # Update SQL with Obsidian version
            # Return None to signal that sync should continue
            return None

        else:  # manual
            return {
                "action": "conflict",
                "conflict": conflict,
                "requires_manual_resolution": True,
            }

    def _fetch_project_from_sql(self, project_id: int) -> dict[str, Any]:
        """Fetch project from SQL"""
        with self._db.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, description, discovered_by, discovery_id,
                       cluster_ids, confidence_score, status, importance, urgency,
                       deadline, work_estimate, pressure_score, verified_by_user,
                       created_at, updated_at, obsidian_file_path,
                       last_synced_to_obsidian, last_synced_from_obsidian
                FROM projects
                WHERE id = %s
                """,
                (project_id,),
            )
            row = cur.fetchone()

        if not row:
            raise ValueError(f"Project {project_id} not found")

        # Map to dict
        return {
            "id": row[0],
            "title": row[1],
            "description": row[2],
            "discovered_by": row[3],
            "discovery_id": row[4],
            "cluster_ids": row[5],
            "confidence_score": row[6],
            "status": row[7],
            "importance": row[8],
            "urgency": row[9],
            "deadline": row[10],
            "work_estimate": row[11],
            "pressure_score": row[12],
            "verified_by_user": row[13],
            "created_at": row[14],
            "updated_at": row[15],
            "obsidian_file_path": row[16],
            "last_synced_to_obsidian": row[17],
            "last_synced_from_obsidian": row[18],
        }
