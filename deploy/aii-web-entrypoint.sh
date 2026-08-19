#!/bin/sh
# Next.js bakes rewrites from next.config at *build* time. Runtime env
# STRATUM_API_BASE / STRATUM_SL_BASE is ignored for those destinations.
# Patch the standalone manifests before start so Docker service names work.
set -e

API_BASE="${STRATUM_API_BASE:-http://stratum-api:9302}"
SL_BASE="${STRATUM_SL_BASE:-http://stratum-sl:9304}"

# Normalize trailing slash
API_BASE="${API_BASE%/}"
SL_BASE="${SL_BASE%/}"

for f in \
  /app/aii-web/.next/routes-manifest.json \
  /app/aii-web/.next/required-server-files.json \
  /app/aii-web/server.js
do
  if [ -f "$f" ]; then
    # Replace any previous localhost or docker-name targets with current env
    sed -i \
      -e "s|http://localhost:9302|${API_BASE}|g" \
      -e "s|http://stratum-api:9302|${API_BASE}|g" \
      -e "s|http://localhost:9304|${SL_BASE}|g" \
      -e "s|http://stratum-sl:9304|${SL_BASE}|g" \
      "$f"
  fi
done

echo "aii-web: API rewrites → auth/legacy ${API_BASE}  sl ${SL_BASE}"
exec node server.js
