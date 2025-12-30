#!/bin/bash
# Quick script to check code quality locally before committing/pushing

set -e

echo "🔍 Running code quality checks..."
echo

# Check if venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found. Run: python -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Run Ruff
echo "→ Running Ruff linter..."
.venv/bin/ruff check .
ruff_exit=$?

# Run Black
echo
echo "→ Running Black formatter check..."
.venv/bin/black --check .
black_exit=$?

echo
if [ $ruff_exit -eq 0 ] && [ $black_exit -eq 0 ]; then
    echo "✅ All quality checks passed!"
    exit 0
else
    echo "❌ Quality checks failed!"
    echo
    if [ $ruff_exit -ne 0 ]; then
        echo "Fix Ruff errors with: .venv/bin/ruff check --fix ."
    fi
    if [ $black_exit -ne 0 ]; then
        echo "Fix Black formatting with: .venv/bin/black ."
    fi
    exit 1
fi
