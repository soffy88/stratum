-- Migration 031: folder_watches table for monitored local/remote paths
CREATE TABLE IF NOT EXISTS folder_watches (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    path VARCHAR NOT NULL,
    description VARCHAR,
    status VARCHAR DEFAULT 'active',
    last_scan_at TIMESTAMP,
    file_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);
