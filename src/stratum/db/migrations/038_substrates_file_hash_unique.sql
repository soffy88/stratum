-- Prevent duplicate file ingestion: unique index on (user_id, file_hash).
-- Scoped per user so different users can hold the same file independently.
-- NULL file_hash excluded (some substrates have no hash, e.g. web clips).
-- Run dedup_backup_20260620.json cleanup before applying this migration.
-- DuckDB does not support partial indexes; NULL values do not conflict in UNIQUE indexes.
CREATE UNIQUE INDEX IF NOT EXISTS idx_substrates_user_file_hash
    ON substrates (user_id, file_hash);
