# A P5.2 FREEZE REPORT v1.0

TASK=STRATUM_A_P5_2_RELATION_CANDIDATE_LAYER
BASELINE=P5.1_MECHANISM=FROZEN (078), 077=FROZEN, 075=FROZEN
IMPLEMENTATION_RECORD=A_P5_2_RELATION_SPEC_v0.2
STATUS=FROZEN
SCHEMA=070..079
RELATION_TYPE=PRECEDES_ONLY

---

## 0. 冻结锚点

```
079_a_relation_candidate.sql
  sha256 = 58910b307ea79b1f571415a613a8cae80a6384c07067d45e42d6c368d7307d2f

artifacts/a_repository/p5_2_relation.json
  sha256 = 3c80b47a4657f4d7a8c302f8d4af5ffee5dd94853253c4c1e6f2d18e19829a19
```

075 未被本阶段改动，可独立校验：

```
075_a_ku_evolution.sql
  sha256 = b29432e8340faedc94919811a4b76e8776c81c21e27b936245b4836a747dd7bd
  git diff HEAD -- 075_a_ku_evolution.sql  ->  空
```

DB 侧状态（`stratum_a_p3_staging`）：

```
migrations = 10, newest = 079_a_relation_candidate.sql
relation_rows = 1
baseline units/events/revisions/identities = 11 / 12 / 1 / 11
baseline conditions/boundaries = 6 / 0
mechanisms = 1 / 3      ku_relation = 2 (075, 未动)      source_versions = 1
```

## 1. 冻结契约

### 1.1 产物是什么

`relation_candidate` 记录**一条被声明的关系候选的指纹**：同一本书里两个冻结
knowledge_unit，按声明的先后排列，两侧各自带证据。

```
relation_id   = rlc_4d5a399df2cd
relation_hash = rlh_7d49298f8a2970ef
source_version= sv_f548f51a5df5
relation_type = PRECEDES
extractor     = pilot-declared
status        = GENERATED

left   ku_6460a6062a10  p.1  ev_22f99d11e192  信贷的历史早于工业、银行业与铸币业
right  ku_59cb9040d0f0  p.3  ev_fc56fbbea715  《汉谟拉比法典》（约前1800年）是最早的成文信贷法典之一
```

方向是**声明的**，不是推断的，且实测与书中顺序一致：p.1 < p.3。
`relation_hash` 覆盖 relation_type / source_version / 两侧 unit /
两侧证据 / extractor_version，因此同一对单元换了证据就是另一条关系。

### 1.2 产物不是什么

- 不是语义判断。`CONTRASTS` = 「两个对象存在明确差异/对比」，
  而 075:189-192 已经明确拒绝过这一类值：

  > deciding either is a semantic judgement: it belongs to B仓, and A仓 has no
  > authority to make it.

  `SUPPORTS` / `DEPENDS_ON` 同理。三个类型**不在 079 的 CHECK 里**，
  不是「暂不使用」，而是 raw SQL 也写不进去。
- 不是抽取结果。`extracted_rows = 0`：本阶段**不含抽取器**。
- 不是覆盖。`SUPPORTED` 与 `REJECTED` 都是终态；纠错是追加一条新关系（新 hash）。
- 不是第二套 ku_relation。075 保持不变，见 §2。

### 1.2.1 与 075 冻结关系层的关系（本阶段的核心决策）

A仓 已经有一张关系表：`stratum.ku_relation`（075，已冻结，2 行，
`SHARES_EVIDENCE` / `SAME_SOURCE_SPAN` / `REVISES`）。079 是**并行的第二层**：

```
                ku_relation (075, 冻结)     relation_candidate (079)
relation_type   SHARES_EVIDENCE /           PRECEDES
                SAME_SOURCE_SPAN / REVISES
方向            无向（CHECK from < to）      有向（left/right 各带证据）
source_version  无此列                      NOT NULL
同书约束        无此约束（见 §6.4）         两个复合外键
证据            0 列                        左右各一列，非空 CHECK
```

两套词表**完全不相交**，因此一行不会同时是另一行，也没有优先级规则。
079 刻意不接受任何一条 075 的词表，也不把 `PRECEDES` 反写进 075。

## 2. 075 未被触碰（实测）

```
R8  DELETE FROM stratum.knowledge_unit WHERE id = <relation 的 left_unit>
    -> ERROR violates foreign key constraint "ku_freeze_event_knowledge_unit_id_fkey"
       （073 先拦下，单位本身早已受保护）

R8b ku_relation 的两个外键都是 RESTRICT，指向 knowledge_unit；
    即 075 保护的是「被引用的 unit 不可删」，而不是「ku_relation 行不可删」。
    删除一行 ku_relation 本身合法——它没有子表指向它。
```

`ku_relation_untouched_gate` 与测试 `test_the_frozen_075_relation_layer_is_untouched`
每跑一次读一次 075 的原文，确认其词表里不含任何被推迟的类型。

## 3. KNOWN_LIMITATION（冻结）

以下均为**实测**，不是推测。

1. **DB 层没有状态机守卫。** 直连 SQL 可以把 `SUPPORTED` 改回 `GENERATED`。
   `CHECK` 读不到列的上一个值，所以合法转移只能由 `RelationWriter.transition()`
   把守，「终态」是约定而非约束。
2. **locator 顺序不是 DB 保证。** `PRECEDES` 的方向需要比较
   `reading_evidence`，而 PostgreSQL 拒绝读其它表的 CHECK：
   `ERROR: cannot use subquery in check constraint`。
   方向由 writer gate 把守，并由 `order_gate` 读取。
3. **`TEXT[]` 无法建外键。** 两个 `cardinality >= 1` 只证明数组非空，
   不证明成员是真实行、属于同一本书。由 writer 校验，可追溯率门读取。
4. **冻结的 `ku_relation` 有跨书缺口。** 实测它没有 `source_version_id`，
   也没有同书约束，能写入跨书对。079 补上了这道约束，但**两表严格程度从此不同**。
   修 075 需要 ALTER 已被冻结的迁移，本阶段不做。
5. **抽取质量未测。** 召回率与精确率是未知数，不是「已验证为空」。
   本阶段验收的是持久化、重放、可追溯、隔离。

## 4. 冻结时的验收状态

```
A_P5_2_RELATION_SCHEMA        = PASS
A_P5_2_RELATION_IMPLEMENTATION = PASS

GATE_1_schema / fk_verb / isolation_schema / frozen_index = PASS
GATE_1_constraints / vocabulary / not_null / column_parity / banned_fields = PASS
GATE_2_authority / ku_relation_untouched / baseline_unchanged = PASS
GATE_3_trace / double_side                                    = PASS
GATE_4_replay / idempotency / hash_stability                  = PASS
GATE_5_isolation / order                                      = PASS
GATE_6_negative                                               = PASS  (22 / 22)

relation_persisted = 1     both_sides_evidenced = True
traceability = 100.0%      source_isolation = PASS
replay_stable = PASS       deferred_types_present = 0
self_relations = 0         B/C contamination = 0    BU2 = 0    baseline_mutated = 0
```

`tests/architecture/test_a_relation_authority.py` — 50 passed。
`tests/architecture` 全量 806 passed / 6 skipped。

DB 侧独立验证（不经 Python，直接 psql）：

```
trace        : rows=1 left_evidence_exists=1 right_evidence_exists=1 same_book=1
order_check  : left page 1 < right page 3  holds=true  chapter=第一章 古代时期的信贷
R1 CONTRASTS          -> refused (relation_candidate_relation_type_check)
R2 SUPPORTS           -> refused (同上)
R3 duplicate hash     -> refused (relation_candidate_hash_uniq)
R4 empty evidence     -> refused (relation_candidate_left_evidence_ids_check)
R5 NULL status        -> refused (not-null constraint)
R6 self relation      -> refused (relation_no_self)
R7 cross-book lie     -> refused (relation_left_same_source)   <-- 见 §6.4
R8  delete unit       -> refused (073 的 ku_freeze_event 先拦下)
三个外键 confdeltype 全部 = r (RESTRICT)；指向 A 仓以外的外键 = 0
```

重放：同一份 SQL 连跑 3 次，`relation_candidate` 稳定在 1 行，
`distinct relation_hash` = 1。

回归：`tests/` 与 HEAD 基线**逐项相同**——HEAD 218 项 failed/errored，
本阶段 217 项，差异集合为空（少的一项是
`test_admin_stats_no_secret_env_returns_503`，一个与本阶段无关的环境依赖用例）。
新增 50 个测试全部通过。P5.2 的代码只被自己的测试文件 import。

Ruff 未在本机执行（`ruff` 二进制未安装，`line-length = 100` 已按
pyproject 人工核对：新文件 0 行超长）。

## 5. 决策记录：与提案 v0.2 的偏离

Phase 0 停下后，实测发现两处需要你决定，两处都已决定并落地。

**偏离 1 — 恢复 `extractor_version`（列 + 进入 hash）。**
v0.2 的列清单与 hash 公式都丢掉了它。丢掉之后，本行里就再也没有任何字段
能说明这条关系是抽取的还是声明的；而 `extractor_version` 不进 hash 意味着
未来抽取器对同一对单元、同一批证据跑一次会撞上同一个 `relation_hash`，
被当成 pilot 的重放**静默吞掉**。已恢复为 `relation_extractor_v1` / `pilot-declared`。

**偏离 2 — `SUPPORTED` 为终态。**
v0.2 的箭头图（`GENERATED ↓ SUPPORTED ↓ REJECTED`，`REJECTED terminal`）
允许 `SUPPORTED → REJECTED`，而 v1.0 §9 明确禁止，077/078 也都把
「已支持者不可静默撤销」冻结为理由。已改回：`GENERATED → {SUPPORTED, REJECTED}`，
两者皆终态。

**未偏离但已收紧**（按建议执行）：`status` / `side` 类字段 NOT NULL、
`created_at DEFAULT now()`、两侧各一条 cardinality CHECK。

## 6. Phase 0 实测发现（写 079 之前查出来的）

详见 `A_P5_2_RELATION_SCHEMA_REVIEW.md`。摘要：

### 6.1 `ku_relation` 已存在（BLOCKER，已决策）
A仓 已有 075 的关系层，2 行真实数据，词表不相交。已按你的决策处理为并行第二层。

### 6.2 `CONTRASTS` 与 075 的授权理由冲突（BLOCKER，已决策）
三个语义类型全部推迟出 079 的 CHECK。

### 6.3 `status` / `side` 可为 NULL，CHECK 被绕过
实测 `CHECK (status IN (...))` 在 NULL 上通过，`status IS NULL` 的行能进库
并绕开整个词表。已加 NOT NULL，并在 DB 上以 R5 复验。

### 6.4 §4 同书约束：§10 声称 DB 保证，实测不保证
按 v1.0 §3.1 的单列外键，实测**跨书关系被接受**（两个 unit id 都真实，
`source_version_id` 谎报另一本书）。复合外键实测拦下：

```
ERROR: insert or update on table "relation_candidate" violates foreign key
       constraint "relation_left_same_source"
DETAIL: Key (left_unit_id, source_version_id)=(ku_15a527238f5c, sv_probe2)
        is not present in table "knowledge_unit".
```

复合外键需要一个落点索引：

```sql
CREATE UNIQUE INDEX knowledge_unit_id_source_version_uniq
    ON stratum.knowledge_unit (id, source_version_id);
```

这是 079 对冻结表的**唯一**改动，由你的决策授权。要点：
`(id, source_version_id)` 因 `id` 是主键而**本就唯一**，该索引不声明任何新事实，
不可能在既有数据上失败，它只为复合外键提供落点，代价只有写放大。
`knowledge_unit` 的行、列、值一个都没动。

被否掉的替代方案是 BEFORE INSERT 触发器（同样实测可行），理由：
A仓 070–078 没有任何 trigger 或 function，本阶段不为此引入第一个。

### 6.5 §6 双侧证据无法由 DB 保证（已缓解）
`UNIQUE(relation_id, side)` 能挡「两个 LEFT」，挡不住「只有 LEFT」。
v0.2 改成单表双数组后，两条 `cardinality >= 1` 让「两侧都非空」**成为 DB 保证**
（v1.0 的两行设计做不到），因此这一条在 v0.2 下已经解决。

### 6.6 没有状态机守卫（已冻结为已知限制）
与 P5.1 同级。

### 6.7 一次实测到的失败：索引写在建表之后
首次 apply 失败：

```
ERROR: there is no unique constraint matching given keys for referenced table
       "knowledge_unit"
```

因为 `CREATE UNIQUE INDEX` 写在 `CREATE TABLE` 之后，复合外键没有落点。
DDL 是事务性的，所以整份迁移回滚、什么都没留下——这是好的那一半。
坏的那一半是 psql 包装器仍然退出 0，我据此往 ledger 写了一条**假的** 079 记录，
已发现并删除，ledger 回到 9 条。迁移文件已改为索引先于建表。

## 7. 阶段状态

```
P5_0_CONDITION_BOUNDARY = FROZEN
P5_1_MECHANISM          = FROZEN
P5_2_RELATION           = FROZEN     (PRECEDES_ONLY)
P5_2_PILOT              = 1 relation, extractor = pilot-declared
P5_2_EXTRACTION         = NOT_STARTED（extracted_rows = 0）
P5_2_DEFERRED           = SUPPORTS / CONTRASTS / DEPENDS_ON（B仓 权限问题）
075_ku_relation         = FROZEN，未动
NEXT                    = 抽取器；或先修 075 的跨书缺口（需改冻结迁移）
```

## 8. FINAL REPORT

```
A_P5_2_RELATION      = PASS
MIGRATION_079        = 079_a_relation_candidate.sql
RELATION_TYPE        = PRECEDES_ONLY
RELATION_ROWS        = 1
TRACEABILITY         = 100.0%
SOURCE_ISOLATION     = PASS
REPLAY               = PASS
AUTHORITY_SCAN       = PASS
B_CONTAMINATION      = 0
C_CONTAMINATION      = 0
DB_MUTATION          = 0
BU2_MUTATION         = 0
075_UNTOUCHED        = PASS
COMMIT_SHA           = PENDING
TAG                  = PENDING
FINAL_STATUS         = PASS
```

`COMMIT_SHA` 与 `TAG` 如实写 `PENDING`：本阶段**没有提交**。
冻结报告自己编一个 commit id 比没有更糟，所以这两项等提交时再填
（runner 读 `A_P5_2_COMMIT_SHA` / `A_P5_2_TAG`）。

---

FINAL AUTHORITY:

```
STRATUM_A stores explicit textual relations.
STRATUM_A does not decide meaning.
```