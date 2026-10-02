# A_LJG_SCHEMA_PROPOSAL v1.0

TASK=STRATUM_A_LJG_SKILLS_ALIGNMENT_AUDIT
TYPE=A_SCHEMA_PROPOSAL — **提案，未执行任何迁移**
DB_MUTATION=0
SCHEMA_CHANGE=0
A_BASELINE=P7 / migrations 070..076

> 本文件描述**若采纳**需要什么。没有任何 DDL 被执行，070..076 未被修改，
> `stratum_a_p3_staging` 未被写入。

---

## 1. 提案总览

SPEC Phase 9 提议 4 张表。审计后：

| 提议表 | 裁定 | 迁移编号（若采纳） |
|---|---|---|
| `a_relation_candidate` | **ADOPT 加约束** | `077` |
| `a_mechanism_candidate` | **ADOPT** | `077` |
| `a_structure_candidate` | **DEFER** | 待定（语料 ≥2 章后） |
| `a_question_candidate` | **REJECT** | **不分配编号** |
| （新增）`a_assumption_candidate` | PARTIAL | `078`，需先定判据 |
| （新增）KU 增补 `condition` / `boundary` | **ADOPT** | `078` |

共同要求（SPEC 已定，全部确认）：

```
append-only        永不 UPDATE，永不 DELETE
evidence-linked    每行至少一条 evidence，外键 RESTRICT
no overwrite       同 evidence 下重复 = 同 id（内容派生），重放即 no-op
no merge           无 dedup、无 merge、无自动并入
```

---

## 2. `a_relation_candidate` — ADOPT 加约束

### 2.1 这是本次提案里风险最高的一张表

实测：`SPEC 提议的 6 个关系类型与 P5 已落地的词表 **0/6 重叠**。

```
SPEC : SUPPORTS CONTRADICTS CAUSES DEPENDS_ON QUALIFIES EXAMPLE_OF
P5   : SHARES_EVIDENCE  SAME_SOURCE_SPAN  REVISES
```

零重叠本身不是问题。问题是：P5 的 migration 明确写着**为什么**它不包含语义
关系 ——

> deciding either is a semantic judgement: it belongs to B仓, and A仓 has no
> authority to make it.

现在 SPEC 要求 A仓 引入那一类。因此本表必须付出 P5 没有付出的代价：**把判断
变成可检查的约束。**

### 2.2 列

```sql
-- 提案，未执行
CREATE TABLE stratum.a_relation_candidate (
    id                      TEXT PRIMARY KEY,

    -- 两端。canonical id（knowledge_unit.id），不重新 hash。
    from_ku_id              TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,
    to_ku_id                TEXT NOT NULL
        REFERENCES stratum.knowledge_unit(id) ON DELETE RESTRICT,

    relation_type           TEXT NOT NULL
        CHECK (relation_type IN (
            'SUPPORTS', 'CONTRADICTS', 'CAUSES',
            'DEPENDS_ON', 'QUALIFIES', 'EXAMPLE_OF'
        )),

    -- 双端证据：至少一条 from 侧、一条 to 侧。见 §2.4 的 R1。
    evidence_ids            JSONB NOT NULL,

    confidence              FLOAT NOT NULL
        CHECK (confidence >= 0.0 AND confidence <= 1.0),

    -- 只有三个值。不得存在 VERIFIED —— 见 R3。
    candidate_status        TEXT NOT NULL DEFAULT 'GENERATED'
        CHECK (candidate_status IN ('GENERATED', 'ACCEPTED', 'REJECTED')),

    relation_hash           TEXT NOT NULL,

    -- 同一 source_version 内才允许语义关系。见 R2。
    source_version_id       TEXT NOT NULL
        REFERENCES stratum.source_version(id) ON DELETE RESTRICT,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT a_relation_candidate_hash_uniq UNIQUE (relation_hash),
    CONSTRAINT a_relation_candidate_not_self CHECK (from_ku_id <> to_ku_id),
    CONSTRAINT a_relation_candidate_evidence_nonempty
        CHECK (jsonb_array_length(evidence_ids) >= 2)
);
```

### 2.3 为什么没有 `VERIFIED`

`ku_verification.verification_status` 有 `VERIFIED`。关系表**故意不含**这个值。

理由：一条语义关系一旦被标为「已核验」，A仓 就替 B仓 做了那个判断，而 A仓 的
权威链是 `SourceVersion > Evidence > Verification > Frozen KU` —— 关系不在这条
链的任何一个位置上。关系的最高状态是 `ACCEPTED`：**被采纳进 A仓 作为一条关于
这本书的记录**，而不是被证明为真。

### 2.4 四条硬约束（缺一不可）

| 编号 | 约束 | 理由 |
|---|---|---|
| **R1** | **双端证据**：`evidence_ids` 必须同时含 `from_ku` 与 `to_ku` 各自的证据 | 只带一端的 `SUPPORTS` 无法区分「支持」与「同章并列」。这是把判断变成检查的关键一条 |
| **R2** | **同 source_version** | `CONTRADICTS` 在跨书语境下是平凡的：两本不同作者的书对同一主题给出不同答案，不必矛盾 |
| **R3** | **不得有 `VERIFIED`** | 见 §2.3 |
| **R4** | **追加禁止项**：`EQUIVALENT_TO` / `SAME_AS` / `CONTRADICTS`(跨版本) | 与 SPEC 已禁的 `SIMILAR_TO` / `RELATED_TO` / `IMPORTANT_TO` 同理由：模型主观相似 |

**R1 的可检查性**：A仓 已有能力可以在写入前判定 —— 每个 KU 的候选者→证据链都可
解析（P7 的 `trace_complete` 已实测 11/11）。所以 R1 是一个**布尔检查**，不是承诺。

### 2.5 反例（必须被 R1 拒绝）

```
from_ku = 罗马对超上限利息处以4倍损害赔偿
to_ku   = 巴比伦要求所有贷款附书面合约
relation_type = SUPPORTS
evidence_ids = [罗马那一条]        ← 只有单端
```

两句话在同一章里出现，不构成支持关系。**R1 拒绝。** 而模型很可能输出这一条。

---

## 3. `a_mechanism_candidate` — ADOPT

### 3.1 类型已存在

```
CandidateType = DEFINITION, CLAIM, FACT, CONCEPT, ARGUMENT, MECHANISM
                                              ^^^^^^^^^^ 已声明，无抽取阶段
```

所以这不是新分类学，是给一个空类型配抽取器。成本与可信度都优于 SPEC 的假设。

### 3.2 列

```sql
-- 提案，未执行
CREATE TABLE stratum.a_mechanism_candidate (
    id                      TEXT PRIMARY KEY,

    ku_candidate_id         TEXT NOT NULL
        REFERENCES stratum.ku_candidate(id) ON DELETE RESTRICT,

    entity                  TEXT NOT NULL,
    transition_before_state TEXT NOT NULL,
    transition_action       TEXT NOT NULL,
    transition_after_state  TEXT NOT NULL,

    -- 复用 Phase 2 的 condition / boundary。
    conditions              JSONB NOT NULL DEFAULT '[]'::jsonb,
    boundaries              JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- 关系槽只能是候选，不得是 A仓 关系层的已采纳关系。
    relation_candidate_ids  JSONB NOT NULL DEFAULT '[]'::jsonb,

    evidence_ids            JSONB NOT NULL,
    confidence              FLOAT NOT NULL
        CHECK (confidence >= 0.0 AND confidence <= 1.0),
    candidate_status        TEXT NOT NULL DEFAULT 'GENERATED'
        CHECK (candidate_status IN ('GENERATED', 'ACCEPTED', 'REJECTED')),
    mechanism_hash          TEXT NOT NULL,

    -- P3 已有的 anchored。复用，不新造。
    anchorable              BOOLEAN NOT NULL DEFAULT FALSE,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT a_mechanism_candidate_hash_uniq UNIQUE (mechanism_hash),
    CONSTRAINT a_mechanism_candidate_evidence_nonempty
        CHECK (jsonb_array_length(evidence_ids) >= 1)
);
```

### 3.3 SPEC 的强制条件，确认并加严

SPEC 要求 `EVIDENCE_COUNT >= 1` 与 `ANCHORABLE=true`。**同意。**

加严一条 SPEC 没写而审计认为必须的：

> **`transition` 的三个槽位必须各自可回指跨度。** 任一槽位无法锚定时，该候选
> 必须 `REJECTED`，**不得留空字符串通过**。

理由：「状态变化」通常是读者从叙述里重构的，跨度里未必写着 before/after。
`NOT NULL` 只挡得住缺值，挡得住不住「填空」。需要一道**非空白且可在跨度中找到**
的检查。`ANCHORABLE` 复用 P3 的 `SemanticIntegrity.anchored`，不新造。

### 3.4 次序约束

`a_mechanism_candidate` 依赖 `a_relation_candidate` 先存在（`relation_candidate_ids`
外键指向它）。因此 **Phase 4 必须先于 Phase 3 落地** —— 见 ALIGNMENT SPEC §6。

---

## 4. `a_structure_candidate` — DEFER

SPEC 提议的列（`book_id` / `pattern` / `instances[]` / `evidence_ids[]` /
`counter_examples[]` / `status`）本身没问题。

**推迟理由是语料，不是设计。** 实测：

```
chapters in evidence : 1
sections             : 5
```

「跨章节模式」在一章语料上无法被证伪也无法被证实。`status: SUPPORTED` 需要多次
证据验证 —— 一章里凑出的多次证据不是模式。

**先扩语料到第 2 章及以后，再评估这张表。**

一条 SPEC 已写、审计认为理由更强的：`禁止 VERIFIED_PATTERN 进入 A`。模式一旦标为
已核验，它就是**关于书的结论**，不是**关于书的记录**。

---

## 5. `a_question_candidate` — REJECT

SPEC Phase 9 提议此表。**审计否决。**

Phase 6 是**验证工具**。问题是一次性核验输入。把核验输入存成 A仓 的事实行，等于
把「我们检查了什么」变成「我们知道什么」—— **这反转了权威顺序**。

落地形态（替代方案）：

```
问题在 ku_verification 的一次运行内生成 → 判定 → 丢弃
只留存：判定结果 + missing_evidence[] 清单
那属于既有核验层，不需要新表
```

ljg-qa 的四段（结论/形式化/步骤/边界）与 P3 的四项检查
（DEFINITION/TRACE/SOURCE/QUALITY）四对四同形 —— 它是 A仓 已有能力更好的**接口
叙述**，不是新的一层。

---

## 6. `a_assumption_candidate` — PARTIAL

SPEC Phase 1 的 `ASSUMPTION` 部分。SPEC 与本审计都同意 `book_summary` /
`book_answer` / `book_truth` 不得直接落库。

**推迟条件**：需要先给出「前提」的可判定判据。提案：

```
前提成立 ⟺ 跨度原文含该前提，且含标记（"我们假定" / "本书假设" / "前提是"）
```

未给出可判定判据之前落表，会得到一批无法复现的 `assumption` 行。

---

## 7. KU 增补字段 — ADOPT（P0，最先落地）

SPEC Phase 2 的 `condition` / `boundary`。这是全部提案里**信噪比最高**的一项。

```sql
-- 提案，未执行
-- 以 078 追加，不可 ALTER 073 的 knowledge_unit：
-- 改为在候选层承载，与 ku_candidate 并列。

CREATE TABLE stratum.a_insight_candidate (
    id                TEXT PRIMARY KEY,
    ku_candidate_id   TEXT NOT NULL
        REFERENCES stratum.ku_candidate(id) ON DELETE RESTRICT,
    evidence_ids      JSONB NOT NULL,

    -- ljg-read 的「有条件的关系」。A仓 目前没有。
    condition         TEXT,
    condition_kind    TEXT
        CHECK (condition_kind IN ('CONDITIONAL', 'EXCEPTION', 'SCOPE')),

    -- ljg-qa 四段里的「边界」+ ljg-constraint 的三层。
    boundary          TEXT,
    boundary_kind     TEXT
        CHECK (boundary_kind IN ('HARD', 'SOFT', 'SELF_DEFINED', 'EVIDENCE_EDGE')),

    -- P3 已有槽位，不新增。
    anchorable        BOOLEAN NOT NULL DEFAULT FALSE,
    insight_hash      TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT a_insight_candidate_hash_uniq UNIQUE (insight_hash),
    CONSTRAINT a_insight_candidate_evidence_nonempty
        CHECK (jsonb_array_length(evidence_ids) >= 1)
);
```

**为什么 `object` / `action` 不在这里**：

```
SemanticIntegrity slots = ACTION, ACTOR, ANCHORED, DEFINITION_SPAN,
                         OBJECT, PREDICATE, SUBJECT, TIME
```

它们已经是 P3 核验的语义槽位。新建列会造成两个真相来源。

---

## 8. 门（若采纳，每张表必须通过）

| 门 | 要求 | A仓 现有能力 |
|---|---|---|
| ORPHAN | 每行 `evidence_ids` 可解析到存在的证据 | P7 `trace_complete` 已实测 11/11 |
| REPLAY | 重复执行 `NEW_EVIDENCE=0` `NEW_KU=0` | P6 G4 / P7 G3-G4 已实测 PASS |
| EXPLAIN | 反查 source → page → span → extractor_version | P7 `EvidenceTraceMap` 已逐字段落地 |
| DETERMINISM | 内容派生 id，同输入同字节 | P7 `content_hash` x3 相同 |
| NO_MERGE | 无 dedup / merge / 自动并入入口 | P6 `merge_units` / `dedupe_units` 抛异常 |
| CONTAMINATION | 导入图 + 产物 + FK 目标三处为 0 | 见 ALIGNMENT SPEC §5 |

**不要按字面扫描源码做 contamination 门** —— A仓 的守卫清单本身含被禁名字，
实测 24 处假阳性。正确做法见 ALIGNMENT SPEC §1.3。

---

## 9. 汇总

```
提案表        : 4（SPEC） → 2 ADOPT + 1 DEFER + 1 REJECT
新增字段      : condition, boundary（+ 两组 kind）
新增核验      : contribution_check（来自 ljg-paper，SPEC 未提及）
否决          : book_question_candidate, a_question_candidate
推迟          : a_structure_candidate（语料）, a_assumption_candidate（判据）
最先可落地    : a_insight_candidate（无依赖，可进 A P5）

DB_MUTATION=0   SCHEMA_CHANGE=0   本文件未执行任何 DDL
```

A_LJG_SCHEMA_PROPOSAL=PASS
