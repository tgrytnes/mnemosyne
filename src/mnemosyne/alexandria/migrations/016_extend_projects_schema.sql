-- Migration 016: Extend projects schema for Project Manager Agent (Story 016)
--
-- This migration adds metadata columns to the projects table to support:
-- - User-provided project importance and urgency (1-5 scale)
-- - Work estimates for pressure score calculation
-- - Deadline tracking
-- - Bidirectional Obsidian sync timestamps and file paths
--
-- Related Stories:
-- - Story 016: Project Manager Agent
-- - CR-014-001: SQL Gatekeeper Direct User Updates
--
-- Author: Mnemosyne Team
-- Date: 2026-01-01

-- Add importance field (1-5 scale, user-only metadata)
-- NULL means user hasn't set it yet (Project Manager will request)
ALTER TABLE projects ADD COLUMN importance INTEGER
    CHECK (importance >= 1 AND importance <= 5);

-- Add urgency field (1-5 scale, user-only metadata)
-- NULL means user hasn't set it yet (Project Manager will request)
ALTER TABLE projects ADD COLUMN urgency INTEGER
    CHECK (urgency >= 1 AND urgency <= 5);

-- Add deadline field for time-sensitive projects
-- NULL means no deadline set (Project Manager requests for high-priority projects)
ALTER TABLE projects ADD COLUMN deadline TIMESTAMP;

-- Add work estimate field (in hours)
-- Used for pressure score calculation: Pressure = Work ÷ Time
-- NULL uses default heuristic (20 hours for medium project)
ALTER TABLE projects ADD COLUMN work_estimate INTEGER;

-- Add pressure score field (calculated: work_estimate ÷ time_remaining)
-- Automatically updated by Project Manager hourly
-- Higher pressure = more urgent action needed
ALTER TABLE projects ADD COLUMN pressure_score REAL;

-- Add Obsidian file path for bidirectional sync
-- Example: "Projects/Implement-dark-mode-toggle.md"
-- NULL means not yet synced to Obsidian
ALTER TABLE projects ADD COLUMN obsidian_file_path TEXT;

-- Add timestamp for SQL → Obsidian sync
-- Tracks when this project was last written to Obsidian markdown
ALTER TABLE projects ADD COLUMN last_synced_to_obsidian TIMESTAMP;

-- Add timestamp for Obsidian → SQL sync
-- Tracks when this project was last updated from Obsidian markdown edits
ALTER TABLE projects ADD COLUMN last_synced_from_obsidian TIMESTAMP;

-- Create index on importance for priority queries
CREATE INDEX IF NOT EXISTS idx_projects_importance ON projects(importance);

-- Create index on urgency for priority queries
CREATE INDEX IF NOT EXISTS idx_projects_urgency ON projects(urgency);

-- Create index on deadline for deadline tracking queries
CREATE INDEX IF NOT EXISTS idx_projects_deadline ON projects(deadline);

-- Create index on pressure_score for high-pressure project queries
CREATE INDEX IF NOT EXISTS idx_projects_pressure ON projects(pressure_score DESC NULLS LAST);

-- Create index on obsidian_file_path for sync lookups
CREATE INDEX IF NOT EXISTS idx_projects_obsidian_path ON projects(obsidian_file_path);

-- Add comment to table documenting the new fields
COMMENT ON COLUMN projects.importance IS 'User-provided importance (1-5), where 5 is most important. NULL means not yet set.';
COMMENT ON COLUMN projects.urgency IS 'User-provided urgency (1-5), where 5 is most urgent. NULL means not yet set.';
COMMENT ON COLUMN projects.deadline IS 'User-provided or calculated deadline. NULL means no deadline set.';
COMMENT ON COLUMN projects.work_estimate IS 'Estimated work in hours. Used for pressure score calculation.';
COMMENT ON COLUMN projects.pressure_score IS 'Calculated pressure (work ÷ time). Higher = more urgent. Updated hourly.';
COMMENT ON COLUMN projects.obsidian_file_path IS 'Path to Obsidian markdown file for this project. NULL if not synced.';
COMMENT ON COLUMN projects.last_synced_to_obsidian IS 'Last time SQL metadata was written to Obsidian.';
COMMENT ON COLUMN projects.last_synced_from_obsidian IS 'Last time Obsidian edits were synced to SQL.';
