-- ============================================================================
-- aii.substrate_discipline — substrate_id → 真学科 的权威映射表
--
-- 为什么需要它(2026-07-20 实测):
--   concept_onto.discipline 一直是脏的: 190 种取值里大部分是 per-book 的 substrate id
--   (econ_zh_2726f38224 / 01KVABDEXD2V985Q9GZWFWPERW), 混着中英文同义(经济学/economics)
--   和空值。下游一切按学科的判断都因此失真(跨学科误判、判同的 discipline 硬隔离失效)。
--
--   ★而"按前缀推学科"和"读 ingested_substrate.subject"两条捷径都被实证否掉了——
--   它们记录的是【哪条管线灌的】, 不是书的学科:
--     · advmath_zh 前缀 30 本里 23 本是经济学教材(自然债务限制/Cournot/Walrasian均衡)
--     · misc_zh 登记 subject='经济学', 实际一本经济书没有(什么是数学/中国哲学简史/认知心理学)
--     · advmath_en 不是书, 是 arXiv 论文
--   所以映射必须逐 substrate 落表, 且以【实物内容】为准。这是 DOMAIN-ONTOLOGY-SPEC-001
--   "以实在为基准"在数据层的一次具体兑现。
--
-- 受控集合(Wiki 2026-07-20 拍板, 粗粒度): 数学/经济学/哲学/心理学/计算机/其他
--   · 粗粒度足以修复判同的 discipline 硬隔离; 二级学科归属本身是判断题, 现在不需要。
--   · 将来要细分是【增量列】sub_discipline, 不破坏本表(与改 UNIQUE 约束那种伤筋动骨不同)。
--   · ★集合受控(同 archiver 的 project 集合): 出现集合外的值 → 报人批准, 不自造。
--
-- 论文(advmath_en 等)刻意【不在本表】: Wiki 决定排除出 M0 概念层——教科书是沉淀过的
-- 知识, 论文是前沿主张, 大量概念是论文自造的局部构造, 灌进 canonical 等于用未沉淀的
-- 东西污染领域本体。KU 仍留在 A仓不删, 将来立专门的论文管道再定怎么进。
-- ============================================================================

CREATE TABLE IF NOT EXISTS aii.substrate_discipline (
  substrate_id text PRIMARY KEY,
  discipline   text NOT NULL
    CHECK (discipline = ANY (ARRAY['数学','经济学','哲学','心理学','计算机','其他'])),
  -- 这条映射怎么来的, 可回溯: program_keyword=程序化关键词命中; human=人工裁定;
  -- registry=直接采信 ingested_substrate.subject(仅用于该来源可信的少数)
  decided_by   text NOT NULL DEFAULT 'program_keyword'
    CHECK (decided_by = ANY (ARRAY['program_keyword','human','registry'])),
  evidence     text,                       -- 命中的关键词 / 人工裁定的理由
  confirmed_by text,                       -- 人工核过的记 'wiki'; 未核为 NULL
  created_at   timestamptz DEFAULT now(),
  updated_at   timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_substrate_discipline_disc
  ON aii.substrate_discipline USING btree (discipline);

COMMENT ON TABLE aii.substrate_discipline IS
  'substrate_id→真学科权威映射。onto_persist 插入概念时从这里读 discipline, 不再留 NULL 窗口。新书登记必须在此有行, 否则 discipline 继续烂。';
