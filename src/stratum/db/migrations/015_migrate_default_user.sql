-- src/stratum/db/migrations/015_migrate_default_user.sql

-- 创建默认 user (wiki自己), corpus_id 跟旧数据匹配
INSERT INTO users (id, email, username, password_hash, corpus_id, email_verified, is_active)
VALUES (
    '01KSDQWBSV0EHDDDA8QNMX5GAZ_DEFAULT', -- 固定 ULID or use the one I created if I can find it
    'wiki@stratum.local',
    'wiki_admin',
    'argon2_placeholder_to_be_reset',
    'corpus_default',
    TRUE,
    TRUE
) ON CONFLICT (email) DO NOTHING;
