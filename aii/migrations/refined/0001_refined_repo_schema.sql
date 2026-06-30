-- ============================================================================
-- AII B仓（精炼仓 aii_refined）完备 schema — 四层知识有机体
-- Doc: AII-REFINED-REPO-SCHEMA-001 §二 + §6.2(strength) ; 术语: AII-INVARIANT-LAYER-001
-- 库: aii_refined (独立容器 aii-refined-postgres, port 5436) ; schema: rf
-- 固化进 repo(VHDX 教训): DDL 不依赖现库存活, 可重建。
--
-- ★忠实修正(报审): SCHEMA-001 §2.1 的 refined_ku 用了示意列名(point/facets/ku_type),
--   与真实 aii.ku_onto 不符。文档原则=「沿用 ku_onto 结构, 不重新设计」, 故 refined_ku
--   镜像真实 ku_onto 的知识承载列(含六类CHECK/生成列 is_positional/fts) + 加 B仓出处字段。
--   按 §6.4 砍掉 A仓的时序/版本列(valid_from/valid_until/superseded_by) 与 A仓专属
--   substrate_id(B仓改用 sources 软溯源指针回查 A仓)。
--
-- ★空库不灌数据。表/索引/外键到位即验收, 等去重机制(AII-KU-DEDUP-001)灌入。
-- ★命门: B仓无重复/四层一次预留完备/出处可追溯/A·B职责纯粹/完备不臃肿。
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA IF NOT EXISTS rf;
SET search_path TO rf, public;

-- ----------------------------------------------------------------------------
-- ④ 第④层 本性 invariant (预留, M4 才填) — 先建, 供 concept/cross_domain 外键引用
--   术语锁定: 本性=invariant(非nature); 本性概念=is_invariant_concept 字段(不独立建表);
--   本性同一=invariant-identity。
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_invariant (
  invariant_id          bigserial PRIMARY KEY,
  statement             text,                              -- 本性是什么(道非相)
  invariant_vector      vector(1024),                      -- 本性向量(同一本性向同处收敛)
  is_invariant_concept  boolean      DEFAULT false,        -- false=普通本性 / true=升华为本性概念(不独立建表)
  member_concept_ids    jsonb,                             -- 共有此本性的概念们(≥2 可升华)
  status                text         DEFAULT 'candidate'   -- candidate/confirmed(宁标未发现)
                        CHECK (status IN ('candidate','confirmed')),
  created_at            timestamptz  DEFAULT CURRENT_TIMESTAMP,
  updated_at            timestamptz  DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- ① 去重 KU refined_ku — 镜像真实 aii.ku_onto 知识承载列 + B仓出处字段
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_ku (
  ku_id           text PRIMARY KEY,
  title           text,
  natural_text    text NOT NULL,                            -- 讲透正文(英文统一)
  natural_text_zh text,                                     -- 中文
  knowledge_type  text NOT NULL
                  CHECK (knowledge_type IN ('conceptual','rationale','factual','metacognitive','positional','procedural')),
  sub_type        text
                  CHECK (sub_type IS NULL OR sub_type IN ('classification','conditional','principle','self_knowledge','skill','strategic','task_knowledge','technique','theory')),
  is_positional   boolean GENERATED ALWAYS AS ((knowledge_type = 'positional')) STORED,
  stance_holder   text,
  opposing_stance text,
  grade           text NOT NULL DEFAULT 'unverified'
                  CHECK (grade IN ('contradicted','high','low','moderate','pending','refuted','unverified','verified')),
  grounded_by     jsonb,
  intuition       text,
  insight         text,
  example         text,
  embedding       vector(1024),                             -- B仓独立向量(BGE-M3 1024维, 干净KU)
  -- ★B仓出处/去重字段
  sources         jsonb       DEFAULT '[]'::jsonb,          -- [{book_id,version,extract_batch,chapter,raw_ku_id,contributed}] 多出处,回查A仓
  is_fragmented   boolean     DEFAULT false,                -- 是否片段化合并产物(多书内容拼成, 越读越厚)
  merge_count     integer     DEFAULT 1,                    -- B仓去重并入次数
  provenance      jsonb,
  fingerprint     text,                                     -- 内容指纹(去重精确匹配)
  created_at      timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at      timestamptz DEFAULT CURRENT_TIMESTAMP,
  fts             tsvector GENERATED ALWAYS AS (to_tsvector('english', (COALESCE(title,'') || ' ' || COALESCE(natural_text,'')))) STORED,
  -- 沿用 ku_onto 的知识完整性约束(六类本体): grade=verified 须有非default方法; positional 须有 stance_holder
  CONSTRAINT ck_refined_ku_grade_mandate    CHECK ((grade <> 'verified') OR (COALESCE(grounded_by->>'method','default') <> 'default')),
  CONSTRAINT ck_refined_ku_positional_holder CHECK ((knowledge_type <> 'positional') OR (stance_holder IS NOT NULL AND stance_holder <> ''))
);

-- ----------------------------------------------------------------------------
-- ② canonical 概念 refined_concept — 归一 + 判别维度(AII-CONCEPT-IDENTITY-001)
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_concept (
  concept_id      bigserial PRIMARY KEY,
  name            text,                                     -- canonical 名
  name_zh         text,
  aliases         jsonb,                                    -- 归一并入的别名(各书变体)
  level           text,                                     -- concrete/abstract
  discipline      text,                                     -- 学科(硬隔离用)
  discriminative  jsonb,                                    -- ★判别维度取值(逐维度判同: price≠income 不合并)
  embedding       vector(1024),                             -- B仓独立概念向量
  invariant_id    bigint REFERENCES rf.refined_invariant(invariant_id),  -- → 本性(可空; 抽不出留 NULL)
  sources         jsonb,                                    -- 出现在哪些书
  created_at      timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at      timestamptz DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- ③ 主题 KC refined_theme_kc — 谱社区, 跨书(无按章 KC, 按章在 A库)
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_theme_kc (
  kc_id         bigserial PRIMARY KEY,
  theme_name    text,
  theme_name_en text,
  summary       text,
  summary_zh    text,
  embedding     vector(1024),
  source_books  jsonb,                                      -- 这个主题跨哪些书
  created_at    timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at    timestamptz DEFAULT CURRENT_TIMESTAMP
);

-- 主题 KC ↔ 去重 KU 成员(跨书)
CREATE TABLE rf.refined_kc_member (
  kc_id bigint REFERENCES rf.refined_theme_kc(kc_id) ON DELETE CASCADE,
  ku_id text   REFERENCES rf.refined_ku(ku_id)       ON DELETE CASCADE,
  PRIMARY KEY (kc_id, ku_id)
);

-- ----------------------------------------------------------------------------
-- KU ↔ 概念 incidence (HyperGraphRAG 式隐式超边, 共现/聚类用)
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_ku_concept (
  ku_id      text   REFERENCES rf.refined_ku(ku_id)            ON DELETE CASCADE,
  concept_id bigint REFERENCES rf.refined_concept(concept_id)  ON DELETE CASCADE,
  PRIMARY KEY (ku_id, concept_id)
);

-- ----------------------------------------------------------------------------
-- 第①层 有向关系 refined_directed_edge — 概念骨架(M0 后步骤4.5 readout 建)
--   + §6.2 strength(关系强度)
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_directed_edge (
  edge_id       bigserial PRIMARY KEY,
  src_concept   bigint REFERENCES rf.refined_concept(concept_id) ON DELETE CASCADE,
  dst_concept   bigint REFERENCES rf.refined_concept(concept_id) ON DELETE CASCADE,
  relation_type text   CHECK (relation_type IN ('derives','subsumes','prerequisite')),
  strength      real,                                       -- §6.2 关系强度 0-1
  grade         text   DEFAULT 'unverified',
  evidence      jsonb,
  created_at    timestamptz DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 第②层 有向超边 refined_hyperedge + member — explains n元(M1抽取/M2生长)
--   对齐 AII-HYPEREDGE-EXPLAINS-001(status/evidence/cross_disc) + §6.2 strength
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_hyperedge (
  hyperedge_id   bigserial PRIMARY KEY,
  relation_type  text DEFAULT 'explains',                   -- 受控, 现 explains
  head_ku_id     text REFERENCES rf.refined_ku(ku_id) ON DELETE SET NULL,  -- 解释者: rationale KU
  nl_description text,                                       -- 机制 NL 描述(向量检索)
  embedding      vector(1024),                              -- nl_description 向量(hyperedge_vdb)
  grade          text DEFAULT 'unverified',
  evidence       jsonb,
  created_at     timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at     timestamptz DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE rf.refined_hyperedge_member (
  hyperedge_id bigint REFERENCES rf.refined_hyperedge(hyperedge_id) ON DELETE CASCADE,
  concept_id   bigint REFERENCES rf.refined_concept(concept_id)     ON DELETE CASCADE,
  source_ku_id text,
  status       text    DEFAULT 'confirmed' CHECK (status IN ('confirmed','candidate')),  -- 宁缺毋附会
  strength     real,                                        -- §6.2 解释强度 0-1(这个机制对这个概念多核心)
  evidence     jsonb,
  cross_disc   boolean DEFAULT false,                       -- 跨学科(尤其严, 先 candidate)
  added_at     timestamptz DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (hyperedge_id, concept_id)
);

-- ----------------------------------------------------------------------------
-- ★第③层 跨域关系 refined_cross_domain_relation — SME 式⟨M,C,S⟩(预留, M3填)
--   关系层(base↔target 对应), ≠ 本性。提炼出共享内核 → invariant_id 指向第④层。
-- ----------------------------------------------------------------------------
CREATE TABLE rf.refined_cross_domain_relation (
  relation_id          bigserial PRIMARY KEY,
  description          text,
  source               text,                                -- motif 挖掘 / 结构映射(SME)
  base_domain          text,
  target_domain        text,
  correspondences      jsonb,                               -- ★M: [{base:水压,target:电压}...]
  member_concept_ids   jsonb,
  member_disciplines   jsonb,
  shared_structure     text,                                -- 共享高阶结构(flow)
  candidate_inferences jsonb,                               -- ★C: 候选推断
  structure_score      real,                                -- ★S: 结构质量分
  embedding            vector(1024),
  invariant_id         bigint REFERENCES rf.refined_invariant(invariant_id),  -- 升第④层则指向; 提炼不出留 NULL(停在关系)
  status               text DEFAULT 'candidate',
  created_at           timestamptz DEFAULT CURRENT_TIMESTAMP,
  updated_at           timestamptz DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 向量索引(pgvector HNSW cosine, 对齐 A仓 ku_onto 的 vector_cosine_ops)
-- ----------------------------------------------------------------------------
CREATE INDEX idx_refined_ku_embedding        ON rf.refined_ku                   USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_ku_fts              ON rf.refined_ku                   USING gin  (fts);
CREATE INDEX idx_refined_ku_type             ON rf.refined_ku                   USING btree(knowledge_type);
CREATE INDEX idx_refined_concept_embedding   ON rf.refined_concept              USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_concept_discipline  ON rf.refined_concept              USING btree(discipline);
CREATE INDEX idx_refined_theme_kc_embedding  ON rf.refined_theme_kc             USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_hyperedge_embedding ON rf.refined_hyperedge            USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_cdr_embedding       ON rf.refined_cross_domain_relation USING hnsw (embedding vector_cosine_ops);
CREATE INDEX idx_refined_invariant_vector    ON rf.refined_invariant            USING hnsw (invariant_vector vector_cosine_ops);

-- 关联表常用查询索引
CREATE INDEX idx_refined_kc_member_ku        ON rf.refined_kc_member            USING btree(ku_id);
CREATE INDEX idx_refined_ku_concept_concept  ON rf.refined_ku_concept           USING btree(concept_id);
CREATE INDEX idx_refined_dedge_src           ON rf.refined_directed_edge        USING btree(src_concept);
CREATE INDEX idx_refined_dedge_dst           ON rf.refined_directed_edge        USING btree(dst_concept);
CREATE INDEX idx_refined_he_member_concept   ON rf.refined_hyperedge_member     USING btree(concept_id);
CREATE INDEX idx_refined_concept_invariant   ON rf.refined_concept              USING btree(invariant_id);
