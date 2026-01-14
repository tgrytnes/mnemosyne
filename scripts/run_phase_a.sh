#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env.phase_a.local}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Phase A env file not found: $ENV_FILE" >&2
  exit 1
fi

shift || true

PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python"
fi

exec "$PYTHON_BIN" -m mnemosyne.phase_a.runner --env-file "$ENV_FILE" "$@"
