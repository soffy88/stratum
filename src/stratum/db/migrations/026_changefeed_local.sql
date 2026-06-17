-- 026_changefeed_local.sql
-- Create missing changefeed_local table.
-- Found missing during E2E R-3 verification.

CREATE TABLE IF NOT EXISTS changefeed_local (
    seq        BIGINT DEFAULT nextval('changefeed_seq') PRIMARY KEY,
    table_name VARCHAR NOT NULL,
    row_id     VARCHAR NOT NULL,
    op         VARCHAR NOT NULL,
    payload    JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW()
);
