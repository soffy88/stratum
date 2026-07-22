-- 0009: 论文 BU skill 检索向量(2026-07-16)
-- 「agent 用 skill」落地: agent 用任务描述检索相关论文技能。
-- 在 bu_onto 加 embedding(BGE-M3 1024维, 同 ku_onto), 检索文本 = overview+problem+use_when+do_not_use_when。
-- 只有 doc_type='paper' 行会被填充; 教材行保持 NULL。
ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS embedding vector(1024);
COMMENT ON COLUMN aii.bu_onto.embedding IS
  'doc_type=paper: 技能检索向量(BGE-M3, 检索文本=overview+problem+use_when+do_not_use_when)。供 /api/skills/search 用。';
