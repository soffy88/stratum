# A × ljg-skills CAPABILITY MATRIX v1.0

TASK=STRATUM_A_LJG_SKILLS_ALIGNMENT_AUDIT
TARGET=`lijigang/ljg-skills` @ `d4d39115c8fc7a6baac9f8841f1a6b343e153f07`
TARGET_SCALE=24 skills / 7.4k stars / 845 forks / 227 commits（2026-10-01 实测）
A_BASELINE=P7 / migrations 070..076

> 上游描述一栏是 `lijigang/ljg-skills` README 的作者原话，不是本审计的转述。
> 24 个技能全部列出。SPEC 的 Phase 7 矩阵只点名 12 个，其余 10 个在此补齐。

---

## 1. 裁定词表

| 词 | 含义 |
|---|---|
| **ADOPT** | 方法直接可落 A仓，落点是既有结构或一张新候选表 |
| **ADAPT** | 方法可用，但落点必须被 A仓 的证据约束改写后才可用 |
| **REJECT** | 方法本身会造成解释污染或反转权威顺序，不落 A仓 |
| **DEFER** | 方法合理，但当前语料/约束不足以验证 |
| **RESERVE** | 方法属 B仓/C仓 域，A仓 不吸收，但记录以备他仓取用 |
| **NOT_IN_A** | 表达/输出层，与 A仓 事实链无关 |

---

## 2. 全部 24 个技能

### 2.1 表达 / 输出层 — `NOT_IN_A`

| 技能 | 上游描述 | 裁定 | 理由 |
|---|---|---|---|
| **ljg-card** | 内容铸卡 — 文本铸成长图/全文保真卡/漫画/白板四种 PNG | NOT_IN_A | 渲染层。A仓 产物是 JSON 与 markdown，不是位图 |
| **ljg-plain** | 白话引擎 — 改写到聪明的十二岁小孩也能懂 | NOT_IN_A | **改写即解释污染**：改写后的句子不是原文跨度，无法锚定 |
| **ljg-writes** | 写作引擎 — 把观点写成可理解可迁移的中文文章 | NOT_IN_A | 生成层 |
| **ljg-present** | Unix 演讲设计 — 保真排版 / 单文件离线 HTML | NOT_IN_A | 输出层 |
| **ljg-classic** | 古文精读 — 原文/逐字注解/句义/章节意旨图/全章解读排成一张长 PNG | NOT_IN_A | 逐字**注解**不是原文，属解释层 |
| **ljg-roundtable** | 圆桌讨论 — 真实人物逐轮交锋，每轮一张 ASCII 结构图 | NOT_IN_A | 虚构对话，不可能有 evidence |

`ljg-plain` 值得单独说一句：它是最诱人的一个，因为它最像「理解」。但白话改写产出的
句子在原书里不存在，`ANCHORABLE` 恒为 false。它只能是 A仓 冻结 KU 的**下游消费者**。

### 2.2 交互 / 教学层 — `RESERVE`（C仓 域）

| 技能 | 上游描述 | 裁定 | 理由 |
|---|---|---|---|
| **ljg-teach** | 体验式教学 — 让学习者先选择，用公平的意外显化认知缺口，再迁移复测 | RESERVE | 学习状态属 C仓 `learning_progress`。方法可被 A仓 **引用**，状态不可存 A仓 |
| **ljg-relationship** | 关系分析 — 五层结构诊断 + 精神分析 | RESERVE | 精神分析不可锚定 |
| **ljg-invest** | 投资分析 — 判断项目是否是一台「秩序创造机器」 | RESERVE | 决策输出，非书摘 |

### 2.3 解释 / 生成层 — `RESERVE`（SPEC 已列 3 个）

| 技能 | 上游描述 | 裁定 | 理由 |
|---|---|---|---|
| **ljg-learn** | 概念解剖 — 从八个方向切开一个概念，压成一句顿悟 | RESERVE | 「顿悟」是压缩结论。SPEC 判断正确：偏 B/C |
| **ljg-rank** | 降秩引擎 — 给一个领域找出不可再少的独立生成器 | RESERVE | 领域级降维，属 B仓 跨书聚合 |
| **ljg-think** | 追本之箭 — 纵向深钻到不可再分的本质 | RESERVE | 「本质」是解释结论 |

### 2.4 理解方法层 — 本次对标的实质内容

| 技能 | 上游描述 | 裁定 | A仓 落点 | 实测重叠 |
|---|---|---|---|---|
| **ljg-read** | 用《学习观》的「下上结构」，从具体情境讲清概念、判别依据与**有条件的关系** | **ADOPT (P0)** | `condition` / `boundary` 两个新候选字段 | `object`/`action` 已在 P3 槽位里 |
| **ljg-book** | 讲清全书主要内容、主线如何相连、事实/事件/后果怎样改变理解 | **ADAPT** | `assumption_candidate` + `structure_candidate` | — |
| **ljg-qa** | 核心观点抽成 Q-A 链，Q 切要害，A 四段（结论/形式化/步骤/**边界**） | **ADOPT (P0)** 作为验证工具 | `AVerificationPipeline` 增强 | 与 P3 四项检查同形 |
| **ljg-is** | 把名词「是什么」与动词「怎样运作」接起来，推出认知修正与可执行判断 | **ADAPT (P1)** | `mechanism_candidate` | `CandidateType.MECHANISM` **已声明** |
| **ljg-map** | 提取概念、判别依据与联结；按内容自身结构绘图 | **ADAPT (P1)** | `relation_candidate` | 与 P5 词表 **0/6** 重叠 |
| **ljg-structure** | 从表层问题找到反复出现的母题，提炼可迁移结构，设计最小可逆实验 | **DEFER** | `structure_candidate` | 试读语料只有 1 章 |
| **ljg-paper** | 面向无行业背景读者，讲清研究问题、作者贡献、结果如何得来及**证据边界** | **ADOPT (P0)** | 「证据边界」= A仓 Evidence→Source 锚定 | SPEC **未提及** |
| **ljg-constraint** | 找出框住领域的约束（硬/软/自设三层），揪出被当成硬约束的假墙 | **ADAPT (P1)** | `boundary` 的实例化：`kind ∈ HARD/SOFT/SELF_DEFINED` | SPEC **未提及** |
| **ljg-word** | 深度拆解一个英语单词的核心语义和顿悟时刻 | RESERVE | 词典义项 ≠ 书中语境义 | SPEC **未提及** |

### 2.5 工具层 — `NOT_IN_A`

| 技能 | 上游描述 | 裁定 | 理由 |
|---|---|---|---|
| **ljg-blind** | 盲区扫描 — 读某日 AI 对话找结构性盲区，用微信读书章节补上 | NOT_IN_A | 消费 AI 对话，非书。语义上属 C仓 缺口驱动 |
| **ljg-push** | 推送引擎 — git 同步 `~/.agents/skills/ljg-*` | NOT_IN_A | 运维，与知识无关 |

---

## 3. SPEC 未提及但审计认定为高价值的三个

### 3.1 ljg-paper — 应当是 P0

*讲清研究问题、作者贡献、结果如何得来及**证据边界***。

「证据边界」与 A仓 的 `Evidence → Source` 锚定是同一件事，只是上游用散文表达，
A仓 用 `page / locator / span / extractor_version` 表达。它还带来一个 A仓 目前
没有的东西：**贡献声明的核验**（作者声称的贡献 vs 跨度是否支持）。这可以直接挂在
P3 的四项检查上做第五项。

### 3.2 ljg-constraint — 直接把 `boundary` 变成可分类的

*找出框住领域的约束（硬/软/自设三层），揪出被当成硬约束的假墙*。

这给了 Phase 2 的 `boundary` 一个**三层判别**，而 SPEC 的 `boundary` 只是一个空
字符串字段。`HARD / SOFT / SELF_DEFINED` 是可从跨度判定的（书用「必须/不得」还是
「通常/往往」），比无类型的 `boundary` 强得多。

### 3.3 ljg-qa 的四段 ≈ P3 的四项检查

```
ljg-qa   A = 结论 / 形式化 / 步骤 / 边界
A仓  P3    = DEFINITION / TRACE / SOURCE / QUALITY
```

四对四。**含义**：ljg-qa 不是要新增的能力层，而是 A仓 已有能力的一个更好的
**接口叙述**。采纳它 = 改核验的输出形态，不是加一张表。这降低了 Phase 6 的成本，
也说明为什么 SPEC 提议的 `a_question_candidate` 表是不必要的。

---

## 4. Phase 映射与裁定汇总

| Phase | 技能 | 提议对象 | 实测重叠 | 裁定 |
|---|---|---|---|---|
| 1 | ljg-book | `book_structure_candidate` | 无 | **ADAPT** |
| 1 | ljg-book | `assumption_candidate` | 无 | **ADOPT**（需前提判据） |
| 1 | ljg-book | `book_question_candidate` | — | **REJECT** |
| 1 | ljg-book | 上帝视角 → BU2 | — | **NO**（BU2 权威） |
| 2 | ljg-read | `reading_insight_candidate.object` | **P3 已有槽位** | **不新增** |
| 2 | ljg-read | `reading_insight_candidate.action` | **P3 已有槽位** | **不新增** |
| 2 | ljg-read | `condition` | **无** | **ADOPT (P0)** |
| 2 | ljg-read | `boundary`（含 ljg-constraint 三层） | **无** | **ADOPT (P0)** |
| 3 | ljg-is | `mechanism_candidate` | **类型已声明** | **ADAPT (P1)** |
| 4 | ljg-map | `relation_candidate` | **0/6** | **ADAPT (P1)**，须双端证据 |
| 5 | ljg-structure | `structure_candidate` | 语料不足 | **DEFER** |
| 6 | ljg-qa / ljg-paper | 验证增强 | 与 P3 同形 | **ADOPT (P0)** |
| 6 | ljg-qa | `a_question_candidate` | — | **REJECT**（不落库） |

---

## 5. 净新增一览

审计后，A v0.2 真正需要的：

```
新增字段  : condition, boundary(+HARD/SOFT/SELF_DEFINED)
新增表    : relation_candidate, mechanism_candidate
新增核验  : contribution_check（来自 ljg-paper）
延后      : assumption_candidate
推迟      : structure_candidate（待语料 ≥2 章）
否决      : book_question_candidate, a_question_candidate
```

对照 SPEC 的 4 张提议表：`a_structure_candidate` 推迟、`a_question_candidate` 否决、
`a_mechanism_candidate` 保留、`a_relation_candidate` 保留并加约束。

A_LJG_CAPABILITY_MATRIX=PASS
