# A_P5_1_MECHANISM_SPEC v0.1 — 前置 SPEC（未实现）

> **SUPERSEDED by `A_P5_1_MECHANISM_SPEC_v0.2.md`.**
> 本文的两处实测发现（链式键、缺重放指纹）已被 v0.2 采纳：
> 单 `knowledge_unit_id` 键 → `mechanism_node` 链式实体；缺 `mechanism_hash`
> → 补 `UNIQUE` 指纹。保留本文作为发现记录，其 schema 段不再有效。


TASK=STRATUM_A_P5_1_MECHANISM
AUTHORITY=STRATUM_A
TYPE=PRE_SPEC — **未写代码，未执行任何迁移**
PREREQUISITE=P5.0_FREEZE=PASS ✓
STATUS=SPEC_ONLY
SCHEMA=070..077（本阶段不新增迁移）

> 本文件是提案与冻结前的最后一道。它记录两处**实测发现**，它们改变
> 「078 值不值得建」，因此属于 SPEC 而不是实现细节。

---

## 1. 定义

```
MechanismCandidate

  A仓允许 : 事件链描述
  A仓不允许 : 因果判断
```

### 1.1 A仓 与 B仓 的分工（提案原文，冻结采纳）

```
A仓 : what happened
B仓 : why it matters
```

提案给的例子，本 SPEC 逐字采纳作为判例：

```
允许 : 利率限制 → 法律规定 → 债务成本变化
不允许 : 利率限制导致经济繁荣          ← 第二个进 B
```

「不允许」那一句有两个原因，都不是风格问题：

1. **无可锚定跨度。** 「经济繁荣」在源里不存在。
2. **它是一个因果断言**，而因果判断属 B仓。A仓 若把它写成一条已核验记录，
   就是替 B仓 做了那个判断。

---

## 2. 三段式

```
INITIAL STATE  ->  TRANSITION  ->  OBSERVED OUTCOME
```

```
禁止 : CAUSE / EFFECT / PROOF / EXPLANATION        这些词属于 B
```

### 2.1 词表禁令的定位需要更正

提案把这一条写成词表禁令。但实测语境后有一个问题必须说清：

**中文因果词汇（因为 / 所以 / 导致）正是事件链的自然词汇。** P5.0 的 guard 已经
把 因为/所以/导致 挡在 condition 之外（理由：那是因果断言）。如果 078 也用同一
套词表禁令，机制层能写的就只剩中性顺序词，register 极窄。

正确的分层是：

| 层次 | 手段 | 作用 |
|---|---|---|
| **主要** | 字段语义：无 `cause` / `effect` 列，只有 `trigger_event` / `transition_event` / `result_event` | 让「断言因果」在结构上无处安放 |
| **主要** | 结构要求：三段各自锚定各自的跨度 | 让机制成为被观察到的链，而非推断出的链 |
| **次要** | 词表禁令：拒绝注入的因果措辞 | 防止污染被写进来，不承担主要纪律 |

提案测试要求里的 `cause_keyword injection` 正是**次要**那一层的用例：它测的是
污染注入，不是抽取规则。所以词表禁令保留，但它不是机制纪律的主体。

**若把词表当主体，会得到两个坏结果**：要么语句空洞到没有信息，要么对真实语料
大面积假阴性。

---

## 3. ⚠️ 实测发现 1 — 当前语料无法供给三段式

机制要求三段**各自锚定各自的跨度**。实测 10 个锚定跨度的子句数：

```
ku_10fef8f2ffa4  clauses=2
ku_15a527238f5c  clauses=1
ku_4ccc104bb7a8  clauses=1
ku_5840cc146f9f  clauses=1
ku_5d49563b2149  clauses=1
ku_639e79172556  clauses=1
ku_6460a6062a10  clauses=1
ku_8b366dd7b4d1  clauses=1
ku_93a979cb6fab  clauses=1
ku_fa902e0bc115  clauses=1

子句数分布 = {1: 9, 2: 1}
三个子句的跨度 = 0
```

**没有一条锚定跨度能提供三个子句。** 所以按提案 schema 建表，在当前冻结链上
会是空表 —— 且原因不是「抽取器不够好」，而是**结构性的**：

> 提案 schema 以**单个** `knowledge_unit_id` 为键，而 A仓 的单元粒度是
> 「一个命题锚定一个跨度」。一条需要三个独立锚点的链，放不进一个以单单元为键
> 的表。

这与 boundary 的 0 行**性质不同**：boundary 的缺口是「这本书没有陈述适用范
围」，换一本书可能出现；这里的缺口是「表键与链的粒度不匹配」，换一本书不一定
解决。

### 3.1 两条出路 —— 需要你决定

**(a) 改 schema 的键。** 让机制以**单元链 / 证据链**为键，允许跨单元：

```
mechanism_candidate:
    id
    knowledge_unit_ids[]        <- 数组，不是单值
    trigger_event   + trigger_evidence_ids[]
    transition_event + transition_evidence_ids[]
    result_event    + result_evidence_ids[]
    ...
```

代价：`knowledge_unit_id` 不再是外键（数组带不了外键），ORPHAN 退回写入方强制
（同 P5.0 的 `KNOWN_LIMITATION 1`）。

**(b) 先扩抽取粒度。** 让跨度更长（当前 `source_span` 是命题的最小锚定跨度），
使一个跨度内能容纳三段。这是 P1/P3 的改动，**不在 P5.1 范围内**。

**倾向 (a)**，因为 (b) 会改动已被 073–077 依赖的冻结假设，而 (a) 只加一张新表。
但这是你的决定，不在本 SPEC 内代做。

---

## 4. ⚠️ 实测发现 2 — 提案 schema 缺重放指纹

实测 073–077 每一张表都带内容指纹：

```
073  content_hash
074  event_hash
075  observation_hash / relation_hash / review_hash / revision_hash
076  identity_hash
077  condition_hash / boundary_hash
```

（070–072 早于这个模式，它们用自然 UNIQUE on id。）

**提案的 078 字段表里没有 hash 列，也没有 UNIQUE 指纹约束：**

```
id / knowledge_unit_id / trigger_event / transition_event / result_event
condition_ids[] / evidence_ids[] / extractor_version / confidence
status / created_at
```

缺了它，重放只剩写入方的前置检查这一道。P4.1 明确认定单层不够，做法是双重
强制：service 前置检查 **加上** `ON CONFLICT DO NOTHING`。078 应保持这一致，
即补 `mechanism_hash TEXT NOT NULL` 与 `UNIQUE (mechanism_hash)`。

同时建议补一条 `condition_ids[]` 的存在性检查：提案给了字段但没给约束，
空数组会像 P5.0 的 `array_length` 那样静默通过（**该陷阱已实测过一次**：
`array_length(ARRAY[]::text[],1)` 是 NULL，CHECK 在 NULL 上通过，空数组被接受）。

---

## 5. Schema（提案，pending 决定）

```
预计迁移 : 078_a_mechanism_candidate.sql
禁止     : ALTER ku_candidate / ALTER ku_verification / ALTER BU2

mechanism_candidate:
    id                    内容派生
    knowledge_unit_id     -> knowledge_unit(id) ON DELETE RESTRICT
    trigger_event         NOT NULL
    transition_event      NOT NULL
    result_event          NOT NULL
    condition_ids[]       引用 P5.0 的 condition 候选
    evidence_ids[]        NOT NULL, cardinality >= 1
    extractor_version     NOT NULL
    confidence            NUMERIC 0..1
    mechanism_hash        NOT NULL, UNIQUE      <- §4 补
    status                GENERATED / SUPPORTED / REJECTED
    created_at            TIMESTAMP NOT NULL
```

```
status 禁止 : VERIFIED / CONFIRMED / TRUE
status 允许 : GENERATED / SUPPORTED / REJECTED
```

`CONFIRMED` 一并禁止的理由：`CONFIRMED` 在 A仓 里有确切含义 —— `ku_verification.
verification_status` 的成功值。让它出现在另一张表里会造成两个"已确认"的语义。

---

## 6. Evidence Rule

```
必须 : evidence_count >= 1
必须 : every mechanism node -> evidence span
禁止 : LLM inferred transition
```

这条与 §3 的发现直接相关：**每个 node 都要有自己的跨度**，而当前语料一个跨度
给不出三个 node。所以 §6 的严格形式（每 node 独立跨度）在当前链上不可满足，
只有宽松形式（三段共享同一单元的跨度）可满足 —— 而后者会允许抽取器在一段跨度
里编出三个阶段，即 `LLM inferred transition`。

**§6 与提案 schema 之间存在张力**：schema 是单 `knowledge_unit_id`，§6 要求
三段各自锚定。这两者在当前语料上无法同时成立。这不是实现问题，是 SPEC 内部
的不一致，需要在冻结前解决。

---

## 7. Gate（提案，采纳）

```
Authority   KU_MUTATION=0        VERIFICATION_MUTATION=0
Evidence    ORPHAN=0             TRACEABILITY=100%
Contamination  复用 external_imports() / artifact_drift()
              禁止文本扫描
```

污染检测**第四次**不做文本扫描：扫源码会命中 A仓 自己的守卫清单（P6/P7 各踩
过一次，实测 24 处假阳性）。

---

## 8. 测试要求（提案，采纳）

```
新增 : tests/architecture/test_a_mechanism_authority.py
```

| 类别 | 必须覆盖 |
|---|---|
| Schema | table exists · FK correct · status enum |
| Negative | `status=VERIFIED` · `evidence_ids=[]` · missing KU · cause_keyword injection |
| Replay | 同 KU fingerprint + extractor_version，重复执行 new rows = 0 |

`evidence_ids=[]` 的负例必须用**真实数据库**验证过一次 —— P5.0 实测证明
schema 层的空数组守卫曾经无效，而测试环境不连数据库时这一条无法证伪。建议该
测试在应用 078 后由一次 psql 探针确认，而不是仅靠单元测试。

---

## 9. Migration Gate

```
执行前必须 : P5.0_FREEZE=PASS          ✓ 已满足
然后       : 078
禁止       : ALTER KU / ALTER verification / ALTER BU2
```

---

## 10. 本阶段结论

P5.1 的**边界定义**（A仓 记发生了什么 / B仓 判断为什么重要）、**三段式**、
**状态机**、**每 node 锚定**四项都清晰且可冻结。

但有两处必须先决定，否则 078 会建成一张当前链上永远为空的表：

```
§3  当前语料 0/10 跨度能供给三段式，且 schema 的单单元键与「三段各自锚定」
    互不相容。出路：(a) 改为链键  (b) 先扩抽取粒度（超出 P5.1 范围）
§4  提案 schema 缺 mechanism_hash / UNIQUE，重放会退回单层守卫
```

因此本 SPEC 冻结**定义**，冻结**schema 的修正项**，但**不冻结**「按单单元键
建表」这一结构选择。

```
A_P5_1_MECHANISM=SPEC_ONLY
BLOCKED_ON=KEY_GRANULARITY_DECISION
BLOCKED_ON=REPLAY_FINGERPRINT
NEXT=决定 §3 的键粒度，然后补 mechanism_hash，再写架构测试，最后才允许 078
```

mechanism / relation / paper / constraint 四者中，**只有 mechanism 现在被认真
考虑**；relation 仍是上一轮审计标为最大风险项的那一项（0/6 重叠、语义类别、
且缺同 source_version 守卫）。
