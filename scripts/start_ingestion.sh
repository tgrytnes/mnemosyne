#!/usr/bin/env bash
set -euo pipefail

echo "Starting one-time ingestion pipelines..."

echo "1/3: Running Obsidian vault initial load..."
python -m mnemosyne.cli.ingest once --vault-path "${OBSIDIAN_VAULT_PATH:-/data/fake_vault}"

echo "2/3: Running PDF ingestion..."
python -m mnemosyne.aletheia.pdf_ingestor

echo "3/3: Running email ingestion..."
python -m mnemosyne.aletheia.email_ingest

echo "Launching vault watcher (keeps running)..."
exec python -m mnemosyne.cli.ingest watch --vault-path "${OBSIDIAN_VAULT_PATH:-/data/fake_vault}"
