# STRATUM_A_P5_LJG_EXTENSION_SPEC v0.1 — 冻结

TASK=STRATUM_A_LJG_TARGETED_ADOPTION
HEAD=`d4d3911c8fc7a6baac9f8841f1a6b343e153f07`（审计目标，已冻结）
A_SCHEMA=070..076
MODE=ADD_ONLY
AUTHORITY=A仓
TYPE=SPEC_FREEZE — **本轮未写任何代码，未执行任何迁移**
STATUS=FROZEN

---

## 0. 冻结声明与两个必须先解决的冲突

本 SPEC 在冻结时修正了三处会导致实测失败或不一致的地方，全部以实测为依据。
未修正的部分按任务原文冻结。

### 0.1 阶段编号冲突（标签层，不影响迁移）

A仓 的 **A_P5 已被占用** —— `A_P5_KU_EVOLUTION` / migration `075`。
本任务把新工作称作「A P5」并用 `P5.0`–`P5.4` 作子阶段。

```
已有 : A_P4(073)  A_P4_1(074)  A_P5(075)  A_P6(076)  A_P7(no migration)
新增 : "A_P5_LJG_EXTENSION"  -> 标签冲突
```

**迁移编号无冲突**：077 / 078 / 079 确实接在 076 之后，已核实。

处置：子阶段名沿用任务原文 `P5.0`–`P5.4`（便于对照），但**顶层阶段名在冻结文档
中记为 `A_P8`**。若坚持沿用 `A_P5`，需接受「`A_P5` 在文档中指两个不同阶段」。
**这一项需要你决定，我按 A_P8 记录但不单方面改写任务原文。**

### 0.2 ⚠️ P5.0 的关键修正 —— CONDITION/BOUNDARY **不得**进入 `required_slots()`

任务 P5.0 写「新增 Verification Slot」。若字面实现为加入 `required_slots()`，
实测后果：

```
FACT   today : 4 required -> 满分 4/4 = 1.000  -> VERIFIED
FACT   +2    : 6 required -> 同一候选 4/6 = 0.6667 < 0.8 -> REJECTED
EVENT  +2    : 6 required -> 同一候选 4/6 = 0.6667 < 0.8 -> REJECTED

实测：当前 VERIFIED=11 / REJECTED=7，11 个已通过者全部满足现有 4 个槽位。
=> 11 个全部翻转为 REJECTED。
```

且这 11 个单元**已经冻结并持久化**（`knowledge_unit=11`、`ku_freeze_event=12`、
staging 实测 11 行）。槽位一改，**活体验证与冻结基线立刻脱钩** —— 而 A仓 的
不变量正是「冻结的东西不得被后来的判定改写」。

**冻结裁定**：

```
CONDITION / BOUNDARY  =  可观测槽位（observable），非必需要槽位（required）
required_slots()      =  不变
077                   =  ku_condition_candidate / ku_boundary_candidate 两张独立表
```

这与任务自己的迁移计划一致（077 是独立候选表，不是 `ku_candidate` 的列）。
**P5.0 的正文与它自己的迁移计划原本矛盾，本裁定以迁移计划为准。**

同时：`SemanticIntegrity.slots()` 可以**暴露**这两个槽位供观测与门使用，但
`definition_score` 的分母不得改变。

### 0.3 ⚠️ CONDITION 五因子就绪度 —— 5 个里只有 2 个可抽

任务要求 CONDITION 至少含 `actor / state / time / location / prerequisite`
之一。实测：

```
候选者                : 18
actor  今天可抽       : 12   （P3 的 ACTOR 槽位已有抽取器）
time   今天可抽       : 9    （P3 的 TIME 槽位已有抽取器）
state                 : 0    无抽取器
location              : 0    无抽取器
prerequisite          : 0    无抽取器
```

**「至少一个」的实际含义是：一个 CONDITION 可以仅凭 `actor` 通过 —— 那是五个
因子里最弱的一个，而最弱的门槛恰恰是实际生效的门槛。**

冻结裁定：

```
P5.0 首批只允许 actor / time 作为 CONDITION 因子。
state / location / prerequisite 标记为 NOT_YET_EXTRACTABLE，
在抽取器落地前不得作为通过依据。
```

---

## 1. Phase P5.0 — Boundary Contract Freeze

**吸收目标**：ljg-read 的 `condition` / `boundary`。

**A仓 现状**（实测）：

```
SemanticIntegrity slots = ACTION, ACTOR, ANCHORED, DEFINITION_SPAN,
                         OBJECT, PREDICATE, SUBJECT, TIME
缺失                    = CONDITION, BOUNDARY
```

### 1.1 CONDITION — claim 成立条件

强约束按任务原文冻结：

```
禁止 hedger : 可能 / 通常 / 一般
              （不是可验证条件）
必须至少命中一因子，且该因子今日可抽：
              actor  /  time
              state / location / prerequisite  -> 暂不可作通过依据（§0.3）
必须       : ≥1 evidence anchor
```

### 1.2 BOUNDARY — claim 不适用范围

任务未给 hedger 禁止清单。**裁定：与 CONDITION 同规则。**

理由：boundary 若允许「通常不适用」，它就是一条 SOFT constraint，而不是边界。
两者必须同严，否则 BOUNDARY 会成为绕过 CONDITION 限制的侧门。

### 1.3 ⚠️ CONDITION 与 CONSTRAINT 的词表必须不相交

任务内含一处**字面冲突**：

```
P5.0 : 禁止 condition 含「通常」
P5.4 : constraint type SOFT，定义示例正是「通常情况下」
```

即：**一条 SOFT constraint 作为 CONDITION 是非法的。** 这在语义上自洽（前提是
可验证的，倾向不是前提），但 SPEC 原文没写，实现者会踩。

冻结裁定：

```
condition  与  boundary  : 可验证前提/边界，禁 hedger
constraint (P5.4)        : 显式陈述的倾向，允许 hedger
两者词表不相交，同一句话不得同时是两者的合法实例。
校验点：condition/boundary 的写入路径检查 hedger；
        constraint 的写入路径不检查。
```

### 1.4 验收

```
CONDITION_SLOT=PASS      槽位可观测，且未进入 required_slots()
BOUNDARY_SLOT=PASS       同上
EVIDENCE_LINK=100%       每条 condition/boundary ≥1 evidence，RESTRICT
NO_BASELINE_DRIFT=0      重跑不改变任何已冻结单元
```

新增门 `NO_BASELINE_DRIFT`（任务未列，但 §0.2 的脱钩风险要求它存在）。

---

## 2. Phase P5.1 — Mechanism Extraction Adapter

**裁定：ADAPT，不新增 CandidateType。** 与实测一致：

```
CandidateType = DEFINITION, CLAIM, FACT, CONCEPT, ARGUMENT, MECHANISM
                                              ^^^^^^^^^^ 已声明，无抽取器
```

### 2.1 冻结 schema

```
mechanism_candidate:
    id                    内容派生
    source_ku_id          ★ canonical knowledge_unit.id（P6 之后）
    actor
    initial_state
    action
    transition            ← 见 §2.2
    final_state
    condition[]
    boundary[]
    evidence_ids[]
    status
```

**修正 1 —— `source_ku_id` 必须是 canonical id。** P6 已确立唯一身份，退役 alias
经 resolver 解析。机制表不得直接存 alias id，也不得重新 hash。

**修正 2 —— `transition` 与 `initial_state`/`action`/`final_state` 冗余。**
冻结裁定：三者取其一。推荐保留 `initial_state` / `action` / `final_state` 三列，
删除 `transition` 单字段 —— 单字段无法对三个槽位分别做非空与非锚定检查。

### 2.2 状态机

```
允许 : GENERATED / SUPPORTED / REJECTED
禁止 : VERIFIED
```

理由（任务原文，审计确认）：机制解释仍属语义层。**A仓 不得声称一条机制为真。**

### 2.3 Gate

```
EVIDENCE_REQUIRED = true
ORPHAN            = 0
AUTO_VERIFY       = false
```

`AUTO_VERIFY=false` 与 A仓 既有设计一致：核验只能由核验阶段产生，抽取阶段不得
自带判定。

---

## 3. Phase P5.2 — Relation Layer Design

**这是最大风险项。任务把它标为最大风险项，是对的。**

### 3.1 任务对上一轮审计的两处改进（采纳）

| 改进 | 评价 |
|---|---|
| 改名 `ku_relation` → **`ku_relation_candidate`** | **采纳。** 直接落实「Relation 不是 Knowledge」 |
| `evidence_left[]` / `evidence_right[]` 两个独立数组 | **优于上一轮提议。** 双侧证据从「一条 JSON 里检查」变成**结构上不可能单侧**，检查从运行期移到 schema |

### 3.2 冻结 schema

```
ku_relation_candidate:
    id
    source_ku          canonical knowledge_unit.id
    target_ku          canonical knowledge_unit.id
    relation_type
    evidence_left[]    NOT NULL, 长度 >= 1
    evidence_right[]   NOT NULL, 长度 >= 1
    confidence
    status             GENERATED / ACCEPTED / REJECTED  （无 VERIFIED）
```

### 3.3 关系类型 v0

```
允许 : SUPPORTS / CONTRASTS / DEPENDS_ON / QUALIFIES / EXAMPLE_OF
禁止 : CAUSES / IMPLIES / PROVES / EXPLAINS
```

任务对 `CAUSES` 的禁止比上一轮审计更严（上一轮曾提议带同版本约束的
`CONTRADICTS`）。**采纳更严版。** 因果是因果断言，不是观察到的关系。

### 3.4 ⚠️ 缺失的一条守卫：同 source_version

双端证据解决的是**单侧**。它**不解决跨书**：

```
实测：当前语料 1 本书 / 1 个 source_version（11 个单元全在 sv_f548f51a5df5）
=> 跨书 CONTRASTS 在当前语料上不可测，但规则缺口是真的：
   两本不同作者的书对同一主题给出不同答案，天然 CONTRASTS，
   而这不构成一本书内部的任何矛盾。
```

冻结裁定：

```
R2b  source_ku 与 target_ku 必须同 source_version_id。
     该约束无法由 schema 表达（需跨 knowledge_unit 比较一列），
     与 P6 的 cross_namespace_collisions 同理：
     服务层强制 + gate 读取，测试必须给出跨版本反例。
```

**裁定理由**：P5.2 的全部价值在于「不把语义判断放进 A仓」。若 `CONTRASTS` 可以
跨书成立，它就退化成了「两本书看法不同」，那正是 B仓 的活。

### 3.5 Gate

```
SINGLE_SIDE_RELATION = 0
VERIFIED_RELATION    = 0
ORPHAN               = 0
CROSS_VERSION        = 0   ★ 新增（§3.4）
```

---

## 4. Phase P5.3 — ljg-paper 吸收

**裁定：ADOPT(P2)，不进第一批。** 与任务一致。

### 4.1 冻结 schema

```
contribution_candidate:
    paper_id
    claim
    claimed_by
    evidence_span
    verification_status   FOUND / SUPPORTED / REJECTED
禁止 : IMPORTANT / NOVEL / SIGNIFICANT   （评价词）
```

评价词禁令是本阶段的核心，冻结保留。

### 4.2 ⚠️ 缺口：A仓 没有 source type

实测：

```
book_source 字段 = author, id, isbn, language, metadata, publisher, title
```

字段**足够容纳一篇论文**，但没有任何列断言来源**类型**。因此
`contribution_candidate.paper_id` 与 `book_source.id` 无从区分，两篇同题论文
无法分辨。

冻结裁定：

```
P5.3 落地前必须先有 source type 判定（book_source.metadata 或新增列）。
该缺口在 077/078/079 之外，不占这三个迁移号。
```

---

## 5. Phase P5.4 — ljg-constraint 吸收

**裁定：ADOPT(P1)，补充 boundary。**

```
constraint_candidate:
    type        HARD / SOFT / SELF_DEFINED
    statement
    scope
    evidence_ids[]
```

定义按任务原文冻结：

| type | 定义 | 判据 |
|---|---|---|
| `HARD` | 文本明确限制（"不允许超过 X"） | 跨度含禁止/必须类措辞 |
| `SOFT` | 倾向（"通常情况下"） | 跨度含倾向类措辞 —— **允许 hedger** |
| `SELF_DEFINED` | 作者自己的框架规则 | 跨度明示为本书/本学科的规则 |

**禁止直接成为事实。** 冻结保留。

与 §1.3 的关系：`constraint` 允许 hedger，`condition` / `boundary` 不允许。

---

## 6. Reject List Freeze（永久拒绝进入 A仓）

| 能力 | 原因 | 接受 |
|---|---|---|
| 核心问题 | 读者解释 | ✅ |
| summary | 生成内容 | ✅ |
| answer | 模型输出 | ✅ |
| ranking | 评价 | ✅ |
| importance | 价值判断 | ✅ |
| question bank | 学习层 | ✅ |

七项全部接受冻结。其中 `answer` 与本轮 P5.1/P5.2 的「禁止 VERIFIED」同源：
模型输出与已核验事实，都不是 A仓 的记录。

---

## 7. Schema Migration Plan

**不立即执行 077。** 顺序按任务原文冻结：

```
P5 Design Freeze
   ↓
P5 Architecture Tests
   ↓
077 migration
```

预留编号（实测无冲突，接在 076 之后）：

| 迁移 | 表 |
|---|---|
| `077_a_ljg_condition_boundary.sql` | `ku_condition_candidate` · `ku_boundary_candidate` |
| `078_a_ljg_mechanism_candidate.sql` | `ku_mechanism_candidate` |
| `079_a_ljg_relation_candidate.sql` | `ku_relation_candidate` |

### 7.1 078 先于 079 是安全的 —— 但有一个条件

实测：`mechanism_candidate` 的冻结 schema（§2.1）**不含关系字段**。
因此 078 不依赖 079，次序自洽。

**条件**：若日后给机制加回 `relation_candidate_ids`，078/079 次序必须反转。
该条件写在此处以防后人误加。

### 7.2 命名

`ku_*` 前缀与 A仓 既有 `ku_candidate` / `ku_revision` / `ku_review_event` /
`ku_identity` 一致。**优于上一轮审计提议的 `a_*` 前缀。**

---

## 8. Test Contract

新增：

```
tests/architecture/test_a_ljg_boundary_contract.py
tests/architecture/test_a_mechanism_authority.py
tests/architecture/test_a_relation_authority.py
```

必须验证：

| 维度 | 断言 |
|---|---|
| Authority | `A_AUTHORITY=PASS` |
| Evidence | `ALL_NEW_OBJECTS_HAVE_EVIDENCE=true` |
| Contamination | **不用文本扫描**，改三层检测（见下） |

### 8.1 污染三层检测

任务指定的三层与 A仓 **P7 已实现的形式完全一致**：

```
1 import graph     P7 external_imports()        —— 已在 P7 实现，可直接复用
2 migration FK     P7 schema_change_count() + FK 目标集 —— 可复用其模式
3 runtime artifact P7 artifact_drift()          —— 已在 P7 实现，可复用
```

**不要重写这套门。** 上一轮审计实测：按字面扫描 A仓 源码会得到 **24 处假阳性**，
全部是 A仓 自己的守卫清单（`projection.FORBIDDEN_AUTHORITY`、
`projection_builder.ISOLATED_TABLES`）。A仓 的 P6 与 P7 已经各踩过一次并留下记录。
P5 的三个测试文件应当 import P7 的门，而不是另起一套。

---

## 9. 执行顺序（严格）

```
P5.0  Condition / Boundary          ← 首批，唯一现在可执行
   ↓
P5 Architecture Freeze
   ↓
P5.1  Mechanism
   ↓
P5.2  Relation
   ↓
P5.3  Paper / P5.4 Constraint
```

**不要一次引入全部 ljg。** 冻结保留。

---

## 10. 终局

```
Source → Evidence → Quality → Verification → Frozen KU
      → Condition → Boundary → Mechanism → Relation Candidate → BU2
```

---

## 11. 当前判断

### 11.1 任务给出的判断（原样）

```
STRATUM_A_LJG_IMPLEMENTATION_READY = NO
NEXT_GATE                          = P5_SPEC_FREEZE
FIRST_IMPLEMENTATION               = CONDITION_BOUNDARY_ONLY
```

### 11.2 冻结后的判断（本轮交付后更新）

```
STRATUM_A_P5_LJG_EXTENSION_SPEC     = FROZEN
SPEC_FREEZE                          = YES
P5_SPEC_FREEZE                       = PASSED

首批 CONDITION_BOUNDARY_ONLY         = UNBLOCKED
  · 依赖：仅 077，无前置
  · 强制修正：CONDITION/BOUNDARY 不进 required_slots()（§0.2）
  · 强制限定：只允许 actor / time 作通过因子（§0.3）
  · 新增门  ：NO_BASELINE_DRIFT

P5.1 Mechanism                       = BLOCKED_ON_P5.0
P5.2 Relation                        = BLOCKED_ON_R2b_DESIGN（§3.4 的同版本守卫尚未设计）
P5.3 Paper                           = BLOCKED_ON_SOURCE_TYPE（§4.2）
P5.4 Constraint                      = BLOCKED_ON_P5.0

STRATUM_A_LJG_IMPLEMENTATION_READY   = PARTIAL
  （首个切片可执行；其余三个切片各有未解决的设计缺口）
```

### 11.3 与上一轮审计的一致性

上一轮（`STRATUM_A_LJG_ALIGNMENT_SPEC.md`）的裁定与本 SPEC 逐项一致，并有两处
被本 SPEC 改进：

| 项 | 上一轮 | 本 SPEC |
|---|---|---|
| relation 双端证据 | JSON blob + 运行期检查 | **两个独立数组，schema 级强制** |
| `CONTRADICTS` | 提议带同版本约束 | **改 `CONTRASTS`，且禁 `CAUSES`（更严）** |

另有一处**新增缺口**，由本轮实测发现：CONDITION 五因子里 3 个无抽取器（§0.3），
上一轮未覆盖。

---

## 12. 待你决定的一项

**顶层阶段名**：`A_P5` 已被 `A_P5_KU_EVOLUTION`（075）占用。本文件按 `A_P8`
记录，任务原文的 `P5.0`–`P5.4` 子阶段名保留。迁移号 077–079 不受影响。

STRATUM_A_P5_LJG_EXTENSION_SPEC=FROZEN
P5_SPEC_FREEZE=PASSED
FIRST_IMPLEMENTATION=CONDITION_BOUNDARY_ONLY
