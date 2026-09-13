-- 017_optimization_agents.sql
-- Integration of My Brain Is Full Crew patterns into Stratum
--
-- Registers new scheduled jobs and provides seed data.

-- Vault Audit: monthly health audit (runs 1st of each month at 03:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    user_id,
    name,
    cron_expression,
    timezone,
    agent_name,
    enabled,
    created_at
) VALUES (
    'vault_health_audit',
    'system',
    'vault_health_audit',
    '0 3 1 * *',
    'Asia/Shanghai',
    'vault_audit',
    true,
    NOW()
) ON CONFLICT DO NOTHING;

-- Knowledge Gap Analysis: weekly (Sunday 04:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    user_id,
    name,
    cron_expression,
    timezone,
    agent_name,
    enabled,
    created_at
) VALUES (
    'knowledge_gap_analysis',
    'system',
    'knowledge_gap_analysis',
    '0 4 * * 0',
    'Asia/Shanghai',
    'knowledge_gap',
    true,
    NOW()
) ON CONFLICT DO NOTHING;

-- Graph Health Scoring: daily (05:00 CST)
INSERT INTO scheduled_jobs_sl (
    id,
    user_id,
    name,
    cron_expression,
    timezone,
    agent_name,
    enabled,
    created_at
) VALUES (
    'graph_health_daily',
    'system',
    'graph_health_daily',
    '0 5 * * *',
    'Asia/Shanghai',
    'graph_health',
    true,
    NOW()
) ON CONFLICT DO NOTHING;
