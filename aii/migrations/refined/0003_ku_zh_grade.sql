-- ============================================================================
-- rf.refined_ku.zh_grade — KU 中文译文的 grade (AII-LEARNING-COACH-SPEC-001 §1.4)
-- 译文是"相"不是"道": 原文 natural_text(英文)永远权威, natural_text_zh 只是受控译文。
--   NULL       = 还没译(英文源KU默认)
--   unverified = 本地LLM机器译(默认)——译文默认不可信, 同 grade 铁律
--   verified   = Wiki 读时校对/修正过, 升级为可信译文
-- 中文源KU(抽取时就带 natural_text_zh)不经翻译, zh_grade 可留 NULL 或按需标注。
-- ============================================================================

ALTER TABLE rf.refined_ku
  ADD COLUMN IF NOT EXISTS zh_grade text;
