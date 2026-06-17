ALTER TABLE folder_watches ADD COLUMN IF NOT EXISTS scanned_count INTEGER DEFAULT 0;
ALTER TABLE folder_watches ADD COLUMN IF NOT EXISTS ingested_count INTEGER DEFAULT 0;
ALTER TABLE folder_watches ADD COLUMN IF NOT EXISTS current_file VARCHAR DEFAULT '';
ALTER TABLE folder_watches ADD COLUMN IF NOT EXISTS scan_status VARCHAR DEFAULT 'idle';
-- scan_status: idle | scanning | completed | error
