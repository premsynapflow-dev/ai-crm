#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
PORT_VALUE="${PORT:-8000}"

# The background worker is started from FastAPI startup in app.main.
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT_VALUE"
