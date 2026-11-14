#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.txt
(cd frontend && npm ci && npm run build)
exec .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
