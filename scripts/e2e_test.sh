#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python scripts/e2e_test.py "$@"
elif command -v python3 &> /dev/null; then
    python3 scripts/e2e_test.py "$@"
else
    python scripts/e2e_test.py "$@"
fi
