#!/usr/bin/env bash
set -euo pipefail
cd /srv
exec python -m uvicorn docs_service.app:app --host 0.0.0.0 --port 8300
