-- 017_optimization_agents.sql
-- Integration of My Brain Is Full Crew patterns into Stratum
--
-- Registers new scheduled jobs and provides seed data.

-- Vault Audit: monthly health audit (runs 1st of each month at 03:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    user_id,
    name,
    agent_name,
    cron_expression,
    timezone,
    enabled,
    max_items,
    created_at
) SELECT
    'builtin:vault_health_audit',
    'system',
    'vault_health_audit',
    'vault_audit',
    '0 3 1 * *',
    'Asia/Shanghai',
    true,
    20,
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM scheduled_jobs_sl WHERE name = 'vault_health_audit'
);

-- Knowledge Gap Analysis: weekly (Sunday 04:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    user_id,
    name,
    agent_name,
    cron_expression,
    timezone,
    enabled,
    max_items,
    created_at
) SELECT
    'builtin:knowledge_gap_analysis',
    'system',
    'knowledge_gap_analysis',
    'knowledge_gap',
    '0 4 * * 0',
    'Asia/Shanghai',
    true,
    20,
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM scheduled_jobs_sl WHERE name = 'knowledge_gap_analysis'
);

-- Graph Health Scoring: daily (05:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    user_id,
    name,
    agent_name,
    cron_expression,
    timezone,
    enabled,
    max_items,
    created_at
) SELECT
    'builtin:graph_health_daily',
    'system',
    'graph_health_daily',
    'graph_health',
    '0 5 * * *',
    'Asia/Shanghai',
    true,
    20,
    NOW()
WHERE NOT EXISTS (
    SELECT 1 FROM scheduled_jobs_sl WHERE name = 'graph_health_daily'
);
