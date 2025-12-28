# Mnemosyne - Personal Memory System

## Vision

Build a personal knowledge management system that doesn't just store notes, but actively helps discover insights and connections.

## Core Components

### Aletheia - The Truth Seeker
Handles ingestion and data cleaning. Should support:
- Markdown files from Obsidian
- Email archives (MBOX format)
- PDF documents with OCR

### Alexandria - The Library
Vector database (Weaviate) for semantic storage. Each note chunk gets embedded and indexed for similarity search.

### Argus - The Watcher
Two modes:
1. **Reactive**: Answer user queries using semantic search
2. **Proactive**: Autonomously discover patterns and connections

### Hermes - The Messenger
Telegram bot for notifications and approvals. Should support:
- Daily digest of discoveries
- Yes/No approval prompts
- Quick query interface

## Key Insights

The system should preserve **sovereignty** - no automated changes to the canonical vault without explicit approval. All edits happen in a shadow copy first.

## Technical Decisions

- **Embeddings**: qwen3-embedding:0.6b (lightweight, runs on Pi 5)
- **LLM**: qwen3:0.6b for reasoning and synthesis
- **Vector DB**: Weaviate (better Python support than Qdrant)
- **Graph DB**: PostgreSQL with pg_vector (simpler than Neo4j)

## Open Questions

1. How to measure quality of semantic chunking?
2. Should we preserve document structure (headings) during ingestion?
3. What's the right balance between fixed-size and semantic chunking?

#project #ai #knowledge-management
