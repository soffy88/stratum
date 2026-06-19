CREATE TABLE IF NOT EXISTS arxiv_subscriptions (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    name VARCHAR,
    categories_json VARCHAR DEFAULT '[]',
    keywords VARCHAR,
    author VARCHAR,
    after_date VARCHAR,
    max_results INTEGER DEFAULT 10,
    llm_filter VARCHAR,
    status VARCHAR DEFAULT 'active',
    scan_status VARCHAR DEFAULT 'idle',
    last_check TIMESTAMP,
    found_count INTEGER DEFAULT 0,
    ingested_count INTEGER DEFAULT 0,
    current_paper VARCHAR DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS arxiv_processed_papers (
    subscription_id VARCHAR NOT NULL,
    arxiv_id VARCHAR NOT NULL,
    processed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (subscription_id, arxiv_id)
);
