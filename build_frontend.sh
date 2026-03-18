#!/bin/bash
set -e

echo "Building SynapFlow frontend..."

cd frontend
npm install
npm run build

echo "Frontend build complete! Output in frontend/out/"
