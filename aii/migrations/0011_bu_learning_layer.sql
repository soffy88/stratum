-- 0011: BU 学习层(2026-08-14) — 按 su-learning-map 学习内容标准升级教材 BU
-- 背景: 原 BU 只有七项书级抽象文本(soul/positioning/question/skeleton/thinking/for_whom/boundary),
--   回答"这本书是什么", 不回答"人怎么学"。升级后教材 BU = 七项人读摘要 + 学习层(能力路径+深卡)。
-- 学习层字段对齐 su-learning-map learning-content-schema(深卡): 每卡 context/arguments/source_digest/
--   boundary/connections/practice; 证据分级(primary/corroborated/external/inference/current)由代码
--   按 KU grade 计算(LLM 无权决定); 原文切片(source_excerpts)由代码从 ku_onto.grounded_by 注入, 逐字不改写。
-- 论文路径(doc_type=paper)不受影响; 这些列对 paper 行保持 NULL。
ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS learning_paths jsonb;
ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS deep_cards jsonb;
ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS bu_quality jsonb;

COMMENT ON COLUMN aii.bu_onto.learning_paths IS
  '教材 BU 学习层: 3-7 条能力转变路径(学完能做什么, 非原书章节名)。键: id,no,name,promise,card_ids[]。';
COMMENT ON COLUMN aii.bu_onto.deep_cards IS
  '教材 BU 学习层: 深卡(每卡改变一个判断)。键: id,name,path,ku_ids[],evidence(代码按 KU grade 计算),'
  'desc,excerpt(逐字≤150字),context(≥50字),arguments(≥3条),source_digest(≥2段),boundary(≥40字),'
  'connections[],practice,source_excerpts[{text,ku_id,locator}]。';
COMMENT ON COLUMN aii.bu_onto.bu_quality IS
  '教材 BU 学习层质量门记录(全确定性): {status: ok|partial|insufficient_data, checks:[], dropped:[{card,name,reason}]}。';
