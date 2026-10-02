# A P5.0 FREEZE REPORT v1.0

TASK=STRATUM_A_CONDITION_BOUNDARY_CANDIDATE_LAYER
BASELINE=STRATUM_A_P5_LJG_EXTENSION_SPEC v0.1 (frozen)
IMPLEMENTATION_RECORD=A_P5_0_CONDITION_BOUNDARY_SPEC.md
STATUS=FROZEN
SCHEMA=070..077

---

## 0. 冻结锚点

冻结不是一句话，是一个可校验的内容指纹。

```
077_a_condition_boundary.sql
  sha256 = fe4d613f5bb95508e69cd1f85f4013eb487fd9f6dce33c7f6ecaf59c8d8b7f6f

artifacts/a_repository/p5_0_condition_boundary.json
  sha256 = 19232068fff99d8348c09ca3fc7e041a768292d7d832c12280b081612193efa6
```

任何后续对 077 的改动都会改变第一个哈希。任何对抽取结果的改动都会改变第二个。
**这两个哈希是「077 已冻结」这句话的可执行形式。**

DB 侧状态（`stratum_a_p3_staging`）：

```
migrations = 8, newest = 077_a_condition_boundary.sql
condition_rows = 6    boundary_rows = 0
baseline units/events/revisions/identities = 11 / 12 / 1 / 11
```

## 1. 冻结契约

### 1.1 产物是什么

```
ConditionBoundaryCandidate

  authority : A仓
  role      : evidence-linked annotation
```

### 1.2 产物不是什么

| 不是 | 说明 |
|---|---|
| Knowledge | 它是对既有 span 的标注，不新增命题 |
| Verification | 它不参与任何判定，也不改变任何判定 |
| B仓 Concept | 它不做跨单元语义聚合 |

### 1.3 Condition — 冻结词表

```
允许 : ACTOR / TIME
当前真实支持 : ACTOR 4 单元 / TIME 2 单元 / 已知假阳性 0
禁止自动扩展 : STATE / LOCATION / PREREQUISITE
```

**三个因子直到新书验证才解冻。** 实测依据：这三者在 18 个候选上命中 **0**。
把它们放进 CHECK 会让 schema 出现无法兑现的值。代码里它们是具名常量
（`NOT_YET_EXTRACTABLE_CONDITION_TYPES`），解冻是一次有意的编辑，不是意外。

### 1.4 Boundary — 冻结词表

```
schema 已存在 : ku_boundary_candidate
ACTIVE_ROWS   : 0
这是 PASS。
```

```
absence != failure
```

四个 `boundary_type` 声明、两个准入。`SCOPE_LIMIT` / `EXCEPTION` 同样因
0 命中而withheld。

空表的理由是**语料里没有一句话陈述适用范围**（探针 12 个边界标记，0/10 命中）。
表建好、约束正确、正反探针已验证，只是没有行可写。门断言行数为 0，runner
报告 `BOUNDARY_CANDIDATES = 0`。

## 2. KNOWN_LIMITATION（冻结）

四条随本层一同冻结。它们不是待办，是这层的**已声明边界**。

```
KNOWN_LIMITATION 1
  evidence_ids TEXT[]
  database FK unavailable

KNOWN_LIMITATION 2
  condition != logical premise

KNOWN_LIMITATION 3
  confidence != truth probability

KNOWN_LIMITATION 4
  boundary extractor unvalidated
```

逐条展开：

**1 — `evidence_ids TEXT[]` 没有数据库外键。** 数组带不了外键。后果直说：
`ORPHAN=0` 由写入方强制、由门读取，**不由数据库保证**。073–077 里其余每一张
表都有外键兜底，这张没有。schema 被冻结为此形状，所以这是选择；它同时是本层
与其他表之间一处明确的强度落差。

**2 — condition 不是逻辑前提。** 抽出来的是跨度里逐字存在的施动 / 时间限定语。
冻结语料的跨度大多陈述事实而非陈述前提。边界由封闭词表 + 剔除表限定，两者都是
在 10 个跨度上量出来的。

**3 — confidence 不是真值概率。** 它衡量**锚点歧义度**：跨度内标记出现 1 次
= 1.0，n 次每次降 0.1，下限 0.5。当前 6 条全是 1.0，即无歧义。它不回答
「这个读法对不对」。

**4 — boundary 抽取器未经验证。** 与 P5.0 的 condition 不同：condition 在 10 个
跨度上产出 6 条并通过锚定门；boundary 的标记列表**从未产出过任何一行**，因此它的
召回率与精确率都是未知数，不是「已验证为空」。这一条区别于「absence != failure」
的表述：absence 是 PASS，但**未经检验**是第 4 条限制。

## 3. 冻结时的验收状态

```
A_P5_0_CONDITION_BOUNDARY = PASS
FROZEN_KU_MUTATION          = 0
VERIFICATION_LOGIC_MUTATION = 0
EVIDENCE_TRACEABILITY       = 100.0
ORPHAN                      = 0
REPLAY                      = PASS   (NEW_CONDITION=0, NEW_BOUNDARY=0)
B_CONTAMINATION             = 0
C_CONTAMINATION             = 0
```

`tests/architecture/test_a_condition_boundary_contract.py` — 86 passed。
A-suite 618 passed。Ruff（项目生效规则集）在三个新文件上全清。

## 4. 077 已冻结

- additive only：`ALTER` 0 / `DROP` 0 / `UPDATE` 0 / backfill 0
- 唯一外键：`knowledge_unit(id)` `ON DELETE RESTRICT`
- 070–076 逐字节未改
- 迁移门按提案执行：先 `A_P5_0_ARCH_TEST=PASS`，再应用 077

**冻结期内 077 不再修改。** 若 P5.1 证明需要改动 077 的结构，新阶段必须新迁移，
不得回头改 077 —— 与 P5→P6→P7 每次新增而不改写前一阶段的做法一致。

## 5. P5.0 授权了什么

```
P5.0_CONDITION_BOUNDARY = FROZEN
```

授权范围仅限：condition 候选层、boundary 候选层、077、对应门与测试。

**未授权**：任何对 `required_slots()` / `SemanticIntegrity` / `verification_score` /
`knowledge_unit` / `ku_candidate` / `ku_verification` 的改动。这些在本层保持原样，
且 `test_verification_and_freeze_logic_are_untouched` 锁定它们。

## 6. 冻结时的阶段状态

```
STRATUM_A_LJG_STATUS:

P5.0_CONDITION_BOUNDARY : FROZEN
P5.1_MECHANISM          : SPEC_ONLY
P5.2_RELATION           : BLOCKED
P5.3_PAPER              : BLOCKED
P5.4_CONSTRAINT         : BLOCKED
```

**下一步是 P5.1 SPEC 冻结，不是直接写 078。** 提案的执行顺序成立：
提交本报告 → 冻结 077 → 写 `A_P5_1_MECHANISM_SPEC` → 架构测试 → 才允许 078。

## 7. 两条实测发现，需要在 078 之前决定

写在冻结里是因为它们改变「078 值不值得建」，不属于实现细节。详见
`A_P5_1_MECHANISM_SPEC.md` §3、§4。

**发现 1 — 当前语料无法供给三段式。** 机制要求 trigger / transition / result
**各自锚定各自的跨度**。实测 10 个锚定跨度的子句数：

```
子句数分布 : {1: 9, 2: 1}
三个子句的跨度 : 0
```

因此 `mechanism_candidate` 若按提案 schema 建，在当前冻结链上会是**空表**，
且原因是结构性的而非偶然的：提案 schema 以**单个** `knowledge_unit_id` 为键，
而 A仓 的单元粒度是「一个命题锚定一个跨度」。一条需要三个独立锚点的链，
放不进一个以单单元为键的表。

两条出路，都需要你决定：
(a) 把 schema 改为以**单元链 / 证据链**为键，允许跨单元；
(b) 先扩抽取粒度（跨度更长），再评估 P5.1。

**发现 2 — 提案 schema 缺重放指纹。** 实测 073–077 每一张表都带：

```
073 content_hash · 074 event_hash · 075 ×4 · 076 identity_hash · 077 ×2
```

提案的 078 字段表里**没有 hash 列、没有 UNIQUE 指纹约束**。缺了它，重放只剩
写入方的前置检查这一道 —— 而单层守卫正是 P4.1 认定不够的那一层。P4.1 的做法
是双重强制（service 前置 + `ON CONFLICT DO NOTHING`），078 应保持。

## 8. 状态

```
P5.0_FREEZE=PASS
P5.0_CONDITION_BOUNDARY=FROZEN
P5.1_MECHANISM=SPEC_ONLY
P5.2_RELATION=BLOCKED
P5.3_PAPER=BLOCKED
P5.4_CONSTRAINT=BLOCKED
NEXT=A_P5_1_MECHANISM_SPEC
```
