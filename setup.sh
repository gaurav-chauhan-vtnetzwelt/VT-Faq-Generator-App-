#!/bin/bash
# FAQ SaaS — create .venv and install Python deps (optional npm if react-app exists)

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${ROOT}/.venv"
PY="${VENV}/bin/python"
PIP="${VENV}/bin/pip"

if ! command -v python3 &> /dev/null; then
    echo "Python 3 required."
    exit 1
fi

if [ ! -f "$ROOT/server/.env" ]; then
    cp "$ROOT/server/.env.example" "$ROOT/server/.env"
    echo "Created server/.env — add GEMINI_API_KEY / GROQ_API_KEY / OPENAI_API_KEY."
fi

if [ ! -x "$PY" ]; then
    echo "Creating virtualenv at .venv ..."
    python3 -m venv "$VENV"
fi

echo "Installing Python dependencies..."
"$PIP" install --upgrade pip
"$PIP" install -r "$ROOT/server/requirements.txt"

if [ -f "$ROOT/react-app/package.json" ]; then
    echo "Building optional React bundle..."
    ( cd "$ROOT/react-app" && npm install && npm run build )
fi

echo ""
echo "Done. Run: ./start.sh"
echo "Or: cd server && ../.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
