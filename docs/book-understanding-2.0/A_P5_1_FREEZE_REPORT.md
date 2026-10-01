# A P5.1 FREEZE REPORT v1.0

TASK=STRATUM_A_MECHANISM_CHAIN
BASELINE=STRATUM_A_P5_0_CONDITION_BOUNDARY (FROZEN, 077)
IMPLEMENTATION_RECORD=A_P5_1_MECHANISM_SPEC.md
STATUS=FROZEN
SCHEMA=070..078

---

## 0. 冻结锚点

```
078_a_mechanism_chain.sql
  sha256 = ed963f7e82854b047efe31287e88489d22997a0068586b1c0267aaf1e8d413b2

artifacts/a_repository/p5_1_mechanism.json
  sha256 = bf036fe5f26cfd8a2e7a2f6f438f67bcd68c22e4983a7a955999f11d1e59fd53
```

P5.0 的两个哈希继续有效，本阶段未改动 070–077 中的任何一个。

DB 侧状态（`stratum_a_p3_staging`）：

```
migrations = 9, newest = 078_a_mechanism_chain.sql
mechanism_rows = 1    node_rows = 3
baseline units/events/revisions/identities = 11 / 12 / 1 / 11
baseline conditions/boundaries = 6 / 0
```

## 1. 冻结契约

### 1.1 产物是什么

`mechanism_candidate` 记录**一个被声明的机制链的指纹**，`mechanism_node`
记录这条链**按阅读顺序排列的三个跨度**，每个跨度各自锚定一个冻结
knowledge_unit 与其证据。

链的身份由内容导出，不由生成时刻决定：

```
mechanism_id     = mec_0feb304c720b
mechanism_hash   = meh_39d54f61b77cd81b
source_version   = sv_f548f51a5df5
extractor_version= pilot-declared
status           = GENERATED

1 TRIGGER     ku_6460a6062a10  p1  ev_22f99d11e192  men_6631fe0db330
2 TRANSITION  ku_93a979cb6fab  p6  ev_291e662405a9  men_8cd152d9f602
3 RESULT      ku_5840cc146f9f  p7  ev_d862c5f48966  men_8a0bb2fa8539
```

顺序是**声明的**，不是推断的：`sequence_order` 与页序一致，且参与
`node_id` → `mechanism_hash` 的派生，因此调换顺序会产生另一条链。

### 1.2 产物不是什么

- 不是 knowledge claim，不是 verified fact。A仓 描述**发生了什么**；
  「这为什么重要」是 B仓 的事。
- 不是因果解释。字段名里没有 cause / effect / because，
  `MECHANISM_BANNED_FIELDS` 把它们列成禁止项并有门在查。
- 不是抽取结果。`extracted_rows = 0`：本阶段**不含抽取器**。
  唯一的链是人工声明的，`extractor_version = pilot-declared`，
  与未来的 `mechanism_extractor_v1` 在类型上就不可能混淆。
- 不是覆盖。链不改写：纠错是追加一条新链（新 hash），不是降级旧链。

### 1.3 词表（冻结）

```
status    : GENERATED / SUPPORTED / REJECTED
node_role : TRIGGER / TRANSITION / RESULT
转移      : GENERATED → SUPPORTED | REJECTED
            SUPPORTED → ∅（终态）
```

`VERIFIED` 是 `ku_verification` 的成功值，`CONFIRMED` 是同一件事的第二个
词。两者都不进机制表——一处事实一个词。

## 2. KNOWN_LIMITATION（冻结）

以下三条是**实测**得到的，不是推测。均在 `stratum_a_p3_staging` 上跑过 SQL。

1. **DB 层没有状态机守卫。** 实测 `UPDATE ... SET status='SUPPORTED'` 成功。
   合法转移由 `MechanismWriter` + `transition()` 把守，
   `SUPPORTED` 的终局性是**约定**，不是约束。绕过 writer 直连 SQL 可以降级。
2. **`UNIQUE(mechanism_id, sequence_order)` 不禁止跳号。** 实测在
   sequence 3 之后插入 9 被接受（1,2,3,9 合法）。连续性由服务层保证。
3. **`evidence_ids TEXT[]` 无法建外键。** DB 只能查
   `cardinality >= 1`；证据是否真实存在、是否属于同一本，由服务层校验。

继承自 P5.0 的第 4 条：

4. **链完整性无法由 CHECK 保证。** `CHECK` 数不了另一张表的行，
   因此「三个角色齐全」是 `chain_is_complete()` 的职责（`KNOWN_LIMITATION 5`）。
5. **抽取质量未测。** 召回率与精确率是未知数，不是「已验证为空」。
   本阶段验收的是**持久化、重放、可追溯**，不是抽取。

## 3. 冻结时的验收状态

```
A_P5_1_MECHANISM_SCHEMA        = PASS
A_P5_1_MECHANISM_IMPLEMENTATION = PASS

GATE_1_schema / fk_verb / constraints / column_parity / banned_fields = PASS
GATE_2_trace / completeness                                            = PASS
GATE_3_replay / idempotency                                            = PASS
GATE_4_authority / baseline_unchanged                                  = PASS
GATE_5_negative                                                        = PASS

mechanism_persisted   = 1        nodes_ordered  = True
evidence_linked       = 100.0    traceability   = 100.0
replay_stable         = PASS     transaction_atomic = PASS
negative_refusals     = 15 / 15 negative_cases
B_CONTAMINATION = 0    C_CONTAMINATION = 0    BU2_DEPENDENCY = 0
baseline_mutated = 0
```

`tests/architecture/test_a_mechanism_authority.py` — 45 passed。

DB 侧独立验证（不经 Python，直接 psql）：

```
nodes=3  ku_exists=3  has_evidence=3  evidence_exists=3  same_book=3
R1 VERIFIED status        → refused  (mechanism_candidate_status_check)
R2 duplicate hash         → refused  (mechanism_candidate_hash_uniq)
R3 empty evidence_ids     → refused  (mechanism_node_evidence_ids_check)
R4 duplicate order        → refused  (mechanism_node_order_uniq)
R5 undeclared role        → refused  (mechanism_node_node_role_check)
R6 delete a mechanism     → refused  (RESTRICT, 非 CASCADE)
R7 node on non-durable KU → refused  (mechanism_node_knowledge_unit_id_fkey)
三个外键 confdeltype 全部 = r (RESTRICT)；指向 BU2/B/C 的外键 = 0
```

重放：同一份 SQL 连跑 3 次，`mechanism_candidate`/`mechanism_node`
稳定在 1/3，`distinct mechanism_hash` = 1。

回归：`tests/architecture` 756 passed / 6 skipped。
全量 `tests/` 与 HEAD 基线**逐项相同**——48 failed / 170 errors / 25 skipped，
P5.1 引入 0 个新失败（那 48/170 是 `aii` / `scripts` 包缺失的既有状态，
HEAD 上同样存在）。P5.1 的代码只被自己的测试文件 import。

Ruff 未在本机执行（`ruff` 二进制未安装，`line-length = 100` 已按
pyproject 人工核对：新文件 0 行超长）。

## 4. 078 已应用

```
070_a_repository_foundation.sql   075_a_ku_evolution.sql
071_a_evidence_quality.sql        076_a_ku_identity.sql
072_a_ku_verification.sql         077_a_condition_boundary.sql
073_a_knowledge_unit_freeze.sql   078_a_mechanism_chain.sql
074_a_ku_freeze_persistence.sql
```

078 是**纯新增**：两张表、两个索引、四个外键、四个 CHECK。
文件内不含 `ALTER TABLE` / `DROP` / `UPDATE` / `INSERT`，
070–077 的任何一张表都没有出现在 078 里。

## 5. P5.0 §7 两条实测发现的处置

P5.0 冻结时留下两条必须在 078 之前决定的问题。两条都已按实测证据处置。

**发现 1 —「当前语料无法供给三段式」→ 采纳出路 (a)。**
实测每个锚定跨度的子句数为 `{1: 9, 2: 1}`，三个子句的跨度为 0。
以**单个** `knowledge_unit_id` 为键的 schema 必然是空表。
078 因此不以单元为键，而以**单元链**为键：`mechanism_node` 一行一个跨度，
`UNIQUE(mechanism_id, sequence_order)` 定序，三个节点跨三个单元。
这正是实测可行的形态——链本身可以跨单元，粒度问题不再阻塞 P5.1。

**发现 2 —「提案 schema 缺重放指纹」→ 已补齐。**
实测 073–077 每张表都带 hash 与 UNIQUE。078 保持同一做法：

```
mechanism_hash UNIQUE  +  内容导出的 id  +  ON CONFLICT DO NOTHING
```

P4.1 认定单层守卫不够，因此是双重强制：服务层前置检查 + 写入方
`ON CONFLICT DO NOTHING`。实测连跑 3 次写 0 行。

## 6. 与提案 schema 的三处偏离（需要你确认）

实现过程中实测发现提案 schema 有三处与 A仓 既成事实冲突，改动如下。
三处都记录在这里，因为它们改变契约，不属于实现细节。

1. **`mechanism_node.mechanism_id` 由提案的 `ON DELETE CASCADE` 改为
   `RESTRICT`。** 实测 070–077：CASCADE 只出现在 070–072 的抽取链
   （删一本书应带走它的证据）；073 之后的每张冻结表都是 RESTRICT，
   且 073 在迁移注释里写明了理由。机制链是冻结产物，
   在 A仓 做第一个「删父静默带走子」的地方不合适。R6 已实测拒绝删除。

2. **不写 `ku_freeze_event`。** 提案的事务契约第 3 步要求插入冻结事件，
   但 074 的词表是 `CREATED/FROZEN/SUPERSEDED` + `FREEZE_PENDING/FROZEN/FAILED`，
   机制状态放不进去，事件哈希的输入也随之含混。P5.0 的先例是把生命周期
   放在候选表自己的 `status` 上，078 沿用。**这是与提案的一处实质偏离**，
   不是遗漏。

3. **不做「一个机制一行」的扁平 schema。** 见 §5 发现 1。

## 7. 状态

```
P5_0_CONDITION_BOUNDARY = FROZEN
P5_1_MECHANISM          = FROZEN
P5_1_PILOT              = 1 chain / 3 nodes, extractor=pilot-declared
P5_1_EXTRACTION         = NOT_STARTED（extracted_rows = 0）
P5_2_RELATION           = BLOCKED
P5_3_PAPER              = BLOCKED
P5_4_CONSTRAINT         = BLOCKED
NEXT                    = 决定 §6 的三处偏离是否接受；之后才谈抽取
```