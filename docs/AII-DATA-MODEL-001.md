# AII 三层数据设计：KU / KC / BU（终版）

> **Doc ID:** AII-DATA-MODEL-001（终版）
> **依据:** 知识本体论 AII-KNOWLEDGE-ONTOLOGY-002（六分类）+ 知识图谱工程最佳实践 + GraphRAG/LeanRAG 分层聚合 + 认识论（epistemic status / temporal validity）。
> **目的:** 把知识本体落地成确定的数据结构，作为 **LLM 抽取的判据**。判据先定死，抽取才有依据。
> **★ 前提:** 现有 1.6 万 KU 全部舍弃，不迁移。本设计无历史包袱，按本体一次建对。
>
> **本终版已定的决策:**
> 1. KC / BU **独立建表**（不混入 ku 表）。
> 2. **六分类直接做 knowledge_type**，砍掉 kind 轴——元认知、立场性等平等地是六类之一，不被迫归 how/why。
> 3. **concept 表现在就建**（跨书汇聚是终极价值，概念复用是地基）。
> 4. **KC 聚类用强本体关系加权**（要"讲透一个主题"，非几何邻近）。
> 5. **BU 不缩水**：并入 BU-UPGRADE-001 全部字段 + 新增 core_explanations。

---

## 〇、三层总览

知识图谱工程（GraphRAG/LeanRAG/HiRAG/RAPTOR）一致采用三层结构，与本体"原子→簇→整体"对应：

```
BU  书级理解        一本书的整体把握（论点网络 / 立场 / 核心解释 / 可信度基调）
     ▲ 综合(LLM, bottom-up)
KC  知识簇          一组强相关 KU 的主题聚合 + LLM 簇摘要
     ▲ 聚类(社区发现, 强本体关系加权) + 综合(LLM)
KU  知识单元        原子知识：六分类，图的节点
     ── 关系边 ──    KU 之间的边（含 explains 解释链）
```

**三层本体地位不同（命门）：**
- **KU 是知识本身**（被表示之物的替身）。
- **KC、BU 是 AII 对 KU 的综合(synthesis)**，是 AII 的二次创造，不是原始来源的断言。
  > **KC/BU 必须永远标记"AII 综合，非原文断言"，其 grade ≤ 来源 KU，且永不为最高确证级。** 否则 AII 把自己的概括冒充成被验证的知识。

---

## 一、KU 表设计（核心判据）

### 1.1 设计原则（知识图谱工程实证）

1. **正交维度建为独立轴。** 知识种类、立场性、可信度、时效是互相正交的轴，各占独立字段，不混。
2. **每条断言可追溯来源(provenance)、带可信度(confidence)与时效(time validity)**（语句级限定 reification）。
3. **高频查询字段列化**，低频/可变结构留 jsonb。

### 1.2 KU 表结构

```yaml
KU:
  # ── 标识 ──
  id:                 唯一标识（uuidv7）
  name:               知识单元名称（简短标题）
  natural_text:       完整自然语言陈述
  natural_text_zh:    中文译文（英文原文保留，embedding 用原文算）
  symbolic_form:      jsonb，结构化形式（公式/步骤/命题形式）

  # ══ 轴 1：本体六分类（唯一的种类轴）══
  knowledge_type:     factual | conceptual | positional
                    | procedural | explanatory | metacognitive
  sub_type:           # 细化用，可空
                      # conceptual:    classification | principle | theory
                      # procedural:    skill | technique | conditional
                      # metacognitive: strategic | task_knowledge | self_knowledge

  # ══ 轴 2：立场性（仅 positional 时必填）══
  is_positional:      bool
  stance_holder:      谁的主张（人/学派）          # positional 必填
  opposing_stance:    对立立场（文本或 KU id）      # positional 必填

  # ══ 轴 3：认识论地位（可信度）══
  grade:              unverified（默认）| verified | refuted
                    | high | moderate | low | contradicted | pending
  grounded_by:        jsonb，可信度来源链（见 1.3）

  # ══ 轴 4：时效（可修订）══
  valid_from:         成立起始
  valid_until:        失效时点（可空 = 当前有效）
  superseded_by:      被哪个 KU 取代（可空）

  # ── 深度内容（产生"回响"）──
  intuition:          直观理解 / 为什么重要 / 反直觉点
  insight:            深层洞察（解释性与思想类尤重）
  example:            应用实例（论据降级到此）

  # ── 来源与去重 ──
  source:             出处（书/论文 + 位置）
  substrate_id:       来源文档 id
  sources:            jsonb，多来源多表述（跨源合并）
  merge_count:        合并次数
  provenance:         jsonb，抽取溯源（chunk_id / 抽取方法 / 全书理解版本）

  # ── 网络与系统 ──
  embedding:          向量（BGE-M3，英文原文算）
  fingerprint:        去重指纹
  created_at / updated_at
```

> **注：knowledge_kind（know-what/how/why）不入库为字段。** 它是认识论的解释层（说明六类同根），不是数据轴。六分类本身就是完整的种类分类——元认知就是元认知，立场性就是立场性，不在其上再套一个 kind 轴逼它们归属。这是本终版相对前稿的修正。

### 1.3 grounded_by：可信度从哪来

> 认识论铁律：默认未证(conjecture)，经机制确证才升级，弱证据不抬高置信(conservative aggregation)。

| method | 含义 | 适用 | grade 上限 |
|---|---|---|---|
| `default` | 未核验，仅抽取得到 | 所有新 KU 初始态 | unverified |
| `formal_proof` | 形式化系统验证 | 数学/逻辑命题 | verified |
| `source_crosscheck` | 多权威来源交叉 | 事实性 | high |
| `stance_internal` | 立场内部论证强度 | 立场性（**永不 verified**） | moderate |

> **铁律：grade 不是 LLM 标的。** LLM 抽取一律标 `unverified`；grade 提升只能由确证机制写入，`grounded_by` 留证据链。

### 1.4 六分类判据表（LLM 抽取的核心依据）

| 类型 | 本质问题 | 判据 | 例 |
|---|---|---|---|
| **factual** 事实性 | "是什么情况？" | 特定、可考证、有确定真值的记录 | 赤壁之战 208 年 |
| **conceptual** 概念性 | "X 是什么？什么为真？" | 抽象的本质/原理/分类/理论 | 损失厌恶；勾股定理 |
| **positional** 立场性 | "谁主张？论证是什么？" | **无确定真值、持有者相对** | 凯恩斯 vs 奥地利学派 |
| **procedural** 程序性 | "怎么做？何时做？" | 步骤/方法，靠练习，难完全言传 | 待定系数法步骤 |
| **explanatory** 解释性 | "为什么？机制如何？" | 因果/机制/"之所以如此" | 勾股定理为何成立 |
| **metacognitive** 元认知 | "怎么学/思考/反思？" | 关于认知本身的知识 | 间隔重复原理；审题先找关键词 |

**判据优先级（治 proposition 垃圾桶）：**
1. 是"为什么/机制"→ explanatory；"怎么做"→ procedural；"怎么思考/学"→ metacognitive。
2. 剩下的"是什么"：无确定真值/持有者相对 → positional；抽象本质/原理 → conceptual；特定可考证记录 → factual。
3. **一个对象同时有"是什么/怎么用/为什么"→ 拆成多个 KU**，用关系边连（本体 §2.2）。这是"讲透"，不是冗余。

### 1.5 concept 节点（现在就建）

KU 引用的概念单列（多对多），使同一概念跨 KU 复用、跨书汇聚——**这是 AII 区别于普通笔记的终极价值的地基**，现在就建：

```yaml
concept:        { id, name, name_zh, aliases[], created_at }
ku_concept:     { ku_id, concept_id }   # 多对多
```
> 同一概念在不同 KU 中指向同一 concept 节点（entity resolution）。跨书的"己所不欲"↔"换位思考"↔"同理心"汇聚到同一 concept。

---

## 二、关系边设计（含 explains 解释链）

### 2.1 边表结构

```yaml
edge:
  src_id / dst_id:    两端 KU
  relation_type:      受控词表（见 2.2，不可自由生成）
  grade:              边可信度（规则边可高，LLM 边默认 unverified）
  extraction_method:  rule | llm | textbook_order
  evidence:           jsonb，该关系的依据
```

### 2.2 受控关系词表

| 类别 | relation_type | 含义 |
|---|---|---|
| **解释 ★** | `explains` | A 解释 B 为什么成立（know-why 命门，支持 why 递归） |
| 因果 | `causes` | A 导致 B |
| 层级 | `subsumes` | A 上位包含 B |
| 层级 | `special_case_of` | A 是 B 的特例 |
| 依赖 | `prerequisite_of` | 理解 A 须先理解 B |
| 对比 | `contrasts_with` | 并列对照 |
| 立场 | `opposes` | 立场对立 |
| 冲突 | `contradicts` | 内容矛盾（AII 发现，不裁决） |
| 支撑 | `supported_by` | A 被论据/证据 B 支撑 |
| 跨源 | `same_as` | 跨源同一知识（触发合并，不建边） |

> **explains 是本设计最重要的新增。** 解释性 KU 经 `explains` 指向被解释 KU；why 递归 = explains 边层层链下去。**这是"深度"在数据层的实现。**

---

## 三、KC（知识簇）设计

### 3.1 KC 是什么

**KC = 一组强相关 KU 的主题聚合 + 一份 LLM 簇摘要。** 是 AII 对局部知识网络的综合，使系统能回答"主题性、跨条目"的问题。

### 3.2 聚类规则

```yaml
聚类算法:    Leiden（社区发现，优于 Louvain）   # 在 KU 图上跑
分层:        多层级（Level 0 细粒度 → Level 1 聚合 → …），形成簇树
粒度控制:    限制每簇最大 KU 数（Z_c），过大簇再细分   # 防巨簇（768成员教训）
★ 边权:      强本体关系高权重——explains / subsumes / prerequisite_of / special_case_of
             给高权重，使一个概念 KU 与它的"是什么/怎么用/为什么/有何争议" KU 倾向聚到同簇
```

> **KC 的本体取向（已定决策）：** 不要纯几何邻近的簇，要"把一个主题讲透"的知识团。基础 Leiden 保证客观可扩展；强本体关系加权使 KC 理想上 = 围绕一个核心概念的完整知识团（what + how + why + 立场）。

### 3.3 KC 结构

```yaml
KC:
  id:                 唯一标识
  level:              社区层级（0=最细）
  community_label:    主题标签（LLM 生成）
  summary:            簇摘要（LLM 生成，bottom-up）
  summary_zh:         中文
  member_ku_ids:      成员 KU
  core_concept_id:    核心概念（可空）
  grade:              ≤ 成员 KU 最高 grade，永不为最高确证级
  synthesis_marker:   "AII 综合，非原文断言"   # 强制
  parent_kc_id:       上层 KC（簇树）
  created_at / updated_at
```

> **KC 间也要建关系边**（同 §2 词表），避免 LeanRAG 所述"语义孤岛"。KC 是网络高层节点，不是孤立摘要。

---

## 四、BU（书级理解）设计 ★ 不缩水

> **本节并入 BU-UPGRADE-001 全部字段，并新增 core_explanations。一个不减。**

### 4.1 BU 是什么

**BU = AII 对一本书的整体把握。** 最高层综合，回答"这本书整体讲什么、持什么立场、核心解释是什么、对谁适用"。

### 4.2 BU 结构（完整，不缩水）

```yaml
BU:
  id:                 唯一标识
  substrate_id:       对应的书
  doc_type:           textbook | monograph | popular | paper | lecture

  # ══ 来源可信度（BU-UPGRADE ①）══
  source_credibility: high | medium | low
                      # 教材可 high；畅销书上限 low；取 doc_type 与内容更严者

  # ══ 整体把握（BU-UPGRADE ②③④⑤⑥）══
  problem_statement:  这本书要解决/回答的核心问题            # ②
  overview_oneline:   一句话概括这本书是什么                  # ③
  learning_thread:    学习主线（读这本书的认知路径）          # ④
  applicability:      适用范围（对谁、何种情境有用）          # ⑤
  core_takeaways:     jsonb，核心要点（读完该记住的几条）     # ⑥

  # ══ 论点结构（BU-UPGRADE ⑦⑧）══
  main_claims:        jsonb，核心论点                          # ⑦
                      # [{claim, stance_marker:"X书主张", claim_grade, key_ku_ids}]
                      # ★ 每条带 stance：论点≠真理
  argument_structure: jsonb，论点→论据                         # ⑧
                      # [{point, evidence:[...], evidence_grade, boundary}]
                      # ★ evidence 不复述 point；标 boundary（论证边界/局限）

  # ══ ★ 新增：全书的核心"为什么"（know-why）══
  core_explanations:  jsonb，这本书的核心解释/机制
                      # [{question:"为什么X", explanation, ku_ids}]
                      # ★ 捕捉全书 know-why 内核——深度的来源，不只罗列论点

  # ══ 概念网络与骨架（BU-UPGRADE ⑨⑩）══
  concept_network:    jsonb，关键概念 + 关系（概念地图）
                      # {concepts:[ku_ids/concept_ids], key_relations:[...]}
  structure:          jsonb（list），章节骨架                  # ⑨ 改 list
  key_concept_ku_ids: 核心概念 KU                              # ⑩

  # ══ 思想类专属 ══
  positional_summary: jsonb，若思想类：这本书持什么立场、对立面是谁
                      # {stance, holder, opposing}

  # ══ 综合标记与可信度 ══
  grade:              ≤ 成员 KU，永不为最高确证级
  synthesis_marker:   "AII 综合，非原文断言"   # 强制
  member_kc_ids:      构成它的 KC
  created_at / updated_at
```

### 4.3 BU 字段来源对照（确保不缩水）

| BU-UPGRADE-001 字段 | 终版位置 | 状态 |
|---|---|---|
| ① source_credibility | source_credibility | ✅ 保留 |
| ② problem_statement | problem_statement | ✅ 保留 |
| ③ overview_oneline | overview_oneline | ✅ 保留 |
| ④ learning_thread | learning_thread | ✅ 保留 |
| ⑤ applicability | applicability | ✅ 保留 |
| ⑥ core_takeaways | core_takeaways | ✅ 保留 |
| ⑦ main_claims（stance_marker + claim_grade） | main_claims | ✅ 保留 |
| ⑧ argument_structure（evidence 不复述 + boundary） | argument_structure | ✅ 保留 |
| ⑨ structure（改 list） | structure | ✅ 保留 |
| ⑩ key_concept_ku_ids | key_concept_ku_ids | ✅ 保留 |
| — concept_network（原有概念地图） | concept_network | ✅ 保留 |
| — positional_summary（原有立场） | positional_summary | ✅ 保留 |
| **★ core_explanations（全书 why）** | core_explanations | 🆕 新增 |

> **结论：旧版 10 字段 + 概念网络 + 立场摘要全部保留，再加 core_explanations。只增不减。**

---

## 五、三层挂接与存储

### 5.1 存储方式

| 层 | 存储 | 理由 |
|---|---|---|
| KU | 独立 `ku` 表，六分类等正交轴为正式列 | 高频筛选/查询 |
| 关系 | 独立 `edge` 表，受控 relation_type | 图查询、explains 链遍历 |
| concept | `concept` + `ku_concept` | 概念复用、跨书汇聚 |
| KC | **独立 `kc` 表** | 综合物，本体地位不同于 KU |
| BU | **独立 `bu` 表** | 同上 |

> **KC/BU 独立建表（已定决策）。** 不再塞进 ku 表用 is_synthesis 区分——它们本体地位不同（综合物 vs 知识本身），混库导致查询/确证/展示反复过滤。分表是本体诚实。

### 5.2 三层关系

```
bu.member_kc_ids   → kc.id     （BU 由哪些 KC 构成）
kc.member_ku_ids   → ku.id     （KC 由哪些 KU 构成）
kc.parent_kc_id    → kc.id     （簇树层级）
edge(src,dst)      → ku.id     （KU 间关系，含 explains）
ku_concept         → concept   （KU 引用的概念）
```

---

## 六、这份设计如何成为 LLM 抽取的判据

抽取时（下一步实现），LLM 对照本设计：

1. **每个候选 → 过准入**（连接>收集、信息vs知识、原材料vs成品、未来可被需要、论据降级为 example）。
2. **通过 → 判六分类**（1.4 判据表，按优先级，治 proposition 垃圾桶）。
3. **填本体字段**：立场性填 stance_holder/opposing；一律 grade=unverified, grounded_by.method=default；填 intuition/insight；关联 concept。
4. **拆透**：一个对象有"是什么/怎么用/为什么"就拆多个 KU，用 explains/特例等边连。
5. **主动抽 why**：每个概念追问是否有解释性 KU（机制/原因）尚未抽出——**深度的保证**。
6. **聚 KC**（Leiden + 强本体关系加权）→ **综合 BU**（含 core_explanations 等全字段），全部标 synthesis_marker。

> **判据定死了，抽取才有依据，不会再退回"挑重点 + proposition 垃圾桶 + 无 why + 论据当 KU"。**

---

## 七、建表清单（供 CC 实施时对照，不含 DDL）

新建表（全新，无迁移）：
- `ku`（六分类 + 立场性 + 可信度 + 时效 + 深度内容，正交轴列化）
- `edge`（受控 relation_type，含 explains）
- `concept` + `ku_concept`（概念复用）
- `kc`（知识簇，独立表）
- `bu`（书级理解，独立表，含 BU-UPGRADE 全字段 + core_explanations）

> 实施 DDL 由 CC 按本规范编写并验证（Claude 不直接写 SQL）。本文档是规范与判据，非实现。

---

*依据：知识本体论 002（六分类）+ 知识图谱工程（正交轴 / provenance / reification / 受控词表 / entity resolution）+ GraphRAG·LeanRAG·HiRAG·RAPTOR（社区发现 / 分层摘要 / 避免语义孤岛）+ 认识论（默认未证 / 保守聚合 / 证据时效）+ BU-UPGRADE-001（全字段并入）。*
