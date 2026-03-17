#!/usr/bin/env bash
set -e

python -m app.db.schema_guard

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
