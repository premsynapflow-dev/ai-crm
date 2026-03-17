#!/usr/bin/env bash
set -euo pipefail

export PYTHONUNBUFFERED=1
PORT_VALUE="${PORT:-8000}"

alembic upgrade head

exec python -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT_VALUE"
