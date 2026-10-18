-- 092: parse-quality columns on the service-layer substrates table.
-- Read/written by stratum.dao.substrate, api/routers/{quality,scan_ocr,substrates,inbox}
-- and lib/quality/ingest_quality_gate (DuckDB schema already has them).
-- Idempotent: safe on databases where the columns were added by hand.
ALTER TABLE IF EXISTS substrates ADD COLUMN IF NOT EXISTS parse_quality TEXT;
ALTER TABLE IF EXISTS substrates ADD COLUMN IF NOT EXISTS quality_reason TEXT;
