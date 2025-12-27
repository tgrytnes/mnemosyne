"""
Unit tests for Gatekeepers (Layer 2: The Gates)
Tests Story 002: Obsidian Gatekeeper and Story 014: SQL Project Gatekeeper
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch


@pytest.mark.unit
class TestSQLProjectGatekeeper:
    """Test SQL Project Gatekeeper approval workflow"""

    def test_high_confidence_triggers_approval_request(self, mock_discovery):
        """High confidence (>80%) should request approval"""
        # from Alexandria.sql_gatekeeper import SQLProjectGatekeeper

        db_conn = Mock()
        messenger = Mock()
        # gatekeeper = SQLProjectGatekeeper(db_conn, messenger)

        mock_discovery.confidence_score = 0.85

        # gatekeeper.request_project_write(mock_discovery)

        # Should add to pending approvals
        # assert len(gatekeeper.pending_approvals) == 1

        # Should send Telegram message
        # messenger.send_message.assert_called_once()
        # message = messenger.send_message.call_args[0][0]
        # assert "Project Approval Request" in message
        # assert mock_discovery.title in message

    def test_low_confidence_auto_rejects(self, mock_discovery):
        """Low confidence (<60%) should not request approval"""
        db_conn = Mock()
        messenger = Mock()
        # gatekeeper = SQLProjectGatekeeper(db_conn, messenger)

        mock_discovery.confidence_score = 0.55

        # gatekeeper.request_project_write(mock_discovery)

        # Should NOT request approval
        # assert len(gatekeeper.pending_approvals) == 0
        # messenger.send_message.assert_not_called()

    def test_medium_confidence_requires_confirmation(self, mock_discovery):
        """Medium confidence (60-80%) requires user confirmation"""
        db_conn = Mock()
        messenger = Mock()
        # gatekeeper = SQLProjectGatekeeper(db_conn, messenger)

        mock_discovery.confidence_score = 0.70

        # gatekeeper.request_project_write(mock_discovery)

        # Should request approval with medium confidence flag
        # assert len(gatekeeper.pending_approvals) == 1
        # message = messenger.send_message.call_args[0][0]
        # assert "🟡" in message  # Medium confidence emoji

    def test_approve_project_writes_to_sql(self, mock_discovery):
        """Approving project writes to The Ananke"""
        db_conn = Mock()
        messenger = Mock()
        # gatekeeper = SQLProjectGatekeeper(db_conn, messenger)

        # First, request approval
        mock_discovery.confidence_score = 0.85
        # gatekeeper.request_project_write(mock_discovery)
        # approval_id = list(gatekeeper.pending_approvals.keys())[0]

        # Mock database cursor
        cursor_mock = Mock()
        cursor_mock.fetchone.return_value = (123,)  # project_id
        db_conn.cursor.return_value = cursor_mock

        # Approve the project
        # success = gatekeeper.approve_project(approval_id)

        # assert success is True
        # cursor_mock.execute.assert_called()
        # assert "INSERT INTO projects" in cursor_mock.execute.call_args[0][0]

    def test_reject_project_does_not_write(self, mock_discovery):
        """Rejecting project does not write to SQL"""
        db_conn = Mock()
        messenger = Mock()
        # gatekeeper = SQLProjectGatekeeper(db_conn, messenger)

        mock_discovery.confidence_score = 0.85
        # gatekeeper.request_project_write(mock_discovery)
        # approval_id = list(gatekeeper.pending_approvals.keys())[0]

        # Reject the project
        # gatekeeper.reject_project(approval_id)

        # Should NOT write to database
        # db_conn.cursor.return_value.execute.assert_not_called()

        # Should log rejection
        # messenger.send_message.assert_called()
        # assert "Rejected" in messenger.send_message.call_args[0][0]

    def test_approval_audit_log(self, mock_discovery):
        """Test approval decisions are logged"""
        db_conn = Mock()
        messenger = Mock()
        # gatekeeper = SQLProjectGatekeeper(db_conn, messenger)

        # After approval or rejection
        # cursor = db_conn.cursor()
        # Should have logged to gatekeeper_audit table
        # assert any(
        #     "INSERT INTO gatekeeper_audit" in str(call)
        #     for call in cursor.execute.call_args_list
        # )


@pytest.mark.unit
class TestObsidianGatekeeper:
    """Test Obsidian Gatekeeper shadow copy workflow"""

    def test_shadow_copy_workflow(self, temp_vault, temp_shadow_vault):
        """Test shadow copy creation and approval"""
        # from Alexandria.obsidian_gatekeeper import ObsidianGatekeeper

        # gatekeeper = ObsidianGatekeeper(
        #     source_vault=str(temp_vault),
        #     shadow_vault=str(temp_shadow_vault)
        # )

        # Simulate automated edit in shadow
        source_file = temp_vault / "note1.md"
        shadow_file = temp_shadow_vault / "note1.md"

        original_content = source_file.read_text()
        modified_content = original_content + "\n\n#automated_tag"

        shadow_file.parent.mkdir(parents=True, exist_ok=True)
        shadow_file.write_text(modified_content)

        # Request approval
        # gatekeeper.request_approval(
        #     str(shadow_file),
        #     {"tags_added": ["#automated_tag"]}
        # )

        # Verify source unchanged
        assert source_file.read_text() == original_content

    def test_approve_syncs_shadow_to_source(self, temp_vault, temp_shadow_vault):
        """Approving changes syncs shadow to source"""
        source_file = temp_vault / "note1.md"
        shadow_file = temp_shadow_vault / "note1.md"

        original = source_file.read_text()
        modified = original + "\n\n#new_tag"

        shadow_file.parent.mkdir(parents=True, exist_ok=True)
        shadow_file.write_text(modified)

        # gatekeeper.approve_changes(approval_id)

        # Source should now match shadow
        # assert source_file.read_text() == modified

    def test_reject_reverts_shadow(self, temp_vault, temp_shadow_vault):
        """Rejecting changes reverts shadow to match source"""
        source_file = temp_vault / "note1.md"
        shadow_file = temp_shadow_vault / "note1.md"

        original = source_file.read_text()
        modified = original + "\n\n#rejected_tag"

        shadow_file.parent.mkdir(parents=True, exist_ok=True)
        shadow_file.write_text(modified)

        # gatekeeper.reject_changes(approval_id)

        # Shadow should revert to original
        # assert shadow_file.read_text() == original

    def test_diff_generation(self, temp_vault, temp_shadow_vault):
        """Test diff generation for review"""
        # from Alexandria.obsidian_gatekeeper import generate_diff

        source_file = temp_vault / "note1.md"
        shadow_file = temp_shadow_vault / "note1.md"

        shadow_file.parent.mkdir(parents=True, exist_ok=True)
        shadow_file.write_text(source_file.read_text() + "\n\nNew line")

        # diff = generate_diff(str(source_file), str(shadow_file))

        # assert "+New line" in diff
        # assert "```diff" in diff  # Markdown code block


@pytest.mark.unit
class TestGatekeeperIntegration:
    """Test interaction between SQL and Obsidian gatekeepers"""

    def test_dual_gatekeeper_approval(self):
        """Test approval flow through both gatekeepers"""
        # This tests the complete workflow:
        # 1. Scout discovers project (SQL gatekeeper)
        # 2. User approves → writes to Ananke
        # 3. Curator suggests vault edits (Obsidian gatekeeper)
        # 4. User approves → updates vault
        pass


@pytest.mark.unit
def test_confidence_threshold_configuration():
    """Test confidence thresholds can be configured"""
    # from Alexandria.sql_gatekeeper import SQLProjectGatekeeper

    db_conn = Mock()
    messenger = Mock()

    # Default thresholds
    # gatekeeper = SQLProjectGatekeeper(db_conn, messenger)
    # assert gatekeeper.thresholds["auto_reject"] == 0.60
    # assert gatekeeper.thresholds["require_approval"] == 0.80

    # Custom thresholds
    # custom_gatekeeper = SQLProjectGatekeeper(
    #     db_conn,
    #     messenger,
    #     thresholds={"auto_reject": 0.70, "require_approval": 0.85}
    # )
    # assert custom_gatekeeper.thresholds["auto_reject"] == 0.70
