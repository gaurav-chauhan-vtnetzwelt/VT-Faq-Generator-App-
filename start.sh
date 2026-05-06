#!/bin/bash
# FAQ SaaS — start API + static UI (dev)

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY="${ROOT}/.venv/bin/python"

if [ ! -f "$ROOT/server/.env" ]; then
    echo "No server/.env — creating from template..."
    cp "$ROOT/server/.env.example" "$ROOT/server/.env"
    echo "Edit server/.env (API keys), then run ./setup.sh and this script again."
    exit 1
fi

if [ -x "$VENV_PY" ]; then
    PY="$VENV_PY"
else
    echo "Warning: no .venv — using system python3 (run ./setup.sh for an isolated env)."
    PY="python3"
fi

echo "Starting server at http://0.0.0.0:8000"
echo "Web UI: $ROOT/web/"
echo ""

cd "$ROOT/server"
exec "$PY" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
