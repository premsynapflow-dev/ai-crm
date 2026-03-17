#!/usr/bin/env bash
set -euo pipefail

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL is required"
  exit 1
fi

mkdir -p backups
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT="backups/neuronyx_${TIMESTAMP}.sql"

pg_dump "$DATABASE_URL" > "$OUTPUT"
echo "Backup written to $OUTPUT"
