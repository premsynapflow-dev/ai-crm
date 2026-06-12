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

    # Build the Vite+React frontend so FastAPI can serve it from frontend/out/
    if [ -f "frontend/package.json" ] && [ ! -d "frontend/out" ]; then
        echo "Building frontend..."
        cd frontend
        npm ci --prefer-offline 2>/dev/null || npm install
        npm run build
        cd ..
        echo "Frontend build complete."
    fi

    echo "Running migrations..."
    timeout 60 alembic upgrade head || echo "Migration failed or timed out, continuing..."

    timeout 30 "$PYTHON_BIN" -m app.db.schema_guard || echo "Schema guard failed or timed out, continuing..."

    WEB_CONCURRENCY="${WEB_CONCURRENCY:-1}"
    echo "Starting Uvicorn with ${WEB_CONCURRENCY} worker(s)..."
    exec "$PYTHON_BIN" -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "$WEB_CONCURRENCY"
fi
