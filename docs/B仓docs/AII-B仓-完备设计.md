# AII B仓（精炼仓 aii_refined）完备设计

> B仓（aii_refined）是 AII 的知识有机体——给机器深加工的纯知识：去重、四层结构（有向关系·超边·跨域关系·本性）、跨书生长。从 0 空库建，A 仓原始 KU 去重灌入。
>
> **两条不变量,贯穿全文:**
> 1. **损失函数不对称**——宁可冗余/碎片/漏,不可误删/错合/附会。关系≠本性,宁停在关系不附会。
> 2. **B仓是可重放派生物**——`B = f(A仓, 决策台账)`。B仓任何状态必须能从 A仓 + append-only 决策台账确定性复现。这条把"误删/错合"从**不可逆灾难**变成**可修可放的决策**,是不对称损失函数得以真正兑现的工程基础。
>
> **唯一尺子:真知识(不编)、真联结(不附会)、真本性(宁标未发现)。看裸真相,不让"看起来对"冒充"真的对"。** 三重保证:结构层面让错事发生不了(数据模型)、决策层面可回放可修(台账)、验收层面可度量(金集)。

---

# 一、双仓架构

## 1.1 两个独立数据库,互不污染
- **A 仓(原始仓 aii_kg,已有、运行中)= 给人读的数字化记录**:全、不漏、中文、按书+按章 KC+BU。忠实记录每本书抽出的原始 KU(**有重复、有噪声**),是原始证据与可追溯源。不去重、不归一——职责是"忠实记录抽取了什么"。一本书抽完就定。
- **B 仓(精炼仓 aii_refined,待建)= 给机器深加工的知识有机体**:去重、四层、纯知识。concept canonical、超边、跨域关系、本性都长在 B 仓。**不存单本书任何数据**(BU/按章 KC 都在 A 仓)。跨书整合,永远在长。B 仓是知识有机体本身,最重要。

## 1.2 为什么不能一个库混着(污染四点)
```
原始 KU（有重复）和归一/超边/本性在同一库 →
  ① canonical 污染：同概念 5 份重复 KU，归一处理 5 份噪声
  ② 超边污染：explains 超边连到哪份重复 KU？歧义
  ③ 本性污染：motif 挖掘在有重复 KU 的图上跑，重复制造虚假"反复出现"，把噪声当 motif
  ④ 向量污染：重复 KU 向量挤一起，影响相似度
```
两仓独立 → B 仓的归一/超边/本性永远在干净(无重复)数据上;A 仓的重复噪声进不了 B 仓的图。

## 1.3 单向流 + 可重放派生物
```
A 仓（抽取，有重复 KU，中文）  ── 单向 ──▶  B 仓（去重整合，四层，原语言真身 + 中文优先渲染）
                              决策台账（append-only：每次判同/合并/生长/升华的输入·证据·LLM原始输出·裁决）
B = f(A仓, 台账)：B 仓每个状态都由"A 仓证据 + 台账决策"确定性生成。A 仓保留原貌，B 仓不回写 A 仓。
```
- **可追溯**:B 仓每个 KU/概念经 sources 回查 A 仓证据。
- **可重放**:B 仓不是"一堆算出来就固化的结果",是"A仓 + 台账"的物化视图。改一条台账决策 + 重放受影响子图 = 修复,不在活库上做外科手术(见第三章)。
- **增量(新书进来)**:新书 → A 仓抽取(原始 KU,可能与已有重复)→ 去重合并到 B 仓 → B 仓主题"越读越厚"(**厚在网络:更多 KU、更多边;不是节点变肥**,见 5.2)→ 触发 canonical/超边生长更新,每步决策入台账。
- **A 仓固定、B 仓生长** —— 这正是"死知识 → 有机体"。

## 1.4 A/B 职责对照
| 维度 | A 仓（aii_kg） | B 仓（aii_refined） |
|---|---|---|
| KU | 原始（**有重复**，中文） | 去重（**无重复**，多源片段结构化，标出处） |
| KC | **按章 KC**（书原貌，读这本书） | **只主题 KC**（谱社区，跨书有机体） |
| 概念 | 裸概念名 | **canonical 概念**（归一，判别维度） |
| 高级层 | — | 四层：有向关系/超边/跨域关系/本性 |
| 向量 | A 自己的 | **B 独立向量空间** |
| BU | 有（给人读这本书） | 无（不存单本数据） |
| 派生性 | 源（真相基准） | **可重放派生物 B=f(A,台账)** |
| 职责 | 忠实记录每本书 | 跨书知识有机体 |

## 1.5 两种 KC 的角色
- **按章 KC**:书内固定结构(读这本书用),在 A 仓做"书视图"。
- **按主题 KC(谱社区)**:B 仓的组织方式——成员是去重后 KU,跨书,标来源书。谱社区天然把"同主题 KU"聚到一起,为 concept canonical 提供"哪些 KU 讲同概念"的聚类线索。
- **谱社区 / 去重 / canonical 三者在 B 仓内闭环互助**。

---

# 二、四层架构（B 仓核心）

```
第①层 有向关系  directed_edge（concept→concept：derives/subsumes/prerequisite）
第②层 有向超边  hyperedge + member（机制→被解释目标集，explains，n元，动态生长）
第③层 跨域关系  cross_domain_relation（motif/结构映射出的 base↔target 对应，SME 式⟨M,C,S⟩）
第④层 本性      invariant（从第③层提炼共享内核，is_invariant_concept 字段标记升华）
```

**生长链**:有向关系给概念骨架 → 超边在骨架上生长跨学科机制网 → motif/结构映射在机制网发现跨域关系(第③层)→ 跨域关系提炼共享内核升为本性(第④层)。越往上越是 AII 独有、越是"有机体"的体现。

**★第③层"关系" ≠ 第④层"本性"(最易犯错处)**:
- 第③层跨域关系 = "水流↔电流"的对应(它们像)——是**关系**。
- 第④层本性 = "势差驱动流"的共享内核(像在哪)——是**本性**。
- 提炼出内核才从③升④(cross_domain_relation.invariant_id 指向 invariant);提炼不出停在第③层(invariant_id=NULL)。**宁停在关系不附会。**

## 2.1 第①层 有向关系(概念骨架)
- **怎么来**:**读出法**——从已讲透的 KU 里读出它已表达的关系(不是 judge、不是信号匹配),O(N) 一次调用/KU,准确率由 50–65% 提到 **85%**。根因:读"已表达的"而非"猜"。
- **隐藏优势(固化)**:先讲透(不编)→ 再从讲透读关系(继承不编)。关系质量上界由 KU 质量保证。
- 概念级关系进 directed_edge;KU 内部逻辑另存(不污染概念图)。

## 2.2 第②层 有向超边
- head = rationale KU(机制本身);members = **被解释目标集合**(n元,可 1 可多)。目标可以是**概念**(机制解释一组概念),也可以是**命题 KU**(机制解释一个命题,如"勾股定理的 why-KU 解释勾股命题 KU")——member 多态(见 3.6)。
- nl_description = 机制自然语言陈述(向量检索用)。n=1 与 n>1 统一(同结构同查询,不分叉)。
- **动态生长 = 超边的本性**(非可选功能,见第七章)。

## 2.3 四层协调(不分裂,单一存储单一查询)
| 结构 | 语义 |
|---|---|
| ku_concept(隐式超边) | **无向**:KU 涉及哪些概念(共现/聚类用) |
| directed_edge(概念→概念) | 概念间**结构**(derives/subsumes/prerequisite) |
| hyperedge(机制→目标集) | explains,n元,目标多态(概念或命题 KU) |
- **一切 explains 关系(概念级、KU 级)统一收进 hyperedge**;不存在"数学线走二元边、经济线走超边"的双轨。全库同一存储、同一"为什么"查询路径。

## 2.4 前沿依据(设计理由)
- **n元超边不拆二元** = 前沿共识(Freebase 61% 关系 n元,拆二元有损)+ 信息论(二元条件熵 `H(X|φ)>0`,超图 `=0`)。
- **有向超边** = direction-aware hypergraph 研究印证(无向超边缺因果方向/因果链推理逻辑)。
- **本性浮现** = 超图 motif 挖掘(motif 统计、高阶聚类、rich-club 检测);不是玄学,是"跨语料反复出现的高阶 motif"。
- **本性理论** = 结构映射理论(SMT);第③层跨域关系 = 结构映射引擎 SME 四十年标准 ⟨M 对应, C 候选推断, S 结构分⟩。
- **AII 独有 = 四块合一**:结构映射理论 + 超图 motif 挖掘 + 有向超边 + 真实书语料·讲透 KU。

---

# 三、决策台账与可重放（B 仓的地基不变量）

> B 仓的每一步深加工(判同、合并、超边生长、机制归并、本性升华、拆分)都是一个**决策**。这些决策大量由 LLM 做,而 **LLM 非确定——同样输入重问会得不同答案**。因此"活库上算出来的结果"不可复现:一旦发现错合,你无法靠"重跑一遍"回到干净状态,重跑会引入新的不一致。台账把每个决策**固化成可回放的记录**,B 仓从此是可重放派生物。

## 3.1 台账记什么
append-only,绝不修改历史行。每条决策记:
```
decision_type   ku_dedup / content_merge / concept_merge / hyperedge_grow /
                mechanism_merge / invariant_promote / split(unmerge) / …
inputs          参与对象的 id + 关键判据输入（判别维度取值、候选对、粗筛分…）
evidence        原文依据/引用（回指 A 仓 raw_ku_id + 原文片段）
model           模型档位（local-small / frontier-X），标明这条决策由哪级模型做
llm_raw         ★LLM 原始输出（完整）——重放读它，不重问模型
verdict         最终裁决（same/different/candidate；合并成哪个；加哪个成员；升华 true/false…）
actor           llm / human / program
supersedes      修订指向被改的旧决策 id（改台账=追加一条 supersedes，不改旧行）
```

## 3.2 重放语义(reproduce,不是 re-run)
- **重放**:按 created_at 顺序读台账,对每条决策**应用其 verdict**(读 llm_raw、不重问模型)→ 从 A 仓证据确定性重建 B 仓任意状态。
- **修订**:发现一条决策错(如 price/income 错合)→ 追加一条 `supersedes` 指向它、给出新 verdict → **只重放受影响子图**(那条决策及其下游:该 KU/概念挂的超边成员、KC 成员、invariant 链接)。不在活库上做外科手术。
- **升级重跑 = 用新能力重放**:词典/图谱成熟后想重做早期 M0,不是"重问当年的模型",是"用成熟词典重放当年的决策输入"(见 6.2 的"确定性是挣来的")。

## 3.3 拆分(unmerge)语义
误合的修复必须定义"拆开后怎么归位",否则修订无法落地:
- 拆一个 refined_ku(把误并的多事项拆回多个 KU):按 `contributions` 的 facet/事项边界切(见 5.2),挂在原 KU 上的**超边成员、KC 成员、有向边端点**按证据重新归属到拆出的目标 KU;归属不明的成员降级为 candidate 待人工/重放确认。
- 拆一个 refined_concept(把误合的两概念拆回):别名/判别维度按台账里合并那条决策的 inputs 还原;概念↔本性、概念↔超边成员、有向边端点按 source_ku_id 证据重新归属。
- 拆分本身是一条 `split` 决策,入台账,可再被重放。

## 3.4 红线(写入命门,见第十二章)
> **B 仓任何状态必须能从「A 仓 + 决策台账」确定性复现。任何绕过台账、直接改活库的写入都是违规。**

---

# 四、B 仓完备 Schema（含 DDL）

> 独立数据库 aii_refined,schema **rf**。从 0 空库建(不灌数据),表一次预留完备。
> **两条贯穿 schema 的纪律**:① KU 真身是**结构化多源贡献**,正文是派生渲染(4.1);② 所有"成员集合"用 **junction 关联表**,不用 jsonb id 列表(可加外键、可重放、不漂移)。

## 4.1 去重 KU（refined_ku,真身=结构化贡献）
```sql
CREATE TABLE rf.refined_ku (
  ku_id           text PRIMARY KEY,     -- 新 ULID（B 仓独立 ID 空间；被全库引用，稳定不复用）
  ku_type         text,                 -- factual / conceptual / relational / procedural / rationale
  is_positional   boolean DEFAULT false,-- 立场性（正交样态，见第九章）
  point           text,                 -- 知识点 canonical 名（英文, 跨书/跨语言对齐用; 名称=概念或论断）
  point_zh        text,                 -- 中文名（显示用）
  contributions   jsonb NOT NULL,       -- ★真身：单一可陈述事项的多源片段（各留原语言）
                                        --   [{ source_book_id, version, raw_ku_id, facet, fragment_text, lang }]
  facet_count     int,                  -- 原子性预算监控（越阈值触发拆分，见 5.2）
  natural_text_zh text,                 -- ★中文优先视图（显示主视图；zh 源直接拼装, en 源 en→zh 译）
  natural_text    text,                 -- 英文视图（en 源=原文保留可展开；zh 源不译, 可空）
  embedding       vector(1024),         -- 定稿后算（BGE-M3，干净 KU）
  stance_holder   text, opposing_stance text,  -- 立场性时填
  created_at timestamptz, updated_at timestamptz
);
```
- **contributions 是真身,natural_text 是渲染**:合并 = 向 contributions **追加一个片段**;正文 = 按需从 contributions 拼装;书 v2 重抽 = **换该 source 的片段重渲染**(不做字符串外科);拆分(3.3)= 按 facet/事项切 contributions。
- **一个 refined_ku 恒等于"一个可陈述事项"**(第九章原子性);多源只是同一事项的不同侧面片段。不同事项**不进同一 KU**,用关系边连(5.2 原子性预算)。
- `sources` 由 contributions 聚合派生(每个 source_book_id 贡献了哪些片段),不单列冗余。

## 4.2 canonical 概念（refined_concept）
```sql
CREATE TABLE rf.refined_concept (
  concept_id      bigserial PRIMARY KEY,
  name            text, name_zh text,
  aliases         jsonb,             -- 归一并入的别名（含各书变体）
  level           text,              -- concrete/abstract
  discipline      text,              -- 学科（硬隔离用）
  discriminative  jsonb,             -- ★判别维度取值: {弹性对象: price, 测量法: arc}
  embedding       vector(1024),
  sources         jsonb,             -- 出现在哪些书
  created_at timestamptz, updated_at timestamptz
);
```
（概念↔本性是多对多,单列 junction 表 4.9,不在此放单值 invariant_id。）

## 4.3 主题 KC（refined_theme_kc + member,含快照版本）
```sql
CREATE TABLE rf.refined_theme_kc (
  kc_id           bigserial PRIMARY KEY,
  version         int NOT NULL DEFAULT 1,   -- ★聚类快照版本（重聚类产新版，旧版冻结）
  is_current      boolean DEFAULT true,
  theme_name      text, theme_name_en text,
  summary text, summary_zh text,
  embedding       vector(1024),
  source_books    jsonb,
  created_at timestamptz
);
CREATE TABLE rf.refined_kc_member (
  kc_id  bigint REFERENCES rf.refined_theme_kc(kc_id),
  ku_id  text   REFERENCES rf.refined_ku(ku_id),
  PRIMARY KEY (kc_id, ku_id)
);
```
- **只主题 KC**(按章 KC 在 A 仓)。**社区身份不稳定**(增量语料全局重聚类会洗牌边界)→ 用**快照版本化**:重聚类产新 version、旧 version 冻结,`is_current` 标当前;引用方(超边/检索)显式指版本,不被重聚类悄悄改。

## 4.4 KU↔概念（refined_ku_concept,超图 incidence）
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
  edge_id       bigserial PRIMARY KEY,
  src_concept   bigint REFERENCES rf.refined_concept(concept_id),
  dst_concept   bigint REFERENCES rf.refined_concept(concept_id),
  relation_type text,              -- derives/subsumes/prerequisite
  strength      real,              -- 关系强度
  grade         text DEFAULT 'unverified',
  evidence      jsonb, decision_id bigint,   -- 回指台账
  created_at timestamptz
);
```
概念骨架。**也供判同关2(类层级/互斥)判上下位**。

## 4.6 第②层 有向超边（refined_hyperedge + 多态 member）
```sql
CREATE TABLE rf.refined_hyperedge (
  hyperedge_id    bigserial PRIMARY KEY,
  relation_type   text DEFAULT 'explains',
  head_ku_id      text REFERENCES rf.refined_ku(ku_id),   -- 解释者: rationale KU（单一机制，非"一捆"）
  mechanism_key   jsonb,                       -- ★机制判别维度（因果变量/作用方向/适用条件/机制类型），供 head 判同
  nl_description  text,
  embedding       vector(1024),                -- nl_description 向量（hyperedge_vdb）
  grade           text DEFAULT 'unverified',
  evidence        jsonb, decision_id bigint,
  created_at timestamptz, updated_at timestamptz
);
CREATE TABLE rf.refined_hyperedge_member (
  member_id     bigserial PRIMARY KEY,
  hyperedge_id  bigint REFERENCES rf.refined_hyperedge(hyperedge_id),
  member_kind   text NOT NULL,                 -- ★'concept' | 'ku'（目标多态）
  concept_id    bigint REFERENCES rf.refined_concept(concept_id),
  member_ku_id  text   REFERENCES rf.refined_ku(ku_id),
  CHECK ( (member_kind='concept' AND concept_id IS NOT NULL AND member_ku_id IS NULL)
       OR (member_kind='ku'      AND member_ku_id IS NOT NULL AND concept_id IS NULL) ),
  status        text DEFAULT 'confirmed',      -- confirmed/candidate（宁缺毋附会）
  strength      real,                          -- 解释强度（这机制对这目标多核心）
  source_ku_id  text, evidence jsonb, decision_id bigint,
  cross_disc    boolean DEFAULT false,
  added_at timestamptz
);
CREATE UNIQUE INDEX ON rf.refined_hyperedge_member (hyperedge_id, member_kind, coalesce(concept_id,-1), coalesce(member_ku_id,''));
```
- **member 多态**:目标既可是概念,也可是命题 KU("机制解释命题")——把数学线"why 解释命题"收进同一超边模型,消灭双轨。

## 4.7 第③层 跨域关系（refined_cross_domain_relation + junction member）
```sql
CREATE TABLE rf.refined_cross_domain_relation (
  relation_id          bigserial PRIMARY KEY,
  description          text,
  source               text,              -- motif 挖掘 / 结构映射(SME)
  base_domain          text, target_domain text,
  correspondences      jsonb,             -- [{base:水压, target:电压}, {base:流量, target:电流}]
  shared_structure     text,              -- 共享高阶结构（flow）
  candidate_inferences jsonb,             -- C: 候选推断
  structure_score      real,              -- S: 结构分
  embedding            vector(1024),
  invariant_id         bigint REFERENCES rf.refined_invariant(invariant_id),  -- 提炼出内核→指；否则 NULL（停在关系）
  status               text DEFAULT 'candidate',
  decision_id bigint, created_at timestamptz, updated_at timestamptz
);
CREATE TABLE rf.refined_cdr_member (           -- 跨域关系的参与概念（junction，替 jsonb）
  relation_id bigint REFERENCES rf.refined_cross_domain_relation(relation_id),
  concept_id  bigint REFERENCES rf.refined_concept(concept_id),
  role text,                                   -- base / target
  PRIMARY KEY (relation_id, concept_id)
);
```

## 4.8 第④层 本性（refined_invariant + junction）
```sql
CREATE TABLE rf.refined_invariant (
  invariant_id          bigserial PRIMARY KEY,
  statement             text,              -- 本性是什么（道非相，如"无外力则只增、不可逆、有方向"）
  invariant_vector      vector(1024),
  is_invariant_concept  boolean DEFAULT false,  -- false=普通本性 / true=升华为本性概念（不独立建表）
  status                text DEFAULT 'candidate',  -- 默认 candidate，确证才认定
  decision_id bigint, created_at timestamptz, updated_at timestamptz
);
CREATE TABLE rf.refined_concept_invariant (    -- ★概念↔本性 多对多（junction，替单值 FK）
  concept_id   bigint REFERENCES rf.refined_concept(concept_id),
  invariant_id bigint REFERENCES rf.refined_invariant(invariant_id),
  PRIMARY KEY (concept_id, invariant_id)
);
-- 本性概念 = WHERE is_invariant_concept=true（升华前后同一条记录，只是标记变）
-- 升华判据：多概念 invariant_vector 收敛到同一 invariant 且 ≥2 概念共有 → is_invariant_concept=true
```
- **概念↔本性用 junction**:一个概念可承载多条本性("均衡"可同时承载"不动点"与"稳定性"两条 invariant),单值 FK 的"一概念一本性"假设是错的;junction 也可加外键、不与 invariant 端双向冗余漂移。

## 4.9 决策台账（rf.decision_ledger，第三章）
```sql
CREATE TABLE rf.decision_ledger (
  decision_id   bigserial PRIMARY KEY,
  decision_type text NOT NULL,
  inputs        jsonb NOT NULL,
  evidence      jsonb,
  model         text,          -- 模型档位
  llm_raw       jsonb,         -- LLM 原始输出（重放不重问）
  verdict       jsonb NOT NULL,
  actor         text,          -- llm/human/program
  supersedes    bigint REFERENCES rf.decision_ledger(decision_id),  -- 修订
  created_at    timestamptz DEFAULT now()
);
```
所有四层表带 `decision_id` 回指产生它的那条决策 → 决策与产物双向可查,重放/修订有据。

## 4.10 向量与索引
- 类型隔离**由表结构达成**:概念/本性/KU 向量各在**自己的表自己的列**,pgvector 按表建索引,天然不混——**不用额外"标记维"**(烧容量且引入"标记维意外进距离计算"的 bug 面)。**类型 = 表。**
- hyperedge_vdb = refined_hyperedge.embedding 上的 pgvector 索引(nl_description 向量),生长粗筛 + 检索用。

## 4.11 实证完备性(对照前沿)
- **已对齐**:二部图存储超图(无损)、双向量库(同 BGE-M3 空间)、超边带 NL+confidence、confidence 分级 confirmed/candidate + human-in-loop、provenance(contributions/sources 回指)。
- **补的真缺口(都不建 chunk 表)**:原文 chunk 检索融合——AII 结构在 B 仓、原文 chunk 在 A 仓,经 `contributions.raw_ku_id` 回查 A 仓原文融合(检索逻辑,不在 B 仓存 chunk);边/成员 `strength`;来源 `version`(进 contributions,适用"书重抽",不适用"facts 过时")。
- **明确不加**:temporal 时序图、bi-temporal 版本、审计/访问控制表——教科书知识不过时、单用户。

## 4.12 建库步骤
```
1. 建独立库 aii_refined（容器 aii-refined-postgres:5436，与 aii_kg 硬隔离，严禁 dblink/FDW）
2. 建 schema rf + 全部表（含 decision_ledger、各 junction、快照版本列）
   + pgvector 索引（各 embedding 列）+ 外键（超边/边/KC/概念↔本性/跨域 member）
3. 空库（不灌数据）——等去重机制把 A 仓 KU 去重后灌入
4. 验证：表全、外键对、向量索引在、台账表在、空库
```

---

# 五、KU 去重机制（A 仓 → B 仓入口工序）

> B 仓生长入口。去重错(误删/错合)→ 概念归一、超边、本性全建在错误数据上。第一道关。**判同作用在 KU 名称的原文语义(名称=概念或论断);内容不做 zh↔en 翻译**(见 5.3);每个整合/合并决策入台账(可重放)。

## 5.1 流程(判同读原文;内容不译,显示层才 en→zh)
```
A 仓 KU（按书、有重复、原语言）
  ① KU 判同（作用在 KU 名称的原文语义，名称=概念/论断；中英并排给判官，不预翻译）
       判"两 KU 是不是讲同一个点"：名称语义同 + 讲同一个可陈述事项
       ★存疑 → 判为不同（不强合）           ── 决策入台账
  ② 同点 KU 内容整合（结构化贡献，非拼正文）
       判为同点 → 向 contributions 追加片段（相同片段丢、不同片段补、各标出处、留原语言）
       ★原子性预算：合并后事项/facet 超阈值 → 拆成多个 KU + 关系边（5.2）
       ★宁冗余不误删                        ── 决策入台账
  ③ 存为 B 仓 KU（contributions 真身 + 派生渲染）
  ④ 概念归一（M0，在去重 KU 上做，四道关，第六章）
  ⑤ 谱社区 KC（按概念聚类，主题 KC，跨书，快照版本）
  ⑥ 定稿渲染（内容不做 zh↔en 翻译）：contributions 原文按语言拼装 → 中文优先视图 natural_text_zh
       （zh 源直接；en 源为显示译中文）；英文原文留 natural_text，前端默认隐藏可展开
B 仓自然生长（新书来→重复 1-6→网络变厚）
```

## 5.2 内容整合:结构化贡献 + 原子性预算(命门:判相同不误删、节点不肥)
- **误删(判太松)**:数分 ε-δ 严格定义 vs 同济应用定义,都是"导数定义"但内容不同(一严格一应用)。判"相同"删一个 → 丢知识。
- **权衡**:误删 = 不可逆丢知识;冗余 = 可逆。→ **误删 >> 冗余危害**,判相同**宁严勿松**,拿不准当"不同"保留。
- **整合 = 结构化追加,不是拼正文**:同一事项的多源片段进 `contributions: [{source, facet, fragment_text}]`;正文按需渲染。
  ```
  导数定义 KU:
    contributions: [
      { book: 数分, facet: 定义,   fragment_text: "ε-δ 严格定义…" },
      { book: 同济, facet: 应用,   fragment_text: "应用导向定义…" },
      { book: 同济, facet: 几何,   fragment_text: "几何意义…" }
    ]
  ```
- **★原子性预算(节点不肥)**:一个 refined_ku 只装**一个可陈述事项**。若整合后跨越多个事项(定义 / 几何意义 / 应用本就是三个可陈述事项)→ **facet_count 超阈值触发拆分**为多个 KU,彼此用关系边连。**越读越厚 = 网络变厚(更多 KU/边),不是节点变肥。** 节点肥会连锁污染:向量糊成"关于导数的一切"、超边 head 变"一捆机制"、版本替换成字符串外科——结构化贡献 + 原子性预算一并根除。

## 5.3 语言与呈现:内容留原文,名称英文对齐,显示中文优先
- **判同读原文,不读译文**:判同主要作用在 KU 名称(概念或论断),读原文语义。zh-zh 判中文;zh-en 由最强模型双语判原文——比"先译成英文再判 en-en"信息更多(译文把 边际/增量 塌缩成 marginal、数列/序列→sequence,区分永久丢失,再也判不出"不同")。**有损翻译绝不进不可逆决策上游**(违命门方向性)。
- **粗筛不需要同语言**:BGE-M3 / qwen3-embedding 跨语种对齐向量空间,zh-zh / zh-en / en-en 同空间可比,cross-lingual 捞候选。
- **内容不做 zh↔en 翻译**:判同确认后,中文内容保持中文、英文内容保持英文,contributions 片段各留原语言。B 仓不追求"英文统一内容"。
- **英语只在名称/术语层做受控对齐**:概念名/术语经**闭集术语词典**映射到英文 canonical(跨书/跨语言对齐用,与 §6.3 判别维度词典**同一套基础设施**)——这是**查表不是自由翻译**,不塌缩。英文 canonical 名服务判同对齐,不是内容语言。
- **呈现层中文优先(受众多为中文母语者)**:前端主视图 `natural_text_zh` 中文——zh 源直接、en 源为显示 en→zh 译;**英文原文保留(`natural_text`)、默认隐藏、可展开查看**。显示翻译是**前端非阻塞事项**,不进灌库关键路径。

## 5.4 两层判同破循环
| | KU 判同(步骤①) | 概念归一(步骤④) |
|---|---|---|
| 判什么 | 两 KU 是不是讲同一个点 | 两概念是不是同一概念 |
| 依据 | KU 名 + 内容(原文语义) | 概念名 + 判别维度 + 上下位 |
| 时机 | 先行 | 去重后(干净 KU 上) |
KU 判同用自己名+内容,不强依赖概念已归一,破"去重依赖归一、归一依赖去重"的循环。

---

# 六、概念判同"真正同一"（M0）

> 单靠 LLM 判同不稳(LLM 倾向"强行匹配,即使没有正确匹配")——会真错合(price-inelastic ← income-inelastic 类冲突、子概念过合)。**诚实定位:M0 阶段前三关全是 LLM,只是 prompt 结构不同——它是"三个结构不同的 LLM 探针 + 风险分流",不是"确定性把关"。确定性是随词典和图谱成熟挣来的(6.2)。** 前沿:错合是实体对齐头号问题,42.2%–55.7% 是"类冲突"(OntoEA);解法 = 本体约束(类层级/互斥 + 属性值比较)兜住 LLM。

## 6.1 "真正同一"定义(正向)
两概念 A、B 真正同一 ⟺ 全部满足:
```
① 判别维度全对齐（每个本质维度取值相同，非名字像）
② 非上下位（A 不是 B 的子类/特化）
③ 非互斥（不属互斥并列类：价格弹性 ⊥ 收入弹性）
④ 核心结构相同（关系结构同，非表面）
缺任一 → 不同概念 → 不合并（宁留碎片）
```

## 6.2 四道关(探针 + 风险分流;确定性是挣来的)
```
候选对 (A,B) ← 向量粗筛（同 discipline 余弦≥阈值）
  探针1 判别维度对齐 —— 判别维度取值来自 LLM 抽取（初期非确定；词典成熟后趋确定）
        任一本质维度取值不同 → DIFFERENT
        price-inelastic{对象:price} vs income-inelastic{对象:income} → DIFFERENT
  探针2 类层级/互斥 —— M0 初期用当场 LLM few-shot 判上下位；第①层图（步骤4.5）建好后趋确定
        A subsumes/derives B → 上下位 → 不合并
  探针3 LLM 判语义 —— 前两关后的窄候选
        反义/方向反/不确定 → DIFFERENT（默认拒合）
  分流   跨学科 / 任一探针存疑 / 置信不足 → status='candidate'（不自动合）
        四探针全过 + 高置信 → confirmed，真合并（★用最强模型，见 6.4）
```
- **确定性是挣来的**:探针1 随**判别维度闭集词典**成熟变确定,探针2 随第①层图建好变确定。有台账+重放(第三章),可用成熟后的词典/图谱**重放早期 M0**,让地基回溯性变干净。

## 6.3 判别维度:闭集枚举 + 本质 vs 表述
- 判别维度族做成**闭集枚举**:人工维护词典、按学科扩展、约束 LLM 抽取只能输出词典内的键;抽取结果落库可审。
  ```
  弹性族：弹性对象(price/income/cross)、测量法(arc/point)、时期(short/long-run)
  成本族：成本对象(production/investment)、增量性(basic/increasing/marginal)
  ```
- 每维标"本质"或"表述":**本质维度**(弹性对象)取值不同 = 不同概念 → DIFFERENT;**表述维度**(测量法 arc/point、单复数)不同但本质同 → 可合。

## 6.4 模型分级(命门不对称 → 算力也不对称)
| 环节 | 模型档 | 理由 |
|---|---|---|
| 向量粗筛、判别维度抽取、candidate 判定 | 本地小模型（qwen3 等，0 成本） | 量大、可逆、错了进 candidate 兜住 |
| **不可逆的 confirmed 合并/机制归并** | **最强可用模型（钉死）** | 过了前关后量很小、成本可控;而这一级判断质量恰是整个地基 |

## 6.5 命门
错合 = 地基污染(上层超边/本性全错,且难发现——合了看不出原来是两个);碎片可恢复。→ **阈值宁严勿松,拿不准导向碎片不导向错合**。**全局归一强制 dry_run**(算+打印"会合并哪些"不落库),抽查无错合再真合。每条合并决策入台账,错合修复 = 改台账 + 重放(第三章)。

---

# 七、超边 explains（第②层）与机制判同

**本相**:explains 是"有向 n元超边"——一个 rationale(机制)联合解释一组目标(概念或命题 KU),不拆二元。
```
explains 超边 H = ( head: rationale KU, 机制NL描述, { 被解释目标集合（概念/命题KU 多态） } )
   例: "可替代品的多寡决定需求对价格的敏感度"
       → explains → { 需求价格弹性, 供给价格弹性, 奢侈品vs必需品弹性差异 }
```

## 7.1 ★机制判同(head):比概念判同更难,同等严防
超边生长的前置判断是"新 rationale 与已有超边**是不是同一机制**"——这是一个实体判同问题,而且**比概念判同更难**(机制是命题,不是词项)。head 合错 → motif 在假的"同机制跨域反复"上挖 → **直接污染第③④层**,毒性与概念错合同级。因此:
- **给机制定义它自己的判别维度**(`hyperedge.mechanism_key`):因果变量、作用方向、适用条件、机制类型。
- **复用第六章四道关骨架**:粗筛(nl_description 向量)→ 机制判别维度对齐 → LLM 判因果内核 → 高风险 candidate;不可逆的机制归并用最强模型(6.4)。
- 机制归并决策入台账(mechanism_merge),可重放可修。

## 7.2 动态生长 = 超边的本性
机制不变、被解释目标集随知识摄入生长。新书发现同一机制还解释别的目标 → 给已有超边**加成员**(机制 canonical 不动,成员集生长),而非新建。生长 5 条严判据:
```
① 不是 nl_description 相似就合并（表面相似 ≠ 同机制；embedding 只是候选）
② 内核同一个机制/同一推理结构（同因果结构，非措辞撞；LLM 给结构层面理由）
③ 加的成员必须有原文依据（source_ku_id + evidence）
④ 存疑 → status='candidate'，不自动并入主网
⑤ 跨学科扩成员 → 一律先 candidate（far analogy 最易附会）
```

## 7.3 LLM 判不准的强制导向
判据由 LLM 判会错。强制:LLM 判"同"但置信不足/跨学科/有疑 → 一律 candidate,不写 confirmed。confirmed 门槛高。把"判错"导向"漏"(candidate 可补)不导向"附会"(错误 confirmed 污染本性网)。candidate 成员不进主网检索、不喂本性挖掘;积累证据/人工确认 → 升 confirmed;本性挖掘(M4)只用 confirmed。

## 7.4 检索(双路+双向)
问"为什么" → ① hyperedge_vdb 向量检索相关机制超边;② 从概念/命题经 member 反查"哪些机制解释我";③ 双向扩展。**所有 explains(概念级、KU 级)同一路径,无双轨。**

## 7.5 忠于原文
成员只标原文真表达的解释关系,不附会;生长加成员也要原文依据;grade 一律 unverified(机制是否真成立留核验,LLM 不标可信度)。

---

# 八、本性层（第④层）

## 8.1 本性是道,非相
- 相:能观测/描述/测量的样子(量、公式),静态可见。
- 本性(invariant):驱动它、决定它命运的内在规律/必然趋势,穿透一切相不变。熵:相="无序度量 / S=k·lnW";**本性="无外力下,只增、不可逆、有方向"**。拓扑不变量语义:咖啡杯↔甜甜圈形状随意变、亏格不变。

## 8.2 本性 ≠ 本性概念
- 某抽象概念的本性(熵的本性)= 该概念属性。
- 本性概念 = **多个**抽象概念**共有**的那个本性凝结成的独立实体(≥2 概念共有才 is_invariant_concept=true,涌现非预设)。

## 8.3 ★关系 ≠ 本性(防附会,最易错处)
- 跨域关系:两领域的结构对应(水流↔电流)——关系层(analogical mapping)。
- 本性:多领域共享的抽象内核本身("势差驱动流")——本性层(schema abstraction)。
- **命门**:motif/映射推出的先承认是"跨域关系";只有提炼出"共享抽象内核"才升本性;提炼不出停在关系层(invariant_id=NULL,仍有价值)。**把关系当本性 = 附会。宁停在关系不附会。**

## 8.4 两条发现路径
- **路径 A(自下而上)**:超边生长 → 跨学科同机制实例(二部图)→ motif 挖掘 → 跨域反复结构(第③层)→ 提炼内核 → 第④层本性。
- **路径 B(自上而下)**:核心抽象概念(熵/均衡/势差驱动流)本身即高度抽象 schema → 直接抽本性。
- 两路都过"关系≠本性"关,不把"相似"直接当本性。

## 8.5 两条腿的诚实边界(本层是全系统最不可自动化处)
本性由两条腿互证:**层一 本性向量收敛**(概念抽本性 → invariant_vector → 收敛)、**层二 motif 结构**(超边二部图 motif 挖掘)。设计上要它们"互相印证防附会"——但必须诚实:
- **两条腿并非真独立**:本性陈述是 LLM 写的(措辞高度趋同,"X 驱动 Y"体 → 向量收敛可能反映**文体**而非本质);motif 跑在 LLM 建的超边上、向量算在 LLM 写的陈述上——**共享同一生成器的系统性偏差**,"两独立证据"实为两个弱相关信号。
- **没有纯工程修法**(加一层 LLM 治不了 LLM 的系统偏差)。只有三条纪律,都不漂亮但必须写死:
  ① 两条腿**用不同模型/不同 prompt 家族**做,尽量解耦;
  ② **人工审是 M4 的常设闸,不是初期措施**;
  ③ **本性长期停在 candidate**,认定门槛设到"人不看都觉得不可能是巧合"。
- 本性层是 AII 最前沿、最独有、最未验证的部分;最后做、最审慎、最依赖前三层干净积累。

## 8.6 升华与三种连接
- **升华判据**:多概念 invariant_vector 收敛到同一 invariant 且 ≥2 概念共有 → is_invariant_concept=true(同一条记录标记变,不割裂)。
- **本性提取判据(最严)**:≥3 语义远领域(far analogy)+ 形式各异内核相同 + 两层互证 + 全 confirmed 支撑 + **抽不出留 NULL(宁标未发现不编)**;默认 candidate。
- **三种连接绝不互相冒充**:边(edge,局部强)/ 概念共指(弱)/ **本性同一(invariant-identity,最深,连"名字不搭学科不搭但本质同构"的概念如经济均衡↔生态稳态)**。

---

# 九、KU 本体基础（分类 / 相 / 本性定义）

**KU 定义**:KU 不是文本,是**被表示之物的替身(surrogate)** + 一组本体承诺。文本是载体,KU 是载体所替代的那个东西。

**四个本体属性**:① 原子性(恰好一个连贯可陈述事项——B 仓由 contributions + 原子性预算保证,5.2);② 自足性(脱离上下文仍可陈述);③ 可陈述性(可被断言的知识,非问题/任务);④ 可关联性(能入网络,连不上者本体上可疑)。

**知识三分(认识论,不可相互还原)**:
| 类型 | 哲学名 | 问题 |
|---|---|---|
| 陈述性 | know-that | X 是什么/什么为真 |
| 程序性 | know-how | 怎么做（不能完全言传） |
| 释因性 | know-why | 为什么/机制如何运作 |
**深度 = know-why 的在场**(只抽 know-what 丢 know-why 的库是浅的)。

**陈述性内部**:factual(可考证,抽象度低)/ conceptual(本质与意义的抽象)/ relational(知识本身是关系,常体现为 KU 间的边)。同一对象沿不同类型展开为多个 KU(勾股定理→命题/程序/why 三个 KU)。

**★分类枚举(与本体一致,单一权威)**:`ku_type ∈ { factual, conceptual, relational, procedural, rationale }`;`is_positional bool` 是正交样态(立场性:命题无确定真值、只在某立场内成立,记 stance_holder + opposing_stance,绝不脱离持有者当事实)。知识类型与认知操作(记住/运用/分析)是两个正交维度。

**KU 准入(质量命门)**:连接 > 收集(Connect not Collect);信息 vs 知识(能否用来推理);原材料 vs 成品;**黄金标准=未来可被需要**;论据 ≠ KU;量由知识密度决定不预设。

**认识论地位**:可信度默认 unverified(新抽取只是线索),经**核验机制**提升——核验机制是排期项(见 12 命门),在其落地前 grade 恒为 unverified(诚实,非空头承诺);立场性永不"确证为真"。

---

# 十、术语锁定

| 中文 | 英文 | 锚定含义 |
|---|---|---|
| **本性** | **invariant** | 拓扑不变量语义——一切相之下穿透不变的内核。不是 nature(=性质/特征=相)。熵的本性="只增、不可逆、有方向"，非"无序度量"。 |
| **本性概念** | **invariant concept** | 多概念共有的本性升华。不独立建表——refined_invariant 的 `is_invariant_concept=true`。 |
| **本性同一** | **invariant-identity** | 两概念共享同一本性的最深连接。identity=同一，非 equivalence/similarity。 |

---

# 十一、评测与验收（把命门从原则变成指标）

> 合并精度是 B 仓的神圣指标——但"神圣"必须可度量。**回测有罪推定:没跑过对抗金集、给不出 precision/recall 的判同/合并逻辑,一律视为未验证,不得灌库。**

## 11.1 金集(灌库前先建)
从 A 仓抽几百对 KU 对 / 概念对,人工标 `same / different / uncertain`,**必须含对抗对**:
- price/income 弹性(类冲突)、上下位对(increasing opportunity cost ⊂ 机会成本)、arc/point 表述变体(该合)、跨书同名异义、方向反的机制对(head 判同用)。

## 11.2 指标与验收线
- 每次改阈值/prompt/模型 → 跑金集出 **precision / recall**。
- 验收线体现命门不对称:**merge precision 逼近 1(错合近零),recall 可以低(宁碎片)**。把"宁碎片不错合"从一句原则变成一条数字线。

## 11.3 里程碑功能化
M0–M4 完成定义**不能只看结构**(表建了、边长了),要看**功能**:
- M1/M2:"为什么 X"检索在标注查询集上**打赢 A 仓 chunk RAG 基线**,才算过。
- M3/M4:候选跨域关系/本性经人工审的**准确率**达线。

## 11.4 先答:B 仓为谁的哪些问题服务
灌库前定义**消费方与查询负载**——B 仓服务哪类查询(为什么/机制检索、跨域类比、概念溯源、本性检索…),典型问题清单是什么。这决定四层的取舍与检索设计,是评审该最先回答的。

---

# 十二、命门与红线

## 12.1 命门家族(统一原则:宁可冗余/碎片/漏,不可误删/错合/附会)
| 层 | 命门 | 守法 |
|---|---|---|
| KU 去重 | 宁冗余不误删 | 判相同宁严勿松,拿不准当"不同";多源=contributions 追加,不拼肥正文 |
| 概念归一(M0) | 宁碎片不错合 | 四道关(闭集词典+图谱+LLM+分流)+ dry_run;错合=地基污染 |
| 机制判同(head) | 宁碎片不错合 | 机制判别维度 + 四关骨架;head 错合毒性同概念错合 |
| 超边生长(M2) | 宁缺毋附会 | 5 判据;LLM 判不准→candidate;跨学科→默认 candidate |
| 跨域关系(M3) | 关系≠本性 | 不直接认定本性;提炼出内核才升 M4;停在关系 invariant_id=NULL |
| 本性(M4) | 宁标未发现 | ≥3 跨学科+内核同+两层互证+全 confirmed;抽不出留 NULL;两条腿弱相关→人工审常设 |

## 12.2 红线
1. **可重放**:B 仓任何状态必须能从「A 仓 + 决策台账」确定性复现;绕过台账直接改活库 = 违规。
2. **看裸真相**:不被"测试绿/数量多/看起来对/跨学科涌现惊艳"骗。假联结比漏联结危险。
3. **不可逆决策用最强模型**:confirmed 合并/机制归并/本性认定,算力向命门倾斜。
4. **判错导向漏不导向附会**:LLM 判断处一律存疑→candidate;grade 全程 unverified,直到核验机制落地(排期项)。
5. **先金集后灌库、先验证后全量、破坏性测试先 dry_run**:未过金集不灌库;每步先一本验证再全量。
6. **B 仓不存单本数据**:BU/按章 KC 在 A 仓;contributions 是溯源指针,非存书。
7. **术语不凭印象拼**:本性=invariant 非 nature,本性同一=invariant-identity。
8. **单一存储单一查询**:explains 全走超边(member 多态),不留双轨;成员集全走 junction 表,不用 jsonb id 列表。

---

# 十三、实施顺序

## 13.1 灌库前的三件事(此序,越前越省;灌库后每件返工代价翻倍)
```
① 金集（可度量地基）—— 没它，后面两件改完都无法证明真改好了
② 决策台账 + 可重放红线 + unmerge 语义（结构不变量）
③ contributions 结构化 + 原子性预算（改数据模型；灌库后拆已积厚正文代价大）
（内容不做 zh↔en 翻译；显示层 en→zh 是前端非阻塞事项，不在灌库前关键路径）
```

## 13.2 建仓完整顺序
```
步骤1  建 B 仓库 + 全 schema（含台账/junction/快照，空库，纯 DDL）
步骤2  KU 去重机制（判同读原文、内容不译、contributions 追加、原子性预算），决策入台账
步骤3  现有 A 仓 KU 去重灌入 B 仓（首批经济/数学）—— 先过金集
步骤4  M0 concept canonical（B 仓去重 KU 上，四道关，dry_run，不可逆用最强模型）
步骤4.5 第①层有向关系（readout 建概念骨架）← M0 之后、M1 之前，别漏
步骤5  M1 超边（n元，member 多态，机制判同）→ M2 生长 → M3 跨域关系 → M4 本性
       每步先一本验证再全量，里程碑按功能验收（11.3）
```

## 13.3 依赖链(破"M0 判同 ↔ 有向关系"假循环)
判同探针2 需要"判候选对上下位"的**能力**(当场 LLM few-shot),不是"全局图已建好"。M0 判同(当场判)→ M0 完成 → 步骤4.5 建全局图 → M1。**不循环。** 图建好后反哺判同(确定性增强),但 M0 不阻塞等它;有台账,可用成熟后的图**重放**早期 M0。
**为什么不可逆序**:canonical 不先做 → 超边"同概念当不同概念"长不起来;有向关系不先建 → 超边没骨架;超边不积累 confirmed 跨学科成员 → 跨域/本性没料。

## 13.4 M3 发现流程
```
输入：超边-目标二部图（只用 confirmed 成员）
  → motif 统计/高阶聚类 + 结构映射(SME)：找反复高阶结构 / base↔target 对应
  → 候选跨域关系（跨 ≥2 学科、有结构对应）→ 落 cross_domain_relation（⟨M,C,S⟩ + junction member）
  → invariant_id 暂 NULL（停在第③层），等 M4 判是否提炼出内核
```

---

# 十四、标识符

- **PG**:A 仓在 aii-postgres 容器(库 aii_kg,已有);**B 仓 = 独立容器 `aii-refined-postgres`(port 5436),库 aii_refined,schema rf**——独立容器独立库,与 A 仓硬隔离(A→B 单向流走应用层 ETL,严禁 dblink/FDW)。
- **建库 DDL**:`~/projects/stratum/aii/migrations/refined/`(0001 repo schema、0002 dedup_decision_ledger、0003 concept_decision_ledger;按本文补齐 decision_ledger、junction、多态 member、快照版本、contributions)。
- **代码**:`~/projects/AII/aii` 及 `/home/soffy/projects/AII`;远端 `git@github.com:soffy88/aii.git`。
- **书源**:`/home/soffy/shared/stratum-to-aii/`;AII↔Stratum 队列 `/home/soffy/shared/aii-to-stratum/`。
- **前端**:aii.uex.hk,API:8101,前端:3101。
- **embedding**:BGE-M3(vector(1024))/ qwen3-embedding(本地,0 成本)。
- **模型分级**:粗筛/candidate 用本地小模型;不可逆 confirmed 决策用最强可用模型(钉死)。

---

> **一句话**:B 仓(aii_refined)是 AII 的知识有机体——去重·四层(有向关系·超边·跨域关系·本性)的纯知识,**是 A 仓 + 决策台账的可重放物化视图**。KU 真身是结构化多源贡献(节点不肥、网络变厚),判同读原文(名称为主)、内容不译显示中文优先,不可逆决策用最强模型、且必过对抗金集。严格按依赖:金集 → 台账 → contributions → 建库 → 去重 → canonical → 有向关系 → 超边 → 跨域关系 → 本性。**命门:宁可冗余/碎片/漏,不可误删/错合/附会;误删/错合靠"可重放"变可逆,靠"金集"变可度量。关系≠本性,宁停在关系不附会。看裸真相。**
