-- parse_quality: ok | garbled | scanned | empty | duplicate
ALTER TABLE substrates ADD COLUMN IF NOT EXISTS parse_quality VARCHAR DEFAULT NULL;
