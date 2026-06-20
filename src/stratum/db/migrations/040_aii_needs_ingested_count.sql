-- G1护栏改为限总入库篇数：新增 ingested_count 字段
-- _guardrail_need_count 改为 SUM(ingested_count) 而非 COUNT(*)
ALTER TABLE aii_processed_needs ADD COLUMN IF NOT EXISTS ingested_count INTEGER DEFAULT 0;
