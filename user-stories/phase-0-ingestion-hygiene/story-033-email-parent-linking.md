# Story 033: Email Parent Records + Chunk Linking

**As a** user with raw email archives
**I want** each ingested email to have a parent record linked to its chunks
**So that** I can retrieve the original email and treat it as a single unit with a compact topic summary.

## Acceptance Criteria

### Functional
- [ ] **Scenario: Parent email collection exists**
  - **Given** Weaviate is running
  - **When** email ingestion starts
  - **Then** a parent collection (e.g., `EmailMessages`) exists with fields:
    - `emailId` (Message-ID or `hash-...` fallback, stable)
    - `subject`, `sender`, `date`, `sourcePath`
    - `body` (cleaned full email body)
    - `messageId` (Message-ID header if present)
    - `documentType=email`
    - `chunkCount` (number of chunks stored in TheLethe)
    - `topicSummary` (2-3 short topic strings)

- [ ] **Scenario: Parent records are idempotent**
  - **Given** a SOURCE_DIR with emails already ingested
  - **When** ingestion is re-run
  - **Then** parent records are updated (not duplicated) and `chunkCount` reflects current chunks.

- [ ] **Scenario: Chunks link back to parent**
  - **Given** an email is chunked into multiple items in `TheLethe`
  - **When** those chunks are stored
  - **Then** each chunk includes `parentEmailId` matching the parent record `emailId`.

- [ ] **Scenario: Retrieve original email from chunk**
  - **Given** a chunk from `TheLethe`
  - **When** querying the parent collection with its `parentEmailId`
  - **Then** the parent record returns the full cleaned body and header metadata for the original email.

- [ ] **Scenario: Topic summary derived from chunks**
  - **Given** an email with multiple semantic topics
  - **When** ingestion completes
  - **Then** the parent record stores `topicSummary` with 2-3 non-empty topic strings derived from chunk texts.

### Non-Functional & Quality
- [ ] **Scenario: Cleaning is preserved at the parent level**
  - **Given** an email containing HTML, tracking links, and signatures
  - **When** the parent record is stored
  - **Then** its `body` is plain text cleaned via `email_cleaner.py`.

- [ ] **Scenario: Schema compatibility**
  - **Given** existing `TheLethe` email chunks
  - **When** the schema is extended
  - **Then** ingestion of PDFs/emails continues without breaking existing chunk reads.

## Testing Plan
- Unit: ensure `emailId` generation matches Message-ID or `hash-...` fallback.
- Unit: verify topic summary extraction returns 2-3 items and never empty strings.
- Integration: ingest mixed .eml/.mbox and confirm parent collection has 1 record per email and each chunk has `parentEmailId`.
- E2E: ingest a multi-topic email and verify `topicSummary` strings align with chunk topics and parent body is retrievable.

## Technical Notes
- Parent collection name: `EmailMessages` (or `EmailParents`) in Weaviate.
- Parent record `emailId` should be stable and used for idempotent upserts.
- `topicSummary` can be derived from chunk texts using a lightweight summarizer; fall back to first-sentence heuristics if LLM fails.

## Affected Components
- **Aletheia**: email ingestion pipeline, chunk-to-parent linking, summary extraction.
- **Alexandria**: Weaviate schema additions (new parent collection, new `parentEmailId` property in TheLethe).

## Priority
**Medium** - enables reliable retrieval and grouping of chunked emails.

## Estimate
5 story points (3-5 days)

## Related Stories
- Story 031: Robust Raw Email Ingestion with Semantic Chunking
- Story 024: Email Archive Ingestion (deprecated TSV path)
