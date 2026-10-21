#!/usr/bin/env bash
set -euo pipefail
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
# Vite requires a recent Node version. Render Python environments may not include Node.
# Install Node LTS locally under the build workspace when unavailable.
if ! command -v node >/dev/null 2>&1 || ! node -e 'process.exit(Number(process.versions.node.split(".")[0])>=20?0:1)'; then
  echo 'Node.js 20+ is required for the React build.'
  echo 'Use an environment with Node.js available or deploy with the Dockerfile.'
  exit 1
fi
(cd frontend && npm install --no-audit --no-fund && npm run build)
mkdir -p backend/static
cp -R frontend/dist/. backend/static/
