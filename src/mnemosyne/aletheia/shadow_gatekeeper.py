"""
Obsidian Gatekeeper for shadow copy approvals (Story 025).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ApprovalRequest:
    shadow_file: str
    source_file: str
    changes: dict
    requested_at: datetime


class ObsidianGatekeeper:
    def __init__(self, source_vault: str, shadow_vault: str):
        self.source_vault = Path(source_vault)
        self.shadow_vault = Path(shadow_vault)
        self.pending_approvals: list[ApprovalRequest] = []

    def get_source_path(self, shadow_file: str) -> str:
        rel = Path(shadow_file).relative_to(self.shadow_vault)
        return str(self.source_vault / rel)

    def request_approval(self, shadow_file: str, changes: dict):
        req = ApprovalRequest(
            shadow_file=shadow_file,
            source_file=self.get_source_path(shadow_file),
            changes=changes,
            requested_at=datetime.utcnow(),
        )
        self.pending_approvals.append(req)

    def approve_all(self):
        for req in list(self.pending_approvals):
            src = Path(req.source_file)
            shadow = Path(req.shadow_file)
            src.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(shadow, src)
            self.pending_approvals.remove(req)
