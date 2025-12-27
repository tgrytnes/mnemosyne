# Mnemosyne System Architecture

## Overview

Mnemosyne is a personal knowledge management system organized into **layered architectural components** that bridge curated knowledge (Obsidian vault) with archived data (emails, PDFs), using AI agents to discover patterns, manage projects, and provide intelligent assistance.

**Architecture Philosophy**: The system follows a layered design where each layer has clear responsibilities - from input processing through storage, pattern discovery, intelligence services, and user interaction.

---

## Architectural Layers

### Layer 1: **Input Processing** (Section 1-3)
Raw data ingestion and embedding generation

### Layer 2: **Alexandria** (Storage & Governance)
All data storage with gatekeeper protection

### Layer 3: **Argus** (Subconscious)
Pattern discovery and exploration

### Layer 4: **Iris** (Intelligence Services)
Query answering and semantic search

### Layer 5: **Hermes** (Interaction Layer)
User communication and project management

### Layer 6: **Prometheus** (Execution & Drafting) [Phase 5+]
Generative proposal creation (designed but not yet implemented)

---

## System Actors

### Human User (Thomas)

**Primary Interaction Channels**:
- Web interface (future)
- Phone/Telegram (current)

**System Roles**:
- Knowledge creator (writes Obsidian notes)
- Project manager (via Telegram commands)
- Gatekeeper approver (for SQL writes and vault edits)
- Discovery reviewer (approves/rejects pattern proposals)
- Deadline setter and priority manager

**Key Responsibilities**:
- Approves/rejects project proposals
- Sets deadlines and project priorities
- Reviews discovered patterns
- Manages project lifecycle via Telegram

---

## Layer 1: Input Processing

### Section 1: Obsidian Vault Processing

**Component**: **The Ingestor**

**Purpose**: Monitors Obsidian vault and ingests changes into The Muses

**Process**:
1. File watcher detects changes in vault
2. Cleans markdown (removes YAML frontmatter, wiki-links, HTML)
3. Chunks content (400 chars with 100-char overlap)
4. Embeds via Ollama (qwen3-embedding:0.6b)
5. Stores in The Muses (Weaviate)

**Output**: The Muses (core knowledge vectors)

**Implementation**: Story 000

---

### Section 2: Email Archive Processing

**Component**: **Email Ingestor**

**Purpose**: Processes large email archives for search/retrieval

**Process**:
1. Reads mbox/Thunderbird archives
2. Cleans HTML, tracking codes, signatures
3. Clusters by semantic content (MiniBatchKMeans)
4. Labels with TF-IDF keywords (multilingual: EN/DE/NO)
5. Classifies by TYPE (newsletter, tracking, invoice, personal)
6. Embeds and stores in The Lethe

**Output**: The Lethe (archive vectors)

**Implementation**: Story 001

---

### Section 3: Document Archive Processing

**Components**: **OCR + PyPDF processors**

**Purpose**: Ingests PDF documents and scanned materials

**Inputs**:
- Raw archives (PDFs)
- Scanned documents (via OCR)

**Process**:
1. OCR processing (OCRmyPDF, multi-language: EN/DE/NO)
2. Text extraction (Tika, Unstructured.io)
3. Cleaning and chunking
4. Embedding generation
5. Storage in The Lethe

**Output**: The Lethe (archive vectors)

**Implementation**: Story 003

---

## Layer 2: Alexandria (Storage & Governance)

**Alexandria** is the complete data storage layer, consisting of three main databases governed by The Gates approval system.

---

### Database 1: **The Muses** (Vectors)

**Purpose**: Core curated knowledge for pattern analysis

**Contents**:
- Obsidian vault embeddings (~1,500-2,500 chunks)
- 300-500 markdown files
- High-quality, manually curated content

**Weaviate Schema**:
```python
{
    "class": "TheMuses",
    "description": "CORE KNOWLEDGE: Obsidian vault only",
    "vectorizer": "none",  # We provide vectors via Ollama
    "properties": [
        {"name": "text", "dataType": ["text"]},
        {"name": "sourceFile", "dataType": ["text"]},
        {"name": "sourceType", "dataType": ["text"]},  # Always "obsidian"
        {"name": "chunkIndex", "dataType": ["int"]},
        {"name": "ingestedAt", "dataType": ["date"]},
        {"name": "fileModifiedAt", "dataType": ["date"]}
    ]
}
```

**Used By**:
- ✅ Scout (Argus) - pattern detection
- ✅ Iris - semantic search
- ✅ Cluster analysis (Phase 1)
- ✅ Graph taxonomy generation

**NOT Used For**:
- ❌ Email/document storage

**Performance**:
- Clustering: ~5 minutes on Pi 5
- Size: Intentionally kept small for fast analysis

---

### Database 2: **The Lethe** (Big Vector Archive)

**Purpose**: Large-scale archive for retrieval only

**Contents**:
- Email archives (19k+ emails → 30k-100k chunks)
- PDF documents
- OCR'd content
- Historical reference data

**Weaviate Schema**:
```python
{
    "class": "TheLethe",
    "description": "Archive: emails, PDFs, historical data",
    "vectorizer": "none",
    "properties": [
        {"name": "text", "dataType": ["text"]},
        {"name": "sourceFile", "dataType": ["text"]},
        {"name": "sourceType", "dataType": ["text"]},  # "email", "pdf", "ocr"
        {"name": "sender", "dataType": ["text"]},      # For emails
        {"name": "subject", "dataType": ["text"]},     # For emails
        {"name": "date", "dataType": ["date"]},
        {"name": "clusterId", "dataType": ["int"]},    # Email clustering
        {"name": "classification", "dataType": ["text"]}  # Email type
    ]
}
```

**Used By**:
- ✅ Iris - semantic search for emails/docs
- ✅ RAG retrieval for factual questions

**NOT Used For**:
- ❌ Pattern detection
- ❌ Project candidate discovery
- ❌ Clustering for analysis (too expensive)

**Performance**:
- Size: 30k-100k+ chunks
- Clustering: 60-90 minutes (too expensive for frequent use)

---

### Database 3: **The Ananke** (SQL)

**Purpose**: "Hard facts" - committed projects and cluster metadata

**PostgreSQL Schema**:

```sql
-- Projects table (the core "commitment" database)
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,

    -- Source tracking
    discovered_by TEXT,        -- 'scout', 'manual', 'prometheus'
    discovery_id TEXT,         -- Link to Discovery Vector DB
    cluster_ids TEXT[],        -- Which clusters contributed

    -- Confidence and verification
    confidence_score FLOAT,
    verified_by_user BOOLEAN DEFAULT FALSE,
    verified_at TIMESTAMP,

    -- Project management
    status TEXT DEFAULT 'candidate',  -- candidate, active, paused, completed
    deadline TIMESTAMP,
    pressure_score FLOAT,             -- Work ÷ Time (Project Manager calculates)
    work_estimate INTEGER,            -- Hours (for pressure calculation)

    -- Lifecycle tracking
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- Cluster metadata (ONLY for The Muses)
CREATE TABLE clusters (
    id TEXT PRIMARY KEY,
    collection TEXT NOT NULL DEFAULT 'TheMuses',
    theme_summary TEXT,
    key_entities TEXT[],
    tags TEXT[],
    note_count INTEGER,
    centroid_vector VECTOR(1024),
    created_at TIMESTAMP DEFAULT NOW(),
    profile JSONB  -- Structured metadata from Phase 1
);

-- Gatekeeper audit trail
CREATE TABLE gatekeeper_audit (
    id SERIAL PRIMARY KEY,
    approval_id TEXT NOT NULL,
    approved BOOLEAN NOT NULL,
    project_id INTEGER REFERENCES projects(id),
    decided_at TIMESTAMP DEFAULT NOW(),
    decided_by TEXT DEFAULT 'telegram_user'
);
```

**Used By**:
- ✅ SQL Gatekeeper (writes approved projects)
- ✅ Monitor Agent (checks for orphaned discoveries)
- ✅ The Project Manager (manages lifecycle)
- ✅ Iris (queries for project status)

**Write Policy**: ONLY via The Gates (SQL Gatekeeper) after user approval

**Project Lifecycle**:
```
candidate → active → completed
         ↓
       paused → active
```

---

### Database 4: **Discovery Vector DB** (Weaviate)

**Purpose**: Stores pattern discoveries from Scout (Argus)

**Contents**:
- Discovery records (project candidates, themes, contradictions)
- Confidence scores
- Linked cluster IDs
- Detection metadata

**Schema**:
```python
{
    "class": "Discoveries",
    "properties": [
        {"name": "discoveryId", "dataType": ["text"]},
        {"name": "title", "dataType": ["text"]},
        {"name": "description", "dataType": ["text"]},
        {"name": "patternType", "dataType": ["text"]},  # "project_candidate", "theme", etc.
        {"name": "confidenceScore", "dataType": ["number"]},
        {"name": "clusterIds", "dataType": ["text[]"]},
        {"name": "detectedAt", "dataType": ["date"]},
        {"name": "metadata", "dataType": ["object"]},
        {"name": "convertedToProject", "dataType": ["boolean"]}
    ]
}
```

**Used By**:
- ✅ Scout (writes discoveries)
- ✅ SQL Gatekeeper (reads for approval)
- ✅ Monitor Agent (checks against SQL)
- ✅ Iris (user can query discoveries)

---

### Supporting Databases (SQLite)

**Monitor State DB**:
```sql
CREATE TABLE monitor_state (
    discovery_id TEXT PRIMARY KEY,
    asked_at TIMESTAMP,
    ask_count INTEGER DEFAULT 1,
    rejected_at TIMESTAMP,
    rejected_confidence FLOAT,
    snoozed_until TIMESTAMP
);
```

**Ingestion State DB**:
```sql
CREATE TABLE ingested_files (
    file_path TEXT PRIMARY KEY,
    last_modified TIMESTAMP,
    ingested_at TIMESTAMP,
    chunk_count INTEGER
);
```

---

## The Gates: Approval & Safety Layer

**The Gates** is a unified gatekeeper system controlling all writes to protected systems. It provides a single conceptual layer for all approval workflows.

---

### Gate 1: **SQL Project Gatekeeper** (Phase 4: Story 014)

**Purpose**: Controls ALL writes to The Ananke (SQL project database)

**Capabilities**:
- Confidence-based threshold gating
- User approval workflow via The Liaison
- Audit trail for all decisions
- Rollback capability (<7 days)

**Decision Logic**:
```
Confidence >= 80%: Request approval (high confidence flag)
Confidence 60-80%: Request approval (standard)
Confidence < 60%: Auto-reject (don't ask user)
```

**Triggers**:
- Scout discovers high-confidence project
- Monitor Agent reconciliation
- User manual project creation

**User Interactions** (via Telegram):
- `/approve_project {approval_id}` - User approves → SQL write
- `/reject_project {approval_id}` - User rejects → No SQL write
- `/view_project {approval_id}` - See full details before deciding
- `/pending_projects` - List all pending approvals

**Data Flow**:
1. Receives discovery from Scout or Monitor Agent
2. Evaluates confidence threshold
3. Sends approval request via The Liaison (Hermes)
4. Waits for user decision
5. If approved: Writes to The Ananke + logs to audit table
6. If rejected: Logs to audit table only

---

### Gate 2: **Obsidian Gatekeeper** (Phase 0: Story 002)

**Purpose**: Controls writes to Obsidian Vault via shadow copy pattern

**Capabilities**:
- Shadow copy for all automated edits
- Diff review before applying
- User approval required
- Prevents automated corruption of notes

**Sub-Agents**:
- **Janitor**: Fixes typos, formatting, broken links
- **Tagger**: Suggests tags based on content

**Workflow**:
1. Agent makes edits to shadow copy (not vault)
2. User reviews diff in Obsidian Gatekeeper
3. User approves → Apply to vault
4. User rejects → Discard shadow changes

**Data Access**:
- Reads: Obsidian vault (read-only)
- Writes: Shadow copy directory
- After approval: Obsidian vault

---

## Layer 3: Argus (Subconscious)

**Argus** is the pattern discovery layer, operating autonomously to find latent insights in your knowledge base.

**Components**:
1. **Scout** (the pattern detection agent)
2. **Discovery Vector DB** (storage for discovered patterns)

---

### Scout (Phase 4: Stories 010-013)

**Also known as**: Latent Scout

**Role**: Proactive pattern discovery and project detection

**Capabilities**:
- Autonomous pattern detection (no user trigger)
- Project candidate discovery
- Emerging theme identification
- Contradiction detection
- Cross-cluster relationship analysis
- Weak link discovery (orphaned notes)

**Triggers**: Scheduled (nightly or on-demand)

**Data Access**:
- Reads: The Muses ONLY (curated knowledge)
- Writes: Discovery Vector DB

**Output**: Discovery records with confidence scores

**Workflow**:
1. Scans The Muses for patterns
2. Analyzes cluster relationships
3. Generates discovery records (title, description, confidence)
4. Stores discoveries in Discovery Vector DB
5. Triggers SQL Gatekeeper for high-confidence projects
6. Sends notifications via The Liaison

**Key Constraint**: NEVER runs on The Lethe (too large, mixed quality)

**Pattern Detection Decision Tree**:
```
Scan The Muses clusters
│
├─ Multiple clusters about same topic?
│  └─ Create discovery: "project_candidate"
│     └─ Confidence = cluster_overlap × note_recency × semantic_density
│        │
│        ├─ Confidence >= 80%? → Send to SQL Gatekeeper
│        ├─ Confidence 60-80%? → Send to SQL Gatekeeper
│        └─ Confidence < 60%? → Store in Discovery DB only
│
├─ Contradictory statements across notes?
│  └─ Create discovery: "contradiction"
│     └─ Send notification via The Liaison
│
├─ Emerging theme (new cluster growth)?
│  └─ Create discovery: "emerging_theme"
│     └─ Send notification via The Liaison
│
└─ Orphaned notes (weak cluster links)?
   └─ Create discovery: "weak_link"
      └─ Send notification via The Liaison
```

---

## Layer 4: Iris (Intelligence Services)

**Iris** is the user-facing intelligence layer, providing semantic search and query answering capabilities.

**Also known as**: Reactive Agent (in story documents)

**Components**:
1. **Multi-RAG**: Multi-database RAG capabilities
2. **Semantic Search**: Search routing across The Muses/The Lethe

---

### Capabilities

**Core Functions**:
- Semantic search across The Muses and/or The Lethe
- Query routing (determines which database to search)
- RAG-enhanced responses
- Multi-hop reasoning with LangGraph
- Can detect "projectness" in user queries
- LangGraph checkpointing for long-running tasks

**Triggers**: User messages via The Liaison (Hermes)

**Data Access**:
- Reads: The Muses, The Lethe, The Ananke (via RAG)
- Writes: None (read-only agent)

**Example Interactions**:
- User: "What are my notes about Docker?"
  - → Iris searches The Muses
- User: "Find emails from John about the project"
  - → Iris searches The Lethe
- User: "Do I have a project about machine learning?"
  - → Iris queries The Ananke + The Muses

**Query Routing Logic**:
```
User Query → Router Analysis
│
├─ Query about notes/ideas/patterns?
│  └─ Search The Muses (core knowledge)
│
├─ Query about emails/documents?
│  └─ Search The Lethe (archive)
│
├─ Query about projects/deadlines?
│  └─ Query The Ananke (SQL)
│
└─ Query needs comprehensive answer?
   └─ Search ALL databases, merge results
```

**Implementation**: Phase 2-3 (Stories 005-009)

---

## Layer 5: Hermes (Interaction Layer)

**Hermes** is the user communication layer, managing all interactions between the user and the system.

**Components**:
1. **The Liaison** - Message routing and formatting
2. **The Project Manager** - Active project lifecycle management

**Primary Interface**: Telegram bot

**Future Interfaces**: Web (planned)

---

### The Liaison

**Role**: Message routing and formatting layer between user and agents

**Capabilities**:
- Routes user commands to appropriate agents
- Formats agent responses for Telegram
- Manages conversation state
- Handles approval workflows
- Sends proactive notifications

**Message Types**:

**Proactive Notifications** (Agent → User):
- Discovery proposals (from Scout)
- Deadline reminders (from Project Manager)
- Stall alerts (from Project Manager)
- Orphaned discoveries (from Monitor Agent)
- Daily/weekly digests (from Project Manager)

**User-Initiated** (User → Agent):
- Commands (see command list below)
- Natural language queries (routed to Iris)

---

### The Project Manager (Phase 4: Story 016)

**Also known as**: Strategist

**Role**: Active project lifecycle management in The Ananke

**Architecture Note**: While The Project Manager has scheduled triggers (8 AM daily), it's architecturally part of the Interaction Layer because it manages the dialogue between user and project state.

**Capabilities**:
- Deadline enforcement (ensures all active projects have deadlines)
- Pressure score calculation (Work ÷ Time)
- Stall detection (no updates in 7+ days)
- Deadline reminders (<3 days)
- Daily digests and weekly summaries

**Triggers**:
- Scheduled: Daily (8 AM), Weekly (Sunday 9 AM)
- User commands via Telegram

**Workflow (Daily at 8 AM)**:
1. Check active projects for missing deadlines → Request from user
2. Calculate pressure scores for all projects
3. Identify stalled projects (no updates 7+ days) → Alert user
4. Check approaching deadlines (<3 days) → Remind user
5. Send daily digest (status summary, top 3 high-pressure)

**Pressure Score Algorithm**:
```python
pressure = work_estimate / time_remaining_hours
# Default work_estimate: 20 hours (medium project)
# Overdue projects: pressure = 999.0
```

**Data Access**:
- Reads: The Ananke (projects table)
- Writes: The Ananke (pressure scores, timestamps)

**User Interactions** (via Telegram):
- `/projects [status]` - List projects (active/candidate/paused/completed)
- `/set_deadline {project_id} 7d` - Set deadline
- `/complete_project {project_id}` - Mark as done
- `/pause_project {project_id}` - Pause tracking
- `/extend_deadline {project_id} 3d` - Extend deadline
- `/update_project {project_id}` - Mark as recently touched (unstall)
- `/view_project {project_id}` - Full project details

---

## Supporting Agents

### Monitor Agent (Phase 4: Story 015)

**Role**: Reconciles Discovery Vector DB with The Ananke (SQL)

**Purpose**: Ensures high-value discoveries don't get lost when SQL Gatekeeper denies them

**Capabilities**:
- Finds "orphaned discoveries" (high confidence but not in SQL)
- Tracks user responses to avoid re-asking
- Re-surfaces discoveries when confidence increases (+15%)
- Reconciliation state management (SQLite)

**Triggers**: Scheduled (daily at 3 AM)

**Workflow**:
1. Query Discovery DB for high-confidence discoveries (>70%)
2. Check which exist in The Ananke
3. Identify orphans (not in SQL)
4. Filter out already-asked/rejected/snoozed
5. Forward to user via The Liaison
6. Track user responses

**Data Access**:
- Reads: Discovery Vector DB, The Ananke
- Writes: Monitor State DB (SQLite)

**User Interactions** (via Telegram):
- `/monitor_approve {discovery_id}` - Add to SQL projects
- `/monitor_reject {discovery_id}` - Not a project (logged)
- `/monitor_snooze {discovery_id} 7d` - Ask again later
- `/monitor_view {discovery_id}` - Full details
- `/monitor_status` - Agent statistics

**Reconciliation Logic**:
```
Daily at 3 AM:
│
Query Discovery DB: confidence > 70%
│
For each discovery:
│
├─ Exists in The Ananke (projects table)?
│  └─ YES: Skip (already committed)
│  └─ NO: Orphaned discovery
│     │
│     Check Monitor State DB:
│     │
│     ├─ Never asked before?
│     │  └─ Forward to user via The Liaison
│     │
│     ├─ User rejected previously?
│     │  └─ Confidence increased by +15%?
│     │     ├─ YES: Forward to user (re-ask)
│     │     └─ NO: Skip (respect rejection)
│     │
│     └─ User snoozed?
│        └─ Snooze expired?
│           ├─ YES: Forward to user
│           └─ NO: Skip (still snoozed)
```

---

## Layer 6: Prometheus (Execution & Drafting) [Phase 5+]

**Status**: Designed but not yet implemented

**Purpose**: Generative layer that creates actionable project plans from discovered patterns, bridging pattern detection (Argus) to committed projects (The Ananke).

**Components**:

### 1. The Architect

**Role**: Drafts project proposals and implementation plans

**Capabilities** (Planned):
- Generates detailed project proposals from discoveries
- Creates implementation plans with steps
- Suggests deadlines and work estimates
- Drafts sub-tasks and dependencies

**Input**: High-confidence discoveries from Scout
**Output**: Proposals stored in Proposal DB

**Future Workflow**:
1. Scout creates discovery
2. The Architect drafts detailed proposal
3. Proposal sent to user via The Liaison
4. User reviews and approves/rejects
5. If approved: SQL Gatekeeper writes to The Ananke

### 2. Proposal DB

**Purpose**: Stores generated proposals awaiting user review

**Planned Schema**:
```python
{
    "class": "Proposals",
    "properties": [
        {"name": "proposalId", "dataType": ["text"]},
        {"name": "discoveryId", "dataType": ["text"]},  # Source discovery
        {"name": "title", "dataType": ["text"]},
        {"name": "fullProposal", "dataType": ["text"]},  # Detailed plan
        {"name": "estimatedWork", "dataType": ["int"]},  # Hours
        {"name": "suggestedDeadline", "dataType": ["date"]},
        {"name": "createdAt", "dataType": ["date"]},
        {"name": "userReviewed", "dataType": ["boolean"]}
    ]
}
```

**Future Integration**: Phase 5+

---

## Complete System Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                      Thomas (User)                                 │
│                      via Web/Phone                                 │
└────────────────────────┬───────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  HERMES (Interaction Layer)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────┐      ┌──────────────────────────┐        │
│  │   The Liaison       │      │  The Project Manager     │        │
│  ├─────────────────────┤      ├──────────────────────────┤        │
│  │ • Route commands    │      │ • Deadline enforcement   │        │
│  │ • Format messages   │      │ • Pressure calculation   │        │
│  │ • Manage approvals  │      │ • Stall detection        │        │
│  │ • Send notifications│      │ • Daily/weekly digests   │        │
│  └─────────────────────┘      └──────────────────────────┘        │
│                                                                     │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│               IRIS (Intelligence Services)                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────┐         ┌────────────────────┐              │
│  │   Multi-RAG      │         │  Semantic Search   │              │
│  ├──────────────────┤         ├────────────────────┤              │
│  │ • Query routing  │         │ • The Muses search │              │
│  │ • Multi-DB RAG   │         │ • The Lethe search │              │
│  │ • LangGraph      │         │ • Result merging   │              │
│  └──────────────────┘         └────────────────────┘              │
│                                                                     │
└────────────┬────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              ALEXANDRIA (Storage & Governance)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐       │
│  │  The Muses   │  │  The Lethe   │  │   The Ananke       │       │
│  │  (Vectors)   │  │ (Big Vector  │  │    (SQL)           │       │
│  │              │  │  Archive)    │  │                    │       │
│  ├──────────────┤  ├──────────────┤  ├────────────────────┤       │
│  │ Obsidian     │  │ Emails       │  │ Projects           │       │
│  │ vault        │  │ PDFs         │  │ Cluster metadata   │       │
│  │ ~2.5k chunks │  │ OCR docs     │  │ Audit logs         │       │
│  │              │  │ 30k-100k     │  │                    │       │
│  │              │  │ chunks       │  │                    │       │
│  └──────────────┘  └──────────────┘  └────────────────────┘       │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │           Discovery Vector DB                            │     │
│  │           (Pattern discoveries from Scout)               │     │
│  └──────────────────────────────────────────────────────────┘     │
│                                                                     │
└────────────┬────────────────────────────────────────────────────────┘
             │
             │ (controlled by)
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   THE GATES (Approval Layer)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────┐      ┌─────────────────────┐            │
│  │ SQL Project          │      │ Obsidian            │            │
│  │ Gatekeeper           │      │ Gatekeeper          │            │
│  ├──────────────────────┤      ├─────────────────────┤            │
│  │ Controls writes to   │      │ Shadow copy pattern │            │
│  │ The Ananke           │      │ for vault edits     │            │
│  │                      │      │                     │            │
│  │ Confidence threshold │      │ User approves diffs │            │
│  │ User approval req    │      │                     │            │
│  └──────────────────────┘      └─────────────────────┘            │
│                                                                     │
└────────────┬────────────────────────────────────────────────────────┘
             │
             │ (receives discoveries from)
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                  ARGUS (Subconscious)                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────┐      ┌─────────────────────┐            │
│  │      Scout           │      │  Discovery Vector   │            │
│  │ (Latent Scout)       │─────▶│       DB            │            │
│  ├──────────────────────┤      └─────────────────────┘            │
│  │ • Pattern detection  │                                          │
│  │ • Project discovery  │                                          │
│  │ • Theme analysis     │                                          │
│  │ • Contradiction find │                                          │
│  │                      │                                          │
│  │ Scans: The Muses     │                                          │
│  │ Trigger: Nightly     │                                          │
│  └──────────────────────┘                                          │
│                                                                     │
└────────────┬────────────────────────────────────────────────────────┘
             │
             │ (future: feeds)
             ▼
┌─────────────────────────────────────────────────────────────────────┐
│           PROMETHEUS (Execution & Drafting) [Phase 5+]            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────────────┐      ┌─────────────────────┐            │
│  │   The Architect      │      │   Proposal DB       │            │
│  ├──────────────────────┤      ├─────────────────────┤            │
│  │ Drafts project       │─────▶│ Stores generated    │            │
│  │ proposals            │      │ proposals           │            │
│  │                      │      │                     │            │
│  │ Creates impl plans   │      │ Awaits user review  │            │
│  └──────────────────────┘      └─────────────────────┘            │
│                                                                     │
│  Status: Designed but not yet implemented                          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
             ▲
             │
             │
┌────────────┴────────────────────────────────────────────────────────┐
│                INPUT PROCESSING (Sections 1-3)                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Section 1:              Section 2:              Section 3:        │
│  ┌──────────────┐        ┌──────────────┐       ┌──────────────┐  │
│  │ Obsidian     │        │ Email        │       │ OCR + PyPDF  │  │
│  │ Vault        │        │ Archive      │       │ Raw Archives │  │
│  └──────┬───────┘        └──────┬───────┘       └──────┬───────┘  │
│         │                       │                      │           │
│         ▼                       ▼                      ▼           │
│  ┌──────────────┐        ┌──────────────┐       ┌──────────────┐  │
│  │ The Ingestor │        │ Email        │       │ Document     │  │
│  │              │        │ Ingestor     │       │ Processor    │  │
│  │ • Clean MD   │        │              │       │              │  │
│  │ • Chunk      │        │ • Clean HTML │       │ • OCR        │  │
│  │ • Embed      │        │ • Cluster    │       │ • Extract    │  │
│  │              │        │ • Classify   │       │ • Embed      │  │
│  └──────┬───────┘        └──────┬───────┘       └──────┬───────┘  │
│         │                       │                      │           │
│         └───────────────────────┴──────────────────────┘           │
│                                 │                                   │
│                                 ▼                                   │
│                      To Alexandria databases                        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Agent Interaction Matrix

| Component | Reads From | Writes To | Triggers | User Interaction |
|-----------|-----------|-----------|----------|------------------|
| **Iris (Intelligence Services)** | The Muses, The Lethe, The Ananke | None | User message via The Liaison | Direct Q&A via The Liaison |
| **Scout (Argus)** | The Muses | Discovery Vector DB | Scheduled (nightly) | None (proactive) |
| **SQL Gatekeeper (Gates)** | Discovery DB | The Ananke, Audit Log | Scout, Monitor, User | Approval via The Liaison |
| **Obsidian Gatekeeper (Gates)** | Obsidian Vault | Shadow Copy, Vault (after approval) | Shadow agents | Approval of edits |
| **Monitor Agent** | Discovery DB, The Ananke | Monitor State DB | Scheduled (daily 3 AM) | Reconciliation via The Liaison |
| **The Project Manager (Hermes)** | The Ananke | The Ananke | Scheduled (daily 8 AM) + user commands | Project mgmt via The Liaison |
| **The Liaison (Hermes)** | All agents | None | All user/agent messages | All user interactions |
| **The Ingestor** | Obsidian Vault | The Muses | File watcher | None |
| **The Architect (Prometheus)** | Discovery DB | Proposal DB | Future/Phase 5+ | Future |

---

## Telegram Commands (via The Liaison)

### Discovery & Approval (SQL Gatekeeper)
- `/approve_project {approval_id}` - Approve project write to SQL
- `/reject_project {approval_id}` - Reject project proposal
- `/view_project {approval_id}` - View full details before deciding
- `/pending_projects` - List all pending approvals

### Monitor Agent
- `/monitor_approve {discovery_id}` - Add orphaned discovery to projects
- `/monitor_reject {discovery_id}` - Mark discovery as not a project
- `/monitor_snooze {discovery_id} 7d` - Snooze reminder
- `/monitor_view {discovery_id}` - View discovery details
- `/monitor_status` - Show Monitor agent statistics

### Project Management (The Project Manager)
- `/projects [status]` - List projects (active/candidate/paused/completed/all)
- `/set_deadline {project_id} 7d` - Set deadline (7d, 2w, 1m, or YYYY-MM-DD)
- `/complete_project {project_id}` - Mark project as completed
- `/pause_project {project_id}` - Pause project tracking
- `/extend_deadline {project_id} 3d` - Extend deadline
- `/update_project {project_id}` - Touch project (unstall)
- `/view_project {project_id}` - View full project details

### Query & Search (Iris)
- Natural language queries - Routed to Iris for semantic search
- `/search {query}` - Explicit search command
- `/ask {question}` - Explicit question command

### Configuration
- `/set_confidence {type} {value}` - Adjust confidence thresholds

---

## Scheduled Jobs Timeline

| Time | Component | Task | Frequency |
|------|-----------|------|-----------|
| Continuous | The Ingestor | Watch Obsidian vault for changes | File watcher |
| 3:00 AM | Monitor Agent | Discovery reconciliation | Daily |
| 8:00 AM | The Project Manager | Project health checks | Daily |
| 9:00 AM Sunday | The Project Manager | Weekly summary | Weekly |
| Nightly | Scout (Argus) | Pattern detection scan | Daily (configurable) |

---

## Data Flow: Obsidian → Pattern Discovery → Project Commitment

```
┌─────────────────┐
│ Obsidian Vault  │
│  (User writes)  │
└────────┬────────┘
         │
         │ File watcher detects changes
         ▼
┌─────────────────┐
│  The Ingestor   │ Story 000
│                 │
│ 1. Clean MD     │
│ 2. Chunk (400)  │
│ 3. Embed        │
└────────┬────────┘
         │
         │ Store chunks
         ▼
┌─────────────────┐
│   The Muses     │ (Alexandria)
│   (Weaviate)    │
│  ~2,500 chunks  │
└────────┬────────┘
         │
         │ Nightly scan
         ▼
┌─────────────────┐
│     Scout       │ (Argus) Story 010
│                 │
│ • Cluster scan  │
│ • Pattern find  │
│ • Confidence    │
└────────┬────────┘
         │
         │ Create discovery
         ▼
┌─────────────────┐
│  Discovery DB   │ (Alexandria)
│   (Weaviate)    │
└────────┬────────┘
         │
         │ High confidence (>60%)
         ▼
┌─────────────────┐
│ SQL Gatekeeper  │ (Gates) Story 014
│                 │
│ Confidence      │
│ threshold       │
└────────┬────────┘
         │
         │ Request approval
         ▼
┌─────────────────┐
│  The Liaison    │ (Hermes)
│   (Telegram)    │
└────────┬────────┘
         │
         │ User approves
         ▼
┌─────────────────┐
│   The Ananke    │ (Alexandria)
│  (PostgreSQL)   │
│   projects      │
└─────────────────┘
```

---

## Data Flow: Email Archive → Search Retrieval

```
┌─────────────────┐
│  Email Archive  │
│   (19k emails)  │
└────────┬────────┘
         │
         │ Email Hygiene Pipeline
         ▼
┌─────────────────┐
│ Email Ingestor  │ Story 001
│                 │
│ 1. Clean HTML   │
│ 2. Cluster      │
│ 3. Classify     │
│ 4. Embed        │
└────────┬────────┘
         │
         │ Store chunks
         ▼
┌─────────────────┐
│   The Lethe     │ (Alexandria)
│   (Weaviate)    │
│ 30k-100k chunks │
└────────┬────────┘
         │
         │ User query: "Find email from John"
         ▼
┌─────────────────┐
│      Iris       │ (Intelligence Services)
│   + Router      │ Story 005
│                 │
│ Detects: email  │
│ → Query Lethe   │
└────────┬────────┘
         │
         │ Returns results
         ▼
┌─────────────────┐
│  The Liaison    │ (Hermes)
│   (Telegram)    │
└─────────────────┘
```

---

## Data Flow: Monitor Agent Reconciliation

```
Daily at 3 AM:

┌─────────────────┐
│  Discovery DB   │ (Alexandria)
│                 │
│ High confidence │
│ discoveries     │
└────────┬────────┘
         │
         │ Monitor Agent queries
         ▼
┌─────────────────┐
│ Monitor Agent   │ Story 015
│                 │
│ For each disc:  │
│ Check in SQL?   │
└────────┬────────┘
         │
         │ Query projects
         ▼
┌─────────────────┐
│   The Ananke    │ (Alexandria)
│  (PostgreSQL)   │
└────────┬────────┘
         │
         │ Not found = orphan
         ▼
┌─────────────────┐
│ Monitor State   │
│   (SQLite)      │
│                 │
│ Already asked?  │
│ Snoozed?        │
└────────┬────────┘
         │
         │ New orphan found
         ▼
┌─────────────────┐
│  The Liaison    │ (Hermes)
│   (Telegram)    │
│                 │
│ "Reconsider?"   │
└────────┬────────┘
         │
         │ User: /monitor_approve
         ▼
┌─────────────────┐
│ SQL Gatekeeper  │ (Gates) Story 014
│                 │
│ Write to SQL    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   The Ananke    │ (Alexandria)
│  (New project)  │
└─────────────────┘
```

---

## Data Flow: Project Manager Daily Routine

```
Daily at 8 AM:

┌─────────────────┐
│   The Ananke    │ (Alexandria)
│  (PostgreSQL)   │
│                 │
│ All projects    │
└────────┬────────┘
         │
         │ Project Manager scans
         ▼
┌─────────────────────────────┐
│   The Project Manager       │ (Hermes) Story 016
│                             │
│ 1. Missing deadlines?       │
│    → Request from user      │
│                             │
│ 2. Calculate pressure       │
│    pressure = work/time     │
│    → Update SQL             │
│                             │
│ 3. Stalled (7+ days)?       │
│    → Alert user             │
│                             │
│ 4. Deadline < 3 days?       │
│    → Remind user            │
│                             │
│ 5. Daily digest             │
│    → Send summary           │
└────────┬────────────────────┘
         │
         │ All notifications
         ▼
┌─────────────────┐
│  The Liaison    │ (Hermes)
│   (Telegram)    │
│                 │
│ • Deadline req  │
│ • Stall alerts  │
│ • Reminders     │
│ • Daily digest  │
└────────┬────────┘
         │
         │ User: /set_deadline 123 7d
         ▼
┌─────────────────┐
│ Project Manager │ (Hermes)
│                 │
│ Update deadline │
│ Recalc pressure │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   The Ananke    │ (Alexandria)
│  (Updated)      │
└─────────────────┘
```

---

## Performance Considerations

### The Muses (Fast Path)
- **Size**: ~2,500 chunks
- **Clustering**: ~5 minutes on Pi 5
- **Enables**: Nightly pattern detection
- **Constraint**: Obsidian vault only

### The Lethe (Slow Path)
- **Size**: 30k-100k+ chunks
- **Clustering**: 60-90 minutes (emails only)
- **Enables**: Comprehensive search/retrieval
- **Constraint**: Never used for pattern detection

### Optimization Strategy
- Expensive analysis runs ONLY on The Muses
- The Lethe grows infinitely without slowing agents
- Hard database separation prevents accidental expensive operations

---

## Security & Safety Layers

### Gatekeeper Protection (The Gates)

**Layer 1: SQL Project Gatekeeper**
- Prevents unauthorized writes to The Ananke
- Confidence threshold enforcement (>60%)
- User approval required for all projects
- Complete audit trail

**Layer 2: Obsidian Gatekeeper**
- Shadow copy pattern for vault edits
- User reviews diffs before applying
- Prevents automated corruption of notes

**Layer 3: Monitor Agent State**
- Prevents spam by tracking ask history
- Respects user rejections
- Snooze functionality

### User Control Points

1. **Project Approval**: User decides what becomes a committed project
2. **Deadline Setting**: User sets realistic deadlines
3. **Project Status**: User pauses/completes/extends as needed
4. **Discovery Review**: User can view full details before approving
5. **Confidence Thresholds**: User can adjust sensitivity (`/set_confidence`)

---

## Technology Stack

### Storage Layer (Alexandria)
- **Weaviate**: The Muses, The Lethe, Discovery DB
- **PostgreSQL**: The Ananke (projects, clusters, audit)
- **SQLite**: Monitor state, Ingestion state

### AI/ML
- **Ollama**: Local embeddings (qwen3-embedding:0.6b), LLM (qwen3:0.6b)
- **LangGraph**: Iris state management, checkpointing
- **MiniBatchKMeans**: Email clustering (The Lethe)

### Communication (Hermes)
- **Telegram Bot API**: The Liaison (all user interactions)

### Processing (Input Layer)
- **Watchdog**: File system monitoring (Obsidian vault)
- **APScheduler**: Agent scheduling (Monitor, Project Manager, Scout)
- **LangChain**: Text splitting, RAG pipeline

---

## Implementation Phases

### Phase 0: Input Processing (Stories 000-003)
- Story 000: The Ingestor (Obsidian → The Muses)
- Story 001: Email Ingestor (Emails → The Lethe)
- Story 002: Obsidian Gatekeeper (Shadow copy pattern)
- Story 003: Document Processor (PDFs/OCR → The Lethe)

### Phase 1: Clustering & Taxonomy (Stories 001-003 legacy numbering)
- Cluster analysis on The Muses
- Graph taxonomy generation
- Structured metadata synthesis

### Phase 2: Query Intelligence (Stories 005-007)
- Iris: Multi-RAG capabilities
- Query routing
- Semantic search

### Phase 3: LangGraph Showcase (Stories 008-009)
- Advanced multi-hop reasoning
- Checkpointing demonstrations

### Phase 4: Argus (Latent Scout) (Stories 010-016)
- Story 010: Scout pattern detection
- Story 011: Weak link discovery
- Story 012: Proactive notifications
- Story 013: Discovery feed management
- Story 014: SQL Gatekeeper (The Gates)
- Story 015: Monitor Agent
- Story 016: The Project Manager (Hermes)

### Phase 5: Prometheus (Future)
- The Architect: Proposal generation
- Proposal DB implementation
- Integration with Scout and The Gates

---

## Quick Reference: "Who Does What?"

**Q: Who watches my Obsidian vault?**
A: The Ingestor (Story 000) - ingests to The Muses

**Q: Who finds project ideas in my notes?**
A: Scout (Argus, Story 010) - scans The Muses nightly

**Q: Who decides if a project gets committed to SQL?**
A: You (via SQL Gatekeeper approval through The Liaison)

**Q: Who makes sure I don't miss high-value discoveries?**
A: Monitor Agent (Story 015) - reconciliation loop

**Q: Who nags me about project deadlines?**
A: The Project Manager (Hermes, Story 016) - daily health checks

**Q: Who answers my questions?**
A: Iris (Stories 005-009) - query routing and RAG

**Q: Who can write to The Ananke (SQL)?**
A: ONLY SQL Gatekeeper (Gates, Story 014) - after your approval

**Q: Who can edit my Obsidian vault?**
A: Obsidian Gatekeeper (Gates, Story 002) - via shadow copy + your approval

**Q: Where are my emails stored?**
A: The Lethe (Alexandria, Story 001) - retrieval only, not analyzed

**Q: Where is my core knowledge for analysis?**
A: The Muses (Alexandria, Story 000) - Obsidian vault only

**Q: Who routes all my interactions?**
A: The Liaison (Hermes) - message routing and formatting

**Q: What's the difference between Scout and Iris?**
A: Scout (Argus) runs proactively at night to find patterns. Iris responds to your queries on-demand.

---

## Naming Conventions Summary

| Canonical Name | Also Known As | Layer | Stories |
|---------------|---------------|-------|---------|
| **The Ingestor** | The Graphos | Input Processing | 000 |
| **Scout** | Latent Scout | Argus (Subconscious) | 010-013 |
| **Iris** | Reactive Agent, Intelligence Services | Intelligence Layer | 005-009 |
| **The Liaison** | - | Hermes (Interaction) | Implicit in Hermes |
| **The Project Manager** | Strategist | Hermes (Interaction) | 016 |
| **The Muses** | Core Knowledge, Vectors | Alexandria (Storage) | 000 |
| **The Lethe** | Big Vector Archive | Alexandria (Storage) | 001, 003 |
| **The Ananke** | SQL, Hard Facts | Alexandria (Storage) | Multiple |
| **The Gates** | Gatekeeper Layer | Approval Layer | 014, 002 |
| **Argus** | Subconscious | Pattern Discovery | 010-016 |
| **Alexandria** | Storage & Governance | Storage Layer | Multiple |
| **Prometheus** | Execution & Drafting | Generative Layer | Phase 5+ |

---

## End of System Architecture Document

**Document Version**: 2.0 (Aligned with architectural drawing)
**Last Updated**: 2025-12-26
**Total Stories**: 18 (Phase 0-4)
**Architectural Layers**: 6 named layers
**Total Components**:
- 3 Weaviate collections (The Muses, The Lethe, Discovery DB)
- 1 PostgreSQL database (The Ananke)
- 2 SQLite databases (Monitor state, Ingestion state)
- 6+ agents/components across layers
**User Interface**: Telegram (The Liaison in Hermes)

For implementation details, see individual user stories in:
- `phase-0-ingestion-hygiene/` (Stories 000-003)
- `phase-1-clustering-taxonomy/` (Stories 001-003 of original numbering)
- `phase-2-query-intelligence/` (Stories 005-007)
- `phase-3-langgraph-showcase/` (Stories 008-009)
- `phase-4-latent-scout/` (Stories 010-016)
