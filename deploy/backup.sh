#!/usr/bin/env bash
# deploy/backup.sh — Daily backup for Stratum (DuckDB + avatars)
# Usage: ./backup.sh
# Cron example (daily 2am): 0 2 * * * /path/to/stratum/deploy/backup.sh

set -euo pipefail

STRATUM_DIR="${STRATUM_DIR:-$HOME/.stratum}"
BACKUP_ROOT="${STRATUM_DIR}/backups"
TODAY=$(date +%Y-%m-%d)
BACKUP_DIR="${BACKUP_ROOT}/${TODAY}"
RETENTION_DAYS=7

mkdir -p "${BACKUP_DIR}"

# 1. DuckDB database
if [ -f "${STRATUM_DIR}/meta.duckdb" ]; then
  cp "${STRATUM_DIR}/meta.duckdb" "${BACKUP_DIR}/meta.duckdb"
  echo "[backup] DuckDB copied: ${BACKUP_DIR}/meta.duckdb"
fi

# 2. Avatars
if [ -d "${STRATUM_DIR}/avatars" ]; then
  rsync -a "${STRATUM_DIR}/avatars/" "${BACKUP_DIR}/avatars/"
  echo "[backup] Avatars synced: ${BACKUP_DIR}/avatars/"
fi

# 3. Retention: remove backups older than 7 days
find "${BACKUP_ROOT}" -maxdepth 1 -type d -name "20*" -mtime +${RETENTION_DAYS} -exec rm -rf {} \;
echo "[backup] Retention applied: kept last ${RETENTION_DAYS} days"

echo "[backup] Done: ${BACKUP_DIR}"
