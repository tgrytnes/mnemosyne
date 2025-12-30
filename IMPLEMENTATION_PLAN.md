# Mnemosyne Implementation Plan

## 🎯 Project Overview

Building a personal knowledge management system with AI-powered pattern discovery on Raspberry Pi 5.

## 📦 Infrastructure Status

### ✅ Already Running (Docker Containers)

| Service | Container | Port | Data Location | Status |
|---------|-----------|------|---------------|--------|
| **Ollama** | `ollama` | 11434 | `/srv/.../yourproj_ollama_data` | ✅ Running |
| **Weaviate** | `weaviate` | 8081 | `/mnt/sda1/digital_vault/.weaviate_data` | ✅ Running |
| **PostgreSQL (Crystal)** | `crystal_db` | 5432 | - | ✅ Running |
| **Redis** | `redis` | 6379 | - | ✅ Running |

### 📊 Available Resources on Raspberry Pi

| Resource | Location | Count | Notes |
|----------|----------|-------|-------|
| **Obsidian Vault** | `/mnt/sda1/digital_vault/02_active/notes/Obsidian/` | 512 .md files | Active vault with .obsidian config |
| **Email Archive** | `/mnt/sda1/digital_vault/raw_email_archive/` | 19k+ emails | Posteo + Google, .eml format |
| **Email Data (TSV)** | `/mnt/sda1/digital_vault/` | - | Pre-processed: cleaned_emails_full.tsv (33MB) |
| **PDF Scans** | `/mnt/sda1/digital_vault/01_inbox/scans/` | 6 PDFs | Scanned documents |
| **Documents** | `/mnt/sda1/digital_vault/*/documents/` | - | Various locations |

### 🤖 Available Ollama Models

```
✅ qwen3-embedding:0.6b    (1024-dim embeddings)
✅ qwen3:0.6b               (LLM for lightweight tasks)
✅ qwen3:1.7b               (Larger LLM)
✅ all-minilm:latest
✅ nomic-embed-text:latest
✅ gemma3:1b
```

## 📋 Implementation Order & Checklist

### Incremental E2E Pipeline Plan (Current Focus)

This plan follows your sequence: vault data → embeddings DB → scout + project manager → Telegram, with E2E tests at each step.

1. **Vault ingestion + embeddings DB working (Story 000)**  
   Goal: reliable ingestion, chunking, embeddings, and Weaviate writes/reads.  
   E2E: `test_vault_to_muses.py` (ingest → query).
2. **Cluster + profile pipeline (Phase 1 Stories 001-002)**  
   Goal: embeddings → clusters → profiles stored in Postgres.  
   E2E: `test_clustering_pipeline.py` (ingest → cluster → profile).
3. **Checkpointed knowledge + semantic routing (Stories 004-005)**  
   Goal: LangGraph state persistence + routing decisions for Iris.  
   E2E: `test_checkpointed_state.py`, `test_semantic_router.py`.
4. **Scout + Gatekeeper + Project Manager (Stories 010, 014, 016) - local output first**  
   Goal: discoveries + project records without Telegram; log/CLI output OK.  
   E2E: `test_scout_discovery.py`, `test_gatekeeper_workflow.py`, `test_project_manager_integration.py`.
5. **Telegram communication layer (Story 012, plus hooks into 010/014/016)**  
   Goal: notifications, approvals, and commands via Hermes.  
   E2E: new end-to-end tests for notifications + approval flows.

### Phase 0: Foundation & Ingestion (Weeks 1-2)

#### ✅ Story 000: Obsidian Vault Ingestion (The Muses)
**Priority: CRITICAL - Foundation for everything**
- [ ] Create Aletheia package structure
- [ ] Implement ObsidianIngestor class
  - [ ] File watcher (watchdog)
  - [ ] Markdown cleaner (remove frontmatter, wiki-links)
  - [ ] Text chunker (400 chars, 100 overlap)
  - [ ] Ollama embedding client (qwen3-embedding:0.6b)
- [ ] Create Weaviate collection "TheMuses"
- [ ] Implement ingestion state tracking (SQLite)
- [ ] Test with vault: `/mnt/sda1/digital_vault/02_active/notes/Obsidian/`
- [ ] Verify: 512 files → ~1,500-2,500 chunks in TheMuses
- [ ] Uncomment unit tests in `tests/unit/test_ingestor.py`
- [ ] Run: `pytest tests/unit/test_ingestor.py -v`

**Endpoints:**
- Ollama: `http://localhost:11434`
- Weaviate: `http://localhost:8081`

**Output:** TheMuses collection populated with 1,500-2,500 chunks

---

#### ⬜ Story 024: Email Archive Ingestion (The Lethe)
**Priority: HIGH - Large dataset for retrieval**
- [ ] Create EmailIngestor class
- [ ] Parse .eml files from `/mnt/sda1/digital_vault/raw_email_archive/Posteo/`
- [ ] Extract: subject, from, to, date, body
- [ ] Alternative: Use pre-processed `cleaned_emails_full.tsv` (33MB)
- [ ] Chunk email bodies (larger chunks: 800 chars)
- [ ] Generate embeddings (qwen3-embedding:0.6b)
- [ ] Create Weaviate collection "TheLethe"
- [ ] Test with sample (1,000 emails first)
- [ ] Full ingestion: 19k emails → ~30k-50k chunks
- [ ] Verify: Emails queryable by sender, date, subject

**Note:** Use MiniBatchKMeans for clustering (from Story 011)

**Output:** TheLethe collection with email archive

---

#### ⬜ Story 025: Shadow Copy & Hygiene (Obsidian Gatekeeper)
**Priority: CRITICAL - Safety for automated edits**
- [ ] Create shadow vault directory: `/mnt/sda1/digital_vault/02_active/notes/Obsidian_Shadow/`
- [ ] Implement Janitor service
  - [ ] Sync source → shadow on file changes
  - [ ] Text normalization (whitespace, line endings)
- [ ] Implement ObsidianGatekeeper class
  - [ ] Track pending approvals (SQLite)
  - [ ] Generate diffs
  - [ ] Approve/reject workflow
- [ ] Integrate with Hermes (Telegram) for approval commands
  - [ ] `/review_pending`
  - [ ] `/diff {approval_id}`
  - [ ] `/approve {approval_id}`
  - [ ] `/reject {approval_id}`
- [ ] Audit log (SQLite)
- [ ] Uncomment tests: `tests/unit/test_gatekeeper.py`

**Output:** Safe automated editing with approval workflow

---

#### ⬜ Story 026: PDF/OCR Ingestion (The Lethe)
**Priority: MEDIUM - Small dataset**
- [ ] Create PDFIngestor class
- [ ] OCR support (Tesseract or similar)
- [ ] Process PDFs from `/mnt/sda1/digital_vault/01_inbox/scans/`
- [ ] Extract text, chunk, embed
- [ ] Store in TheLethe collection (sourceType: "pdf")
- [ ] Test with 6 scanned PDFs

**Output:** PDFs searchable in TheLethe

---

### Phase 1: Semantic Extraction (Weeks 3-4)

#### ⬜ Story 001 (Phase 1): Cluster Centroid Node
**Priority: HIGH - Enables pattern discovery**
- [ ] Implement clustering for TheMuses
  - [ ] Fetch all embeddings from TheMuses
  - [ ] MiniBatchKMeans clustering (k=20-50)
  - [ ] Calculate centroids
- [ ] Store cluster metadata in PostgreSQL (The Ananke)
  - [ ] Create clusters table
  - [ ] Store: centroid_embedding, note_count, created_at
- [ ] Performance target: <5 minutes for 2,000 chunks

**Output:** Clustered knowledge base in The Ananke

---

#### ⬜ Story 002 (Phase 1): Structured Metadata Synthesis
**Priority: HIGH - Creates cluster profiles**
- [ ] Implement cluster profiling
  - [ ] Extract top keywords (TF-IDF)
  - [ ] Generate theme summary (Ollama qwen3:0.6b)
  - [ ] Extract common tags
- [ ] Store cluster profiles in The Ananke
- [ ] Test with 20-50 clusters from TheMuses

**Output:** Rich cluster metadata for pattern detection

---

#### ⬜ Story 003 (Phase 1): Automated Graph Taxonomy
**Priority: MEDIUM - Enhances organization**
- [ ] Generate hierarchical taxonomy from clusters
- [ ] Create parent-child relationships
- [ ] Store as JSON in The Ananke
- [ ] Export to Obsidian-compatible format

**Output:** Knowledge graph taxonomy

---

### Phase 2: Efficiency Engine (Week 5)

#### ⬜ Story 004: Checkpointed Knowledge (LangGraph State)
**Priority: HIGH - Enables Iris intelligence**
- [ ] Set up LangGraph StateGraph for Iris
- [ ] Implement checkpoint/restore
- [ ] Redis integration for state persistence
  - Use existing Redis container on port 6379
- [ ] Test multi-turn conversations

**Dependencies:** Redis container already running

**Output:** Stateful conversation handling

---

#### ⬜ Story 005: Semantic Routing (Iris Router)
**Priority: HIGH - Performance optimization**
- [ ] Create Iris package structure
- [ ] Implement SemanticRouter class
  - [ ] Query embedding
  - [ ] Cache lookup (SQLite)
  - [ ] Decision logic: cache/TheMuses/TheLethe/web
- [ ] Router node in LangGraph
- [ ] Cache with 0.95 similarity threshold
- [ ] Performance: <100ms routing decision
- [ ] Uncomment tests: `tests/unit/test_router.py`

**Output:** Fast, intelligent query routing

---

#### ⬜ Story 006: Delta Sync Node
**Priority: MEDIUM - Incremental updates**
- [ ] Detect vault changes since last sync
- [ ] Incremental re-embedding
- [ ] Update TheMuses collection
- [ ] Invalidate related cache entries

**Output:** Efficient vault updates

---

### Phase 3: Showcase (Week 6)

#### ⬜ Story 007: Multi-Turn Reasoning Loop
**Priority: MEDIUM - User-facing feature**
- [ ] Implement conversation flow in LangGraph
- [ ] Context window management
- [ ] Multi-turn state tracking
- [ ] Test with Obsidian queries

**Output:** Intelligent Q&A system

---

#### ⬜ Story 008: Traceable Showcase
**Priority: LOW - Demo feature**
- [ ] Create web UI for testing (optional)
- [ ] Show LangGraph execution trace
- [ ] Display sources and reasoning

**Output:** Transparent AI reasoning

---

#### ⬜ Story 009: Actionable Synthesis
**Priority: LOW - Advanced feature**
- [ ] Generate synthesis from clusters
- [ ] Write to shadow vault
- [ ] Request approval via Gatekeeper

**Output:** AI-generated insights

---

### Phase 4: Latent Scout (Weeks 7-8)

#### ⬜ Story 010: Autonomous Pattern Detection (Scout)
**Priority: CRITICAL - Core innovation**
- [ ] Create Argus package structure
- [ ] Implement LatentScout class
  - [ ] Scan TheMuses clusters nightly (3 AM)
  - [ ] Pattern detection algorithms
    - [ ] Project candidates (keywords: project, deadline, milestone)
    - [ ] Improvement opportunities (keywords: optimize, improve, faster)
    - [ ] Technical references (keywords: documentation, API, reference)
  - [ ] Confidence scoring (0.0-1.0)
  - [ ] Cross-cluster pattern detection
- [ ] Create Discovery Vector DB (Weaviate collection)
- [ ] Store discoveries with metadata
- [ ] Scheduled execution (cron or APScheduler)
- [ ] Uncomment tests: `tests/unit/test_scout.py`
- [ ] Performance target: <30 minutes for full scan

**Output:** Automated pattern discovery from vault

---

#### ⬜ Story 011: Radar Vector Exploration
**Priority: MEDIUM - Visualization**
- [ ] Implement cluster visualization
- [ ] Similarity heatmap
- [ ] Export to JSON for frontend

**Output:** Visual cluster exploration

---

#### ⬜ Story 012: Proactive Insight Notifications
**Priority: HIGH - User engagement**
- [ ] Integrate Scout with Hermes (Telegram)
- [ ] Daily digest (8 AM)
  - [ ] New discoveries
  - [ ] Top 3-5 patterns
  - [ ] Confidence scores
- [ ] Commands:
  - [ ] `/discoveries` - List all
  - [ ] `/view_discovery {id}`

**Output:** Daily insights via Telegram

---

#### ⬜ Story 013: Discovery Feed Management
**Priority: MEDIUM - Discovery organization**
- [ ] Filter discoveries by category
- [ ] Mark as read/reviewed
- [ ] Archive low-confidence items

**Output:** Organized discovery feed

---

#### ⬜ Story 014: SQL Project Gatekeeper (The Gates)
**Priority: CRITICAL - Controls The Ananke writes**
- [ ] Create Alexandria package structure
- [ ] Implement SQLProjectGatekeeper class
  - [ ] Confidence thresholds (>0.80 high, 0.60-0.80 medium, <0.60 reject)
  - [ ] Approval request via Telegram
  - [ ] Write to The Ananke only after approval
- [ ] Create projects table in PostgreSQL
  - Can use existing crystal_db container
- [ ] Gatekeeper audit log
- [ ] Telegram commands:
  - [ ] `/approve_project {approval_id}`
  - [ ] `/reject_project {approval_id}`
  - [ ] `/pending_projects`
- [ ] Uncomment tests: `tests/unit/test_gatekeeper.py` (SQL section)

**Output:** Controlled project commitment

---

#### ⬜ Story 015: Monitor Agent
**Priority: MEDIUM - Ensures Scout follow-through**
- [ ] Check Discovery DB for unconverted high-confidence patterns
- [ ] Re-request approval if needed
- [ ] Weekly summary of missed opportunities

**Output:** No high-quality discoveries lost

---

#### ⬜ Story 016: Project Manager Agent (The Strategist)
**Priority: HIGH - Active project management**
- [ ] Create Hermes package structure
- [ ] Implement ProjectManagerAgent class
  - [ ] Calculate pressure scores (Work ÷ Time)
  - [ ] Detect missing deadlines
  - [ ] Identify stalled projects (7+ days no update)
  - [ ] Check approaching deadlines (<3 days)
- [ ] Daily management routine (8 AM)
- [ ] Weekly summary (Sunday 9 AM)
- [ ] Scheduled jobs (APScheduler)
- [ ] Telegram commands:
  - [ ] `/projects [status]`
  - [ ] `/set_deadline {id} {date}`
  - [ ] `/complete_project {id}`
  - [ ] `/pause_project {id}`
  - [ ] `/view_project {id}`
- [ ] Uncomment tests: `tests/unit/test_project_manager.py`

**Output:** Active project tracking and nudges

---

### Phase 5: Vault Curation (Weeks 9-10)

#### ⬜ Story 017: Vault Curator Agent (The Curator)
**Priority: MEDIUM - Vault improvement**
- [ ] Implement VaultCuratorAgent in Argus
- [ ] Weekly curation scan (Sunday 10 AM)
- [ ] 5 improvement detectors:
  - [ ] Missing backlinks (similarity >0.75)
  - [ ] Redundant content (>70% overlap)
  - [ ] Missing tags
  - [ ] Structural issues (orphans, deep nesting)
  - [ ] Inconsistent naming
- [ ] Store proposals in Discovery DB
- [ ] Send top 3-5 via Telegram
- [ ] Commands:
  - [ ] `/view_curation {id}`
  - [ ] `/approve_curation {id}`
  - [ ] `/reject_curation {id}`

**Output:** Proactive vault improvements

---

#### ⬜ Story 018: Vault Editor Agent (The Editor)
**Priority: MEDIUM - Executes approved changes**
- [ ] Implement VaultEditorAgent
- [ ] Execute curation changes in shadow copy
- [ ] Integrate with Obsidian Gatekeeper
- [ ] Support all 5 improvement types
- [ ] Generate diffs for review
- [ ] Commands:
  - [ ] `/review_shadow`
  - [ ] `/approve_shadow {id}`

**Output:** Safe vault editing automation

---

## 📅 Suggested Timeline (10 Weeks)

### Weeks 1-2: Vault + Embeddings DB
- ✅ Story 000: Obsidian ingestion (TheMuses)
- ⬜ Stabilize chunking + embeddings writes/reads
- ⬜ E2E: vault → muses ingestion + query

### Weeks 3-4: Cluster + Profile Pipeline
- ⬜ Story 001 (Phase 1): Clustering
- ⬜ Story 002 (Phase 1): Cluster profiles
- ⬜ E2E: ingest → cluster → profile

### Weeks 5-6: Scout + Project Flow (Local Output)
- ⬜ Story 010: Scout (CRITICAL)
- ⬜ Story 014: SQL Gatekeeper
- ⬜ Story 016: Project Manager
- ⬜ E2E: scout discovery → gatekeeper → project manager

### Weeks 7-8: Telegram Communication Layer
- ⬜ Story 012: Telegram integration
- ⬜ Add Hermes commands + notification flows for Scout/Project Manager
- ⬜ E2E: notification + approval workflows

### Weeks 9-10: Expansion
- ⬜ Story 024: Email ingestion (TheLethe)
- ⬜ Story 025: Shadow copy & Gatekeeper
- ⬜ Story 026: PDF/OCR ingestion (The Lethe)
- ⬜ Story 015: Monitor
- ⬜ Story 017: Curator
- ⬜ Story 018: Editor

## 🏗️ Project Structure

```
Mnemosyne/
├── Aletheia/              Layer 1: Input Processing
│   ├── ingestor.py       Story 000, 024, 026
│   ├── janitor.py        Story 025
│   └── tagger.py         Story 025
│
├── Alexandria/            Layer 2: Storage & Governance
│   ├── weaviate_client.py
│   ├── postgres_client.py
│   ├── obsidian_gatekeeper.py  Story 025
│   └── sql_gatekeeper.py       Story 014
│
├── Argus/                 Layer 3: Subconscious
│   ├── scout.py          Story 010
│   ├── clusterer.py      Story 001 (Phase 1)
│   ├── profiler.py       Story 002 (Phase 1)
│   ├── curator.py        Story 017
│   └── monitor.py        Story 015
│
├── Iris/                  Layer 4: Intelligence Services
│   ├── graph.py          LangGraph setup
│   ├── router.py         Story 005
│   ├── query_handler.py  Story 007
│   └── state.py          Story 004
│
├── Hermes/                Layer 5: Interaction
│   ├── liaison.py        Telegram bot
│   ├── project_manager.py     Story 016
│   └── commands.py       All /commands
│
├── Prometheus/            Layer 6: Execution (Future)
│   └── (Phase 5+)
│
└── tests/                 Testing infrastructure
    ├── unit/             ✅ Ready
    ├── integration/      ✅ Ready
    └── conftest.py       ✅ 20+ fixtures
```

## 🚦 Starting Point: Story 000

**You should start with Story 000** because:
1. ✅ Ollama and Weaviate are already running
2. ✅ Obsidian vault exists (512 files)
3. ✅ Test infrastructure ready
4. ⬜ Foundation for all other stories

### Quick Start Commands

```bash
# 1. Create Aletheia package
mkdir -p Aletheia
touch Aletheia/__init__.py

# 2. Create basic ingestor
# (Implement ObsidianIngestor class)

# 3. Test connection to services
curl http://localhost:11434/api/tags
curl http://localhost:8081/v1/.well-known/ready

# 4. Run initial ingestion test
python -m Aletheia.ingestor --vault /mnt/sda1/digital_vault/02_active/notes/Obsidian --limit 10

# 5. Verify Weaviate collection
curl http://localhost:8081/v1/schema

# 6. Run tests
pytest tests/unit/test_ingestor.py -v
```

## 🎯 Critical Path

**Must complete in order:**

1. **Story 000** → Populates TheMuses
2. **Story 001 (Phase 1)** → Creates clusters
3. **Story 002 (Phase 1)** → Profiles clusters
4. **Story 010** → Scout discovers patterns
5. **Story 014** → Gatekeeper controls writes
6. **Story 016** → Project Manager tracks commitments
7. **Story 012** → Telegram communication layer

All other stories can be done in parallel or skipped initially.

## 📊 Success Metrics

### After Story 000 (Week 2)
- ✅ 512 Obsidian files ingested
- ✅ ~1,500-2,500 chunks in TheMuses
- ✅ Embeddings generated via Ollama
- ✅ Query works: "What notes mention Docker?"

### After Story 010 (Week 8)
- ✅ Scout runs nightly
- ✅ 5-10 patterns discovered per week
- ✅ Discoveries stored in Discovery DB
- ✅ Confidence scores >0.60

### After Story 016 (Week 8)
- ✅ Projects tracked in The Ananke
- ✅ Pressure scores calculated daily
- ✅ Telegram notifications for deadlines
- ✅ No projects stalled >7 days

## 🔧 Technical Notes

### Environment Variables

Create `.env` file:

```bash
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=qwen3-embedding:0.6b
OLLAMA_LLM_MODEL=qwen3:0.6b

# Weaviate
WEAVIATE_HTTP_HOST=localhost
WEAVIATE_HTTP_PORT=8081
WEAVIATE_GRPC_PORT=50051

# PostgreSQL (use existing crystal_db or create new)
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=mnemosyne
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<your_password>

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Paths
VAULT_PATH=/mnt/sda1/digital_vault/02_active/notes/Obsidian
SHADOW_VAULT_PATH=/mnt/sda1/digital_vault/02_active/notes/Obsidian_Shadow
EMAIL_ARCHIVE_PATH=/mnt/sda1/digital_vault/raw_email_archive
PDF_SCAN_PATH=/mnt/sda1/digital_vault/01_inbox/scans

# Telegram (Story 012+)
TELEGRAM_BOT_TOKEN=<your_token>
TELEGRAM_CHAT_ID=<your_chat_id>
```

### Docker Compose (Optional - Services Already Running)

Services already available:
- ✅ Ollama on port 11434
- ✅ Weaviate on port 8081
- ✅ PostgreSQL on port 5432
- ✅ Redis on port 6379

No need to start new containers - use existing ones!

## 📖 Next Steps

1. **Read Story 000** in detail: [`user-stories/phase-0-ingestion-hygiene/story-000-obsidian-vault-ingestion.md`](user-stories/phase-0-ingestion-hygiene/story-000-obsidian-vault-ingestion.md)
2. **Set up environment**: Create `.env` with paths above
3. **Create Aletheia package**: Start implementing ObsidianIngestor
4. **Test with 10 files first**: Don't ingest all 512 immediately
5. **Run unit tests**: Verify implementation works
6. **Full ingestion**: Process entire vault
7. **Move to clustering + profiling**: Stories 001-002 (Phase 1)

---

**📌 Current Status: Ready to start Story 000**

**🎯 First Milestone: TheMuses populated with 1,500-2,500 chunks from Obsidian vault**

---

## 🧪 Testing Strategy & Timeline

### Testing Philosophy: Test-Driven Development (TDD)

For each story, follow this testing sequence:

```
1. Write unit tests first (TDD)
2. Implement code to pass tests
3. Add integration tests when connecting to services
4. Add E2E tests for complete workflows
5. Run all tests before moving to next story
```

### Testing Levels Explained

#### 🟢 Unit Tests (Write FIRST, Run ALWAYS)
- **When**: Before writing implementation code
- **What**: Test individual functions/classes in isolation
- **Mocks**: All external dependencies (Ollama, Weaviate, PostgreSQL)
- **Speed**: <1 second per test
- **Run**: After every code change
- **Command**: `make test` or `pytest tests/unit -m unit`

#### 🟡 Integration Tests (Write AFTER unit tests pass)
- **When**: After unit tests are green
- **What**: Test interactions with real services
- **Requires**: Docker services running (Ollama, Weaviate, PostgreSQL)
- **Speed**: 1-5 seconds per test
- **Run**: Before committing code
- **Command**: `make test-integration` or `pytest tests/integration -m integration`

#### 🔴 E2E Tests (Write LAST, Run for validation)
- **When**: After feature is complete
- **What**: Test complete user workflows end-to-end
- **Requires**: All services + test data
- **Speed**: >5 seconds per test
- **Run**: Before releasing to production
- **Command**: `pytest tests/e2e -m e2e`

---

## 📅 Story-by-Story Testing Plan

### Phase 0: Foundation (Weeks 1-2)

#### Story 000: Obsidian Vault Ingestion

**Week 1, Day 1-2: Unit Tests**
- [ ] Write `test_clean_markdown()` - Test frontmatter removal
- [ ] Write `test_remove_wiki_links()` - Test wiki-link cleaning
- [ ] Write `test_chunk_text()` - Test chunking with overlap
- [ ] Write `test_get_embedding()` - Mock Ollama embedding
- [ ] Write `test_ingestion_state()` - Test state tracking
- [ ] **Run**: `pytest tests/unit/test_ingestor.py::TestMarkdownCleaning -v`
- [ ] **Implement**: ObsidianIngestor.clean_markdown()
- [ ] **Verify**: All unit tests pass

**Week 1, Day 3-4: Integration Tests**
- [ ] Start services: `make services-up`
- [ ] Write `test_weaviate_collection_creation()`
- [ ] Write `test_insert_chunks_to_weaviate()`
- [ ] Write `test_query_by_source_type()`
- [ ] **Run**: `pytest tests/integration/test_weaviate_integration.py -v`
- [ ] **Test with**: 10 files from test_data first
- [ ] **Verify**: Chunks appear in Weaviate

**Week 1, Day 5: E2E Test**
- [ ] Write `test_full_vault_ingestion()`
  - [ ] Ingest test_data/test_vault (50 files)
  - [ ] Verify ~150-250 chunks in TheMuses
  - [ ] Query: "What notes mention Docker?"
  - [ ] Assert results returned
- [ ] **Run**: `pytest tests/e2e/test_vault_to_muses.py -v`
- [ ] **Time target**: Complete in <5 minutes

**Week 2: Production Run**
- [ ] Run with full vault (512 files)
- [ ] Monitor performance (60-90 min target)
- [ ] Verify ~1,500-2,500 chunks
- [ ] Document actual metrics

---

#### Story 024: Email Archive Ingestion

**Week 2, Day 1: Unit Tests**
- [ ] Write `test_parse_tsv_row()`
- [ ] Write `test_chunk_email_body()`
- [ ] Write `test_email_embedding()`
- [ ] **Implement**: EmailIngestor class
- [ ] **Run**: `pytest tests/unit/test_email_ingestor.py -v`

**Week 2, Day 2: Integration Tests**
- [ ] Write `test_insert_emails_to_lethe()`
- [ ] Write `test_email_clustering()`
- [ ] **Test with**: 100 emails from cleaned_emails_sample.tsv
- [ ] **Run**: `pytest tests/integration/test_email_integration.py -v`

**Week 2, Day 3: E2E Test**
- [ ] Write `test_email_archive_to_lethe()`
- [ ] Test with 1,000 emails (TSV sample)
- [ ] Verify chunks in TheLethe collection
- [ ] **Run**: `pytest tests/e2e/test_email_to_lethe.py -v`

---

#### Story 025: Shadow Copy & Gatekeeper

**Week 2, Day 4: Unit Tests**
- [ ] Write `test_sync_to_shadow()`
- [ ] Write `test_approval_workflow()`
- [ ] Write `test_diff_generation()`
- [ ] Write `test_reject_reverts_shadow()`
- [ ] **Implement**: ObsidianGatekeeper class
- [ ] **Run**: `pytest tests/unit/test_gatekeeper.py::TestObsidianGatekeeper -v`

**Week 2, Day 5: Integration Tests**
- [ ] Write `test_shadow_approval_e2e()`
- [ ] Test with real file modifications
- [ ] Verify source remains unchanged until approval
- [ ] **Run**: `pytest tests/integration/test_gatekeeper_integration.py -v`

---

### Phase 1: Semantic Extraction (Weeks 3-4)

#### Story 001 (Phase 1): Cluster Centroid Node

**Week 3, Day 1: Unit Tests**
- [ ] Write `test_fetch_embeddings_from_muses()`
- [ ] Write `test_minibatch_kmeans_clustering()`
- [ ] Write `test_calculate_centroids()`
- [ ] Write `test_store_cluster_metadata()`
- [ ] **Run**: `pytest tests/unit/test_clusterer.py -v`

**Week 3, Day 2-3: Integration Tests**
- [ ] Write `test_cluster_with_real_embeddings()`
- [ ] Test with test_data (150-250 chunks)
- [ ] Verify clusters created in PostgreSQL
- [ ] **Run**: `pytest tests/integration/test_clustering_integration.py -v`
- [ ] **Performance target**: <5 minutes for 250 chunks

**Week 3, Day 4: E2E Test**
- [ ] Write `test_full_clustering_pipeline()`
- [ ] Ingest → Cluster → Store
- [ ] Verify k=20-50 clusters created
- [ ] **Run**: `pytest tests/e2e/test_clustering_pipeline.py -v`

---

### Phase 4: Latent Scout (Weeks 7-8)

#### Story 010: Scout Pattern Detection

**Week 7, Day 1-2: Unit Tests**
- [ ] Write `test_detect_project_candidate()`
- [ ] Write `test_calculate_confidence_score()`
- [ ] Write `test_detect_improvement_opportunity()`
- [ ] Write `test_cross_cluster_pattern()`
- [ ] **Implement**: LatentScout class
- [ ] **Run**: `pytest tests/unit/test_scout.py -v`

**Week 7, Day 3: Integration Tests**
- [ ] Write `test_scout_with_real_clusters()`
- [ ] Write `test_store_discovery_in_vector_db()`
- [ ] Test with real cluster data
- [ ] **Run**: `pytest tests/integration/test_scout_integration.py -v`

**Week 7, Day 4: E2E Test**
- [ ] Write `test_nightly_scout_scan()`
- [ ] Full pipeline: Scan clusters → Detect patterns → Store discoveries
- [ ] Verify discoveries in Discovery DB
- [ ] **Run**: `pytest tests/e2e/test_scout_discovery.py -v`
- [ ] **Performance target**: <30 minutes

**Week 7, Day 5: Scheduled Job Test**
- [ ] Write `test_scout_scheduled_execution()`
- [ ] Test cron/APScheduler integration
- [ ] Verify runs at 3 AM
- [ ] **Run**: Manual verification with scheduler

---

#### Story 014: SQL Project Gatekeeper

**Week 8, Day 1: Unit Tests**
- [ ] Write `test_confidence_threshold_routing()`
  - [ ] High confidence (>0.80) → Request approval
  - [ ] Medium (0.60-0.80) → Request approval
  - [ ] Low (<0.60) → Auto-reject
- [ ] Write `test_approval_writes_to_sql()`
- [ ] Write `test_rejection_does_not_write()`
- [ ] Write `test_audit_logging()`
- [ ] **Implement**: SQLProjectGatekeeper class
- [ ] **Run**: `pytest tests/unit/test_gatekeeper.py::TestSQLProjectGatekeeper -v`

**Week 8, Day 2: Integration Tests**
- [ ] Write `test_gatekeeper_with_postgres()`
- [ ] Test actual SQL writes
- [ ] Verify audit trail
- [ ] **Run**: `pytest tests/integration/test_sql_gatekeeper_integration.py -v`

**Week 8, Day 3: E2E Test**
- [ ] Write `test_discovery_to_project_workflow()`
- [ ] Scout discovers → Gatekeeper requests → User approves → SQL write
- [ ] Verify complete workflow
- [ ] **Run**: `pytest tests/e2e/test_gatekeeper_workflow.py -v`

---

#### Story 016: Project Manager

**Week 8, Day 4: Unit Tests**
- [ ] Write `test_calculate_pressure_score()`
- [ ] Write `test_detect_missing_deadlines()`
- [ ] Write `test_detect_stalled_projects()`
- [ ] Write `test_approaching_deadline_notification()`
- [ ] Write `test_daily_digest_generation()`
- [ ] **Implement**: ProjectManagerAgent class
- [ ] **Run**: `pytest tests/unit/test_project_manager.py -v`

**Week 8, Day 5: Integration Tests**
- [ ] Write `test_project_manager_with_postgres()`
- [ ] Write `test_scheduled_daily_routine()`
- [ ] Test with real projects in database
- [ ] **Run**: `pytest tests/integration/test_project_manager_integration.py -v`

---

## 📊 Testing Metrics & Gates

### Quality Gates (Must Pass Before Moving Forward)

#### After Each Story:
- [ ] All unit tests pass (100%)
- [ ] All integration tests pass (100%)
- [ ] Code coverage >80% for new code
- [ ] No critical bugs in E2E tests
- [ ] Performance targets met

#### Before Phase Completion:
- [ ] All phase stories tested
- [ ] Integration between stories tested
- [ ] E2E workflows for complete phase pass
- [ ] Documentation updated

#### Before Production:
- [ ] Full E2E test suite passes
- [ ] Performance tested with production data size
- [ ] Load testing completed (if applicable)
- [ ] Security review (especially Gatekeepers)

---

## 🎯 Test Data Strategy per Phase

### Phase 0 (Ingestion)
- **Test Data**: 50 vault files, 1,000 emails
- **Integration**: Real Weaviate, real Ollama
- **E2E**: Full ingestion pipeline with test data

### Phase 1 (Clustering)
- **Test Data**: 150-250 chunks from Phase 0
- **Integration**: Real PostgreSQL for clusters
- **E2E**: Ingest → Cluster → Profile

### Phase 4 (Scout)
- **Test Data**: 20-50 clusters from Phase 1
- **Integration**: Real Discovery DB (Weaviate)
- **E2E**: Scout scan → Discovery → Gatekeeper

---

## 🔄 Continuous Testing Workflow

### Daily Development Cycle:
```bash
# 1. Write unit test
vim tests/unit/test_myfeature.py

# 2. Run unit test (should fail - Red)
pytest tests/unit/test_myfeature.py -v

# 3. Implement feature
vim Aletheia/myfeature.py

# 4. Run unit test (should pass - Green)
pytest tests/unit/test_myfeature.py -v

# 5. Refactor if needed (tests still pass)
# 6. Run all unit tests
make test

# 7. Add integration test
vim tests/integration/test_myfeature_integration.py

# 8. Start services
make services-up

# 9. Run integration test
pytest tests/integration/test_myfeature_integration.py -v

# 10. Run all tests
make test-all
```

### Before Commit:
```bash
# Run full test suite
make test-all

# Check coverage
make coverage

# Lint and format
make check
```

### Before Story Completion:
```bash
# Run E2E tests
pytest tests/e2e -v

# Verify performance
time pytest tests/e2e/test_myfeature_e2e.py -v

# Update documentation
vim user-stories/phase-X/story-XXX.md
```

---

## 📈 Test Coverage Goals

| Phase | Unit Tests | Integration Tests | E2E Tests | Coverage Target |
|-------|-----------|------------------|-----------|----------------|
| Phase 0 | 20-30 | 10-15 | 3-5 | >80% |
| Phase 1 | 15-20 | 8-10 | 2-3 | >80% |
| Phase 2 | 10-15 | 5-8 | 2-3 | >75% |
| Phase 3 | 8-12 | 5-8 | 2-3 | >75% |
| Phase 4 | 25-35 | 12-15 | 4-6 | >85% |
| Phase 5 | 15-20 | 8-10 | 3-5 | >80% |

**Overall Target**: >80% code coverage across the project

---

## 🚨 When Tests Should Block Progress

### Block Story Completion If:
- [ ] Any unit test fails
- [ ] Integration tests fail
- [ ] Coverage drops below 70%
- [ ] Performance regression >20%
- [ ] E2E workflow broken

### Block Phase Completion If:
- [ ] Any story incomplete
- [ ] Phase E2E tests fail
- [ ] Integration between stories broken
- [ ] Documentation not updated

### Block Production Release If:
- [ ] Any E2E test fails
- [ ] Performance targets not met
- [ ] Security issues in Gatekeepers
- [ ] No smoke tests for critical paths

---

## 💡 Testing Best Practices

### 1. Write Tests First (TDD)
- Clarifies requirements
- Prevents scope creep
- Ensures testability
- Documents expected behavior

### 2. Keep Tests Fast
- Unit tests: <1s each
- Mock external services
- Use test data (not production)
- Parallel test execution

### 3. Test Isolation
- Each test independent
- No shared state
- Clean up after tests
- Use fixtures for setup/teardown

### 4. Meaningful Assertions
- Test one thing per test
- Clear failure messages
- Test both success and failure paths
- Edge cases and boundaries

### 5. Maintainable Tests
- Follow DRY principle
- Use descriptive names
- Keep tests simple
- Refactor tests when needed

---

## 📝 Test Documentation

For each test file, include:

```python
"""
Unit tests for ComponentName
Tests Story XXX: Story Title

Test Coverage:
- Function 1: Basic operation, edge cases
- Function 2: Error handling, validation
- Integration with Service X

Related Stories: 000, 001
Dependencies: Ollama, Weaviate
"""
```

---

**Next**: Follow this testing strategy for each story implementation. Start with Story 000 unit tests!
