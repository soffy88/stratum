# A P5.5 FREEZE REPORT v1.0

TASK=STRATUM_A_P5_5_082_PAPER_EVIDENCE_COMPOSITE_FK_REPAIR
BASELINE=P5.4_CONSTRAINT=FROZEN (081), 080/079/078/077/075=FROZEN
SPEC=STRATUM_A_P5_5_082_PAPER_EVIDENCE_COMPOSITE_FK_REPAIR_SPEC v1.0
STATUS=FROZEN
SCHEMA=070..082
ROWS_MUTATED=0

---

## 0. 冻结锚点

```
082_a_paper_evidence_composite_fk.sql
  sha256 = db3aa8f3f7673c20d0b99efad2b06026a1b7ffbe9b5f160d5bfa098173433cb2

artifacts/a_repository/p5_5_082_paper_evidence_fk.json
  sha256 = 29035b9c17c3ab0765227cdf61abf1fee4c674db532e791dbe9cd1f044673c28
```

被修复的两个冻结锚点**逐字节不变**，`git diff HEAD` 为空：

```
080_a_paper_source.sql          6215e46078709bc8fc8548ccaa7de218024ba7e44dc917f16ed69f4d6312bfd5
081_a_constraint_candidate.sql  0e9ebc2ddc443412fe9c0203ab3a7150fd7b02d0034c9368e126483283069f4e
```

DB 侧状态（`stratum_a_p3_staging`）：

```
migrations = 13, newest = 082_a_paper_evidence_composite_fk.sql
paper_source_candidate = 1    paper_evidence = 4    （ROWS_MUTATED = 0）
baseline units/events/revisions/identities = 11 / 12 / 1 / 11
```

## 1. 关闭的缺口

080 给 `paper_evidence` 两个**各自独立**的外键：

```
paper_id          -> paper_source_candidate(id)
catalog_source_id -> book_source(id)
```

两者**同时**被一个跨 catalog 的声明满足。修复前实测：

```
INSERT INTO paper_evidence (paper_id = <candidate A>,
                            catalog_source_id = <另一本 catalog 行>)
=> ACCEPTED
```

即：一条声明可以声称由某个 candidate **并不拥有**的编目记录做出。
writer 拦住了它（`DECLARATION_OTHER_CATALOG_ROW`），所以这种行从未被写入；
但 schema 允许它。**允许损坏的 schema 就是洞，与当前 writer 恰好绕开无关。**

修复后（psql 实测）：

```
CASE_1  paper_id 真实 + catalog_source_id 是别本 catalog   -> FK violation
CASE_2  未知 paper_id                                        -> FK violation
CASE_3  未知 catalog_source_id                              -> FK violation
CONTROL paper_id 与 catalog_source_id 相符                  -> ACCEPTED
```

`CONTROL` 这一条同样重要：只会拒绝一切的规则不是修复，是对 writer 的拒绝服务。

## 2. A仓 的第一个 ALTER

078–081 全部纯新增：`CREATE TABLE` / `CREATE INDEX`，无 ALTER。
082 是 A仓 第一条 `ALTER TABLE`，范围只有一个子句：

```sql
ALTER TABLE stratum.paper_evidence
    ADD CONSTRAINT paper_evidence_same_catalog_source_fk
    FOREIGN KEY (paper_id, catalog_source_id)
    REFERENCES stratum.paper_source_candidate (id, book_source_id)
    ON DELETE RESTRICT;
```

加的是**一条规则**，不是一行、一列、一个值。
`ALTER COLUMN` / `DROP` / `RENAME` / `UPDATE` / `DELETE` / `NOT VALID`
在可执行语句中全部为 NONE（逐条实测，见 §5）。

选择触发器之外的这条路的理由：触发器与 function 都被 spec 禁止，
而 composite FK 是声明式的、零运行期开销、并且可正常 drop。
留下这道约束仅由服务层保证，等于让 schema 永久接受一个已知的损坏路径。

## 3. 两步顺序是承重的

外键需要被引用列上的唯一覆盖。实测 079 与 080 都撞过：

```
ERROR: there is no unique constraint matching given keys for referenced table ...
```

所以 STEP 1 必须在 STEP 2 之前：

```
STEP 1  CREATE UNIQUE INDEX IF NOT EXISTS paper_source_candidate_id_book_source_uniq
            ON stratum.paper_source_candidate (id, book_source_id);
STEP 2  ALTER TABLE ... ADD CONSTRAINT ...
```

`(id, book_source_id)` 因 `id` 是主键而**本就唯一**，该索引不声明任何新事实、
不可能在既有数据上失败，只为复合外键提供落点。

## 4. 既有数据由 DDL 自身验证

`ADD CONSTRAINT` 加外键时，除非声明 `NOT VALID`，PostgreSQL 会校验每一行既有数据。
所以 **082 就是它自己的 GATE_2**：若库中存在任何跨 catalog 的声明，
下面的 ALTER 会中止、整个迁移回滚、什么都不留下。

写 082 之前实测：4 条既有声明全部满足该约束。

```
rows=4  tie_holds=true  paper_id_all_exist=true  catalog_all_exist=true
```

`NOT VALID` 被显式禁止，并由测试断言（`test_no_destructive_statement`）
——它会跳过这一步校验，正是把 GATE_2 关掉。

## 5. 冻结时的验收状态

```
082_ACCEPTANCE = PASS

GATE_1_schema / index_target / two_objects      = PASS
GATE_1_index_present / constraint_present       = PASS
GATE_1_no_new_lifecycle / rows_unmutated        = PASS
GATE_2_existing_data / baseline                 = PASS
GATE_3_negative                                  = PASS  (4 / 4)
GATE_4_replay                                    = PASS
GATE_5_authority                                 = PASS

same_catalog_accepted   = True
cross_catalog_refused   = True
unknown_paper_refused   = True
unknown_catalog_refused = True
rows_mutated = 0    FK_OUTSIDE_A = 0
B_CONTAMINATION = 0    C_CONTAMINATION = 0    BU2_DEPENDENCY = 0
```

`tests/architecture/test_a_paper_evidence_fk_repair.py` — 27 passed。
`tests/architecture` 全量 943 passed / 6 skipped。

重放（显式执行第二次）：

```
duplicate_objects=0  index_present=1  constraint_present=1
second_run_refused=1  reported_already_applied=1
=> MIGRATION_ALREADY_APPLIED，且无重复对象
```

STEP 2 没有 `IF NOT EXISTS`（PostgreSQL 不提供），惯用的 `DO` 块包装
等于引入一个匿名 function，而本项目不向 A仓 引入 function。
因此第二次执行**预期失败**并给出 `already exists`——这个失败就是信号，
被门读作 `MIGRATION_ALREADY_APPLIED`，而不是被读作静默 no-op。

## 6. 过程中我自己造成并修掉的三个问题

按纪律如实记录，不修饰。

**问题 1 — 门在“只读”的时候执行了 DDL。**
第一版 runner 把「执行一次迁移以观察重放行为」写进了 `replay_gate()`。
我为了看“apply 之前”的门状态而跑了一次，**结果那次跑把 082 应用了**，
而 ledger 还停在 081——与 079 那次假账同一类错误。

修法不是补一条 ledger，而是改门本身：
`replay_gate()` 默认**只读**，第二次执行需要显式 `A_P5_5_EXECUTE_REPLAY=1`。
一个会改变被验证对象的验证步骤是陷阱，不该只是被小心使用。
ledger 随后补记为 13 条。

**问题 2 — psql 输出解析把所有计数比较变成 FAIL。**
门用 `splitlines()[-1]` 取返回值，但 psql 还会打印表头线和 `(1 row)`，
于是「最后一行」永远是 `(1 row)`。
修法是加 `-t -A`（只输出元组、不对齐）。

**问题 3 — 我自己的禁止词表禁止了 spec 要求的子句。**
`GATE_1_schema` 的破坏性动词检查含 `"DELETE "`（带尾空格），
而它会匹配 082 **必须**写的 `ON DELETE RESTRICT`，于是这道门拒绝了修复本身。
与 077 的 `array_length`、以及 `locator`/`location`、`content`/`content_span`
是同一类子串陷阱。
修法：破坏性动词只在**语句首 token** 位置判定，
而 `ALTER COLUMN` / `NOT VALID` 仍在任意位置判定（它们没有合法出场）。
三种子串陷阱同一个根因：**用子串包含去检查语法**。

## 7. 回归

`tests/` 的 failed/errored 集合与 P5.4 冻结时**逐项相同**（217 项，新增集合为空）。
P5.0–P5.4 五层的测试全部保持 FROZEN 且通过。

## 8. 已知限制的变更

```
关闭：P5.3 §3.3
      paper declaration catalog ownership
      was: service enforced only
      now: database enforced

不变：P5.3 其余限制、P5.4 全部限制
```

## 9. 阶段状态

```
070..081  FROZEN，逐字节未动
082       FROZEN（本次新增：1 索引 + 1 复合外键，0 行变更）
P5.0..P5.4 FROZEN
STRATUM_A_P5_EXTENSION_FREEZE = PASS

NEXT_ALLOWED_WORK = 由你决定
  · 摄取侧：p4/p5/p7 三条禁止性跨度没有冻结 KU（P4.x 范围，非 P5.x）
  · 抽取器：任何一层的首个真实 extractor
  · 082 同类：若还有 service-only 的约束值得提升为 declarative
```

## 10. COMMIT GATE

```
TASK             = STRATUM_A_P5_5_082_PAPER_EVIDENCE_COMPOSITE_FK_REPAIR
MIGRATION        = 082_a_paper_evidence_composite_fk.sql
DB_MUTATION      = staging only
ROWS_MUTATED     = 0
NEW_INDEX        = 1
NEW_FK           = 1
ALTER_SCOPE      = ADD_CONSTRAINT_ONLY
BASELINE         = 11/12/1/11
A_CONTAMINATION  = 0
B_CONTAMINATION  = 0
C_CONTAMINATION  = 0
FINAL_STATUS     = FROZEN
COMMIT_SHA       = PENDING
TAG              = PENDING
```

`COMMIT_SHA` 与 `TAG` 如实写 `PENDING`：本阶段**没有提交**。

---

FINAL AUTHORITY:

```
STRATUM_A records nothing new.
STRATUM_A only stopped tolerating a corruption.
```