#!/usr/bin/env bash
set -euo pipefail

echo "Starting one-time ingestion pipelines..."

echo "1/5: Running Obsidian vault initial load..."
python -m mnemosyne.cli.ingest once --vault-path "${OBSIDIAN_VAULT_PATH:-/data/fake_vault}"

echo "2/5: Running PDF ingestion..."
python -m mnemosyne.aletheia.pdf_ingestor

echo "3/5: Running email ingestion..."
python -m mnemosyne.aletheia.email_ingest

echo "4/6: Running clustering..."
python -m mnemosyne.cli.cluster run --n-clusters "${N_CLUSTERS:-50}"

echo "5/6: Running Scout pattern detection..."
python -m mnemosyne.cli.scout

echo "6/6: Building graph taxonomy in Neo4j..."
python -m mnemosyne.cli.graph_taxonomy

WATCH_ENABLED="${INGESTOR_WATCH_ENABLED:-true}"
if [[ "$WATCH_ENABLED" =~ ^(false|0|no)$ ]]; then
  echo "Vault watcher disabled (INGESTOR_WATCH_ENABLED=$WATCH_ENABLED)."
  echo "Container will remain idle."
  tail -f /dev/null
else
  echo "Launching vault watcher (keeps running)..."
  exec python -m mnemosyne.cli.ingest watch --vault-path "${OBSIDIAN_VAULT_PATH:-/data/fake_vault}"
fi
