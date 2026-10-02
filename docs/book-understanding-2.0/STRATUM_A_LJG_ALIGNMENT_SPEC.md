# STRATUM A × ljg-skills 对标矩阵 SPEC v1.0

TASK=STRATUM_A_LJG_SKILLS_ALIGNMENT_AUDIT
SOURCE_AUTHORITY=STRATUM A
ANALYSIS_TARGET=lijigang/ljg-skills
TARGET_PINNED_AT=`d4d39115c8fc7a6baac9f8841f1a6b343e153f07`（2026-10-01，"feat: sync ljg-* skills [ljg-card] (v1.17.117)"）
A_BASELINE_AS_BUILT=P1..P7 / migrations 070..076
TYPE=AUDIT_ONLY — 未修改任何代码，未执行任何迁移
STATUS=FROZEN

---

## 0. 执行摘要

**本次是 audit + docs，没有一行代码被改动。**

四道验收门全部**实测**通过（不是断言），但 SPEC 提出了 6 个阶段，其中：

- **1 个阶段（Phase 1 的 QUESTION）会造成解释污染**，与本 SPEC 自己的前提冲突
- **1 个阶段（Phase 5）在当前冻结语料上无法验证**，因为试读语料只有一章
- **1 个阶段（Phase 4）引入的正是 A仓 在 P5 主动排除的那一类关系**
- **2 个阶段（Phase 2、Phase 3）的一半内容 A仓 已经有了**

另有三处需要修正的前提，写在 §1。

---

## 1. 三处必须先修正的前提

### 1.1 基线已过期 —— A仓 现在在 P7，不在 P4.1

SPEC 写 `stratum-a-p4-1-ku-durable-writer-v0.1`。实测：

```
migrations present : 070..076  (7)
stages implemented : P1..P7
durable units      : 11
identity aliases   : 11
revisions/reviews  : 1 / 5
relations (P5)     : SHARES_EVIDENCE, SAME_SOURCE_SPAN, REVISES
```

这不是吹毛求疵。P5 的修订链、P6 的唯一身份、P7 的只读投影**已经存在**，而 Phase 4
提出的关系类型与 P5 已落地的 `ku_relation` 词表直接交互。本 SPEC 一律以
**P7 / 070..076** 为基线。

### 1.2 分析目标是 24 个技能，SPEC 的矩阵只覆盖 12 个

实测 `lijigang/ljg-skills` 有 **24 个技能**。SPEC 的 Phase 7 矩阵点名 12 个，
其余 **10 个未被分类**：ljg-blind · ljg-classic · ljg-paper · ljg-constraint ·
ljg-word · ljg-teach · ljg-invest · ljg-relationship · ljg-roundtable · ljg-push。

一份只覆盖一半目标的矩阵不是严格映射。本审计把 24 个全部分类，见
`A_LJG_CAPABILITY_MATRIX.md`。其中 **ljg-paper 与 ljg-constraint 是本次审计里
价值最高、而 SPEC 完全没提到的两个**（理由见 §4.6、§4.7）。

### 1.3 Phase 10 Gate 2 按字面实现会产生 24 个假阳性

对 A仓 源码做 `knowledge_claims` / `refined_ku` / `bu_onto` / `llm_call` …
的朴素词扫描，实测 **24 处命中**。

**24 处全部是 A仓 自己的守卫清单** —— `projection.FORBIDDEN_AUTHORITY`、
`projection_builder.ISOLATED_TABLES`、`ku_identity_runner` 的正则。

也就是说：Gate 2 会因为 A仓 **写下了自己要禁的名字** 而失败。

这不是 A仓 的缺陷。这个陷阱本仓库已经踩过两次并记录在案：P4 的 runner 写着
「a list inside the gate would contain the names it forbids」，P6 重写为
「checked on the source rather than on a list」，P7 进一步改为**不再扫描源码**
而是扫描产物与导入图。

**一个对自己的规则手册触发的门会被关掉 —— 那比没有门更糟。** 本 SPEC 因此把
Gate 2 重新定义为实质性测量（§5）。

---

## 2. Phase 0 — Authority Boundary Audit

| 层 | Authority | ljg 是否允许进入 | 依据 |
|---|---|---|---|
| Source | A | **YES** | A仓 是唯一事实来源 |
| Evidence | A | **YES** | 逐字跨度，带 page/locator/extractor_version |
| KU Candidate | A | **YES** | 候选者，仍需核验 |
| Verification | A | **YES** | A仓 的四项检查 |
| Frozen KU | A | **YES** | 不可变，可按 id 引用 |
| Relation Candidate | A | **YES（有条件）** | 见 §4.4 的双端证据规则 |
| Mechanism Candidate | A | **YES（有条件）** | 见 §4.3 |
| Chapter Understanding | BU2 | **NO** | 跨章综合，非 source-grounded |
| Cross-book Concept | B | **NO** | 语义判断，A仓 无此权威 |
| Learning Object | C | **NO** | 学习投影，C仓 权威 |

实测：

```
A_AUTHORITY_PRESERVED=YES
B_CONTAMINATION=0
C_CONTAMINATION=0
```

三条实质性测量全部为 0（§5）。另有第 11 条边界，来自 §1.3 的发现：

| **Concept Cluster / 图谱节点** | **NO** | 跨单元语义聚类正是 A仓 无权做的判断 |

---

## 3. 单向吸收

```
    ljg-skills  ──(方法)──>  A仓
         │
         └──────(输出/结论/知识)──X        不复制
```

吸收的是**理解方法**与**候选生成能力**。不复制 ljg 输出，不改变 A Authority，
不引入解释污染。

一条 SPEC 未写但必须写死的边界：

> **ljg-read 与 ljg-map 的方法论底座是《学习观》。** 吸收其*结构方法*
> （具体情境 → 概念 → 判别依据 → 有条件的关系）是允许的；把该书的**内容**
> 引入 A仓 是禁止的 —— 那会把一本非 A 来源的书写进 A仓 的事实链。
> **METHOD_ONLY，不是 CONTENT。**

---

## 4. Phase 1–6 逐阶段审计

每阶段给出：ljg 的真实定义（取自上游 README 作者原话）→ A 的落点 → 实测重叠 →
**裁定**。

### 4.1 Phase 1 — ljg-book → Book Understanding Adapter

ljg-book 的实际定义：*讲清全书的主要内容、各条主线如何相连，以及事实、事件与后果
怎样逐步改变理解；保留必要的多线发展。*

| ljg-book | SPEC 提议的 A 落点 | 裁定 |
|---|---|---|
| 核心问题 | `book_question_candidate` | **REJECT** |
| 基础假设 | `assumption_candidate` | **ADOPT（有条件）** |
| 分析框架 | `structure_candidate` | **ADAPT** |
| 核心观点 | KU relation candidate | 见 §4.4 |
| 上帝视角 | BU2 输入 | **NO**（BU2 权威） |

**裁定 REJECT 的理由 —— 这是整份 SPEC 里最高的解释污染风险。**

一本书的「核心问题」是**读者的框定**，不是书里的一句话。书不会说「本书要回答的
核心问题是 X」；那是读完之后的重构。除非原文跨度本身以问句形式提出该问题，
否则 `book_question_candidate` 无法满足本 SPEC 自己的 Gate 1（所有新增对象必须有
`evidence_ids`）—— 它没有可指认的跨度。

而 `assumption` 不同：书**可以**陈述自己的前提，那句话就是跨度，可锚定。

因此：

- `QUESTION` —— **不落库**。若原文明文提出问题，可作为 evidence 的一个 span，
  由既有 Evidence 层承载，不需要新类型。
- `ASSUMPTION` —— **落库**，前提是 `source_evidence_ids` 至少一条且跨度原文含
  该前提。
- `FRAMEWORK` / `STRUCTURE` —— **ADAPT**：`FRAMEWORK` 的落点是既有
  `KIClassification.FRAMEWORK`… 实测 P2 词表为
  `FACT / EVENT / CONCEPT / RELATION / ARGUMENT`，**不含 FRAMEWORK**，所以
  `book_structure_candidate` 是真的新对象；但它必须锚在跨度上，不能锚在
  「全书的分析框架」这一层抽象上。

SPEC 的 `book_summary` / `book_answer` / `book_truth` 禁止直接落库 —— **同意，
且这是本阶段最重要的一条**。

### 4.2 Phase 2 — ljg-read → Deep Reading Engine

ljg-read 的实际定义：*用《学习观》的「下上结构」，从具体情境讲清概念、判别依据
与有条件的关系。*

**实测重叠（本阶段的一半已经在 A仓 里）：**

```
SemanticIntegrity slots = ACTION, ACTOR, ANCHORED, DEFINITION_SPAN,
                         OBJECT, PREDICATE, SUBJECT, TIME
```

`object` 与 `action` **已经存在**，是 P3 核验的语义槽位。所以 SPEC 提议的
`reading_insight_candidate.object` / `.action` 是**重复建设**。

真正缺的只有两个：

| 字段 | A仓 现状 | 裁定 |
|---|---|---|
| `object` | 已有槽位 | **不新增** |
| `action` | 已有槽位 | **不新增** |
| `condition` | **无** | **ADOPT（P0）** |
| `boundary` | **无** | **ADOPT（P0）** |
| `evidence_ids[]` | 已有 | 复用 |
| `confidence` | 已有 | 复用 |

`condition` 与 `boundary` 恰好是 ljg-read 定义里的「有条件的关系」与 ljg-qa 答案
四段里的「边界」。**这是整份对标里信噪比最高的一项**：两个新字段，无重复，直接
提升 KU 可核验性。

`relation_candidates[]` 见 §4.4。

### 4.3 Phase 3 — ljg-is → Mechanism Extraction

ljg-is 的实际定义：*把名词的「是什么」与动词的「怎样运作」接起来，再推出认知
修正与可执行判断。*

**实测：`MECHANISM` 类型早已声明。**

```
CandidateType = DEFINITION, CLAIM, FACT, CONCEPT, ARGUMENT, MECHANISM
                                   ^^^^^^^^^^ 已存在，但没有任何抽取阶段使用它
```

所以 Phase 3 不是「发明一个类型」，而是**给一个已声明的空类型配抽取器与表**。
这降低了成本，也提高了可信度：类型已在 A仓 的枚举里，不需要新的分类学。

SPEC 的强制条件 `EVIDENCE_COUNT >= 1` 与 `ANCHORABLE=true` —— **同意**，且
`ANCHORABLE` 可以直接复用 P3 已有的 `SemanticIntegrity.anchored`，不必新造。

**但 SPEC 的 `entity` / `transition.{before_state, action, after_state}` 有解释
污染风险。** 「状态变化」通常是读者从叙述里重构的，跨度里未必写着 before/after。
裁定：`transition` 三个槽位**必须各自可回指跨度**；任一槽位无法锚定时，该
mechanism 候选必须 `REJECTED`，不得留空字符串通过。

`conditions` 复用 Phase 2 的 `condition`。`LLM_REASONING_ONLY` 禁止 —— **同意**。

### 4.4 Phase 4 — relation → Relation Layer ⚠️ 最大架构张力

**实测重叠：0 / 6。**

```
SPEC 提议 : SUPPORTS CONTRADICTS CAUSES DEPENDS_ON QUALIFIES EXAMPLE_OF
P5 已落地 : SHARES_EVIDENCE  SAME_SOURCE_SPAN  REVISES
```

零重叠意味着六个全部是新的。而更关键的是：**P5 的词表是刻意排除语义关系的**。
P5 的 migration 里写着：

> Every value below is a comparison a machine can make by reading two rows.
> There is no value meaning "these say the same thing" or "these are in
> tension", because deciding either is a semantic judgement: it belongs to B仓,
> and A仓 has no authority to make it.

SPEC 现在要求 A仓 引入**恰好那一类**。这不是不可能，但它必须付出 P5 没有付出的
代价：**把判断变成可检查的约束**。

**采纳条件（缺一不可）：**

1. **双端证据规则** —— 一条语义关系必须携带**两端各自**的 evidence。
   只带一端的 `SUPPORTS` 无法区分「支持」与「同章并列」。这是本裁定里最重要的
   一条。
2. **同 source_version 限定** —— `CONTRADICTS` 在跨书语境下是平凡的：两本
   不同作者的书对同一主题给出不同答案，不必矛盾。任何语义关系必须限定在
   同一 `source_version_id` 内。
3. **落库状态只能是候选** —— 关系进入 A仓 时是 `GENERATED`，只能被核验提升或
   驳回。**不得存在 `VERIFIED_RELATION`**：一旦语义关系被标为已核验，A仓 就
   在替 B仓 做判断了。
4. **禁止清单加严** —— SPEC 已禁 `SIMILAR_TO` / `RELATED_TO` / `IMPORTANT_TO`，
   理由正确（模型主观相似）。**追加禁止 `EQUIVALENT_TO` / `SAME_AS` /
   `CONTRADICTS`（跨版本）**，理由同上。

### 4.5 Phase 5 — ljg-structure → Structural Candidate ⚠️ 当前不可验证

ljg-structure 的实际定义：*从表层问题找到反复出现的母题，提炼可迁移结构，用 ASCII
图说明关系并设计最小可逆实验。*

流程是 `Chapter Evidence → Pattern Candidate → Multiple Evidence Validation → BU2`。

**实测障碍：冻结试读语料只有一章。**

```
chapters in evidence : 1   （第一章 古代时期的信贷）
sections             : 5   （1.1 .. 1.5）
```

「跨章节模式」在一章语料上**无法被证伪也无法被证实**。而
`status: GENERATED / SUPPORTED / REJECTED` 里，`SUPPORTED` 需要多次证据验证 ——
一章里凑出的多次证据不是模式。

**裁定：DEFER。** 先扩语料到第 2 章及以后，再评估。SPEC 的 `禁止 VERIFIED_PATTERN
进入 A` —— **强烈同意**，且理由比 SPEC 写的更强：模式一旦标为已核验，它就是关于
书的结论，不是关于书的记录。

### 4.6 Phase 6 — ljg-qa → Understanding Verification

ljg-qa 的实际定义：*把文章/论文/书的核心观点抽成 Q-A 链，Q 切要害，A 四段
（结论 / 形式化 / 步骤 / 边界）。*

**实测重叠：ljg-qa 的四段与 A仓 P3 的结构高度同形。**

```
ljg-qa  A = 结论 / 形式化 / 步骤 / 边界
A仓  P3   = DEFINITION / TRACE / SOURCE / QUALITY
            + SemanticIntegrity 槽位 ANCHORED / DEFINITION_SPAN / ...
```

ljg-paper（SPEC 未提及）的定义是 *讲清研究问题、作者贡献、结果如何得来及
**证据边界*** —— 其中「证据边界」与 A仓 的 Evidence → Source 锚定是同一件事。

**裁定：ADOPT 作为验证工具，REJECT 作为知识来源 —— 与 SPEC 一致，但补一条。**

SPEC 提议 `a_question_candidate` 落库。**裁定：反对落库。**

理由：Phase 6 是**验证工具**，问题是一次性核验输入。把核验输入存成 A仓 的事实
行，等于把「我们检查了什么」变成「我们知道什么」—— 这反转了权威顺序。问题的
生命周期应是一次运行，不是一次事实。

落地形态：问题在 `ku_verification` 的一次运行内生成、判定、丢弃；只有**判定结果
与缺失证据清单**值得留存，而那属于既有核验层，不属于新表。

---

## 5. Phase 10 — Acceptance Gates（实测）

### Gate 1 Authority — `ORPHAN_COUNT=0`

```
units without an anchor        : 0
revisions with a dead endpoint : 0
reviews citing no evidence     : 0
identity rows with no unit    : 0
candidates with no evidence   : 0
ORPHAN_COUNT = 0  -> PASS
```

### Gate 2 Contamination — 重新定义为实质性测量

朴素词扫描：**24 命中，全部是 A仓 自己的守卫清单**（§1.3）。

| 实质性测量 | 结果 |
|---|---|
| (1) 导入图 — A 模块是否 import A 链之外 | **0** |
| (2) 产物 — 已发出的投影是否携带 B/C token | **0** |
| (3) schema — A 迁移是否 FK 到 A 链之外 | **0** |
| (4) BU2 迁移是否被 A 引用 | **0** |

```
B_REFERENCE = 0
C_REFERENCE = 0  -> PASS
```

**Gate 2 的实施要求：不得扫描源码字面量。** 必须扫描导入图 + 产物 + FK 目标。
若日后有人按字面实现并看到 24 个命中，正确动作是**改门**，不是删守卫。

### Gate 3 Replay

```
rebuild hash equal : True
NEW_SOURCE    = 0
NEW_EVIDENCE  = 0
NEW_CANDIDATE = 0
NEW_KU        = 0  -> PASS
```

（与 P6 G4、P7 G3/G4 同一机制：内容派生 id + `ON CONFLICT DO NOTHING`。）

### Gate 4 Explainability

```
units fully explainable        : 11/11
relation endpoints explainable : 4/4  -> PASS
```

反查路径 source → page → span → extractor_version 已在 P7 的 `EvidenceTraceMap`
里逐字段落地，`extractor_version` 已实测为 `p1-v1`。

---

## 6. Phase 8 — Architecture Integration

SPEC 提议的终局：

```
SOURCE → EVIDENCE → QUALITY → VERIFICATION → KU
      → RELATION → MECHANISM → STRUCTURE → BU2 INPUT
```

**审计意见：RELATION 必须在 MECHANISM 之前，且两者之间需要一道闸。**

理由：mechanism 的 `DEPENDS_ON` / `QUALIFIES` 若以关系候选的形式表达，则机制抽取
依赖关系层先于它存在。若关系层只接受双端证据，机制的关系槽就只能是候选，不能
是已核验关系 —— 这个次序不能倒过来，否则机制会继承一个未经约束的关系层。

采纳的次序：

```
SOURCE → EVIDENCE → QUALITY → VERIFICATION → KU
      → CONDITION / BOUNDARY（Phase 2，无需新关系层）
      → RELATION CANDIDATE（Phase 4，双端证据约束）
      → MECHANISM（Phase 3，relation 槽只能是候选）
      → STRUCTURE（Phase 5，待语料扩充）
      → BU2 INPUT（BU2 权威，A仓 只输出）
```

### 6.1 A v0.2 的净新增

审计后，A v0.2 真正需要新增的只有：

1. `condition` / `boundary` 两个候选字段（Phase 2）—— **无新关系层**
2. `mechanism_candidate` 表（Phase 3）—— 复用已声明的 `MECHANISM` 类型
3. `relation_candidate` 表（Phase 4）—— 双端证据约束
4. `assumption_candidate`（Phase 1，仅 ASSUMPTION）—— 可延后到 3 之后

SPEC 提议的 4 张新表，审计后 **`book_question_candidate` 与
`a_question_candidate` 被否决**，`structure_candidate` 被推迟。详见
`A_LJG_SCHEMA_PROPOSAL.md`。

---

## 7. 最终裁定

```
STRATUM_A_LJG_ALIGNMENT=PASS
A_AUTHORITY_PRESERVED=YES
EVIDENCE_FIRST=YES
B_CONTAMINATION=0
C_CONTAMINATION=0
NEW_SCHEMA_REQUIRED=YES
IMPLEMENTATION_READY=NO
```

**PASS 的含义**：四道验收门实测通过，边界矩阵成立，6 个阶段的裁定明确。
本 SPEC 是一次 audit，不是实现。

**`IMPLEMENTATION_READY=NO` 的理由**（不是含糊，是逐阶段的）：

| 阶段 | 就绪 | 阻塞项 |
|---|---|---|
| Phase 2 condition/boundary | **YES** | 无。可立即进入 A P5 |
| Phase 3 mechanism | **YES** | 无。`MECHANISM` 类型已声明 |
| Phase 4 relation | **YES** | 无，但必须先实现双端证据约束 |
| Phase 1 assumption | PARTIAL | 需先定义「前提」的可判定判据 |
| Phase 5 structure | **NO** | 冻结语料只有一章，无法验证 |
| Phase 1 question / Phase 6 question 表 | **NO** | 会引入解释污染或反转权威顺序 |

整体 `IMPLEMENTATION_READY=NO`，因为 6 个阶段中有一个被否决、一个被推迟、一个
只有一半就绪。**先做 audit + docs 是正确的执行顺序，本 SPEC 确认这一点**：

> 不要直接把 ljg skills 接入 pipeline。Phase 2 的两个字段可以在 A P5 安全落地；
> Phase 4 的关系层必须在双端证据约束落地之后；Phase 5 必须等语料。

## 8. 交付

| 文件 | 内容 |
|---|---|
| `STRATUM_A_LJG_ALIGNMENT_SPEC.md` | 本文：边界、阶段裁定、门、终局 |
| `A_LJG_CAPABILITY_MATRIX.md` | 全部 24 个技能的逐项裁定 + 实测重叠 |
| `A_LJG_SCHEMA_PROPOSAL.md` | `A_SCHEMA_PROPOSAL`：4 张候选表，含否决与推迟项 |
| `A_LJG_ADOPTION_PLAN.md` | 修正后的优先级、分阶段计划与门 |

STRATUM_A_LJG_ALIGNMENT=PASS
