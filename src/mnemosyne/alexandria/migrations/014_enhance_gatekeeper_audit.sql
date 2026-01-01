-- Migration 014-CR-001: Enhance gatekeeper_audit table for direct user updates
--
-- This migration extends the gatekeeper_audit table to support tracking
-- user-initiated direct updates (bypassing approval workflow) in addition
-- to the existing approval/rejection tracking.
--
-- Related Stories:
-- - Story 014: SQL Project Gatekeeper (original)
-- - CR-014-001: Direct User Updates enhancement
-- - Story 016: Project Manager Agent (uses direct updates)
--
-- Author: Mnemosyne Team
-- Date: 2026-01-01

-- Add action_type column to distinguish between different audit actions
-- Values: 'approval', 'rejection', 'direct_update', 'rollback'
-- Default 'approval' maintains backward compatibility with existing rows
ALTER TABLE gatekeeper_audit ADD COLUMN action_type TEXT DEFAULT 'approval';

-- Add updates_json column to store the actual updates payload
-- For direct_update actions, stores the fields that were changed
-- Example: {"importance": 5, "urgency": 4, "deadline": "2026-12-31T23:59:59"}
ALTER TABLE gatekeeper_audit ADD COLUMN updates_json TEXT;

-- Add user_initiated flag to distinguish user vs agent actions
-- TRUE for direct user updates (Telegram commands, Obsidian edits)
-- FALSE for agent-initiated changes (auto-approvals)
ALTER TABLE gatekeeper_audit ADD COLUMN user_initiated BOOLEAN DEFAULT FALSE;

-- Create index on action_type for efficient audit queries
CREATE INDEX IF NOT EXISTS idx_gatekeeper_audit_action ON gatekeeper_audit(action_type);

-- Create index on user_initiated for user action tracking
CREATE INDEX IF NOT EXISTS idx_gatekeeper_audit_user ON gatekeeper_audit(user_initiated);

-- Add comments documenting the new columns
COMMENT ON COLUMN gatekeeper_audit.action_type IS 'Type of action: approval, rejection, direct_update, or rollback';
COMMENT ON COLUMN gatekeeper_audit.updates_json IS 'JSON payload of updates for direct_update actions';
COMMENT ON COLUMN gatekeeper_audit.user_initiated IS 'TRUE if action was directly initiated by user (vs agent)';
