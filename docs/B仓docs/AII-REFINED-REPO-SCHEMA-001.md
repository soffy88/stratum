# AII 精炼仓(B仓)完备数据模型

> **Doc ID:** AII-REFINED-REPO-SCHEMA-001
> **定位:** 精炼仓(B 仓 = 知识有机体本身)的**完备数据模型**。B 仓最重要——concept canonical、超边、本性都长在它上面。一次设计完备，建好后上层建于其上，不用伤筋动骨改 schema。
> **依据决策（已定）:**
> - B 仓 = **独立数据库**（aii_refined，与原始仓 aii_raw 物理隔离）。
> - **A 库（原始仓）= 按章 KC（书原貌）+ 原始 KU（有重复）**；**B 仓（精炼仓）= 只主题 KC（跨书有机体）+ 去重 KU（无重复）**。
> - B 仓 KU **沿用原始仓 ku_onto 结构 + 加出处字段**（不重新设计）。
> - B 仓**从 0 空库建**，原始仓 KU 经去重机制灌入（不直接迁）。
> - 去重粒度 = 内容片段级（判定细节另文 AII-KU-DEDUP-001）。
> **状态:** schema 已**实证完备性检验**（对照 HyperGraphRAG/Hyper-RAG/生产 KG 最佳实践）。大部分对齐前沿（二部图存储/双向量库/confidence 分级/provenance），3 个真缺口已克制补全（见 §六，不建表）。供审 → CC 建库。
> **实证完备性一句话:** 对齐前沿成熟做法、补齐 3 个被前沿证明重要的真缺口、且不过度设计（temporal/版本图等 AII 不需要的不加）——**完备且不臃肿。**

---

## 一、B 仓装什么（完备清单）

```
B 仓 = 跨书知识有机体（无重复），完整容纳：
  · 去重 KU（沿用 ku_onto + 出处字段）          ← 基础
  · canonical 概念（归一，判别维度/level/discipline/向量）
  · 主题 KC（谱社区，跨书）                      ← 不含按章 KC（那在 A 库）
  · 第①层 有向关系（concept→concept）
  · 第②层 有向超边（hyperedge + member）
  · ★第③层 跨域关系（cross_domain_relation，motif/结构映射出的跨域对应，SME 式⟨M,C,S⟩）  ← 预留
  · 第④层 本性（invariant，is_invariant_concept 字段标记升华；从第③层提炼共享内核，稍高一层）  ← 预留
  · 独立向量空间（KU/概念/超边/跨域关系/本性 向量）
  · 出处追溯（KU/片段 → 原始仓哪些书）
```

> **完备原则**：四层（有向关系/超边/跨域关系/本性）的表全部预留，建库一次到位。后加易遗漏外键关联（超边连概念、跨域关系连概念、概念连本性、跨域关系→本性 invariant_id）。**预留不等于立即填**（M1 填超边，M3 填跨域关系/本性），但表结构先到位。本性概念不独立建表（is_invariant_concept 字段），见 §2.8。
> **★四层关系（关键）**：第③层跨域关系（motif/结构映射出的"base↔target 对应"）≠ 第④层本性（提炼出的"共享抽象内核"）。第③层提炼出共享内核 → invariant_id 指向第④层（升华为本性）；提炼不出 → 留 NULL（**停在第③层关系，宁停在关系不附会**）。详见 AII-INVARIANT-LAYER-001。

---

## 二、表设计

### 2.1 ① 去重 KU（refined_ku，沿用 ku_onto + 出处）
```sql
CREATE TABLE rf.refined_ku (
  -- 沿用 ku_onto 的字段（讲透六类/双语/向量那套）
  ku_id           text PRIMARY KEY,
  ku_type         text,              -- 六类: conceptual/rationale/procedural/positional/factual/...
  point           text,              -- 知识点名
  natural_text    text,              -- 讲透正文（英文）
  natural_text_zh text,              -- 中文
  facets          jsonb,             -- 该类型的面（WHAT/WHY/HOW 等）
  embedding       vector(1024),      -- B 仓独立向量（BGE-M3，干净 KU 的向量）
  -- ★出处字段（新增，B 仓特有）
  sources         jsonb,             -- ★多出处: [{book_id, chapter, raw_ku_id, contributed: "什么内容"}]
  is_fragmented   boolean DEFAULT false,  -- 是否片段化合并产物（多书内容拼成）
  created_at / updated_at timestamptz
);
```
- **sources** 是 B 仓关键：一个去重 KU 的内容来自原始仓哪些书的哪些 KU，每个出处贡献了什么内容（追溯 + "越读越厚"的记录）。
- 例：导数定义 KU 的 sources = [{数分: ε-δ 严格定义}, {同济: 应用导向定义}]——两书不同内容并存，各标出处。

### 2.2 ② canonical 概念（refined_concept，归一 + 判别维度）
```sql
CREATE TABLE rf.refined_concept (
  concept_id      bigserial PRIMARY KEY,
  name            text,              -- canonical 名
  name_zh         text,
  aliases         jsonb,             -- 归一并入的别名（含各书变体）
  level           text,              -- concrete/abstract
  discipline      text,              -- 学科（硬隔离用）
  -- ★判别维度（AII-CONCEPT-IDENTITY-001 判同用）
  discriminative  jsonb,             -- ★判别维度取值: {弹性对象: price, 测量法: arc...}
  embedding       vector(1024),      -- B 仓独立概念向量
  invariant_id    bigint,            -- FK → invariant（本性，可空）
  sources         jsonb,             -- 这个概念出现在哪些书
  created_at / updated_at timestamptz
);
```
- **discriminative**：判同升级的核心——存概念的判别维度取值，判同时逐维度比（price≠income → 不合并）。

### 2.3 ③ 主题 KC（refined_theme_kc，谱社区，跨书）
```sql
-- 主题簇（谱社区）
CREATE TABLE rf.refined_theme_kc (
  kc_id           bigserial PRIMARY KEY,
  theme_name      text,              -- 主题名（中文）
  theme_name_en   text,
  summary         text,              -- 簇摘要（双语）
  summary_zh      text,
  embedding       vector(1024),
  source_books    jsonb,             -- ★这个主题跨哪些书（成员标来源书）
  created_at / updated_at timestamptz
);
-- 主题 KC ↔ KU 成员（跨书）
CREATE TABLE rf.refined_kc_member (
  kc_id           bigint REFERENCES rf.refined_theme_kc(kc_id),
  ku_id           text REFERENCES rf.refined_ku(ku_id),
  PRIMARY KEY (kc_id, ku_id)
);
```
- **只有主题 KC**（谱社区），无按章 KC（按章在 A 库）。成员是去重 KU，跨书，标来源书。
- 谱社区天然聚同主题 KU → 帮 concept canonical（提供同概念 KU 线索）。

### 2.4 KU ↔ 概念（refined_ku_concept，超图 incidence）
```sql
CREATE TABLE rf.refined_ku_concept (
  ku_id       text REFERENCES rf.refined_ku(ku_id),
  concept_id  bigint REFERENCES rf.refined_concept(concept_id),
  PRIMARY KEY (ku_id, concept_id)
);
```
- 一个 KU 连它涉及的多个概念 = HyperGraphRAG 式隐式超边（无向，共现/聚类用）。

### 2.5 ④ 第①层 有向关系（refined_directed_edge，概念→概念）
```sql
CREATE TABLE rf.refined_directed_edge (
  edge_id       bigserial PRIMARY KEY,
  src_concept   bigint REFERENCES rf.refined_concept(concept_id),
  dst_concept   bigint REFERENCES rf.refined_concept(concept_id),
  relation_type text,              -- derives/subsumes/prerequisite
  grade         text DEFAULT 'unverified',
  evidence      jsonb,
  created_at timestamptz
);
```
- 概念骨架。**也供判同关2（类层级/互斥）用**：subsumes/derives 判上下位（不合并子概念）。

### 2.6 ⑤ 第②层 有向超边（refined_hyperedge + member）
```sql
-- 有向超边（机制 → 被解释概念集合）
CREATE TABLE rf.refined_hyperedge (
  hyperedge_id    bigserial PRIMARY KEY,
  relation_type   text DEFAULT 'explains',     -- 受控，现 explains
  head_ku_id      text REFERENCES rf.refined_ku(ku_id),   -- 解释者: rationale KU
  nl_description  text,                         -- 机制 NL 描述（向量检索用）
  embedding       vector(1024),                 -- nl_description 向量（hyperedge_vdb）
  grade           text DEFAULT 'unverified',
  evidence        jsonb,
  created_at / updated_at timestamptz
);
-- 超边成员（被解释概念集，动态生长改这张）
CREATE TABLE rf.refined_hyperedge_member (
  hyperedge_id  bigint REFERENCES rf.refined_hyperedge(hyperedge_id),
  concept_id    bigint REFERENCES rf.refined_concept(concept_id),
  source_ku_id  text,
  status        text DEFAULT 'confirmed',       -- confirmed/candidate（宁缺毋附会）
  evidence      jsonb,
  cross_disc    boolean DEFAULT false,          -- 跨学科（尤其严，先 candidate）
  added_at timestamptz,
  PRIMARY KEY (hyperedge_id, concept_id)
);
```
- M1 抽取落超边、M2 动态生长。对齐 AII-HYPEREDGE-EXPLAINS-001（含 status/evidence/cross_disc）。

### 2.7 ★第③层 跨域关系（refined_cross_domain_relation，预留）★SME 式⟨M,C,S⟩
> motif 挖掘/结构映射推出的"跨域结构对应"。按结构映射引擎（SME，四十年验证）标准输出结构 ⟨M 对应, C 候选推断, S 结构分⟩。**这是"关系"层（base↔target 对应），≠ 本性（共享内核）。**
```sql
CREATE TABLE rf.refined_cross_domain_relation (
  relation_id          bigserial PRIMARY KEY,
  description          text,              -- 这个跨域关系是什么（如"水流与热流共享 flow 结构"）
  source               text,              -- 来源：motif 挖掘 / 结构映射(SME)
  -- ★M: correspondences（对应）——SME 核心，跨域关系的本体
  base_domain          text,              -- base 域（如水流）
  target_domain        text,              -- target 域（如热流/电流）
  correspondences      jsonb,             -- ★对应关系：[{base:水压, target:电压}, {base:流量, target:电流}...]
  member_concept_ids   jsonb,             -- 涉及的跨域概念
  member_disciplines   jsonb,             -- 跨哪些学科
  shared_structure     text,             -- 共享的高阶关系结构（flow；motif 的高阶结构）
  -- ★C: candidate inferences（候选推断）——SME 四十年就有，= AII candidate 池
  candidate_inferences jsonb,             -- 从对应能推出的候选推断
  -- ★S: structural score（结构评估分）
  structure_score      real,              -- 这个跨域关系的结构质量分（多强）
  embedding            vector(1024),      -- 向量
  -- ★→第④层本性
  invariant_id         bigint,            -- 若提炼出共享内核（升第④层）指向 invariant；提炼不出留 NULL（停在第③层关系）
  status               text DEFAULT 'candidate',
  created_at / updated_at timestamptz
);
```
- **⟨M,C,S⟩ 对齐 SME**：M=correspondences（base↔target 对应）、C=candidate_inferences（候选推断）、S=structure_score（结构分）。
- **invariant_id = NULL → 停在第③层（是跨域关系，不是本性）**；指向 invariant → 已升华第④层。**宁停在关系不附会。**
- motif 层（走结构统计）的产物落这张表；与第④层本性向量收敛层互证（见 AII-INVARIANT-LAYER-001 §五）。

### 2.8 ⑥ 第④层 本性（refined_invariant，预留）★按 AII-INVARIANT-LAYER-001
> 术语锁定：本性=invariant、本性概念=invariant concept（**不独立建表**，is_invariant_concept 字段）、本性同一=invariant-identity。本性概念**不是独立表**，是 invariant 表里 is_invariant_concept=true 的本性。**本性=从第③层跨域关系提炼出的共享抽象内核，稍高一层。**
```sql
CREATE TABLE rf.refined_invariant (
  invariant_id          bigserial PRIMARY KEY,
  statement             text,              -- 本性是什么（道非相，如"无外力则只增、不可逆、有方向"）
  invariant_vector      vector(1024),      -- ★本性向量，带统一标记（固定维度=本性；同一本性向同一处收敛）
  is_invariant_concept  boolean DEFAULT false,  -- ★false=普通本性 / true=升华为本性概念（不独立建表！）
  member_concept_ids    jsonb,             -- 共有此本性的概念们（≥2 → 可升华 true）
  status                text DEFAULT 'candidate',  -- 本性默认 candidate，确证才认定
  created_at / updated_at timestamptz
);
-- 概念→本性：concept.invariant_id 指向（已在 refined_concept，可空；抽不出留 NULL）
-- 第③层跨域关系→本性：cross_domain_relation.invariant_id 指向（提炼出共享内核才连）
-- ★本性概念不独立建表：WHERE is_invariant_concept=true 即本性概念
-- ★升华判据：多概念 invariant_vector 收敛到同一条 invariant 且 ≥2 概念共有 → is_invariant_concept=true
```
**两层独立 + 互证（见 AII-INVARIANT-LAYER-001 §五）：**
- 层一 本性向量收敛（走语义，第④层）：概念抽本性→invariant_vector→收敛→升华。
- 层二 motif 结构（走拓扑，第③层）：超边二部图 motif 挖掘→跨域反复结构（落 refined_cross_domain_relation）。
- 两层独立运行、各保留信息、互相印证：都指同一本性→高置信；只一层→存疑（防附会）。
- **关系≠本性**：第③层 motif 出的先是跨域关系，提炼共享内核才升第④层 invariant，宁停在关系不附会。
- M3 motif 挖掘填。**只用 confirmed 超边成员**。预留表结构，建库到位，M3 才填。

### 2.8 ⑧ 出处追溯（已在各表 sources 字段 + raw 链接）
- refined_ku.sources / refined_concept.sources / refined_theme_kc.source_books：记录来自原始仓哪些书。
- 可选 refined_to_raw 映射表（refined_ku_id → raw_ku_id 列表），强追溯。

---

## 三、与原始仓(A库)的对照

| 维度 | A 库（aii_raw，原始仓） | B 仓（aii_refined，精炼仓） |
|---|---|---|
| KU | 原始 KU（**有重复**） | 去重 KU（**无重复**，标多出处） |
| KC | **按章 KC**（书原貌，读这本书） | **只主题 KC**（谱社区，跨书有机体） |
| 概念 | 裸概念名 | **canonical 概念**（归一，判别维度） |
| 有向关系 | — | 第①层 directed_edge |
| 超边 | — | 第②层 hyperedge（M1/M2） |
| 跨域关系 | — | 第③层 cross_domain_relation（M3） |
| 本性 | — | 第④层 invariant（M3，is_invariant_concept 字段） |
| 向量 | A 自己的 | **B 独立向量空间** |
| 职责 | 忠实记录每本书（含章节） | 跨书知识有机体 |

- **A 库保留书原貌**（按章 KC = 这本书的结构）；**B 仓是跨书主题有机体**（章在跨书后无意义，只主题）。
- 单向流：A → 去重 → B。B 可追溯到 A（sources）。

---

## 四、建库步骤（CC 执行）

```
1. 建独立数据库 aii_refined（独立 PG 库，与 aii_raw 隔离）
2. 建 schema rf + 上述表（KU/概念/主题KC/KC成员/KU概念/有向边/超边/超边成员/跨域关系/本性invariant）
   + 向量索引（pgvector，各 embedding 列）
   + 外键约束（超边连概念、概念→本性 invariant_id、KC 连 KU）
3. 空库（不灌数据）——等去重机制把原始仓 KU 去重后灌入
4. 验证：9 张表建好、外键对、向量索引在、空库
```

### 完备性自检（建库时）
- 四层表全在否（有向边/超边/跨域关系/本性）——预留到位，不遗漏关联。
- 出处字段全在否（refined_ku/concept/theme_kc 的 sources）。
- 只主题 KC、无按章 KC 否（按章在 A 库）。
- 独立向量空间否（B 仓自己的 embedding 列 + 索引）。

---

## 五、★实证完备性补全（对照前沿，补 3 个真缺口，不过度设计）

> 本节是对 §二 schema 的**实证完备性检验结果**。对照 HyperGraphRAG（二部图/双向量/超边 confidence）、Hyper-RAG、生产 KG 最佳实践（provenance/confidence/human-in-loop）。结论：大部分对齐，3 个真缺口克制补全。

### 6.0 实证确认对齐前沿的部分（已完备，不动）
| 前沿做法 | B 仓 schema | 状态 |
|---|---|---|
| 二部图存储超图（数学证明无损） | hyperedge + hyperedge_member | ✅ 一致 |
| 双向量库（实体/超边各自，同空间） | 各表独立 embedding 列（BGE-M3 同空间） | ✅ 一致 |
| 超边带 NL 描述 + confidence | nl_description + grade | ✅ 一致 |
| confidence 分级 + human-in-loop | confirmed/candidate + 人工确认 | ✅ 更结构化 |
| provenance（记来源，头号要求） | sources 字段 | ✅ 方向对，§6.3 增强 |

### 6.1 缺口① 原文 chunk 检索融合（CR）— 主要是 M1 检索逻辑，schema 仅确认可回查
- **前沿**：HyperGraphRAG 消融证明 Chunk Retrieval Fusion（超图结构 + 原文 chunk 融合）重要，去掉 F1 下降。光有结构（概念/超边）不够，检索要能取原文 chunk（结构给骨架、chunk 给细节原文）。
- **AII 特殊性**：结构在 B 仓（去重 KU/超边/概念），原文 chunk 在 A 仓（原始 KU/书源）。**不在 B 仓建 chunk 表**（违背"B 仓只放精炼"）。
- **克制补法**：
  - **schema 层**：确认 `refined_ku.sources` 的 `raw_ku_id` 能回查 A 仓原文（已有，无需加字段）。可选 `refined_to_raw` 强追溯映射表（仅当 sources jsonb 回查不够时才建）。
  - **逻辑层（M1 检索时实现）**：B 仓超图命中 → 经 raw_ku_id 到 A 仓取原文 chunk → 融合。**这是检索逻辑（M1 做），不是 schema 缺字段。**
- **结论**：schema 不加表/字段（sources 已支持回查），缺口主体在 M1 检索逻辑。**记入 M1 实现要求。**

### 6.2 缺口② 边/成员强度（relationship strength）— 加字段，不建表
- **前沿**：关系应 capture relationship strength；因果连接要区分 genuine causal vs correlation 的强度。
- **AII 缺**：超边成员只有 status（confirmed/candidate）、grade（verified 与否），**没有"这个机制解释这个概念有多核心/多强"**（可替代性对需求弹性=核心解释，对边缘概念=次要）。
- **克制补法**（加字段，不建表）：
  ```sql
  -- refined_hyperedge_member 加：
  strength  real,   -- 解释强度 0-1（这个机制对这个概念的解释有多核心）
  -- refined_directed_edge 加：
  strength  real,   -- 关系强度
  ```
- 强度由抽取/读出时 LLM 估或频次推（核心机制反复解释→强）。**一个字段，不建表。**

### 6.3 缺口③ 来源版本/抽取批次（version）— 进 sources jsonb，不建表
- **前沿**：VersionRAG 等强调 version-aware（文档会更新）。
- **AII 适用性**：教科书知识"facts 过时"**不适用**（导数定义不过时）。但**"书重新抽取"适用**——Stratum 重出 MD、同书重抽（M0 前就遇 58 本等重出），重出后新旧怎么对齐需要 version。
- **克制补法**（sources jsonb 加 key，不建表）：
  ```
  sources: [{ book_id, version, extract_batch, chapter, raw_ku_id, contributed }]
                        ↑新增      ↑新增
  ```
  - version：书的版本（教材第几版/MD 重出版本）。
  - extract_batch：哪次抽取批次（同书重抽区分）。
- **不建表**（jsonb 内加 key）。

### 6.4 ★明确不加的（前沿有，AII 不需要——避免 over-engineering）
> 前沿两处独立警告"过度设计 schema：建模每个细微差别 → 难维护难查询"。以下前沿有但 AII 不加：
- **temporal knowledge graph（时序图，"某日期为真"/facts 随时间变）**：AII 是教科书知识，不会"上季度为真这季度过时"。**不加**（加了就是 over-engineering）。
- **bi-temporal versioning（双时间版本，事务时间+有效时间）**：AII 知识无"有效时间"维度。**不加。**
- **完整审计日志表 / 访问控制表**：AII 自用、单用户，不需要企业级访问控制/审计。**不加。**
- **关系的时间属性（relation 何时成立到何时）**：数学/经济原理无时效。**不加。**

> **克制原则**：3 个真缺口都不建表（strength 加字段、version 进 jsonb、chunk 融合是 M1 逻辑）。前沿的 temporal/版本图/审计等 AII 不需要的一律不加。**完备 = 该有的有 + 不该有的不堆。**

---

## 六、命门

1. **B 仓无重复**：从 0 空库建，去重机制灌入——保证 B 仓从一开始无重复（canonical/超边/本性在干净数据上）。
2. **四层表一次预留完备**：建库到位，上层（M1 超边/M3 跨域关系/本性）建于其上不改 schema。预留 ≠ 立即填。
3. **出处可追溯**：每个去重 KU 标多出处（sources），追溯到原始仓证据 + 记录"越读越厚"（哪书贡献什么内容）。
4. **A/B 职责纯粹**：A=书原貌（按章 KC），B=跨书有机体（主题 KC）。不混。
5. **实证完备且不臃肿**：对齐前沿（二部图/双向量/分级/出处）、补 3 个真缺口（chunk 融合/边强度/版本，都不建表）、不加 AII 不需要的（temporal/版本图/审计）。完备 = 该有的有 + 不该有的不堆。

---

> **一句话**：B 仓（精炼仓 aii_refined）是跨书知识有机体，一次设计完备——去重 KU（沿用 ku_onto + 出处）、canonical 概念（判别维度）、只主题 KC（谱社区）、四层（有向关系/超边/跨域关系/本性，预留到位）、独立向量、出处追溯。从 0 空库建，原始仓 KU 经去重灌入。**B 仓 schema 完备了，canonical/超边/跨域关系/本性才有干净完整的地基长上去。**

---

*依据：用户决策（B 仓独立库/沿用 ku_onto+出处/只主题 KC/从 0 建/去重灌入）+ AII-TWO-REPO-ARCH-001（双仓）+ AII-CONCEPT-IDENTITY-001（判别维度）+ AII-HYPEREDGE-EXPLAINS-001（超边 status/evidence/cross_disc）+ AII-KNOWLEDGE-ADVANCED-IMPL-001（三层）。片段去重判定另文 AII-KU-DEDUP-001。*
