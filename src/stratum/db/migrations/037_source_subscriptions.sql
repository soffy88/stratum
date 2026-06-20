-- 统一源订阅表（arXiv / Gutenberg / OAPEN）
CREATE TABLE IF NOT EXISTS source_subscriptions (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    source_type VARCHAR NOT NULL,       -- 'arxiv' | 'gutenberg' | 'oapen'
    name VARCHAR,
    query_json VARCHAR DEFAULT '{}',    -- 各源查询参数 JSON
    max_results INTEGER DEFAULT 10,
    status VARCHAR DEFAULT 'active',
    scan_status VARCHAR DEFAULT 'idle',
    last_check TIMESTAMP,
    found_count INTEGER DEFAULT 0,
    ingested_count INTEGER DEFAULT 0,
    current_item VARCHAR DEFAULT '',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_processed_items (
    subscription_id VARCHAR NOT NULL,
    external_id VARCHAR NOT NULL,       -- arxiv_id / gutenberg_id / oapen_handle
    processed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (subscription_id, external_id)
);

-- 迁移 arxiv_subscriptions → source_subscriptions
INSERT INTO source_subscriptions (
    id, user_id, source_type, name, query_json,
    max_results, status, scan_status, last_check,
    found_count, ingested_count, current_item, created_at
)
SELECT
    id,
    user_id,
    'arxiv',
    name,
    json_object(
        'categories', COALESCE(categories_json, '[]')::JSON,
        'keywords',   keywords,
        'author',     author,
        'after_date', after_date
    )::VARCHAR,
    COALESCE(max_results, 10),
    COALESCE(status, 'active'),
    COALESCE(scan_status, 'idle'),
    last_check,
    COALESCE(found_count, 0),
    COALESCE(ingested_count, 0),
    COALESCE(current_paper, ''),
    COALESCE(created_at, NOW())
FROM arxiv_subscriptions
ON CONFLICT (id) DO NOTHING;

-- 迁移 arxiv_processed_papers → source_processed_items
INSERT INTO source_processed_items (subscription_id, external_id, processed_at)
SELECT subscription_id, arxiv_id, COALESCE(processed_at, NOW())
FROM arxiv_processed_papers
ON CONFLICT (subscription_id, external_id) DO NOTHING;
