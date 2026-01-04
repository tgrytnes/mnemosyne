#!/usr/bin/env bash
set -euo pipefail

echo "Starting one-time ingestion pipelines..."

echo "1/4: Running Obsidian vault initial load..."
python -m mnemosyne.cli.ingest once --vault-path "${OBSIDIAN_VAULT_PATH:-/data/fake_vault}"

echo "2/4: Running PDF ingestion..."
python -m mnemosyne.aletheia.pdf_ingestor

echo "3/4: Running email ingestion..."
python -m mnemosyne.aletheia.email_ingest

echo "4/4: Running Scout pattern detection..."
python -m mnemosyne.cli.scout

echo "Launching vault watcher (keeps running)..."
exec python -m mnemosyne.cli.ingest watch --vault-path "${OBSIDIAN_VAULT_PATH:-/data/fake_vault}"
