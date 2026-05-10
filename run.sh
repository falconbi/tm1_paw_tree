#!/bin/bash
# Launch the TM1 Governance Suite using the project virtualenv.
# Usage: ./run.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/venv/bin/python3"

if [ ! -f "$PYTHON" ]; then
    echo "ERROR: venv not found at $SCRIPT_DIR/venv"
    echo "Run: python3 -m venv venv && venv/bin/pip install -r requirements.txt"
    exit 1
fi

exec "$PYTHON" "$SCRIPT_DIR/app.py"
