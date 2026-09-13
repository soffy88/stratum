-- Lifecycle support for the canonical Source table.  NULL means active;
-- existing rows are preserved and remain visible until explicitly deleted.
ALTER TABLE stratum.substrates
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
