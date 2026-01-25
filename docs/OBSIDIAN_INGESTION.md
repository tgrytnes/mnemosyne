# Obsidian Vault Ingestion Guide

Complete guide for ingesting your Obsidian vault into Mnemosyne's TheMuses collection.

---

## Overview

Story 000 provides automatic ingestion of Obsidian vault content into TheMuses (core knowledge database). The system monitors your vault for changes and automatically processes new/modified markdown files.

### Key Features

- ✅ **Automatic Monitoring**: Watches vault for file changes (detected within 1-2 seconds)
- ✅ **Incremental Updates**: Only re-processes modified files
- ✅ **Markdown Cleaning**: Removes Obsidian syntax (wiki-links, frontmatter, embeds)
- ✅ **Smart Chunking**: `semantic_consensus` (semantic + recursive consensus) by default
- ✅ **Vector Embeddings**: Uses Ollama qwen3-embedding:0.6b (1024 dimensions)
- ✅ **State Persistence**: Tracks ingestion state across restarts

---

## Prerequisites

### Required Services

1. **Weaviate** (vector database)
   ```bash
   # Default: localhost:8080
   docker run -d -p 8080:8080 cr.weaviate.io/semitechnologies/weaviate:latest
   ```

2. **Ollama** (embeddings)
   ```bash
   # Default: localhost:11434
   docker run -d -p 11434:11434 ollama/ollama:latest

   # Pull embedding model
   docker exec <container-id> ollama pull qwen3-embedding:0.6b
   ```

3. **Python Environment**
   ```bash
   source .venv/bin/activate
   ```

---

## Configuration

### Environment Variables

Create a `.env` file or export these variables:

```bash
# Required
export OBSIDIAN_VAULT_PATH="/path/to/your/obsidian/vault"

# Optional (defaults shown)
export WEAVIATE_HTTP_HOST="localhost"
export WEAVIATE_HTTP_PORT="8080"
export WEAVIATE_GRPC_PORT="50051"
export OLLAMA_BASE_URL="http://localhost:11434"
export INGESTION_STATE_DB="ingestion_state.db"
export CHUNK_SIZE="400"
export CHUNK_OVERLAP="100"
export CHUNKING_STRATEGY="semantic_consensus"
export SEMANTIC_LLM_MODEL="glm-4.6v-flash"
export WATCH_DEBOUNCE_SECONDS="2.0"
```

### Model Choice (Semantic Chunking)

`glm-4.6v-flash` is recommended because it matches the best boundary quality
from larger models while using substantially fewer resources. Larger models
(e.g., gpt-oss-20b) can slightly improve separation scores but tend to cut
more often mid-sentence and cost more to run.

### Configuration File (Optional)

You can also use one of the environment templates:

```bash
# Copy template
cp .env.development .env

# Edit with your vault path
nano .env

# Source it
source .env
```

---

## Usage

### Option 1: Manual Ingestion (One-Time)

Ingest entire vault once:

```bash
# Using environment variable
export OBSIDIAN_VAULT_PATH="/path/to/vault"
python -m mnemosyne.cli.ingest once

# Or specify path directly
python -m mnemosyne.cli.ingest once --vault-path /path/to/vault
```

**Output:**
```
============================================================
Starting Manual Vault Ingestion
============================================================
Vault: /path/to/vault
Weaviate: localhost:8080
Ollama: http://localhost:11434
State DB: ingestion_state.db
============================================================

Scanning vault for markdown files...
Found 327 markdown files

Starting ingestion...
Ingested /vault/note1.md: 3 chunks
Ingested /vault/note2.md: 5 chunks
...

============================================================
Ingestion Complete!
============================================================
Total files: 327
Files processed: 327
Files skipped: 0
Total chunks created: 1,842
============================================================
```

### Option 2: Automatic Monitoring (Continuous)

Watch vault for changes and auto-ingest:

```bash
# Using environment variable
export OBSIDIAN_VAULT_PATH="/path/to/vault"
python -m mnemosyne.cli.ingest watch

# Or specify path directly
python -m mnemosyne.cli.ingest watch --vault-path /path/to/vault
```

**Output:**
```
============================================================
Starting Vault Watcher
============================================================
Vault: /path/to/vault
Weaviate: localhost:8080
Ollama: http://localhost:11434
State DB: ingestion_state.db
Debounce: 2.0s
============================================================

Watcher started. Monitoring for changes...
Press Ctrl+C to stop.

============================================================
Processing: /vault/new_note.md
============================================================
✓ Created 4 chunk(s)

============================================================
Processing: /vault/modified_note.md
============================================================
✓ Created 3 chunk(s)
```

**Stop with**: `Ctrl+C`

---

## How It Works

### Ingestion Pipeline

```
1. Scan/Detect File
   ↓
2. Check State Tracker (skip if unmodified)
   ↓
3. Read Markdown Content
   ↓
4. Clean Obsidian Syntax
   - Remove YAML frontmatter (---)
   - Remove wiki-links [[...]]
   - Remove embeds ![[...]]
   - Remove HTML tags
   - Remove metadata (tags::, etc.)
   ↓
5. Chunk Text
   - 400 characters per chunk
   - 100 character overlap
   - Semantic-aware splitting (respects sentences/paragraphs)
   ↓
6. Generate Embeddings
   - Ollama qwen3-embedding:0.6b
   - 1024-dimensional vectors
   ↓
7. Store in Weaviate (TheMuses collection)
   - text, sourceFile, sourceType: "obsidian"
   - chunkIndex, ingestedAt, fileModifiedAt
   - vector embedding
   ↓
8. Update State Tracker
   - Mark file as ingested with modification time
   - Track chunk count
```

### File Watching

The watcher monitors your vault using `watchdog`:

- **Events**: File creation, modification
- **Debouncing**: 2-second delay to avoid duplicate processing
- **Filtering**: Only processes `.md` files, ignores:
  - Hidden files (`.hidden.md`)
  - Temp files (`file.tmp`, `file~`)
  - Obsidian workspace (`.obsidian/` directory)

---

## Performance

### Expected Metrics (Based on Crystal Project)

| Metric | Value |
|--------|-------|
| Vault Size | 300-500 files → ~1,500-2,500 chunks |
| Ingestion Rate | 3-4 files/minute (Raspberry Pi 5) |
| Initial Ingestion (300 files) | 60-90 minutes (one-time) |
| Incremental Update (10 files) | < 5 minutes |
| Embedding Bottleneck | Ollama (most time spent here) |

### Optimization Tips

1. **Initial Ingestion**: Run overnight for large vaults
2. **Incremental Mode**: Use `watch` for continuous updates
3. **Batch Processing**: Manual `once` mode for bulk changes
4. **State Persistence**: Ingestion state survives restarts

---

## Troubleshooting

### Weaviate Connection Error

```bash
# Check if Weaviate is running
curl http://localhost:8080/v1/.well-known/ready

# Check Docker container
docker ps | grep weaviate

# View logs
docker logs <weaviate-container-id>
```

### Ollama Connection Error

```bash
# Check if Ollama is running
curl http://localhost:11434/

# Check model is pulled
docker exec <ollama-container-id> ollama list

# Pull model if missing
docker exec <ollama-container-id> ollama pull qwen3-embedding:0.6b
```

### State Database Issues

```bash
# Reset state (will re-ingest all files)
rm ingestion_state.db

# Check state
sqlite3 ingestion_state.db "SELECT * FROM ingested_files LIMIT 10;"
```

### Files Not Being Detected

1. **Check file extension**: Must be `.md`
2. **Check file location**: Must be inside vault directory
3. **Check for temp files**: Hidden/temp files are ignored
4. **Check debounce**: Wait 2 seconds between saves
5. **Check logs**: Look for error messages

---

## Advanced Usage

### Custom Chunk Size

```bash
# Smaller chunks (better for specific retrieval)
export CHUNK_SIZE=200
export CHUNK_OVERLAP=50

# Larger chunks (better for context)
export CHUNK_SIZE=600
export CHUNK_OVERLAP=150
```

### Different Weaviate Instance

```bash
export WEAVIATE_HTTP_HOST="weaviate.example.com"
export WEAVIATE_HTTP_PORT="8080"
export WEAVIATE_GRPC_PORT="50051"
```

### Remote Ollama Server

```bash
export OLLAMA_BASE_URL="http://ollama-server:11434"
```

### Custom State Database Location

```bash
export INGESTION_STATE_DB="/data/mnemosyne/state.db"
```

---

## Integration with Docker

### docker-compose.yml

```yaml
version: '3.8'

services:
  mnemosyne-ingestor:
    build: .
    volumes:
      - /path/to/obsidian/vault:/vault:ro  # Read-only mount
      - ./data/state:/state
    environment:
      OBSIDIAN_VAULT_PATH: /vault
      WEAVIATE_HTTP_HOST: weaviate
      WEAVIATE_HTTP_PORT: 8080
      OLLAMA_BASE_URL: http://ollama:11434
      INGESTION_STATE_DB: /state/ingestion_state.db
    command: python -m mnemosyne.cli.ingest watch
    depends_on:
      - weaviate
      - ollama

  weaviate:
    image: cr.weaviate.io/semitechnologies/weaviate:latest
    ports:
      - "8080:8080"
    environment:
      AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED: 'true'
      DEFAULT_VECTORIZER_MODULE: 'none'

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama

volumes:
  ollama_data:
```

---

## Verification

### Check Weaviate Collection

```python
import weaviate

# Connect
client = weaviate.connect_to_local()

# Get collection
collection = client.collections.get("TheMuses")

# Count objects
count = collection.aggregate.over_all(total_count=True)
print(f"Total chunks: {count.total_count}")

# Sample query
result = collection.query.fetch_objects(limit=5)
for obj in result.objects:
    print(f"Source: {obj.properties['sourceFile']}")
    print(f"Text: {obj.properties['text'][:100]}...")
    print()

client.close()
```

### Check State Database

```bash
# Connect to state database
sqlite3 ingestion_state.db

# View ingested files
SELECT file_path, chunk_count, ingested_at
FROM ingested_files
ORDER BY ingested_at DESC
LIMIT 10;

# Total stats
SELECT COUNT(*) as files, SUM(chunk_count) as chunks
FROM ingested_files;
```

---

## Next Steps

After ingesting your vault:

1. **Story 001**: Cluster Centroid Node - Creates semantic clusters
2. **Story 002**: Structured Metadata Synthesis - Generates project metadata
3. **Story 003**: Automated Graph Taxonomy - Builds knowledge graph

---

**Last Updated**: 2025-12-27
