-- G5 anti-loop 根治：miss_rounds 按 (need_hash, source_type) 独立聚合
-- source_type 列已存在（039）；本迁移：回填历史行、去重、建唯一索引、启用 UPSERT 语义
-- ROLLBACK: DROP INDEX IF EXISTS idx_aii_needs_hash_source;

-- 1. 回填 NULL source_type → 'legacy'（历史行保留，不删）
UPDATE aii_processed_needs SET source_type = 'legacy' WHERE source_type IS NULL;

-- 2. 将最新行的 ingested_count 累加为该 (need_hash, source_type) 的历史总量
--    （保证 G1 SUM 在 UPSERT 后仍然正确）
UPDATE aii_processed_needs AS target
SET ingested_count = (
    SELECT COALESCE(SUM(s.ingested_count), 0)
    FROM aii_processed_needs s
    WHERE s.need_hash = target.need_hash AND s.source_type = target.source_type
)
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (PARTITION BY need_hash, source_type
                                  ORDER BY processed_at DESC) AS rn
        FROM aii_processed_needs
    ) t WHERE t.rn = 1
);

-- 3. 删除旧行（每个 (need_hash, source_type) 仅保留最新一行）
DELETE FROM aii_processed_needs
WHERE id NOT IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (PARTITION BY need_hash, source_type
                                  ORDER BY processed_at DESC) AS rn
        FROM aii_processed_needs
    ) t WHERE t.rn = 1
);

-- 4. 建复合唯一索引（启用 ON CONFLICT DO UPDATE UPSERT 语义）
CREATE UNIQUE INDEX IF NOT EXISTS idx_aii_needs_hash_source
    ON aii_processed_needs (need_hash, source_type);
