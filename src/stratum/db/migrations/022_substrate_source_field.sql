-- 022_substrate_source_field.sql
-- Wave 2: add source + published_at to substrates for AII export metadata
ALTER TABLE substrates ADD COLUMN IF NOT EXISTS source VARCHAR;
ALTER TABLE substrates ADD COLUMN IF NOT EXISTS published_at TIMESTAMP;
