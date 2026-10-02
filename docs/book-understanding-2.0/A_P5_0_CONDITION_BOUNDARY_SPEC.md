# A P5.0 CONDITION / BOUNDARY IMPLEMENTATION SPEC v0.1

TASK=STRATUM_A_CONDITION_BOUNDARY_CANDIDATE_LAYER
AUTHORITY=STRATUM_A
MODE=ADDITIVE_ONLY
A_SCHEMA_BEFORE=070..076
A_SCHEMA_AFTER=070..077
BASELINE=STRATUM_A_P5_LJG_EXTENSION_SPEC v0.1 (frozen)
STATUS=FROZEN

---

## 1. 做了什么

在不改变 Frozen KU 判定、不改变已有验证逻辑的前提下，增加 condition/boundary
候选能力。**一行上游代码未改** —— mtime 可证：`verification.py` 停在 06:07、
`freeze.py` 06:55、`persistence.py` 07:26、`identity.py` 10:02、`evolution.py` 10:02、
`projection.py` 10:55，全部早于本阶段（12:14 起）。

## 2. 数据流分叉（这是整个设计的根据）

```
冻结链（未改）                        新增（只读消费）
Source                                 Frozen KU
  |                                       |
Evidence                                 Condition/Boundary Extractor
  |                                       |
KU Candidate                             Condition/Boundary Candidate
  |                                       |
Verification                             Condition/Boundary Candidate table
  |                                      (077)
Frozen KU
```

**为什么是独立两张表而不是 `ku_candidate` 的两列。** 实测，不是假设：

```
FACT 今天 : 4 个 required 槽位 → 满分 4/4 = 1.000 → VERIFIED
FACT +2   : 6 个 required 槽位 → 同一候选 4/6 = 0.6667 < 0.8 → REJECTED
实测：11 个已 VERIFIED 候选全部满足现有 4 槽位 → 11 个全部翻转。
```

而这 11 个单元**已冻结并持久化**（`knowledge_unit=11`）。槽位一改，活体验证与
冻结基线立刻脱钩 —— 而 A仓 的不变量正是「冻结的东西不得被后来的判定改写」。

`required_slots()` 因此一字未动，并有测试锁定：

```
FACT    = ('ANCHORED','SUBJECT','PREDICATE','OBJECT')
EVENT   = ('ANCHORED','ACTOR','TIME','ACTION')
CONCEPT = ('ANCHORED','DEFINITION_SPAN')
```

## 3. 077 — 两张独立表

| 表 | 用途 | 行数 |
|---|---|---|
| `ku_condition_candidate` | 条件候选 | **6** |
| `ku_boundary_candidate` | 边界候选 | **0**（见 §6） |

```
id                   TEXT PK          内容派生
knowledge_unit_id    → knowledge_unit(id) ON DELETE RESTRICT
condition_type       CHECK ('ACTOR','TIME')
statement            NOT NULL, 非空白
evidence_ids         TEXT[] NOT NULL, cardinality >= 1
extractor_version    NOT NULL
confidence           NUMERIC, 0..1
condition_hash       UNIQUE
status               GENERATED / SUPPORTED / REJECTED   ← 无 VERIFIED
created_at           TIMESTAMP NOT NULL
```

- additive only：`ALTER` 0、`DROP` 0、`UPDATE` 0、`INSERT`（backfill）0
- 唯一外键：`knowledge_unit`，`ON DELETE RESTRICT`
- 070–076 逐字节未改
- 三个 UNIQUE 指纹使重放即 no-op

## 4. 三处被实测纠正的提案

### 4.1 ⚠️ `array_length` 守卫**从来没有生效过**

冻结提案写 `CHECK (array_length(evidence_ids, 1) >= 1)`。对真实数据库实测：

```
array_length(ARRAY[]::text[], 1) = NULL
NULL >= 1                         = NULL
CHECK 约束在表达式为 NULL 时通过   → 空数组被接受
```

**这个守卫接受它本该拒绝的空数组。** 只有执行到真实数据库才能发现 —— 读 SQL
看不出，读 Python 也看不出。

```
CHECK (cardinality(evidence_ids) >= 1)
cardinality(ARRAY[]::text[]) = 0  →  0 >= 1 = false  → 拒绝
```

已修。修后重跑 REJ3 探针：`violates check constraint
"ku_condition_candidate_evidence_ids_check"`。并留了常驻回归测试断言用的是
`cardinality` 而不是 `array_length`。

### 4.2 ⚠️ emitter 漏掉 `created_at`，每一行插入都失败

`created_at` 是 `NOT NULL` 且无默认值，而列清单里没有它 —— 于是我写在
emitter 里的 `NOW()` 替换是**死代码**，每条 INSERT 报
`null value in column "created_at"`。

修法：`created_at` 进列清单，替换生效。与 P4.1 处理 `frozen_at` 的做法一致
（073 要求该列，故由写入方提供写时值），**schema 一字未改**。

### 4.3 ⚠️ 复用 P3 词表会引入两个已知假阳性

若照搬 P3 的 `ACTOR_MARKERS` / `TIME_MARKERS`：

```
TIME 命中 4/10，其中 2 个来自裸「年」：
  "贷款的利息被限制为不得超过每年8.333%"   ← 每年是计息基准，不是时间条件
  "银子贷款按重量计算每年20%"               ← 同上
ACTOR 命中 5/10，其中「法典」是误报：
  "更多的是模仿《汉谟拉比法典》"            ← 法典是被模仿的对象，不是施动者
```

裸「年」对**布尔槽位**无害（它只是回答「有没有时间词」），对**被抽成语句的
限定语**有害。所以：

| 词表 | 处置 | 理由 |
|---|---|---|
| ACTOR | 复用 P3，**剔除 `法典`** | 布尔槽位的宽松对语句不成立 |
| TIME | 复用 P3 并**剔除裸 `年`**，补 `古代`/`中世纪` | 「每年」不是时间条件 |

收窄后：**ACTOR 4 个单元、TIME 2 个单元、已知假阳性 0 个**。

`每年` 同时进 `TIME_DISQUALIFIERS`，并在代码里注明**当前是惰性的** —— 没有
TIME 标记是 `每年` 的子串，今天不拒绝任何东西。留着它是因为剔除 `年` 是唯一
阻止 `每年` 回流的东西；一个当前无实例的守卫被如实标注，而不是留着装作在承重。

## 5. Guard：三条词表分开

```
condition / boundary :  可验证前提与边界      禁 hedger、禁因果
constraint (P5.4)     :  显式陈述的倾向       允许 hedger
mechanism  (P5.1)     :  因果断言             条件里禁止
```

提案内含一处字面冲突：P5.0 禁「通常」，P5.4 的 `SOFT` 定义示例正是「通常情况下」。
语义上自洽（前提可验证，倾向不是前提），实现必须让三者词表不相交：

```
condition_constraint_boundary_guard(statement, kind)
  kind="condition" → 拒绝 一般/通常/可能/大多数 + 因为/所以/导致
  kind="boundary"  → 同规则
  从不作用于 constraint 候选  ← 倾向属于那里
```

**是拒绝，不是降权。** 一个被模糊的限定语不是较弱的条件，是另一类对象；把它
放进这张表会模糊这张表唯一在守的那条界线。

## 6. `ku_boundary_candidate` 是空的 —— 这是正确结果

```
实测：10 个冻结跨度中含边界标记的 = 0
探针：仅限/只限/不包括/不适用/除外/截至/止于/以前/之后/之前/限于/仅对/仅在
=> 0/10
```

试读语料里**没有一句话陈述适用范围**。所以这张表建好、约束正确、行为已验证，
但**没有行**。

这是被报告的结果，不是被工程绕开的结果。门断言行数为 0，runner 报告
`boundary_candidates = 0`。四个声明的 boundary_type 里只有两个进 schema，
因为另外两个（`SCOPE_LIMIT` / `EXCEPTION`）也没有任何提取器能产出。

**扩到第 2 章及以后再评估。**

## 7. 抽取结果（6 条，全部逐字锚定）

| unit | type | statement |
|---|---|---|
| `ku_10fef8f2ffa4` | ACTOR | 古代巴比伦王朝的第一个国王汉谟拉比 |
| `ku_10fef8f2ffa4` | TIME | 在大约公元前1800年 |
| `ku_5840cc146f9f` | ACTOR | 索伦的法典取消了对利率的所有限制 |
| `ku_6460a6062a10` | TIME | 信贷在古代和中世纪时期就得到了普遍应用 |
| `ku_93a979cb6fab` | ACTOR | 雅典出现了一次经济危机 |
| `ku_fa902e0bc115` | ACTOR | 古希腊的法律史始于索伦 |

一个子句只记一次。`古代巴比伦王朝的第一个国王汉谟拉比` 同时命中 ACTOR 与 TIME
标记，但它是同一个子句、同一段原文，记两行会虚增计数。保留**归因更具体**的
因子（ACTOR 先于 TIME 被遍历）。

**关于这些是什么的诚实边界**：冻结语料的跨度大多陈述事实，不是陈述前提。抽出来
的是**跨度里逐字存在的施动/时间限定语**，不是逻辑前提。它的边界由封闭词表和
剔除表共同限定，两者都是**在 10 个跨度上量出来的**，下一本书需要重新评估。

`confidence` 衡量的是**锚点歧义度**（跨度内该标记出现 1 次 = 1.0，n 次每次降
0.1，下限 0.5），**不是这个读法正确的概率**。当前 6 条全是 1.0，即无歧义。

## 8. 验收（实测）

```
A_P5_0_CONDITION_BOUNDARY = PASS
FROZEN_KU_MUTATION            = 0
VERIFICATION_LOGIC_MUTATION   = 0
EVIDENCE_TRACEABILITY         = 100.0
ORPHAN                        = 0
REPLAY                        = PASS   (NEW_CONDITION=0 NEW_BOUNDARY=0)
B_CONTAMINATION               = 0
C_CONTAMINATION               = 0
```

| Gate | | 证据 |
|---|---|---|
| A frozen KU immutable | PASS | 三次全表快照（抽取前/抽取后/写入后）逐字段相同 |
| A verification logic | PASS | 抽取后、写之前即比对 —— 抽取器本身被单独抓住 |
| A upstream untouched | PASS | 077 无 ALTER/DROP/UPDATE/backfill |
| B evidence trace | PASS | 6/6 经 evidence → source_version |
| C isolation | PASS | 三层检测，**复用 P7 的 `external_imports()` / `artifact_drift()`** |
| D baseline invariance | PASS | 写入后仍逐字段相同 |
| D extraction purity | PASS | 源码级：槽位无写入、无 DML、无 `transition(` |
| E replay | PASS | 三次应用零新增，6 distinct hash / 6 rows |
| F anchoring | PASS | 6/6 statement 是其跨度子串 |
| schema vocabulary | PASS | 声明值 = 枚举值；withheld 项不在 schema 也不在枚举 |
| schema column parity | PASS | 见 §9 |

污染检测**第三次**不做文本扫描：扫源码会命中 A仓 自己的守卫清单（P6/P7 各踩过一次，
实测 24 处假阳性）。

## 9. 第四个 bug：本次实现的第三个

077 曾在 `UNIQUE (condition_hash)` 与 `UNIQUE (boundary_hash)` 里引用两个
**从未声明的列**（与 P6 的 `id` / `identity_hash` 同型）。这次在应用前就被
`schema_column_parity` 门抓住。

门比较三方：**emitter 写的列 ⊆ schema 声明的列**，且 **⊆ dataclass 带的字段**。
读任一文件都发现不了，只有不一致会暴露。

parsing 本身也踩了两个坑，一并修掉并记录：按空行切分（括号内有空行）、把
SQL 注释当列名（注释里有逗号）。

## 10. DB_MUTATION

只对 staging：

```
stratum_a_p3_staging
  077 applied  (重建一次：修 §4.1 的 array_length 守卫)
  数据脚本执行 3 次：第一次写 6 行，第二三次零新增
  6 rows / 6 distinct condition_hash
  冻结基线未动：units 11 / events 12 / revisions 1 / identities 11
  ledger 8 条，最新 077_a_condition_boundary.sql
```

数据库独立拒绝的探针（全部实测）：未声明 `condition_type`（`STATE`）、
`status='VERIFIED'`、空 `evidence_ids`、`confidence=9.0`、
不存在单元的候选（RESTRICT）、删除被限定的单元（RESTRICT）。
另经查询确认：**6/6 statement 逐字出现在其单元锚定的跨度中**，**0 条含 hedger**。

`aii_kg` 未触碰；BU2_MUTATION=0，B_MUTATION=0。

## 11. 已知限制

1. **`evidence_ids TEXT[]` 没有外键。** 数组带不了外键。后果直说：`ORPHAN=0`
   由写入方强制、由门读取，**不由数据库保证** —— 这是本仓其他三张表都有的
   强度，这里没有。schema 被冻结为此形状，所以这是选择而非疏漏。
2. **边界层为空**，因为语料里没有边界。schema 与行为已验证，内容待语料扩充。
3. **标记词表拟合在 10 个跨度上。** 下一本书很可能需要修订；一份声称适用于
   全部书的词表正是本仓库要避免的那种不可证伪假设。
4. **抽出来的是限定语，不是逻辑前提。** 见 §7。
5. **state / location / prerequisite 三因子无提取器**，因此不在 CHECK 里。
   声明它们而不产出它们，会让 schema 出现无法兑现的值。
6. **`TIME_DISQUALIFIERS` 当前惰性**，已在代码里标注。

## 12. 未启动

按提案，`mechanism` / `relation` / `paper` / `constraint` **一律未启动**，
直到 P5.0 实测冻结。

```
A_P5_0_CONDITION_BOUNDARY=PASS
FIRST_IMPLEMENTATION=CONDITION_BOUNDARY_ONLY
P5.1 Mechanism          = NOT STARTED
P5.2 Relation           = NOT STARTED
P5.3 Paper              = NOT STARTED
P5.4 Constraint         = NOT STARTED
```
