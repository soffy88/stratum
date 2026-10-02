-- 046: compatibility schema for legacy DuckDB exports.
-- The active runtime uses PostgreSQL migrations; keeping this file makes the
-- historical migration set self-describing for local vault/test databases.

CREATE TABLE IF NOT EXISTS flashcards (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    source_kind VARCHAR DEFAULT 'substrate',
    source_id VARCHAR NOT NULL,
    source_title VARCHAR,
    front VARCHAR NOT NULL,
    back VARCHAR NOT NULL,
    tags VARCHAR[] DEFAULT [],
    repetitions INTEGER DEFAULT 0,
    easiness DOUBLE DEFAULT 2.5,
    interval_days DOUBLE DEFAULT 0,
    due_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS fsrs_state INTEGER DEFAULT 1;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS fsrs_step INTEGER DEFAULT 0;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS stability DOUBLE;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS difficulty DOUBLE;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS last_review_at TIMESTAMP;
ALTER TABLE flashcards ADD COLUMN IF NOT EXISTS desired_retention DOUBLE DEFAULT 0.9;

CREATE TABLE IF NOT EXISTS learning_preferences (
    user_id VARCHAR PRIMARY KEY,
    desired_retention DOUBLE DEFAULT 0.9,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE highlights ADD COLUMN IF NOT EXISTS confidence DOUBLE DEFAULT 1.0;
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS quote_hash VARCHAR;
ALTER TABLE highlights ADD COLUMN IF NOT EXISTS locator_json JSON DEFAULT '{}';
