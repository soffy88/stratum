-- 每个飞轮保底配额: aii_processed_needs 加 bucket 列(econ/math/misc), 用于按
-- 学科方向分桶统计"今天已处理多少", 让 aii_feedback_service.py 能保证每个
-- 消费该配额的飞轮(econ-zh/math-prog/misc)每天至少拿到 BUCKET_DAILY_MAX 份额,
-- 不被固定/轮转顺序里排前面的其它桶主题占满全局配额饿死。
-- 历史行没有 bucket 归属信息(bucket 由 aii_feedback_service.py 在处理时按
-- topic 所属方向打上, 历史行打不上, 留 NULL——不影响新写入行的分桶统计)。
-- ROLLBACK: ALTER TABLE aii_processed_needs DROP COLUMN IF EXISTS bucket;

ALTER TABLE aii_processed_needs ADD COLUMN IF NOT EXISTS bucket TEXT;
CREATE INDEX IF NOT EXISTS idx_aii_needs_bucket_day ON aii_processed_needs (bucket, processed_at);
