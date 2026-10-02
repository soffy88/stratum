# A_P6_IDENTITY_REFREEZE_SPEC

VERSION=v1.1
STATUS=APPROVED
TASK=A_P6_IDENTITY_REFREEZE
APPROVED_DECISION=A_P6_IDENTITY_REFREEZE_DECISION
BASELINE=STRATUM_A_P5_EXTENSION_FREEZE (`6265038`, tag `stratum-a-p5-freeze`)
DECISION=OPTION_A / REFREEZE_EXISTING_IMPLEMENTATION

> 本文只做两件事：**冻结事实边界**，以及**裁定冻结对象的定义**。
> 不写实现，不写迁移，不写测试。实现要等本 SPEC 被接受之后。
>
> v1.1：已按 `A_P6_IDENTITY_REFREEZE_DECISION` 接受，§10 记录裁定结果与实施状态。

---

## 0. 裁定

```
DECISION = OPTION_A / REFREEZE_EXISTING_IMPLEMENTATION
```

不采用 OPTION_B（supersede）。理由是实测出来的，不是偏好：

- `076` 的设计与本项目 073–082 的约定一致：纯新增、单表、无 `ALTER`、
  `ON DELETE RESTRICT`、闭词表、`UNIQUE` 指纹。
- 它已应用到 staging，11 行数据，重放写 0 行。
- 它有两个真实的 bug **已经被执行发现并修好**（缺 `id` 列、再缺 `identity_hash`
  列），并留下了列一致性常设测试。
- 没有任何东西需要被取代。

需要取代的是一个**验收口径**，不是实现：见 §3 F3。

---

## 1. 事实边界（本次审计实测）

### 1.1 已存在的事实

```
076_a_ku_identity.sql         sha256 2b9de6b42e1c1d87…   已应用，committed
stratum.ku_identity           11 行                        alias_kind 全为 FREEZE_LEGACY
identity_version              a-p6-v0.1
A_P6_KU_IDENTITY_SPEC.md      存在，未 commit
A_P6_FREEZE_REPORT.md         存在，未 commit
test_a_repository_p6_identity.py  95 tests，全绿，未 commit
artifacts/a_repository/p6_ku_identity.json  存在，未 commit
```

### 1.2 表结构（076 已冻结）

```
id                 TEXT PK          内容派生（canonical, alias）
canonical_ku_id    TEXT NOT NULL    FK -> knowledge_unit(id) RESTRICT
alias_id           TEXT NOT NULL    UNIQUE(alias_id)  ← 承重约束
alias_kind         TEXT NOT NULL    CHECK IN ('FREEZE_LEGACY')
id_fingerprint     TEXT NOT NULL    CHECK length(btrim(..)) > 0
identity_hash      TEXT NOT NULL    UNIQUE(identity_hash)
identity_version   TEXT NOT NULL
created_at         TIMESTAMP NOT NULL DEFAULT NOW()

UNIQUE(canonical_ku_id, alias_id)
CHECK(canonical_ku_id <> alias_id)
3 indexes：canonical / kind / created_at
```

权威链：`knowledge_unit ← ku_identity ← 退役 id`。

### 1.3 已声明的冻结（此前记录写作 FREEZE_NOT_DONE，需修正）

`A_P6_FREEZE_REPORT.md` 已经写明：

```
STATUS          = FROZEN
A_P6_IDENTITY   = PASS
G1..G5          = PASS
A-suite         = 461 passed
```

所以 P6 的准确状态不是「未冻结」，而是：

```
P6 冻结 = 已声明、已写报告
P6 冻结 = 未 commit，因此从 tag 无法验证
```

这个区别重要：它决定 P6 需要的是**重新冻结**（补齐验收口径），
而不是**首次冻结**。

---

## 2. 冻结对象（OPTION_A 的定义）

P6_REFREEZE 冻结的对象是**已经存在的东西**，具体为四件：

```
F-1  schema        076 及其全部约束（不改，只记录指纹并断言不可变）
F-2  data          staging 上 11 行 identity，含 fingerprint 可重算
F-3  contract      alias 解析语义：退役 id 必须可解析回 canonical，
                   解析不到就是 UNRESOLVED，不猜
F-4  evidence      G1..G5 五道门的可复现判定
```

**不在冻结对象内**：抽取质量、author 质量、任何 B/C 判断。

---

## 3. 审计发现（4 条，其中 F3 是必须修的）

### F1 — P6 不是 greenfield

迁移已应用、表已存在、行已存在、模块已在 tag 内。
任何后续 SPEC 都**不得假设 CREATE TABLE from zero**。

### F2 — 冻结已声明但不可从 tag 验证

见 §1.3。

### F3 — **验收口径漏掉了 9 道门（必须修）**

`ku_identity_runner.py` 报告 **14** 道门，但裁定只读 5 道：

```python
GATE_ORDER = ("G1_identity_uniqueness", "G2_historical_replay",
              "G3_revision_chain", "G4_regression", "G5_authority")

passed = all(gates[name] == "PASS" for name in GATE_ORDER)
```

未被 `GATE_ORDER` 覆盖、因而在裁定之外的门共 9 道：

```
G1_canonical_id           G2_citations_resolve    G2_retired_id_recomputes
G3_successor_walk         G4_stage_versions       G5_no_external_dependency
G5_no_mutation            idempotency             schema
```

实测后果：

```
不设 A_P6_LEDGER_FILE  ->  schema = NOT_EXECUTED  ->  A_P6_IDENTITY = PASS
设   A_P6_LEDGER_FILE  ->  schema = PASS          ->  A_P6_IDENTITY = PASS
```

**一道可以为 FAIL、也可以根本不执行的门，不影响裁定。**
`gate_results` 的 docstring 写的是「A gate that cannot be evidenced is
NOT_EXECUTED」——这句话本身是对的，但裁定没有兑现它。

裁定（本 SPEC 要求）：

```
1. 所有报告的门都必须进入裁定，reported_set == verdict_set
2. NOT_EXECUTED 永远不得产出 PASS
3. 缺少证据 = BLOCKED，不是 PASS
```

### F4 — 旧 open item 1 现已**被证明不可声明式表达**

`A_P6_FREEZE_REPORT.md` 的 open item 1 写：「别名不得取自
`knowledge_unit.id`」是应用不变式；若要成为数据库保证，
需要复合外键 `knowledge_unit(id, id)`，而那需要 `ALTER`，纯新增禁止。

本次审计**检验并否定了它的后半句**。假设 082 那种复合外键手法可以套用：

```sql
BEGIN;
CREATE UNIQUE INDEX tmp_ku_id_id_uniq ON stratum.knowledge_unit (id, id);
ALTER TABLE stratum.ku_identity ADD CONSTRAINT tmp_alias_not_a_unit_fk
  FOREIGN KEY (alias_id, alias_id)
  REFERENCES stratum.knowledge_unit (id, id);
-- ERROR:  foreign key referenced-columns list must not contain duplicates
ROLLBACK;
```

结论比旧 open item 更强：这条不变式**根本不能写成外键**。
外键断言的是**属于**，而这里要断言的是**不属于**；
重复列又被 PostgreSQL 拒绝。CHECK 读不到别的表，触发器本项目不引入。

```
回滚已核验：knowledge_unit 索引仍为 10，tmp_* 约束 0，ku_identity 仍 11 行。
```

因此裁定：该项**永久留在服务层**，由
`cross_namespace_collisions()` 把守，今天为空。
它不再是「待决定」，而是「已证明不可能用声明式表达」。

---

## 4. 其余 open items 的现状

| # | 内容 | 裁定 |
|---|---|---|
| 1 | 别名不得取自 canonical id | 保留服务层；已证明不可声明式（F4） |
| 2 | 两个命名空间同为 `ku_<12 hex>`，形状不可分辨 | 保留。这正是别名表存在的理由 |
| 3 | `resolve()` 扫描别名行 | 保留。单元自身别名数极小，`UNIQUE(alias_id)` 提供索引 |
| 4 | 耐久性仅在 staging 证明 | 保留。070 以来无任何迁移进入生产库 |

新增一条：

| 5 | `UNRESOLVED` 只在进程内返回，**没有落库**（076 称其为 reportable） | 待裁定：是否需要一张 unresolved 记录表，或明确它就是一次性返回值 |

item 5 是本次审计新增的。076 的注释说「解析不到的 id 是可报告的结果，
不是要糊过去的错误；引入该 id 的阶段与解析失败该 id 的阶段都是值得留下的事实」，
但全库没有任何 unresolved / resolution / report 表。
目前该「事实」只活在返回值里。

---

## 5. P6_REFREEZE 需要交付什么

不重新实现，只补齐验收与记录：

```
D-1  修正裁定口径：全部报告的门进入 verdict，NOT_EXECUTED -> BLOCKED
D-2  schema 门在无 ledger 时必须 BLOCKED，且给出可执行的取证步骤
D-3  11 行 identity 的 fingerprint 逐行可重算（对应 G2_retired_id_recomputes，
    该门已在报告里，但需进入裁定）
D-4  column parity 常设测试继续有效（它抓到过两个真 bug）
D-5  更新 A_P6_FREEZE_REPORT.md：写入本次审计的 F3/F4，改写 open item 1
D-6  重新生成 p6_ku_identity.json，使 artifact 与裁定口径一致
D-7  独立 commit：076 不动，只提交 spec / report / tests / artifact
```

D-7 明确：076 是已应用迁移，**不可修改**（与 077–082 同一条纪律）。

---

## 6. 明确不在本阶段做的事

```
不修改 076
不修改 077-082
不修改 identity.py / ku_identity_runner.py 的语义
不新增迁移
不新增表
不引入 trigger / function
不动 B / C / BU2
不把 P7 的 projection 混进来
不做 archive commit（368 个未提交测试暂不归档，
    理由：它们要证明哪个冻结状态，取决于本 SPEC 的裁定结果）
```

---

## 7. P6_REFREEZE_READY 的判定

只有全部满足才可宣布 READY：

```
R-1  裁定口径已修：reported_set == verdict_set（自动断言）
R-2  NOT_EXECUTED 不可能产出 PASS（构造性测试：抽掉 ledger 必须 BLOCKED）
R-3  13 道门（不含 schema 的 13）在裁定内且全 PASS
R-4  schema 门带 ledger 执行时 PASS
R-5  076 sha256 未变：2b9de6b42e1c1d87…
R-6  ku_identity 仍 11 行，且 baseline 仍 11/12/1/11
R-7  open item 1 的措辞已改为「已证明不可声明式」
R-8  A_P6_FREEZE_REPORT.md 与 p6_ku_identity.json 已按新口径重出
R-9  95 个 P6 测试 + P5.1-P5.5 五个契约测试全绿
R-10 干净 worktree 中可复现
```

R-2 是本 SPEC 最重要的一条：它把「无法取证」与「通过」分开。
P5.1–P5.5 每一层都已经这样做了（`A_P5_x_...` 在 gate 缺证据时产出 BLOCKED），
P6 是唯一一层例外。

---

## 8. P7 的位置

P7 的现状与 P6 同型但更弱：

```
projection.py / projection_builder.py   已在 tag 内
test_a_repository_p7_projection.py      71 tests，未 commit
A_P7_PROJECTION_SPEC.md                 不存在
A_P7_FREEZE_REPORT.md                   不存在
projection.py 的符号在 tag 内无任何测试执行
```

所以 P7 需要的是**完整的 SPEC → REVIEW → FREEZE**，不是 re-freeze。
但它必须在 P6 的裁定口径修好之后做，否则会复制同一个缺陷
（门报告了但不进裁定）。

---

## 9. 状态

```
P5_FREEZE            = VALID
DOC_DRIFT            = 0
TAG_DRIFT            = 0
P6_STATUS            = IMPLEMENTATION_PRESENT, FREEZE_DECLARED_NOT_VERIFIABLE
P6_DECISION          = OPTION_A
P6_REFREEZE_READY    = NOT_YET
P7_STATUS            = IMPLEMENTATION_PRESENT, VERIFICATION_INCOMPLETE, NO_SPEC
NEXT                 = 本 SPEC 的裁定；通过后执行 D-1..D-7
```

---

## 10. 裁定结果与实施状态（v1.1）

### 10.1 已裁定的四项

```
VERDICT_POLICY   = ALL_14_GATES_IN_VERDICT
ALIAS_NAMESPACE  = SERVICE_ENFORCED_ONLY
OPEN_ITEM_5      = EPHEMERAL_REPORT（不建表）
P6_MODE          = OPTION_A / REFREEZE_EXISTING_IMPLEMENTATION
```

裁定理由（原样记录，因为它们是约束而不只是选择）：

- **所有 gate_results 都属于 acceptance evidence**，
  不存在「打印 PASS 但不影响 verdict」。
  `PASS -> PASS`、`FAIL -> FAIL`、`NOT_EXECUTED -> BLOCKED`，
  禁止 `NOT_EXECUTED -> PASS`。
- **schema 门在裁定内**：schema 是 identity contract 的一部分；
  取不到证据则 `P6_IDENTITY=BLOCKED`，不是 PASS。
- **别名命名空间保留服务层**：已证明 FK（membership）、CHECK、
  UNIQUE 都无法表达 non-membership，且禁止 trigger/function。
- **UNRESOLVED 不建表**：它是 identity resolution 的过程结果，
  不是 A仓 knowledge artifact；建表等于造出 resolution authority，
  属于 B/C 语义风险。

### 10.2 F3 已修

`GATE_ORDER` 已删除。`verdict()` 直接由 `gate_results()` 派生，
single authority，无重复门列表。

```
修复前  报告 14  裁定 5   裁定外 9
修复后  报告 14  裁定 14  裁定外 0
```

三个 verdict 状态而非两个：`PASS` / `FAIL` / `BLOCKED`。
`FAIL` 优先于 `BLOCKED`；空门集合为 `BLOCKED`（不是 vacuous pass）；
未识别的状态一律 `BLOCKED`，新增门不会默认通过。

实测 R-2：

```
无 A_P6_LEDGER_FILE  ->  schema=NOT_EXECUTED  ->  A_P6_IDENTITY=BLOCKED
有 A_P6_LEDGER_FILE  ->  schema=PASS          ->  A_P6_IDENTITY=PASS
```

### 10.3 F4 已裁定

`ALIAS_NAMESPACE_INVARIANT = SERVICE_ENFORCED_ONLY`。

原报告 open item 1 写的是「需要复合外键 + ALTER」；本次审计**检验并否定了
该说法**（见 F4）。结论更强：这条不变式根本不能写成外键，
因为它断言的是 non-membership。已改写 `A_P6_FREEZE_REPORT.md` 的 open item 1。

### 10.4 Open item 5 已裁定

```
UNRESOLVED = EPHEMERAL_REPORT
不建 unresolved / resolution 表
```

理由：解析结果是过程事实，不是 A仓 知识权威；落表会产生 resolution
authority，属 B/C 语义风险。已在 P6 冻结报告中写明。

### 10.5 P6_REFREEZE_READY 逐条核对

```
R-1  reported_set == verdict_set                  PASS  14/14，verdict() 由其派生
R-2  NOT_EXECUTED 不得产出 PASS                    PASS  构造性测试：
                                                     抽掉 ledger -> BLOCKED
R-3  裁定内全 PASS                                PASS  14/14 with ledger
R-4  schema 带 ledger 时 PASS                      PASS
R-5  076 sha256 未变                               PASS  2b9de6b42e1c1d87
R-6  ku_identity 11 行，baseline 11/12/1/11        PASS
R-7  open item 1 措辞已改                          PASS  已证明不可声明式
R-8  report 与 artifact 按新口径重出               PASS
R-9  P6 98 tests + P5.1-P5.5 契约全绿              PASS  98（原 95，+3 新契约测试）
R-10 干净 worktree 可复现                          待最终回归后确认
```

### 10.6 实施范围遵守情况

```
已改  ku_identity_runner.py   仅 verdict 聚合，删 GATE_ORDER
已改  test_a_repository_p6_identity.py   跟随新契约（+3 测试）
已改  A_P6_FREEZE_REPORT.md   open item 1 + RE-FREEZE 段
已改  A_P6_IDENTITY_REFREEZE_SPEC.md   本文件 v1.1
已改  p6_ku_identity.json     按新口径重出

未改  076 / 077 / 078 / 079 / 080 / 081 / 082   逐字节未动
未改  identity.py / ku_identity_runner.py 的语义
未新增 迁移、表、trigger、function
未触及  P7 / BU / B / C / BU2
```

### 10.7 同类缺陷（P5-evolution，未修，仅报告）

本次审计顺带发现 `ku_evolution_runner.py` 有**同类缺陷**，不在本次裁定范围内：

```
报告 8   裁定 6   裁定外 2: idempotency, schema
```

即 P5-evolution 也可能在 `schema` 未执行时给出 PASS。
本阶段**不修**，按 P6 的裁定范围只动 P6。
它需要一份与本 SPEC 同形的 re-freeze，且必须在 P7 之前处理，
否则 P7 会复制同一缺陷。
