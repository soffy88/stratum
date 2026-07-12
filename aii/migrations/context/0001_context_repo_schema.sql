-- ============================================================================
-- AII C仓（个人判断资产仓 aii_context）schema — CBR 案例结构
-- 依据: AII-CONTEXT-REPO-SPEC-001（阶段1+2）
-- 库: aii_context（独立 database, 复用 B仓容器 aii-refined-postgres:5436）; schema: cx
--
-- 隔离纪律:
--   ① database 级隔离: 与 aii_refined 跨 database 默认不能 JOIN, 范畴不污染。
--   ② grounded_in 是跨仓"指针"（存 B仓 concept_id/ku_id + 库名）, 严禁把 B仓数据
--      融进来、严禁跨 database JOIN。需要时应用层按 id 去 aii_refined 查
--      （与 B仓 sources 回查 A仓同一套机制）。可空、弱耦合。
--   ③ grade 铁律: 全部默认 'unverified'——AI 归纳的判断不自动可信,
--      Wiki 确认或后续被验证有效才升级。
--
-- CBR 六件套（decision_case）: 情境/备选/理由/★复用条件/结果/教训。
-- 复用条件（reuse_conditions/trigger_context/applicability）是 CBR 核心、最易漏。
--
-- 空库不灌数据（编译提炼是下一个 SPEC）。database+schema+3表0行+HNSW索引到位即验收。
-- 本文件在 aii_context database 内执行（CREATE DATABASE 在外层单独执行, 见 README/操作记录）。
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE SCHEMA IF NOT EXISTS cx;

-- 决策案例（CBR 核心表）
CREATE TABLE cx.decision_case (
  case_id         bigserial PRIMARY KEY,
  title           text NOT NULL,
  project         text,              -- 受控集合（同 archiver: 八项目+general）
  -- CBR 六件套
  situation       text,              -- ① 情境与目标：当时面对什么、要达成什么
  alternatives    jsonb,             -- ② 备选方案：考虑过哪些选项（不只选中的）
  rationale       text,              -- ③ 选择理由：为什么选这个
  reuse_conditions text,             -- ★④ 复用条件：这理由在什么情境成立/什么情境反过来（CBR核心，最易漏）
  result          text,              -- ⑤ 执行结果：后来发生了什么（后续追加，可空）
  lesson          text,              -- ⑥ 教训：模式化、可迁移的那部分（非事件本身）
  -- AII 纪律
  grade           text DEFAULT 'unverified',  -- ★默认未验证；Wiki确认或后续被验证有效才升级
  grounded_in     jsonb,             -- ★跨仓引用：指向 B仓 [{repo:'aii_refined', concept_id/ku_id, note}]（可空，指针非融合）
  source_files    jsonb,             -- 溯源：来自归档区哪些文件（archive_registry.file_id）
  embedding       vector(1024),      -- 情境向量（检索相似案例用；BGE-M3，与A/B仓一致）
  status          text DEFAULT 'active',
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);

-- 教训模式（bad case 模式化，不存具体事件）
CREATE TABLE cx.lesson_pattern (
  pattern_id      bigserial PRIMARY KEY,
  statement       text NOT NULL,     -- 模式化的教训（"CC倾向局部优化忽略全局约束"，非某次具体事件）
  trigger_context text,              -- 什么情境该触发这条教训（=复用条件的一种）
  evidence_case_ids jsonb,           -- 支撑此模式的具体案例（≥N 条才凝结，宁缺毋附会）
  grade           text DEFAULT 'unverified',
  embedding       vector(1024),
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);

-- 方法论资产（可复用做法，procedural）
CREATE TABLE cx.methodology (
  method_id       bigserial PRIMARY KEY,
  name            text NOT NULL,
  description     text,              -- 方法论内容（"预注册+对已知危机窗口压力测试防过拟合"）
  applicability   text,              -- ★适用边界（复用条件的 procedural 版）
  grounded_in     jsonb,             -- 知识依据指向 B仓（可空，指针引用）
  grade           text DEFAULT 'unverified',
  embedding       vector(1024),
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);

-- 向量索引: HNSW cosine（vector_cosine_ops, 对齐 A/B 仓）
CREATE INDEX idx_cx_decision_case_embedding ON cx.decision_case
  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_cx_lesson_pattern_embedding ON cx.lesson_pattern
  USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_cx_methodology_embedding ON cx.methodology
  USING hnsw (embedding vector_cosine_ops);
