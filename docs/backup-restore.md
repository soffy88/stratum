# AII backup and restore

PostgreSQL is the authority backup target. A logical custom-format dump must
include the `aii_kg` database and `stratum`/`aii` schemas. Local index files,
caches and optional provider artifacts are rebuildable and are not authority
backups.

Use `deploy/pg_backup.sh` in the maintained deployment, or the equivalent
Compose command below, with an encrypted, access-controlled destination:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.oss.yml exec -T db \
  pg_dump -U "$AII_DB_USER" -Fc "$AII_DB_NAME" > "${BACKUP_FILE:?set BACKUP_FILE}"
```

Configure `AII_PG_BACKUP_ROOT` and `AII_PG_BACKUP_RETENTION_DAYS` for the
maintained script (its default retention is seven days). The legacy
`deploy/backup.sh` is not an authority backup because it only handles old local
files/avatars.

Restore into a fresh PostgreSQL instance, apply required extensions, then
verify migration state, canonical Source/Fragment/Claim/Artifact IDs and counts,
owner-scoped reads, KnowledgeView retrieval, projection rebuildability, checksums
and health/readiness. Record the dump ID, schema version, duration and result.
Never test restore by deleting the live database.
