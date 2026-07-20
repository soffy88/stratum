-- ============================================================================
-- cx.learning_progress 增补: 持续掌握度 + 知识类型路由 (吸收 DeepTutor, P0)
-- 依据: DeepTutor 吸收报告 P0.1(一次通过≠verified) + P0.2(按 ku_type 路由裁判)
--
-- mastery_score: 近因加权掌握分(0~1), 带置信上限——单次/两次答对封顶0.5/0.8, 防"过早掌握"
--   (原则二: 一次答对不给放行)。verified 现在还额外要求"跨间隔重测的持续通过", 见 learning.py。
-- knowledge_type: 从挂靠的 B仓 KU(rf.refined_ku.ku_type)解析出的主类型, 决定默认裁判:
--   procedural→代码执行, conceptual/rationale/factual→推导裁判(Feynman/托管答案是P1)。
-- ============================================================================

ALTER TABLE cx.learning_progress
  ADD COLUMN IF NOT EXISTS mastery_score real NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS knowledge_type text;
