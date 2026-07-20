-- ============================================================================
-- AII 学习助手模块 — cx.learning_* 表
-- 依据: AII-LEARNING-COACH-SPEC-001 §三 + AII-CONTEXT-REPO-SPEC-001（C仓 aii_context）
-- 库: aii_context（aii-refined-postgres:5436）; schema: cx（同 0001）
--
-- 学习档案/进度/卡点是情景记忆（关于学习者的）, 与决策案例(cx.decision_case)同居C仓。
-- grade 铁律沿用: learning_progress.grade 默认 unverified, 独立通过裁判测试才 verified。
-- learning_stuck 反复卡的点可沉淀成 cx.lesson_pattern（同0001, 教训模式表, 已存在）。
--
-- 步骤1（本SPEC §五）: 随C仓建库一起建表, 不依赖数据。学习内容启动依赖B仓数学KU就绪。
-- ============================================================================

-- 学习档案（一个学习目标一条）
CREATE TABLE cx.learning_profile (
  profile_id      bigserial PRIMARY KEY,
  subject         text NOT NULL,      -- 学什么（如 "Acemoglu 现代经济增长导论"）
  goal            text,               -- 到什么水平（能独立建简单增长模型/论文理论支撑）
  deadline        text,               -- 时限
  real_starting_point jsonb,          -- ★诊断实测的真实起点（非自评）
  gaps            jsonb,              -- 前置短板（如"从微积分主干重建"）
  main_textbook   text,               -- 选定的主教材
  b_repo_domain   text,               -- 依赖 B 仓哪个领域 KU（math/economics…）
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);

-- 学习计划（阶段路线图）
CREATE TABLE cx.learning_plan (
  plan_id         bigserial PRIMARY KEY,
  profile_id      bigint REFERENCES cx.learning_profile(profile_id),
  stages          jsonb,              -- 阶段路线图（每阶段：内容/任务/成果/验收/耗时）
  capabilities    jsonb,              -- 核心能力拆解（含可简化/跳过标注）
  status          text DEFAULT 'active',
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);

-- 知识点掌握进度（每个可测知识点一条，grade 铁律）
CREATE TABLE cx.learning_progress (
  point_id        bigserial PRIMARY KEY,
  profile_id      bigint REFERENCES cx.learning_profile(profile_id),
  point_name      text,               -- 知识点（如"稳态求解""欧拉方程推导"）
  b_repo_ku_ids   jsonb,              -- 挂靠的 B 仓 KU（教学底座 + 溯源）
  grade           text DEFAULT 'unverified',  -- ★unverified/learning/verified（独立测试过才 verified）
  verified_by     text,               -- 裁判方式（独立推导/代码跑通/隔期重测）
  last_tested_at  timestamptz,
  next_review_at  timestamptz,        -- 间隔重复排期
  attempts        jsonb,              -- 历次测试记录（错误驱动的原料）
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);

-- 卡点库（反复卡的点，错误模式化 → 可升 lesson_pattern）
CREATE TABLE cx.learning_stuck (
  stuck_id        bigserial PRIMARY KEY,
  profile_id      bigint REFERENCES cx.learning_profile(profile_id),
  point_name      text,
  stuck_pattern   text,               -- 卡的模式（"横截条件总忘""链式法则用反"）
  occurrences     int DEFAULT 1,
  resolved        boolean DEFAULT false,
  created_at timestamptz DEFAULT now(), updated_at timestamptz DEFAULT now()
);
