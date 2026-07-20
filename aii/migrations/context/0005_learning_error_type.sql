-- ============================================================================
-- cx.learning_stuck.error_type — 四型错误分类 (吸收 DeepTutor, P2.1)
-- 不再只记一条 issue 字符串, 而是把"为什么错"归到四型之一, 驱动对症补救、让沉淀出的
-- lesson_pattern 更可迁移:
--   knowledge_structural 知识结构缺失(缺前置概念/定义没建立)
--   understanding_deviation 理解偏差(概念理解错/混淆)
--   application_error 应用错误(概念懂但用错/算错/跳步)
--   metacognitive 元认知(没意识到自己不会/空白/方法选错)
-- ============================================================================

ALTER TABLE cx.learning_stuck
  ADD COLUMN IF NOT EXISTS error_type text;
