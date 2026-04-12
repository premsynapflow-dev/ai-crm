#!/usr/bin/env bash
set -e

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

if [ "$SERVICE_TYPE" = "worker" ]; then
    echo "Starting worker..."
    exec "$PYTHON_BIN" worker_standalone.py
else
    echo "Starting API..."
    
    echo "Running migrations..."
    alembic upgrade head || echo "Migration failed, continuing..."

    "$PYTHON_BIN" -m app.db.schema_guard || echo "Schema guard failed, continuing..."

    exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 4
fi
