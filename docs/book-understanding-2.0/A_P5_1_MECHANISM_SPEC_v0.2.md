# A_P5_1_MECHANISM_SPEC v0.2 — 冻结

TASK=STRATUM_A_P5_1_MECHANISM
DEPENDENCY=P5.0_CONDITION_BOUNDARY=FROZEN ✓
IMPLEMENTATION=SPEC_ONLY
MIGRATION=078_RESERVED
DB_MUTATION=0
STATUS=FROZEN
SCHEMA=070..077（本阶段不新增迁移）

> v0.2 采纳了 v0.1 的两条实测发现（链式实体、重放指纹）。本文件在冻结前又
> 测出四条，全部写在 §3–§6。**冻结的是定义与判据；四处修正需一并采纳。**

---

## 0. v0.2 的两个核心采纳

| v0.1 发现 | v0.2 处置 | 裁定 |
|---|---|---|
| 单 `knowledge_unit_id` 键无法表达三段链 | 采纳 `mechanism_node` 链式实体 | **采纳，且优于我的建议** —— 我提的是数组键，v0.2 用独立节点表，顺带解决了顺序唯一性与每节点外键 |
| 缺 `mechanism_hash`，重放退回单层守卫 | 采纳 `mechanism_hash TEXT NOT NULL UNIQUE` + 明确公式 | **采纳** |
| 中文因果词不应一律禁 | 采纳 §9「只禁字段污染」 | **采纳，与 P5.0 的 guard 形成对照而非重复** |

## 1. Authority Definition（冻结）

```
Mechanism
  = 从书中显式描述的多个 evidence-linked proposition 中，
    提取事件/状态之间的排列关系

不是：原因解释 · 理论模型 · 作者观点 · 因果判断

MECHANISM_AUTHORITY = A_REPOSITORY
禁止：B_KNOWLEDGE_CLAIM · C_LEARNING_MODEL
```

A仓 / B仓 分工（v0.1 判例，冻结沿用）：

```
A仓 : what happened
B仓 : why it matters

允许 : 利率限制 → 法律规定 → 债务成本变化
不允许 : 利率限制导致经济繁荣            ← 第二个进 B
```

## 2. Chain Entity（冻结）

```
mechanism_candidate
        |
   +----+----+
   |    |    |
  KU-A  KU-B  KU-C        每个节点一个 role、一个顺序、一个自己的证据
```

节点角色固定：`TRIGGER` / `TRANSITION` / `RESULT`，每种 `>= 1`。

节点表同时解决了 v0.1 的三个问题：

| v0.1 问题 | v0.2 的解决方式 |
|---|---|
| 单单元键装不下三段 | 链式实体 |
| 「无序数组推断」被禁 | `sequence_order` 列 + 节点表 |
| 每 node 需各自锚定 | 节点持有 `knowledge_unit_id`（外键）与 `evidence_ids[]` |

## 3. ⚠️ 冻结前测出 1 — `sequence_order` 缺唯一约束

v0.2 声明了 `sequence_order`，但未声明 `UNIQUE(mechanism_id, sequence_order)`。
顺序因此可歧义：两个节点可同号，而 §7 要求「禁止无序数组推断」。

**A仓 已有现成模式（075，两处）：**

```
ku_review_event_seq_uniq      UNIQUE(knowledge_unit_id, sequence)
ku_confidence_seq_uniq        UNIQUE(knowledge_unit_id, sequence)
```

**冻结裁定**：`CONSTRAINT mechanism_node_order_uniq UNIQUE (mechanism_id,
sequence_order)`。这不是新发明，是把 075 已确立的模式搬到新表。

## 4. ⚠️ 冻结前测出 2 — `ACCEPTED` 与已冻结的 077 不一致

实测全部 A 迁移的 status 词表：

```
077  CHECK (status IN ('GENERATED','SUPPORTED','REJECTED'))   ← 唯一先例
ACCEPTED 在 070–077 全部 A 迁移中出现 0 次
```

v0.2 提议 `GENERATED / ACCEPTED / REJECTED`。同一个生命周期位置、两个词、
两张相邻的表。

**冻结裁定：P5.1 用 `SUPPORTED`，不用 `ACCEPTED`。**

理由是成本方向：077 已冻结，冻结报告写明「冻结期内 077 不再修改」。若 P5.1
选 `ACCEPTED`，统一它就需要一个改动 077 的迁移 —— 而那正是冻结要禁止的。
反过来 P5.1 用 `SUPPORTED` 不需要动任何已冻结的东西。

**同时保留一条约束**（v0.2 原文，冻结采纳）：`CONFIRMED` 一并禁止。
`VERIFIED` 在 A仓 有确切含义 —— `ku_verification.verification_status` 的成功值
（072、073 各有一处）。让同一个词在另一张表里表示别的东西，是 P6 那类
「一个对象两个身份」的同源问题。

## 5. ⚠️ 冻结前测出 3 — §10 允许 BU2 表作外键目标，方向反了

v0.2 §10 写 `FK target: 允许 A tables / BU2 frozen tables`。

**这与 A仓 至今确立的方向相反。** 权威链是单向的：

```
A仓  ──> BU2          A 产出，BU2 消费
```

A仓 的表若外键指向 BU2，BU2 的存在就成为 A仓 的前提 —— 下游反过来绑住上游，
而 `No downstream overwrite` 与「BU2 是 A仓 的消费者」都不成立。

**而且它不需要。** 实测 A仓 已经自带章节身份：

```
evidence.locator.chapter = {'第一章 古代时期的信贷'}
```

§11 的 pilot 限定在《利率史》第一章，A仓 自己就知道那是哪一章，一个 BU2
外键都换不来任何东西。

**冻结裁定：078 的外键目标限定为 A 表**（`source_version`、`knowledge_unit`）。
若日后确有跨 BU2 的需求，那是另一个阶段、另一个方向的决定。

## 6. ⚠️ 冻结前测出 4 — pilot 行必须标为「声明」而非「发现」

链式键解决了 v0.1 的阻塞：实测当前语料在**一个** source_version 内有
**10 个** current 单元，链在结构上可表达。

但抽取器仍然找不到链 —— 跨度子句数实测 `{1: 9, 2: 1}`，没有一条跨度能给
出三段。所以：

```
表能装链     ✓
抽取器找得到  ✗
```

v0.2 §11 把 pilot 范围限定为「chain persistence / replay / traceability」而
**不是抽取质量** —— 这个限定是对的。但它有一个后果必须写明：

> **pilot 写入的链是「声明」的，不是「发现」的。** 若不标注，它们会以抽取结果
> 的面目留在表里，而这正是本仓要防的那类污染。

**冻结裁定**：pilot 链使用可辨识的 `extractor_version`
（`pilot-declared` 而非任何抽取器版本号），并由门断言 pilot 行与抽取行可区分。
这样 pilot 验证的是**持久化契约**，而表里没有任何一行冒充抽取产物。

## 7. 中文因果词规则（冻结，沿用 v0.2 §9）

```
不禁：因为 · 导致 · 所以 · 造成        它们可能是书中文字
只禁：字段污染
```

判例（v0.2 原文，冻结）：

```
错误 : {"effect": "经济繁荣"}
正确 : {"result_event": "经济繁荣"}
```

**这与 P5.0 的 guard 是对照而非重复**，需要写清楚区别，否则日后会被当成矛盾：

| 层 | 对象 | 对因果词的态度 | 理由 |
|---|---|---|---|
| P5.0 condition | 跨度里的**可验证前提** | 禁 | 前提不可被「导致」这类词表述 |
| P5.1 mechanism | 跨度里的**事件链** | 不禁，但字段名不含因 | 事件链的自然词汇就是因果词汇；纪律由字段语义与结构承担 |

v0.2 的分层是对的：**字段语义为主**（无 `cause`/`effect`/`explanation`/`proof`
列）＋ **结构要求为主**（每节点各自锚定）＋ 词表禁令只管污染注入。

## 8. Replay Contract（冻结）

```
mechanism_hash = sha256(
      source_version_id
    + ordered_node_ids
    + evidence_fingerprints
    + extractor_version)

第一次 : insert mechanism + insert nodes
第二次 : NOOP
要求   : duplicate = 0
```

**派生顺序必须冻结，否则会重演 P6 的双 id 病。** 三步无循环：

```
1. mechanism_id  = f(source_version_id, ordered_ku_ids, extractor_version)
2. node_id       = f(mechanism_id, node_role, sequence_order, knowledge_unit_id)
3. mechanism_hash = 上述 §8 公式（第 2 步之后才可计算）
```

`mechanism_id` 与 `mechanism_hash` 是两个派生值，与 P5.0 的
`id = kcc_(unit,type,statement)` / `condition_hash = kch_(…,evidence)` 同一模式：
**id 是抽取的身份，hash 额外覆盖证据**，所以证据变了机制会被重新抽取。
这一致性经核实成立，不是本阶段的新发明。

## 9. Evidence Ordering（冻结）

```
TRIGGER     sequence = 1
TRANSITION  sequence = 2
RESULT      sequence = 3
禁止        : 无序数组推断
```

由 §3 的 `UNIQUE(mechanism_id, sequence_order)` 强制，而非由约定。

## 10. Schema（冻结，含四处修正）

```
078_a_mechanism_candidate.sql

mechanism_candidate
    id                  TEXT PK          内容派生，见 §8
    source_version_id   -> source_version(id) ON DELETE RESTRICT
    mechanism_hash      NOT NULL UNIQUE
    status              CHECK ('GENERATED','SUPPORTED','REJECTED')   ← §4
    extractor_version   NOT NULL
    created_at          TIMESTAMP NOT NULL

mechanism_node
    id                  TEXT PK
    mechanism_id        -> mechanism_candidate(id) ON DELETE RESTRICT
    knowledge_unit_id   -> knowledge_unit(id) ON DELETE RESTRICT
    node_role           CHECK ('TRIGGER','TRANSITION','RESULT')
    evidence_ids[]      NOT NULL, CHECK (cardinality(evidence_ids) >= 1)
    sequence_order      NOT NULL CHECK (sequence_order >= 1)
    created_at          TIMESTAMP NOT NULL
    CONSTRAINT mechanism_node_order_uniq UNIQUE (mechanism_id, sequence_order)
```

- additive only：禁 `ALTER ku_candidate` / `ALTER ku_verification` / `ALTER BU2`
- 外键目标**仅限 A 表**（§5）
- **`cardinality()`，禁 `array_length()`** —— 该陷阱已实测过一次：
  `array_length(ARRAY[]::text[],1)` 是 NULL，CHECK 在 NULL 上通过，空数组被接受

## 11. Schema-Enforceable vs Service-Enforced

与 P5.0 的 `KNOWN_LIMITATION 1` 同类问题，逐条列明而不含糊：

| 约束 | schema 能保证吗 |
|---|---|
| 三种 role 各 `>= 1` | **不能** —— 需跨表计数。服务强制 + 门读取 |
| 空链（零节点） | **不能** —— 一个无节点的 mechanism 行是可达状态。服务强制 + 门读取 |
| `evidence_ids[]` 非空 | **能** —— `cardinality() >= 1`（已实测有效） |
| 节点 `sequence_order` 唯一 | **能** —— `UNIQUE(mechanism_id, sequence_order)` |
| `status` 无 VERIFIED | **能** —— 封闭 CHECK |
| 节点 `knowledge_unit_id` 存在 | **能** —— 外键 RESTRICT |

**P5.1 新增 KNOWN_LIMITATION：**

```
KNOWN_LIMITATION 5 (P5.1)
  chain completeness is service-enforced
  三种 role 各 >=1 与「非空链」无法由 schema 表达：
  CHECK 约束不能跨表计数，一个零节点的 mechanism 行在数据库里是可达状态。
```

## 12. Contamination Gate（冻结）

**第四次不做文本扫描。** 扫源码会命中 A仓 自己的守卫清单（P6/P7 各踩过一次，
实测 24 处假阳性）。

```
1 Import   : mechanism 模块不得 import B/C
2 Migration: FK 目标必须是 A 表（§5）
3 Artifact : 产物不得出现 knowledge_claim / concept / learning_objective
```

## 13. Acceptance Gates（冻结）

| Gate | 要求 |
|---|---|
| 1 Schema | `mechanism_candidate` 存在 · `mechanism_node` 存在 · FK 正确 |
| 2 Trace | mechanism → node → KU → evidence **100%** |
| 3 Replay | 重复执行 `new mechanism=0` `new node=0` |
| 4 Authority | B mutation=0 · C mutation=0 |
| 5 Negative | 空链拒 · TRIGGER-only 拒 · 无 evidence 拒 · `VERIFIED` 拒 · 空数组拒（`cardinality`） |

测试文件：`tests/architecture/test_a_mechanism_authority.py`

**空数组那条必须在真实数据库上验过一次。** P5.0 实测证明 schema 层的空数组
守卫曾经无效且不连库的单元测试无法证伪；因此该探针在应用 078 后由一次 psql
确认，而不是只靠单元测试。

## 14. Migration 078 Preconditions

```
P5_0_FREEZE=PASS             ✓ 已满足
MECHANISM_SPEC=FROZEN        ✓ 本文件
SCHEMA_REVIEW=PASS           待：采纳 §3 §4 §5 三处修正后复核
TEST_CONTRACT_READY=PASS     待：测试文件就绪
```

**未全部满足前：`078_NOT_READY`。**

## 15. Pilot 范围（冻结）

```
书   : 利率史（第四版）
章   : 第 1 章「古代时期的信贷」
目标 : 验证 chain persistence / replay / traceability
不是 : 验证抽取质量
```

Pilot 链以 `extractor_version = 'pilot-declared'` 写入，**声明而非发现**（§6）。

## 16. 冻结

```
P5.0_CONDITION_BOUNDARY = FROZEN
P5.1_MECHANISM          = SPEC_FROZEN
078                     = BLOCKED_UNTIL_SCHEMA_REVIEW
P5.2_RELATION           = BLOCKED
P5.3_PAPER              = BLOCKED
P5.4_CONSTRAINT         = BLOCKED
```

采纳 §3、§4、§5 三处修正并完成 `SCHEMA_REVIEW` 之后，才允许写 078。
本文件**不授权**任何迁移执行。

## 17. 未随 v0.2 解决的问题

**抽取器在当前语料上找不到链。** 链式键让表能装链（实测一个 source_version 内
10 个 current 单元），但跨度仍是单子句（`{1:9, 2:1}`）。pilot 按 §15 只验持久化
契约，所以这不是阻塞项；但**「机制抽取有效」这件事在本书上尚未被验证过一次**，
不应在报告里被含糊过去。扩抽取粒度属 P1/P3，不在本阶段范围。
