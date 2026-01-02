-- Migration 027: Create message_outbox table for agent-to-user communication
--
-- This migration creates the message outbox queue that decouples agents from
-- Telegram delivery. Agents enqueue messages, Hermes consumes them, and user
-- responses route back to the originating agent.
--
-- Related Story: Story 027 - Message Outbox Relay (Nexus Middle-Man)
--
-- Author: Mnemosyne Team
-- Date: 2026-01-01

-- Create message_outbox table (SQLite-based queue)
-- Note: This is a SQLite table, not PostgreSQL (different from The Ananke)
CREATE TABLE IF NOT EXISTS message_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Message identification
    message_id TEXT NOT NULL UNIQUE,  -- Idempotency key (e.g., "notification:project:42:abc123")
    message_type TEXT NOT NULL,        -- notification, approval_request, escalation, question

    -- Response routing
    originating_agent TEXT,            -- Agent that sent this (project_manager, monitor, gatekeeper)
    context_id TEXT,                   -- Context for routing responses (e.g., "project:42", "discovery:disco_001")

    -- Message payload
    payload_json TEXT NOT NULL,        -- Message content and metadata as JSON

    -- State management
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, delivered, failed, awaiting_response
    expects_response BOOLEAN DEFAULT FALSE,  -- TRUE if this is an interactive question

    -- Response tracking (for interactive messages)
    response_received_at TIMESTAMP,    -- When user responded
    response_json TEXT,                -- User's response data

    -- Retry logic
    attempts INTEGER NOT NULL DEFAULT 0,     -- Number of delivery attempts
    last_error TEXT,                         -- Most recent delivery error

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,      -- When message was enqueued
    last_attempted_at TIMESTAMP,                        -- Most recent delivery attempt
    delivered_at TIMESTAMP,                             -- When successfully delivered

    -- Constraints
    CHECK (message_type IN ('notification', 'approval_request', 'escalation', 'question')),
    CHECK (status IN ('pending', 'delivered', 'failed', 'awaiting_response')),
    CHECK (attempts >= 0)
);

-- Create index on message_id for idempotency lookups
CREATE INDEX IF NOT EXISTS idx_message_outbox_message_id ON message_outbox(message_id);

-- Create index on status for pending message queries
CREATE INDEX IF NOT EXISTS idx_message_outbox_status ON message_outbox(status);

-- Create index on originating_agent for agent filtering
CREATE INDEX IF NOT EXISTS idx_message_outbox_agent ON message_outbox(originating_agent);

-- Create index on context_id for response routing
CREATE INDEX IF NOT EXISTS idx_message_outbox_context ON message_outbox(context_id);

-- Create index on created_at for FIFO ordering
CREATE INDEX IF NOT EXISTS idx_message_outbox_created ON message_outbox(created_at);

-- Create compound index for response routing queries
CREATE INDEX IF NOT EXISTS idx_message_outbox_response_routing
ON message_outbox(context_id, expects_response, status);
