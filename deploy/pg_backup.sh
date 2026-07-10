#!/usr/bin/env bash
# deploy/pg_backup.sh — Daily logical backup for the AII Postgres knowledge stores.
#
# Why: after the DuckDB→Postgres migration the KU/knowledge graph (aii_kg: schemas
# aii/public/stratum, ~800MB) lives ONLY in aii-postgres. deploy/backup.sh backs up
# DuckDB+avatars but NOT this — a disk loss was unrecoverable. This closes that gap.
#
# Format: pg_dump -Fc (custom, compressed, restorable with pg_restore).
# Restore (into a fresh DB with the timescaledb extension available):
#   docker exec -i aii-postgres pg_restore -U aii -d <newdb> --clean --if-exists < aii_kg_<ts>.dump
#   (aii_kg is timescaledb-ha; if hypertables were used, restore into an empty DB where
#    CREATE EXTENSION timescaledb has been run — plain tables restore without special steps.)
#
# Usage: ./pg_backup.sh
# Cron (daily 3am):  0 3 * * * /data/soffy/projects/stratum/deploy/pg_backup.sh
# (systemd timer aii-pg-backup.timer is the preferred scheduler — see aii/deploy/systemd/)

set -euo pipefail

# Default under $HOME (soffy-owned) so the systemd --user service can write it;
# ~/.stratum is root-owned (container-created) and not writable by the user.
BACKUP_ROOT="${AII_PG_BACKUP_ROOT:-$HOME/aii-backups/pg}"
TODAY=$(date +%Y-%m-%d)
TS=$(date +%Y-%m-%dT%H%M%S)
BACKUP_DIR="${BACKUP_ROOT}/${TODAY}"
RETENTION_DAYS="${AII_PG_BACKUP_RETENTION_DAYS:-7}"

mkdir -p "${BACKUP_DIR}"

fail=0

# dump_db <container> <pg_user> <dbname>
dump_db() {
  local container="$1" user="$2" db="$3"
  if ! docker ps --format '{{.Names}}' | grep -qx "${container}"; then
    echo "[pg_backup] SKIP ${container}/${db}: container not running"
    return 0
  fi
  local out="${BACKUP_DIR}/${db}_${TS}.dump"
  echo "[pg_backup] dumping ${container}:${db} → ${out}"
  if docker exec "${container}" pg_dump -U "${user}" -Fc "${db}" > "${out}" 2>/tmp/pg_backup_${db}.err; then
    # integrity check: pg_restore --list must parse the archive and list objects
    local n
    n=$(docker exec -i "${container}" pg_restore --list < "${out}" 2>/dev/null | grep -c ';' || true)
    local sz
    sz=$(du -h "${out}" | cut -f1)
    if [ "${n:-0}" -gt 0 ]; then
      echo "[pg_backup]   OK ${db}: ${sz}, ${n} archive entries"
    else
      echo "[pg_backup]   FAIL ${db}: archive unreadable/empty (${sz})"; fail=1
    fi
  else
    echo "[pg_backup]   FAIL ${db}: pg_dump error:"; sed 's/^/[pg_backup]     /' /tmp/pg_backup_${db}.err; fail=1
    rm -f "${out}"
  fi
}

# Critical: the KU/knowledge graph + stratum schema.
dump_db aii-postgres aii aii_kg

# Secondary: refined (B-repo, pgvector) if present. User/db default to aii/aii_refined; override via env.
dump_db aii-refined-postgres "${AII_REFINED_PG_USER:-aii}" "${AII_REFINED_PG_DB:-aii_refined}"

# Retention: prune day-dirs older than N days.
find "${BACKUP_ROOT}" -mindepth 1 -maxdepth 1 -type d -name "20*" -mtime +"${RETENTION_DAYS}" -exec rm -rf {} \; 2>/dev/null || true
echo "[pg_backup] retention: kept last ${RETENTION_DAYS} days under ${BACKUP_ROOT}"

if [ "${fail}" -ne 0 ]; then
  echo "[pg_backup] DONE WITH ERRORS"; exit 1
fi
echo "[pg_backup] DONE OK: ${BACKUP_DIR}"
