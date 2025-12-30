# Story 000: Obsidian Vault Ingestion (The Muses)

**As a** knowledge worker
**I want** my Obsidian vault automatically ingested into The Muses (core knowledge DB)
**So that** my curated notes are available for clustering, pattern discovery, and semantic search

## 🎯 Critical Architectural Decision

**This story ONLY ingests Obsidian vault content into The Muses collection.**

### Why Two Separate Databases?

**The Muses** (this story): Small, high-quality, curated knowledge
- Source: Obsidian vault ONLY
- Size: 300-500 files → ~1,500-2,500 chunks
- Purpose: Clustering, project detection, pattern discovery, graph taxonomy
- Performance: ~5 minutes to cluster on Pi 5
- **Used by**: All Phase 1-4 analysis operations

**The Lethe** (Stories 001, 003): Large archive
- Source: Emails, PDFs, OCR documents
- Size: 30k-100k+ chunks
- Purpose: Search/retrieval ONLY, NOT analysis
- Performance: 60-90 minutes to cluster (too expensive!)
- **Used by**: RAG retrieval, document search

**Key Insight**: You cannot run expensive clustering/pattern detection on 30k+ mixed-quality chunks. Separate databases provide hard isolation so analysis runs ONLY on curated knowledge.

**See [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md) for complete system architecture.**

## Acceptance Criteria
- [ ] The Ingestor watcher monitors Obsidian vault directory for changes
- [ ] New/modified markdown files are detected within 1 minute
- [ ] Files are cleaned (YAML frontmatter, wiki-links, HTML removed)
- [ ] Cleaned content is chunked (400 chars with 100-char overlap)
- [ ] Each chunk is embedded using Ollama (qwen3-embedding:0.6b)
- [ ] Chunks stored ONLY in Weaviate collection "TheMuses" (NOT The Lethe)
- [ ] Each chunk tagged with sourceType: "obsidian"
- [ ] Handles 300+ files without performance degradation
- [ ] Incremental updates: only changed files re-processed
- [ ] Ingestion state persisted (avoid re-processing on restart)

## Technical Notes

### Architecture (Adapted from Project Crystal)

```python
class ObsidianIngestor:
    """
    Based on project_crystal/app/ingestor.py
    """
    def __init__(self, vault_path: str, weaviate_client: Client):
        self.vault_path = vault_path
        self.client = weaviate_client
        self.collection_name = "TheMuses"  # CORE KNOWLEDGE ONLY
        # NOTE: Emails/PDFs go to "TheLethe" (Stories 001, 003)

    def ingest_vault(self):
        # 1. Scan for .md files
        md_files = glob(f"{self.vault_path}/**/*.md", recursive=True)

        # 2. For each file
        for file_path in md_files:
            if self.already_ingested(file_path):
                continue

            # 3. Clean markdown
            cleaned = self.clean_markdown(file_path)

        # 4. Chunk (first pass)
        chunks = self.chunk_text(cleaned, chunk_size=400, overlap=100)

        # 5. Embed via Ollama (second pass)
        for chunk in chunks:
            embedding = self.get_embedding(chunk.text)

                # 6. Store in Weaviate (TheMuses ONLY)
                self.store_chunk({
                    "text": chunk.text,
                    "source_file": file_path,
                    "chunk_index": chunk.index,
                    "source_type": "obsidian",  # Tag for DB separation
                    "vector": embedding
                })

    def clean_markdown(self, file_path: str) -> str:
        """
        Remove:
        - YAML frontmatter (---)
        - Wiki-links ([[...]])
        - Embeds (![[...]])
        - HTML comments
        - Obsidian metadata (tags::, etc.)
        """
        # Implementation from crystal ingestor.py:107-139
        pass
```

### File Watching Strategy

**Option 1: Polling (Simple)**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class VaultWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.md'):
            ingestor.ingest_file(event.src_path)

observer = Observer()
observer.schedule(VaultWatcher(), vault_path, recursive=True)
observer.start()
```

**Option 2: Scheduled Batch (Pi 5 Friendly)**
```python
# Run every 5 minutes
@scheduled_job(interval='5 minutes')
def sync_vault():
    changed_files = get_files_modified_since(last_sync)
    for file in changed_files:
        ingestor.ingest_file(file)
```

### Cleaning Logic (From Crystal)

```python
def clean_markdown_content(text: str) -> str:
    """
    Aggressive cleaning for embedding quality
    """
    # Remove YAML frontmatter
    text = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)

    # Remove Obsidian wiki-links
    text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', text)

    # Remove embeds
    text = re.sub(r'!\[\[([^\]]+)\]\]', '', text)

    # Remove HTML
    text = re.sub(r'<[^>]+>', '', text)

    # Remove Obsidian metadata
    text = re.sub(r'\b\w+::[^\n]+', '', text)

    # Remove ChatGPT plugin blocks
    text = re.sub(r'```chatgpt[^`]+```', '', text, flags=re.DOTALL)

    # Remove emoji context markers
    text = re.sub(r'📌|🎯|💡|⚡', '', text)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    return text
```

### Chunking Strategy

**Two-pass ingestion (performance)**:
1. Chunk all eligible files first.
2. Embed and store chunks in a second pass.

This avoids frequent model switching on resource-constrained devices (e.g., Pi 5).

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=400,
    chunk_overlap=100,
    separators=["\n\n", "\n", ". ", " ", ""]
)

chunks = splitter.split_text(cleaned_text)
```

### Embedding Generation

```python
def get_embedding(text: str) -> List[float]:
    """
    Call Ollama for qwen3-embedding:0.6b
    """
    response = requests.post(
        f"{OLLAMA_URL}/api/embeddings",
        json={
            "model": "qwen3-embedding:0.6b",
            "prompt": text
        }
    )
    return response.json()["embedding"]  # 1024-dimensional vector
```

### Weaviate Schema (The Muses - Core Knowledge ONLY)

```python
schema = {
    "class": "TheMuses",
    "description": "CORE KNOWLEDGE: Obsidian vault only (NOT emails/PDFs)",
    "vectorizer": "none",  # We provide vectors via Ollama
    "properties": [
        {
            "name": "text",
            "dataType": ["text"],
            "description": "Cleaned chunk text"
        },
        {
            "name": "sourceFile",
            "dataType": ["text"],
            "description": "Original Obsidian file path"
        },
        {
            "name": "sourceType",
            "dataType": ["text"],
            "description": "Always 'obsidian' for The Muses"
        },
        {
            "name": "chunkIndex",
            "dataType": ["int"],
            "description": "Position in source file (0-indexed)"
        },
        {
            "name": "ingestedAt",
            "dataType": ["date"],
            "description": "Timestamp of ingestion"
        },
        {
            "name": "fileModifiedAt",
            "dataType": ["date"],
            "description": "Last modified time of source file"
        }
    ]
}

# IMPORTANT: The Lethe (emails, PDFs) is a SEPARATE collection (see Stories 001, 003)
# This separation allows expensive clustering to run ONLY on The Muses
```

### Performance Targets (The Muses)

- **Dataset size**: 300-500 files → ~1,500-2,500 chunks
- **Ingestion rate**: 3-4 files/minute on Pi 5 (from Crystal metrics)
- **Initial vault (300 files)**: 60-90 minutes one-time
- **Incremental updates**: <5 minutes for 10 changed files
- **Clustering time**: ~5 minutes for 2k chunks (vs 60-90 min for 30k in The Lethe)
- **Embedding bottleneck**: Ollama is the limiting factor

**Why this matters**: The Muses is intentionally small to enable fast, frequent clustering and analysis. The Lethe (emails/PDFs) can grow infinitely without slowing down pattern detection.

### State Tracking

```python
class IngestionState:
    """
    Track which files have been ingested
    """
    def __init__(self, db_path: str = ".ingestion_state.db"):
        self.conn = sqlite3.connect(db_path)
        self.create_table()

    def create_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS ingested_files (
                file_path TEXT PRIMARY KEY,
                last_modified TIMESTAMP,
                ingested_at TIMESTAMP,
                chunk_count INTEGER
            )
        """)

    def already_ingested(self, file_path: str, modified_time: datetime) -> bool:
        result = self.conn.execute(
            "SELECT last_modified FROM ingested_files WHERE file_path = ?",
            (file_path,)
        ).fetchone()

        if not result:
            return False

        return result[0] >= modified_time
```

### Integration with The Ingestor

The Ingestor (Layer 1: Input Processing) monitors the vault and processes changes. This story implements The Ingestor for Obsidian content.

```yaml
# docker-compose.yml for Aletheia
services:
  the-ingestor:
    build: ./Aletheia
    volumes:
      - /path/to/obsidian/vault:/vault:ro  # Read-only mount
      - ./data/weaviate:/weaviate-data
      - ./data/ingestion-state:/state
    environment:
      VAULT_PATH: /vault
      OLLAMA_URL: http://ollama:11434
      WEAVIATE_URL: http://weaviate:8080
      EMBED_MODEL: qwen3-embedding:0.6b
      SYNC_INTERVAL: 300  # 5 minutes
```

### Dependencies
- Ollama with qwen3-embedding:0.6b model
- Weaviate instance (Alexandria's The Muses collection)
- Obsidian vault mounted or accessible
- Python libraries: watchdog, langchain, weaviate-client, requests

## Affected Components
- **Aletheia**: The Graphos watcher implementation
- **Alexandria**: The Muses (Weaviate collection for vault embeddings)

## Priority
**Critical** - Foundation for all semantic features

## Estimate
8 story points (5-8 days)

## Linear Labels
`phase-0`, `ingestion`, `aletheia`, `alexandria`, `obsidian`, `foundation`

## Related Stories
- Story 001: Cluster Centroid Node (uses these embeddings)
- Story 002: Structured Metadata Synthesis (clusters these chunks)
- Story 006: Delta Sync Node (builds on this ingestion)

## References
- Implementation pattern: `project_crystal/app/ingestor.py`
- Cleaning logic: `project_crystal/app/ingestor.py:107-139`
- Chunking strategy: Crystal uses 400 chars / 100 overlap
- Performance baseline: 306 files → 1,816 chunks in 60-90 min
