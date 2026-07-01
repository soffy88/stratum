# AII B仓（精炼仓）完备设计

> **Doc ID:** AII-REFINED-REPO-MASTER-001
> **这是什么:** B 仓（精炼仓 aii_refined）的**单一完备设计文档**。把双仓架构、四层结构、B 仓 schema、KU 去重、概念判同、本性层合为一份。新窗口/CC 读这一份即可建 B 仓，不用在多份文档间跳。
> **角色:** 负责人是 AII 专属经理人，对 B 仓成败负责，有反驳义务。三原则：长期主义、质量为王、功能至上。**唯一尺子：真知识（不编）、真联结（不附会）、真本性（宁标未发现）。看裸真相，不让"看起来对"冒充"真的对"。**
> **协作:** WSL2 代码归 CC（经理人环境连不上 CC 的 WSL/docker，让 CC 查实物贴出来）。经理人用 ask_user_input 征求 Wiki 决策。每批 commit 必 push（VHDX 教训）。Wiki 中文、技术不懂、要经理人实证决定、输出简洁。

---

# 第一部分 · 双仓架构（为什么有 B 仓）

## 1.1 两个独立数据库，互不污染

- **A 仓（原始仓 aii_kg，已有，运行中）= 给人读的数字化记录**：全、不漏、中文、按书+按章 KC+BU。忠实记录每本书抽出的原始 KU（**有重复**）。
- **B 仓（精炼仓 aii_refined，待建）= 给机器深加工的知识有机体**：去重、英文统一、只主题 KC、纯知识。concept canonical、超边、跨域关系、本性都长在 B 仓。**不存单本书任何数据**（BU/按章 KC 都在 A 仓）。

## 1.2 为什么不能一个库混着
```
原始 KU（有重复）和归一/超边/本性在同一库 →
  ① canonical 污染：同概念 5 份重复 KU，归一处理 5 份噪声
  ② 超边污染：explains 超边连到哪份重复 KU？歧义
  ③ 本性污染：motif 挖掘在有重复 KU 的图上跑，重复制造虚假"反复出现"，把噪声当 motif
  ④ 向量污染：重复 KU 向量挤一起，影响相似度
```
两仓独立 → B 仓的归一/超边/本性永远在干净（无重复）数据上；A 仓的重复噪声进不了 B 仓的图。

## 1.3 单向流 A→B + 可追溯
```
A 仓（抽取，有重复 KU，中文）
  → 去重整合（相同丢/不同补/标出处，翻译英文）
  → B 仓（无重复，英文，主题 KC 组织）
B 仓每个 KU 经 sources 回查 A 仓证据（可追溯）。A 仓保留原貌，B 仓不回写。
```

## 1.4 A/B 职责对照
| 维度 | A 仓（aii_kg） | B 仓（aii_refined） |
|---|---|---|
| KU | 原始（**有重复**，中文） | 去重（**无重复**，英文，标多出处） |
| KC | **按章 KC**（书原貌，读这本书） | **只主题 KC**（谱社区，跨书有机体） |
| 概念 | 裸概念名 | **canonical 概念**（归一，判别维度） |
| 高级层 | — | 四层：有向关系/超边/跨域关系/本性 |
| 向量 | A 自己的 | **B 独立向量空间** |
| BU | 有（给人读这本书） | 无（不存单本数据） |
| 职责 | 忠实记录每本书 | 跨书知识有机体 |

---

# 第二部分 · 四层架构（B 仓的核心）

```
第①层 有向关系  directed_edge（concept→concept：derives/subsumes/prerequisite）
第②层 有向超边  hyperedge + member（机制→被解释概念集，explains，n元，动态生长）
第③层 跨域关系  cross_domain_relation（motif/结构映射出的 base↔target 对应，SME 式⟨M,C,S⟩）
第④层 本性      invariant（从第③层提炼共享内核，is_invariant_concept 字段标记升华）
```

**生长链**：有向关系给概念骨架 → 超边在骨架上生长跨学科机制网 → motif/结构映射在机制网发现跨域关系（第③层）→ 跨域关系提炼共享内核升为本性（第④层）。越往上越是 AII 独有。

**★第③层"关系" ≠ 第④层"本性"（最易犯错处）**：
- 第③层跨域关系 = "水流↔电流"的对应（它们像）——是**关系**。
- 第④层本性 = "势差驱动流"的共享内核（像在哪）——是**本性**。
- 提炼出内核才从③升④（cross_domain_relation.invariant_id 指向 invariant）；提炼不出停在第③层（invariant_id=NULL）。**宁停在关系不附会。**

**前沿实证支撑（不靠内部自洽）**：
- n元超边不拆二元 = 前沿共识（Freebase 61% 关系 n元，拆二元有损）+ 信息论。
- 有向超边 = direction-aware hypergraph 专门研究印证（无向超边缺因果方向）。
- 第③层跨域关系 = 结构映射引擎 SME 四十年标准⟨M 对应, C 候选推断, S 结构分⟩。
- 第④层本性 = 结构映射理论的 schema abstraction（从映射涌现的共同结构/不变量）+ 超图 motif 挖掘。

---

# 第三部分 · ★术语锁定（不再混用，违反即错）

| 中文 | 英文 | 锚定 |
|---|---|---|
| 本性 | **invariant** | 拓扑不变量语义（**不是 nature**；nature=性质/特征=相） |
| 本性概念 | **invariant concept** | 多概念共有的本性升华（**不独立建表**，is_invariant_concept 字段 false/true） |
| 本性同一 | **invariant-identity** | identity=同一（**非 equivalence 等价/similarity 相似**；旧称"本性同源/invariant-shared"作废） |

> 本性 = invariant，是"一切相之下的不变内核"。熵的本性="只增、不可逆、有方向"，**不是**"无序度量"（那是相）。nature 表达不了"穿透一切相不变的内核"。
> **旧文档（AII-GLOSSARY-001 等）仍用"本性同源/invariant-shared"——以本文 invariant-identity 为准。**

---

# 第四部分 · B 仓完备 Schema（建库依据）

> 独立数据库 aii_refined，schema rf。从 0 空库建（不灌数据），四层表一次预留完备（后加易遗漏外键关联）。已实证完备性（见 §4.9）。

> **★CC 建造注（2026-06-30，经理人已拍板）**：下面 §4.1 的 `refined_ku` 用了**示意列名**（ku_type/point/facets）——这是写 schema 时未核实真实 `aii.ku_onto` 列名的示意，**非权威**。已建库**采纳 CC 镜像版**（按文档原则"沿用 ku_onto 结构"镜像真实 ku_onto 知识承载列 + B仓出处字段；按 §4.9 砍 A仓时序列 valid_from/valid_until/superseded_by 与 substrate_id，B仓改用 sources 回查）。**真实建库 DDL 以 `~/projects/stratum/aii/migrations/refined/0001_refined_repo_schema.sql` 为准，未来窗口勿照本节示意列名重建。** §4.2–4.8 表已与建库一致（仅 §4.1 是示意）。

## 4.1 去重 KU（refined_ku，沿用 ku_onto + 出处）
```sql
CREATE TABLE rf.refined_ku (
  ku_id           text PRIMARY KEY,
  ku_type         text,              -- 六类: conceptual/rationale/procedural/positional/factual/metacognitive
  point           text,              -- 知识点名
  natural_text    text,              -- 讲透正文（英文）
  facets          jsonb,             -- 该类型的面（WHAT/WHY/HOW）
  embedding       vector(1024),      -- B 仓独立向量（BGE-M3）
  sources         jsonb,             -- ★多出处: [{book_id, version, extract_batch, chapter, raw_ku_id, contributed}]
  is_fragmented   boolean DEFAULT false,
  created_at timestamptz, updated_at timestamptz
);
```
- **sources 是 B 仓关键**：内容来自哪些书的哪些 KU，每出处贡献什么内容（追溯 + "越读越厚"）。
- 例：导数定义 KU 的 sources = [{数分: ε-δ严格定义}, {同济: 应用导向定义}]——不同侧面并存。

## 4.2 canonical 概念（refined_concept，归一 + 判别维度）
```sql
CREATE TABLE rf.refined_concept (
  concept_id      bigserial PRIMARY KEY,
  name            text, name_zh text,
  aliases         jsonb,             -- 归一并入的别名
  level           text,              -- concrete/abstract
  discipline      text,              -- 学科（硬隔离用）
  discriminative  jsonb,             -- ★判别维度取值: {弹性对象: price, 测量法: arc}
  embedding       vector(1024),      -- B 仓独立概念向量（带 concept 标记）
  invariant_id    bigint,            -- FK → invariant（该概念的本性，可空；抽不出留 NULL）
  sources         jsonb,
  created_at timestamptz, updated_at timestamptz
);
```

## 4.3 主题 KC（refined_theme_kc + member，谱社区，跨书）
```sql
CREATE TABLE rf.refined_theme_kc (
  kc_id bigserial PRIMARY KEY,
  theme_name text, theme_name_en text,
  summary text, embedding vector(1024),
  source_books jsonb,                -- 跨哪些书
  created_at timestamptz, updated_at timestamptz
);
CREATE TABLE rf.refined_kc_member (
  kc_id bigint REFERENCES rf.refined_theme_kc(kc_id),
  ku_id text REFERENCES rf.refined_ku(ku_id),
  PRIMARY KEY (kc_id, ku_id)
);
```
- **只主题 KC**（按章 KC 在 A 仓）。谱社区天然聚同主题 KU → 帮 concept canonical。

## 4.4 KU↔概念（refined_ku_concept，隐式超边）
```sql
CREATE TABLE rf.refined_ku_concept (
  ku_id text REFERENCES rf.refined_ku(ku_id),
  concept_id bigint REFERENCES rf.refined_concept(concept_id),
  PRIMARY KEY (ku_id, concept_id)
);
```

## 4.5 第①层 有向关系（refined_directed_edge）
```sql
CREATE TABLE rf.refined_directed_edge (
  edge_id bigserial PRIMARY KEY,
  src_concept bigint REFERENCES rf.refined_concept(concept_id),
  dst_concept bigint REFERENCES rf.refined_concept(concept_id),
  relation_type text,                -- derives/subsumes/prerequisite
  strength real,                     -- ★关系强度
  grade text DEFAULT 'unverified',
  evidence jsonb, created_at timestamptz
);
```
- 概念骨架。**也供判同关2（类层级/互斥）判上下位**。

## 4.6 第②层 有向超边（refined_hyperedge + member）
```sql
CREATE TABLE rf.refined_hyperedge (
  hyperedge_id bigserial PRIMARY KEY,
  relation_type text DEFAULT 'explains',  -- 受控
  head_ku_id text REFERENCES rf.refined_ku(ku_id),   -- 解释者: rationale KU
  nl_description text,               -- 机制 NL 描述（向量检索用）
  embedding vector(1024),            -- nl_description 向量（hyperedge_vdb）
  grade text DEFAULT 'unverified', evidence jsonb,
  created_at timestamptz, updated_at timestamptz
);
CREATE TABLE rf.refined_hyperedge_member (
  hyperedge_id bigint REFERENCES rf.refined_hyperedge(hyperedge_id),
  concept_id bigint REFERENCES rf.refined_concept(concept_id),
  source_ku_id text,
  status text DEFAULT 'confirmed',   -- confirmed/candidate（宁缺毋附会）
  strength real,                     -- ★解释强度（这机制对这概念多核心）
  evidence jsonb,
  cross_disc boolean DEFAULT false,  -- 跨学科（尤其严，先 candidate）
  added_at timestamptz,
  PRIMARY KEY (hyperedge_id, concept_id)
);
```

## 4.7 ★第③层 跨域关系（refined_cross_domain_relation，SME 式⟨M,C,S⟩）
```sql
CREATE TABLE rf.refined_cross_domain_relation (
  relation_id bigserial PRIMARY KEY,
  description text,                  -- 这个跨域关系是什么
  source text,                       -- motif 挖掘 / 结构映射(SME)
  -- M: correspondences（对应）——SME 核心
  base_domain text, target_domain text,
  correspondences jsonb,             -- [{base:水压, target:电压}, {base:流量, target:电流}]
  member_concept_ids jsonb, member_disciplines jsonb,
  shared_structure text,             -- 共享高阶结构（flow）
  -- C: candidate inferences（候选推断）= AII candidate 池
  candidate_inferences jsonb,
  -- S: structural score（结构分）
  structure_score real,
  embedding vector(1024),
  invariant_id bigint,               -- 提炼出内核→指 invariant；提炼不出留 NULL（停在关系）
  status text DEFAULT 'candidate',
  created_at timestamptz, updated_at timestamptz
);
```
- **invariant_id = NULL → 停在第③层（是跨域关系，不是本性）；指向 invariant → 已升第④层。宁停在关系不附会。**

## 4.8 第④层 本性（refined_invariant，本性概念是字段标记不独立建表）
```sql
CREATE TABLE rf.refined_invariant (
  invariant_id bigserial PRIMARY KEY,
  statement text,                    -- 本性是什么（道非相，如"无外力则只增、不可逆、有方向"）
  invariant_vector vector(1024),     -- ★本性向量，带统一标记（同一本性向同一处收敛）
  is_invariant_concept boolean DEFAULT false,  -- ★false=普通本性 / true=升华为本性概念（不独立建表！）
  member_concept_ids jsonb,          -- 共有此本性的概念（≥2 → 可升华 true）
  status text DEFAULT 'candidate',   -- 本性默认 candidate，确证才认定
  created_at timestamptz, updated_at timestamptz
);
-- 概念→本性：concept.invariant_id 指向
-- 第③层→本性：cross_domain_relation.invariant_id 指向
-- 本性概念 = WHERE is_invariant_concept=true（不独立建表）
-- 升华判据：多概念 invariant_vector 收敛到同一 invariant 且 ≥2 概念共有 → is_invariant_concept=true
```

## 4.9 实证完备性（对照前沿，可复核）
- **已对齐**：二部图存储/双向量库（HyperGraphRAG）、confidence 分级（confirmed/candidate）、provenance（sources）。
- **补的 3 真缺口**（都不建表）：① 原文 chunk 检索融合 CR（主要是 M1 检索逻辑 + sources 回查 A 仓原文）② 边/成员 strength 字段 ③ 来源 version 进 sources jsonb。
- **砍的过度设计**（AII 不需要）：temporal 时序图/bi-temporal 版本/审计表——教科书知识不过时。
- **★新窗口应自行复核这三点**（看裸真相，别信"已实证"三字）。

## 4.10 向量统一标记机制
- 概念/本性/KU 向量各带类型标记（本性用固定维度标识）。**方案 A（推荐）：检索时先按标记维硬分组**（概念 vs 概念、本性 vs 本性内部比相似度），标记维不参与相似度。同一本性无论从哪抽到都向同一处收敛 → 共享即被发现，不靠 N² 逐对判断。

---

# 第五部分 · KU 去重机制（A 仓 → B 仓入口工序）

> B 仓"自然生长"的入口。每本书 KU 进来和已有整合，B 仓越来越厚。去重错（误删/错并）→ 上层全错。

## 5.1 完整流程（6 步）
```
A 仓 KU（中文，有重复）
  ① 翻译英文（B 仓语言统一；副作用好：机会成本→Opportunity Cost，和另一本同名）
  ② KU 判同先行（用 KU 名+内容判"是不是同一个点"，真正同一判据，不强依赖概念已归一）
  ③ 同点内容整合（相同丢/不同补/标出处，★宁冗余不误删）
  ④ 存 B 仓 KU（英文，无重复，内容多书整合）
  ⑤ 概念归一（在去重 KU 上做 canonical，见第六部分）
  ⑥ 谱社区 KC（按概念聚类）
B 仓 KU/KC 自然生长（新书来→重复→越来越厚/全）
```

## 5.2 ★核心难点：内容整合"判相同不误删"
- **误删（判太松）**：数分 ε-δ 严格定义 vs 同济应用定义，都是"导数定义"但内容不同（一严格一应用）。判"相同"删一个 → 丢"越读越厚"。
- **判定**：切成内容片段逐个判，**LLM 判"相同"才丢（门槛高，确信讲同一个事才丢），拿不准→保留（不丢）**。
- **权衡**：误删=不可逆丢知识；冗余=可逆（以后能再合）。**误删 >> 冗余 危害 → 宁严勿松，拿不准当"不同"保留。**

## 5.3 翻译注意（命门：不失真）
- 忠实翻译（换语言非重新表述，不增不减不曲解）+ 术语准（经济/数学标准英文）。术语翻错→后面全错。可用 gemma/本地（0 成本），但术语校验。

## 5.4 两层判同的关系（破循环）
| | KU 判同（步骤2） | 概念归一（步骤5） |
|---|---|---|
| 判什么 | 两 KU 是不是讲同一个点 | 两概念是不是同一概念 |
| 依据 | KU 名 + 内容 | 概念名 + 判别维度 + 上下位 |
| 时机 | 先行（去重前） | 去重后（干净 KU 上） |
- **同一套"真正同一"判据，两层面分时做**。KU 判同用自己名+内容，不必等概念归一——破"去重依赖归一、归一依赖去重"的循环。

---

# 第六部分 · 概念判同升级"真正同一才合一"（M0 用）

> 升级判同逻辑：从"相似度判断"到"本体级同一性判定"。触发：全局归一破坏性测试暴露真错合（price-inelastic ← income-inelastic 类冲突）。前沿：错合是实体对齐头号问题，42-55% 是类冲突（OntoEA）；LLM 倾向"强行匹配"需本体兜底。

## 6.1 "真正同一"定义（正向，非堵漏）
两概念 A、B 真正同一 ⟺ 全部满足：
```
① 判别维度全对齐（每个关键维度取值相同，非名字像）
② 非上下位（A 不是 B 的子类/特化）
③ 非互斥（不是并列的不同类）
④ 核心结构相同（关系结构同，非表面）
缺任一 → 不同概念 → 不合并（宁碎片不错合）
```

## 6.2 四道关（逐层收紧）
```
候选对（向量粗筛：同 discipline 余弦≥阈值）
  关1 判别维度对齐（程序，PARIS 式）：抽判别维度取值，任一本质维度不同→DIFFERENT
       price-inelastic{弹性对象:price} vs income-inelastic{弹性对象:income} → DIFFERENT ✓
       ★本质维度（弹性对象）不同→挡；表述维度（arc/point 测量法）不同→放行进 LLM
  关2 类层级/互斥（用第①层 directed_edge，OntoEA 式）：A subsumes/derives B → 上下位不合并
       increasing opportunity cost derives 机会成本 → 不合并 ✓
  关3 LLM 判语义（前两关后的窄候选）：反义/方向反/不确定 → DIFFERENT
  关4 高风险 → candidate（跨学科/LLM 置信不足 → 不自动合）
```

## 6.3 命门
- **错合 = 地基污染**（上层超边/本性全错，难发现）；碎片可恢复。→ 阈值宁严勿松，拿不准→碎片不→错合。
- **dry_run 强制**：全局归一先 dry_run（算+打印不落库），人工/抽查无错合再真合（杜绝破坏性测试落库错合）。

---

# 第七部分 · 本性层完整设计（第④层，Wiki 已通过）

## 7.1 本性是道，非相
- 相：能观测/描述/测量的样子（量、公式）。本性（invariant）：内在规律/必然趋势（必然怎么动/往哪去），穿透一切相不变。
- 熵：相="无序度量/S=klnW"；**本性="无外力则只增、不可逆、有方向"**（拓扑不变量语义）。

## 7.2 本性 ≠ 本性概念
- 单个概念的本性（熵的本性）= 概念属性。
- 本性概念 = 多个概念**共有**的本性凝结（涌现，非预设；is_invariant_concept=true）。

## 7.3 ★关系 ≠ 本性（防附会）
- 跨域关系（第③层，水流↔电流对应）≠ 本性（第④层，势差驱动流内核）。
- motif/映射出的先是跨域关系，提炼出共享内核才升本性。**提炼不出停在关系（宁停在关系不附会）**。

## 7.4 两条路径
- 路径 A（自下而上）：超边生长→motif→第③层跨域关系→提炼内核→第④层本性。
- 路径 B（自上而下）：核心抽象概念（熵/均衡）本身就是 schema→直接抽本性（前沿：abstraction，"原子是中心力系统"概念本身即 schema）。

## 7.5 ★两层独立 + 互证
- **层一 本性向量收敛（第④层，走语义）**：概念抽本性→invariant_vector→收敛→升华。
- **层二 motif 结构（第③层，走拓扑）**：超边二部图 motif 挖掘→跨域关系。
- **两层独立运行、各保留信息、互相印证**：都指同一本性→高置信；只一层→存疑（双重验证防附会）。

## 7.6 三种连接（绝不互相冒充）
| 连接 | 英文 | 强度 | 媒介 |
|---|---|---|---|
| 边 | edge | 局部强 | explains/causes |
| 概念共指 | — | 弱 | 同一概念 |
| **本性同一** | **invariant-identity** | **最深** | 同一本性 |
- 本性同一连接"名字不同、学科不搭但本质同构"的概念（经济均衡↔生态稳态）。边/共指是关系，本性同一是本性。

## 7.7 本性提取判据（最严）
≥3 跨学科 + 形式各异内核同 + 两层互证 + 全 confirmed 支撑 + **抽不出留 NULL（宁标"未发现"不硬凑）**。本性默认 candidate，确证才认定。

## 7.8 诚实边界
- 本性层是 AII 最前沿、最独有、最未验证的部分。大规模真实语料本性自动提取前沿无人完整做过。**最后做、最审慎、最依赖前三层干净积累。** 初期产候选本性供人工审，不自动认定。

---

# 第八部分 · ★实施顺序（严格按依赖，不可逆序）

```
步骤1 建 B 仓（独立 PG 库 aii_refined）+ 四层完备 schema（空库，纯 DDL，风险小）
步骤2 KU 去重机制（A→B，片段级，宁冗余不误删）
步骤3 现有 A 仓 KU 去重灌入 B 仓（首批：经济/数学书）
步骤4 M0 concept canonical（在 B 仓去重 KU 上做，四道关判同）
       ★M0 之前在 A 仓跑过 dry-run，位置错已停。必须在 B 仓做。
步骤4.5 ★第①层有向关系（directed_edge，在归一概念上 readout 建骨架）← 易漏！
       原 A 仓 readout 步骤，A 仓瘦身已卸到 B 仓。M0 之后、M1 之前。
步骤5 M1 超边抽取 → M2 超边生长 → M3 跨域关系 → M4 本性（每步先一本验证再全量）
```

**★依赖链厘清（破"M0 判同 ↔ 有向关系"假循环）**：判同关2（类层级/互斥）需要"判候选对上下位"的**能力**（当场 LLM few-shot，对齐 OntoEA 把类层级作独立输入），不是"全局有向关系图已建好"。所以 M0 判同（当场判候选上下位）→ M0 完成 → 步骤4.5 建全局图 → M1。不循环。

**为什么不可逆序**：canonical 不先做→超边"同概念被当不同概念"长不起来；有向关系（4.5）不先建→超边没骨架可长；超边不积累 confirmed 跨学科成员→跨域关系/本性没料。

---

# 第九部分 · 命门与红线

## 9.1 命门家族（统一原则）
> **AII 全局：宁可冗余/碎片/漏，不可误删/错合/附会。**

| 层 | 命门 | 守法 |
|---|---|---|
| KU 去重 | 宁冗余不误删 | 判"相同"宁严勿松；拿不准当"不同"保留 |
| 概念归一（M0） | 宁碎片不错合 | 判别维度对齐+类层级互斥+高风险 candidate；错合=地基污染 |
| 超边生长（M2） | 宁缺毋附会 | 内核同机制才扩；LLM 判不准→candidate；跨学科→默认 candidate |
| 跨域关系（M3） | 关系≠本性 | 跨域关系不直接认定本性；提炼出内核才升 M4；停在关系 invariant_id=NULL |
| 本性（M4） | 宁标未发现 | ≥3 跨学科+内核同+两层互证+全 confirmed；抽不出留 NULL |

## 9.2 红线（违反即停报 Wiki）
1. **看裸真相**：不被"测试绿/数量多/看起来对/跨学科涌现惊艳"骗。假联结比漏联结危险。
2. **每步先小范围验证再全量**：防错误形态铺 357×N 个 KU（已踩：数分覆盖不全、explains 写错表、M0 错合 price/income）。
3. **dry_run 验证不落库**：破坏性测试一律 dry_run，看对了再真跑（已踩落库错合）。
4. **红线测试**（测该拦的）：M0 放同名不同学科→不错合；M2 放表面相似实不同机制→不附会；M3 放假跨域关系；M4 放平凡组合假本性→不提取。
5. **CC 会判错**：核实 CC 报的问题不照单全收（已踩：误判 qwen 方向反、explains 写错表）。
6. **术语不凭印象拼**：本性=invariant 非 nature，本性同一=invariant-identity 非本性同源。
7. **commit 必 push**（VHDX 教训）。
8. **B 仓不存单本数据**：BU/按章 KC 在 A 仓；sources 是溯源指针非存书。

---

# 第十部分 · 关键标识符 & 依赖文档

## 标识符
- PG：aii-postgres 容器，A 仓 aii_kg（已有）；**B 仓 aii_refined = 独立容器 aii-refined-postgres（port 5436），非同容器**（经理人拍板，覆盖旧"同容器独立库"）。
- 代码：~/projects/AII/aii 及 /home/soffy/projects/AII；远端 git@github.com:soffy88/aii.git。
- 书源：/home/soffy/shared/stratum-to-aii/；AII↔Stratum 队列 /home/soffy/shared/aii-to-stratum/md_rework_queue.json。

## 依赖文档（本文已整合，按需查原文）
- **M1 超边规格**：AII-HYPEREDGE-EXPLAINS-001（在 CC git 仓库 ~/projects/AII/docs/ 及 stratum/docs/B仓docs/，含 Phase 1 已建表；唯一需补：本性浮现路径加第③层跨域关系）。
- **KU 本体基础**：AII-KNOWLEDGE-ONTOLOGY-002（六分类/概念/相/本性根本定义，上游基础，不冲突）。
- **A 仓抽取层**（B 仓不碰）：AII-MATH-PIPELINE-001、AII-EXTRACT-VALIDATION-001、AII-STRATUM-MD-SPEC-001。
- **⚠️ 已被本文取代的旧文档**（别再依据做 B 仓）：AII-DATA-MODEL-001（单库）、AII-CONCEPT-STORAGE-001（invariant_concept 独立表→本文改字段）、AII-GLOSSARY-001 术语部分（本性同源→本性同一）、AII-NATURE-EXTRACT-001（本性路径缺第③层）。

---

> **一句话**：B 仓（aii_refined）是 AII 的知识有机体——给机器深加工的纯知识（去重/英文/四层：有向关系·超边·跨域关系·本性）。从 0 空库建，A 仓 KU 去重灌入。实施严格按依赖：建库→去重→canonical→有向关系→超边→跨域关系→本性，每步先验证再全量。**命门：宁可冗余/碎片/漏，不可误删/错合/附会。关系≠本性，宁停在关系不附会。术语锁定 invariant/invariant-identity/is_invariant_concept。看裸真相，不让"看起来对"冒充"真的对"。**

---

*本文整合本段全部 B 仓设计（双仓架构/四层/schema/去重/判同/本性层），是 B 仓的单一完备设计。前沿依据：HyperGraphRAG、direction-aware hypergraph、SME 结构映射引擎⟨M,C,S⟩、Structure-Mapping Theory、超图 motif 挖掘、OntoEA/PARIS 实体对齐。*
