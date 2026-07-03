-- ============================================================================
-- AII B仓（精炼仓 aii_refined）完备 schema — 四层知识有机体
-- 库: aii_refined（独立容器 aii-refined-postgres:5436）; schema: rf
--
-- 两条贯穿 schema 的纪律:
--   ① KU 真身 = 结构化多源贡献 contributions; natural_text 是派生渲染（翻译定稿后填）。
--   ② 所有"成员集合"用 junction 关联表, 不用 jsonb id 列表（可加外键、可重放、不漂移）。
--
-- 不变量: B = f(A仓, 决策台账)。每张四层表带 decision_id 回指 rf.decision_ledger,
--         B仓任意状态可从「A仓 + 台账」确定性重放。
--
-- 空库不灌数据。表/索引/外键/台账到位即验收, 等去重机制灌入。
-- 术语锁定: 本性=invariant（非 nature）; 本性概念=is_invariant_concept 字段（不独立建表）;
--          本性同一=invariant-identity。
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rf;
SET search_path TO rf, public;

-- ----------------------------------------------------------------------------
-- 决策台账 decision_ledger — 地基不变量: 每步深加工决策 append-only 固化, 可重放不重问模型
--   append-only: 绝不改历史行; 修订 = 追加一条 supersedes 指向旧决策。
-- ----------------------------------------------------------------------------
CREATE TABLE rf.decision_ledger (
  decision_id   bigserial PRIMARY KEY,
  decision_type text  NOT NULL,          -- ku_dedup/content_merge/concept_merge/hyperedge_grow/
                                         -- mechanism_merge/invariant_promote/split ...
  inputs        jsonb NOT NULL,          -- 参与对象 id + 关键判据输入
  evidence      jsonb,                   -- 原文依据（回指 A仓 raw_ku_id + 片段）
  model         text,                    -- 模型档位（local-small / frontier-X）
  llm_raw       jsonb,                   -- ★LLM 原始输出（重放读它, 不重问模型）
  verdict       jsonb NOT NULL,          -- 最终裁决（same/different/candidate; 合并成哪个; 加哪个成员…）
  actor         text,                    -- llm / human / program
  supersedes    bigint REFERENCES rf.decision_ledger(decision_id),  -- 修订指向被改的旧决策
  created_at    timestamptz DEFAULT now()
);
CREATE INDEX idx_ledger_type       ON rf.decision_ledger USING btree(decision_type);
CREATE INDEX idx_ledger_supersedes ON rf.decision_ledger USING btree(supersedes);

-- ----------------------------------------------------------------------------
-- 第④层 本性 refined_invariant（预留, M4 填）— 先建, 供 concept↔invariant / cross_domain 引用
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_invariant (
  invariant_id          bigserial PRIMARY KEY,
  statement             text,                              -- 本性是什么（道非相）
  invariant_vector      vector(1024),                      -- 本性向量（同一本性向同处收敛）
  is_invariant_concept  boolean DEFAULT false,             -- false=普通本性 / true=升华为本性概念（不独立建表）
  status                text DEFAULT 'candidate' CHECK (status IN ('candidate','confirmed')),  -- 宁标未发现
  decision_id           bigint REFERENCES rf.decision_ledger(decision_id),
  created_at            timestamptz DEFAULT now(),
  updated_at            timestamptz DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 去重 KU refined_ku — 真身 contributions（多源片段）, natural_text 派生渲染
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_ku (
  ku_id           text PRIMARY KEY,                        -- 新 ULID（B仓独立 ID 空间, 稳定不复用）
  point           text,                                    -- 知识点 canonical 名
  ku_type         text NOT NULL
                  CHECK (ku_type IN ('factual','conceptual','relational','procedural','rationale')),
  is_positional   boolean DEFAULT false,                   -- 立场性（正交样态）
  contributions   jsonb NOT NULL DEFAULT '[]'::jsonb,      -- ★真身: 单一可陈述事项的多源片段
                                                           --   [{source_book_id,version,raw_ku_id,facet,fragment_text}]
  facet_count     integer DEFAULT 0,                       -- 原子性预算监控（越阈值触发拆分）
  natural_text    text,                                    -- 派生渲染（英文, 翻译定稿后填; 可懒渲染, 故可空）
  natural_text_zh text,                                    -- 派生渲染（原语言, 从 contributions 拼装）
  embedding       vector(1024),                            -- 定稿后算（BGE-M3, 干净 KU）
  stance_holder   text,
  opposing_stance text,
  grade           text NOT NULL DEFAULT 'unverified'
                  CHECK (grade IN ('unverified','pending','low','moderate','high','verified','contradicted','refuted')),
  decision_id     bigint REFERENCES rf.decision_ledger(decision_id),
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now(),
  fts             tsvector GENERATED ALWAYS AS
                  (to_tsvector('english', COALESCE(point,'') || ' ' || COALESCE(natural_text,''))) STORED,
  -- 立场性须有持有者（绝不脱离持有者当事实）
  CONSTRAINT ck_refined_ku_positional_holder
    CHECK ((NOT is_positional) OR (stance_holder IS NOT NULL AND stance_holder <> ''))
);

-- ----------------------------------------------------------------------------
-- canonical 概念 refined_concept — 归一 + 判别维度
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_concept (
  concept_id      bigserial PRIMARY KEY,
  name            text,                                    -- canonical 名
  name_zh         text,
  aliases         jsonb,                                   -- 归一并入的别名（各书变体）
  level           text,                                    -- concrete/abstract
  discipline      text,                                    -- 学科（硬隔离用）
  discriminative  jsonb,                                   -- ★判别维度取值 {弹性对象:price, 测量法:arc}
  embedding       vector(1024),                            -- B仓独立概念向量
  sources         jsonb,                                   -- 出现在哪些书
  decision_id     bigint REFERENCES rf.decision_ledger(decision_id),
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

-- 概念 ↔ 本性 多对多（junction, 替单值 FK）: 一个概念可承载多条本性
CREATE TABLE rf.refined_concept_invariant (
  concept_id   bigint REFERENCES rf.refined_concept(concept_id)   ON DELETE CASCADE,
  invariant_id bigint REFERENCES rf.refined_invariant(invariant_id) ON DELETE CASCADE,
  decision_id  bigint REFERENCES rf.decision_ledger(decision_id),
  PRIMARY KEY (concept_id, invariant_id)
);

-- ----------------------------------------------------------------------------
-- 主题 KC refined_theme_kc — 谱社区, 跨书; 快照版本化（重聚类产新版, 旧版冻结）
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_theme_kc (
  kc_id         bigserial PRIMARY KEY,
  version       integer NOT NULL DEFAULT 1,                -- ★聚类快照版本
  is_current    boolean DEFAULT true,                      -- 当前版
  theme_name    text,
  theme_name_en text,
  summary       text,
  summary_zh    text,
  embedding     vector(1024),
  source_books  jsonb,                                     -- 跨哪些书
  created_at    timestamptz DEFAULT now()
);

CREATE TABLE rf.refined_kc_member (
  kc_id bigint REFERENCES rf.refined_theme_kc(kc_id) ON DELETE CASCADE,
  ku_id text   REFERENCES rf.refined_ku(ku_id)       ON DELETE CASCADE,
  PRIMARY KEY (kc_id, ku_id)
);

-- ----------------------------------------------------------------------------
-- KU ↔ 概念 incidence（隐式超边, 共现/聚类用）
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_ku_concept (
  ku_id      text   REFERENCES rf.refined_ku(ku_id)           ON DELETE CASCADE,
  concept_id bigint REFERENCES rf.refined_concept(concept_id) ON DELETE CASCADE,
  PRIMARY KEY (ku_id, concept_id)
);

-- ----------------------------------------------------------------------------
-- 第①层 有向关系 refined_directed_edge — 概念骨架（步骤4.5 readout 建）
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_directed_edge (
  edge_id       bigserial PRIMARY KEY,
  src_concept   bigint REFERENCES rf.refined_concept(concept_id) ON DELETE CASCADE,
  dst_concept   bigint REFERENCES rf.refined_concept(concept_id) ON DELETE CASCADE,
  relation_type text   CHECK (relation_type IN ('derives','subsumes','prerequisite')),
  strength      real,                                      -- 关系强度 0-1
  grade         text DEFAULT 'unverified',
  evidence      jsonb,
  decision_id   bigint REFERENCES rf.decision_ledger(decision_id),
  created_at    timestamptz DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 第②层 有向超边 refined_hyperedge + 多态 member — explains n元（M1 抽取 / M2 生长）
--   head=单一机制 rationale KU; mechanism_key=机制判别维度（供 head 判同）
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_hyperedge (
  hyperedge_id   bigserial PRIMARY KEY,
  relation_type  text DEFAULT 'explains',
  head_ku_id     text REFERENCES rf.refined_ku(ku_id) ON DELETE SET NULL,
  mechanism_key  jsonb,                                    -- ★因果变量/作用方向/适用条件/机制类型（head 判同）
  nl_description text,                                     -- 机制 NL 描述（向量检索）
  embedding      vector(1024),                             -- nl_description 向量（hyperedge_vdb）
  grade          text DEFAULT 'unverified',
  evidence       jsonb,
  decision_id    bigint REFERENCES rf.decision_ledger(decision_id),
  created_at     timestamptz DEFAULT now(),
  updated_at     timestamptz DEFAULT now()
);

-- 成员目标多态: 概念 或 命题 KU（把"机制解释命题"收进同一超边模型, 消灭双轨）
CREATE TABLE rf.refined_hyperedge_member (
  member_id     bigserial PRIMARY KEY,
  hyperedge_id  bigint REFERENCES rf.refined_hyperedge(hyperedge_id) ON DELETE CASCADE,
  member_kind   text NOT NULL CHECK (member_kind IN ('concept','ku')),
  concept_id    bigint REFERENCES rf.refined_concept(concept_id) ON DELETE CASCADE,
  member_ku_id  text   REFERENCES rf.refined_ku(ku_id)           ON DELETE CASCADE,
  status        text DEFAULT 'confirmed' CHECK (status IN ('confirmed','candidate')),  -- 宁缺毋附会
  strength      real,                                      -- 解释强度 0-1
  source_ku_id  text,
  evidence      jsonb,
  cross_disc    boolean DEFAULT false,                     -- 跨学科（尤其严, 先 candidate）
  decision_id   bigint REFERENCES rf.decision_ledger(decision_id),
  added_at      timestamptz DEFAULT now(),
  CHECK ( (member_kind='concept' AND concept_id IS NOT NULL AND member_ku_id IS NULL)
       OR (member_kind='ku'      AND member_ku_id IS NOT NULL AND concept_id IS NULL) )
);
CREATE UNIQUE INDEX uq_he_member
  ON rf.refined_hyperedge_member (hyperedge_id, member_kind, COALESCE(concept_id,-1), COALESCE(member_ku_id,''));

-- ----------------------------------------------------------------------------
-- 第③层 跨域关系 refined_cross_domain_relation — SME 式⟨M,C,S⟩（预留, M3 填）
--   关系层, ≠ 本性。提炼出共享内核 → invariant_id 指向第④层; 否则 NULL（停在关系）。
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_cross_domain_relation (
  relation_id          bigserial PRIMARY KEY,
  description          text,
  source               text,                               -- motif 挖掘 / 结构映射(SME)
  base_domain          text,
  target_domain        text,
  correspondences      jsonb,                              -- ★M: [{base:水压,target:电压}...]
  shared_structure     text,                               -- 共享高阶结构（flow）
  candidate_inferences jsonb,                              -- ★C: 候选推断
  structure_score      real,                               -- ★S: 结构质量分
  embedding            vector(1024),
  invariant_id         bigint REFERENCES rf.refined_invariant(invariant_id),  -- 升第④层则指向; 否则 NULL
  status               text DEFAULT 'candidate',
  decision_id          bigint REFERENCES rf.decision_ledger(decision_id),
  created_at           timestamptz DEFAULT now(),
  updated_at           timestamptz DEFAULT now()
);

-- 跨域关系参与概念（junction, 替 jsonb member_concept_ids）
CREATE TABLE rf.refined_cdr_member (
  relation_id bigint REFERENCES rf.refined_cross_domain_relation(relation_id) ON DELETE CASCADE,
  concept_id  bigint REFERENCES rf.refined_concept(concept_id)                ON DELETE CASCADE,
  role        text,                                        -- base / target
  PRIMARY KEY (relation_id, concept_id)
);

-- ----------------------------------------------------------------------------
-- 向量索引（pgvector HNSW cosine, 类型隔离由"不同表不同列"达成, 无标记维）
-- ----------------------------------------------------------------------------
CREATE INDEX idx_refined_ku_embedding        ON rf.refined_ku                    USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_ku_fts              ON rf.refined_ku                    USING gin  (fts);
CREATE INDEX idx_refined_ku_type             ON rf.refined_ku                    USING btree(ku_type);
CREATE INDEX idx_refined_concept_embedding   ON rf.refined_concept               USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_concept_discipline  ON rf.refined_concept               USING btree(discipline);
CREATE INDEX idx_refined_theme_kc_embedding  ON rf.refined_theme_kc              USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_theme_kc_current    ON rf.refined_theme_kc              USING btree(is_current);
CREATE INDEX idx_refined_hyperedge_embedding ON rf.refined_hyperedge             USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_cdr_embedding       ON rf.refined_cross_domain_relation USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_invariant_vector    ON rf.refined_invariant             USING hnsw (invariant_vector vector_cosine_ops);

-- 关联/查询索引
CREATE INDEX idx_refined_kc_member_ku       ON rf.refined_kc_member         USING btree(ku_id);
CREATE INDEX idx_refined_ku_concept_concept ON rf.refined_ku_concept        USING btree(concept_id);
CREATE INDEX idx_refined_dedge_src          ON rf.refined_directed_edge     USING btree(src_concept);
CREATE INDEX idx_refined_dedge_dst          ON rf.refined_directed_edge     USING btree(dst_concept);
CREATE INDEX idx_refined_he_member_concept  ON rf.refined_hyperedge_member  USING btree(concept_id);
CREATE INDEX idx_refined_he_member_ku       ON rf.refined_hyperedge_member  USING btree(member_ku_id);
CREATE INDEX idx_refined_cdr_member_concept ON rf.refined_cdr_member        USING btree(concept_id);
CREATE INDEX idx_refined_ci_invariant       ON rf.refined_concept_invariant USING btree(invariant_id);
