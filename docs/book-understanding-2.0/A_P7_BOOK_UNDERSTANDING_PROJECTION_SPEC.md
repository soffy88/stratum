# A P7 BOOK UNDERSTANDING PROJECTION SPEC — 只读理解投影

TASK=A_P7_BOOK_UNDERSTANDING_PROJECTION
VERSION=A_P7=v0.1
TYPE=READ_ONLY_PROJECTION
AUTHORITY=A_REPOSITORY
BASELINE=A_P6_IDENTITY_CANONICALIZATION
STATUS=FROZEN (re-frozen 2026-10-01, see A_P7_FREEZE_REPORT.md)
VERDICT_CONTRACT=FAIL > BLOCKED > PASS, derived from gate_results

## 1. Objective

在不改变 A仓事实模型的前提下，为真实书籍理解流程提供只读理解投影。

```
    A仓事实
       |
       v
    Projection View
       |
       v
    阅读理解导航
```

P7 不产生新知识，不推理，不压缩，不合并。它只读取 A仓 已冻结的行，把它们排布
成四个读者可以导航的视图。

## 2. Authority Boundary

唯一事实来源：**A Repository**。

| 读取 | 表 |
|---|---|
| | `book_source` · `source_version` · `reading_run` · `reading_evidence` |
| | `evidence_quality` · `ku_candidate` · `ku_verification` |
| | `knowledge_unit` · `ku_freeze_event` · `ku_revision` · `ku_review_event` |
| | `ku_confidence_evolution` · `ku_relation` · `ku_identity` |

禁止进入 P7：legacy knowledge-claims 表、B仓、C仓、KG、embedding memory、
semantic index、LLM summary。

### 2.1 一个被现有约束逼出来的实现细节

A仓 源码对 legacy knowledge-claims 表**名称隔离**——`tests/integration/
test_a_authority_freeze.py` 断言该名字不出现在 `a_repository/*.py` 的任何位置。
所以 P7 的 `FORBIDDEN_AUTHORITY` 词表里**没有**它。

这不是放松，而是服从：G1 的证明本来就是结构性的（导入白名单 + A 表白名单），
比针对单个 token 的名字扫描更强。另有一个测试断言该名字也不出现在产物里。

### 2.2 数据方向单向

```
    A仓 ──> Projection        允许
    Projection ──> A仓        禁止
```

`ProjectionSource` 只持有读句柄。投影视图是 `frozen=True` dataclass，**且所有
集合字段是 tuple** —— 见 §6.3。

## 3. Projection Definition

Projection 是 **derived read model**，不是 new knowledge store。

## 4. Projection Objects

### 4.1 BookReadingMap

`BookReadingProjection`：`book_id`、`source_version_id`、`chapters`
（`chapter_id` / `title` / `evidence_count` / `ku_count` / `verified_count`）、
`reading_status`、`last_run_id`。

`verified_count` 从 verification 状态**核对**得出，不是假定等于 `ku_count`——
一个单元存在正因为它的核验通过了，两者相等是要检查的事实，不是要写死的等式。

### 4.2 EvidenceTraceMap

`EvidenceTraceProjection`：`ku_id` + `evidence[]`（`evidence_id` /
`source_version` / `locator` / `span` / `extractor_version`）。

`locator` 逐字透传（含 `source_id` 这个 A仓 自己的键名）。`span` 是证据行的
原文，`canonical_text` 是其中被锚定的那一段，必须出现在 span 之内。

### 4.3 KUTraversalView

`ku_id` / `previous` / `next` / `same_chapter_units` / `revision_chain`。

顺序键 `(page_number, section, evidence_id)`。前两个是 A仓 记录的事实；第三
个是 tiebreak，**不是事实**——同一页同一节的两个单元没有任何阅读顺序事实区分
它们。按 evidence_id 排序稳定且内容派生，所以重放一致，但**不承载含义**，
读者不得读出含义来。

`same_chapter_units` 是该章的**完整成员，含自身**，所以它的长度等于该章的
`ku_count`，两个视图可以互相校验。

禁止：semantic similarity、concept relation。

### 4.4 UnderstandingCoverageView

`book_id` / `total_candidates` / `verified_units` / `rejected_candidates` /
`coverage_ratio` / `evidence_coverage`。

**`coverage != correctness`** —— 它衡量多少内容已经被建立事实链，不衡量多少
内容为真。字段里带 `disclaimer` 显式写出这一点。

额外加了 `superseded_units`（不在任务字段表内）：§9 禁止 SUPERSEDED 被静默
丢弃，一个计数是让它不消失的最小诚实披露。

## 5. Projection Storage

初版禁止数据库。P7 v0.1 采用 materialized read artifact（JSON）。

```
artifacts/a_repository/p7_projection/book_<book_id>_projection.json
```

§4 的示例路径是 `artifacts/a_repository/projection/`，§13 的必交付目录是
`p7_projection/`。**采用了 §13**（它是"必须产生"的清单），文件名沿用 §4 的
`book_xxx_projection.json` 形状，`xxx` 是 `book_id`。

原因：避免第二数据库产生 authority drift。

## 6. Projection ID

禁止新 ID。产物里出现的身份全部来自 A仓：
`book_id` · `source_version_id` · `knowledge_unit.id` · `evidence.id`。

禁止 `projection_id` / `ku_projection_id` / `book_view_id` 作为业务身份。

`content_hash`（`aph_…`）**是校验指纹，不是身份**，不被任何东西用作键；它存在
只是让 G3/G4 能判断两次构建是否一致。`assert_no_new_ids()` 会遍历产物、报出
任何不在白名单里的身份字段，`no_new_id_gate` 在非空时 FAIL。

### 6.1 偏差 D1：`chapter_id` 与 `title`

A仓 没有 chapter 表，也没有任何 chapter id。它在每条 evidence 的 locator 上
记录一个 chapter **标签**。§3.1 要求 `chapter_id` 字段。

选择：把标签原样放进 `chapter_id`，`title` 重复同一个值。**不铸 id**——铸一个
就是 P7 明确禁止的新知识。两条字段相同这一事实由测试断言并写在此处，不是
巧合。

### 6.2 偏差 D2：`source_id`

产物里出现 `source_id`，因为 locator 是逐字透传的，而那是 A仓 在
`reading_evidence.location` 里自己用的键名（值为 source_version_id）。它被加入
身份白名单并在代码里注明理由。

### 6.3 一个被测试发现的真问题

`frozen=True` 只阻止属性重绑定，**不阻止 list 字段被原地 append**。第一版用的
是 `List`，`read_only_gate` 因此 FAIL——一个只读投影不该允许这种改写。已全部改为
`tuple`，视图现在深度不可变。

## 7. Build Contract

新增 `projection_builder.py`。

```
    P7.1 Load Frozen Units  ──> canonical units and their aliases
             |
    P7.2 Resolve Identity   ──> alias -> canonical, never re-hashed
             |
    P7.3 Attach Evidence    ──> every unit back to its source span
             |
    P7.4 Build Reading Map  ──> chapters, status, last run
             |
    P7.5 Build Coverage     ──> how much has a fact chain
             |
    P7.6 Emit Artifact      ──> canonical JSON, byte-identical on replay
```

- **Deterministic**：`build_projection()` 无参数。序列化用 `canonical_json`
  （sorted keys、固定分隔符、无时间戳、无路径）。三次构建一个 hash。
- **Replay**：重建产出同一字节。
- **No Mutation**：源文件里没有 DML；`_a_state()` 对 §1 边界内的每一张表做
  前后快照比较。

## 8. Identity Rules

读取 canonical `knowledge_unit.id`；alias 经 P6 resolver 解析。**不重新 hash，
不重新生成 id。**

`build_projection()` 对每个投影 id 断言 `canonical(id) == id`，因此产物只以
canonical id 为键。

## 9. Revision Rules

默认只展示 current canonical unit（10 个）。SUPERSEDED 的 1 个不在导航视图里，
但**没有**被删除、合并或替换——它出现在后继者的 `revision_chain` 里，并在
`coverage.superseded_units` 里被计数。

`revision_chain` 最旧在前、以自身结尾，索引由 P5 的修订边单调。

## 10. Quality Gates

| Gate | 要求 | 实现 |
|---|---|---|
| **G1** Authority | A_ONLY，禁 legacy claims / B仓 | 产物无越权 token + 导入白名单（结构性） |
| **G2** Traceability | KU -> Evidence -> Source 100% | 产物里每个 id 都走完整条链 |
| **G3** Determinism | 连续三次 hash 一致 | 三次 `build_projection()` |
| **G4** Replay | 重建 no mutation + same artifact | 字节比较 + 全表快照 |
| **G5** Isolation | 不影响 BU2 / B仓 / C仓 | 零 migration + 产物无越权 token + 无外部导入 |

## 11. Tests

`tests/architecture/test_a_repository_p7_projection.py` — 71 passed.

覆盖任务点名的五项（`no_external_authority_reference`、`projection_is_read_only`、
`canonical_id_preserved`、`alias_resolves`、`every_ku_has_evidence`、
`same_input_same_output`），另加：确定性、无新身份、隔离、零 migration、
遍历语义（无 similarity / concept 邻居）、superseded 仍可达、coverage 免责声明、
深度不可变、名字隔离、扫描器不误伤合法书名。

## 12. Migration

**NO MIGRATION。**

```
    P7 v0.1:  DB_MUTATION=0   SCHEMA_CHANGE=0
```

已对真实 `stratum_a_p3_staging` 核实：`stratum` schema 内 projection/p7 相关表
数量为 **0**，九张 A 表行数如下。

```
book_source=1            reading_run=1              reading_evidence=17
ku_candidate=18          ku_verification=18        knowledge_unit=11
ku_freeze_event=12       ku_confidence_evolution=15
ku_revision=1            ku_identity=11
```

> 本节初版写的是「ledger 仍是 7 条、最新仍是 `076_a_ku_identity.sql`、七张 A 表
> （11/12/1/5/15/2/11）」。那句话在写下时是真的，之后 P5/P6 把 A 链推进到 **13 条
> migration（070–082）**，所以它已经不成立了——不是被谁改坏，是它过期了。现按
> 2026-10-01 重新核实如上。`projection/p7` 表为 0 这一条未变。

`schema_change_count()` 会数 `*p7*` migration；一旦出现即非零，G5 FAIL。

如果未来需要数据库：必须新阶段 **A_P7_1_PROJECTION_STORAGE**，重新评估。

## 13. 两处来自 A仓 的限制，被透传而非抹平

报告它们是 P7 的职责，修它们不是。

- **`reading_status` 永远是 `READING`。** 链条从未把 `reading_run.status`
  推进过 READING 之后的状态。P7 报告这一行，不解释它。
- **`last_run_id` 是按 id 的最后一个，不是按时间的最后一个。**
  `reading_run` 有 `started_at` / `completed_at` 两列，但 P4.1 的 emitter 不写
  它们，数据库里是 NULL。所以这个顺序确定且稳定，**但不是编年**。这一点写在
  spec 和模块 docstring 里，以免日后被误读成时间线。

## 14. Commit Boundary

新增：`projection.py` · `projection_builder.py` ·
`tests/architecture/test_a_repository_p7_projection.py` · 本 spec ·
`artifacts/a_repository/p7_projection/`。

未修改：070–082 migrations · `persistence.py`（knowledge_unit writer）·
`identity.py` · `evolution.py`（revision）· `verification.py` · BU2 · B仓。

## 15. Known Limits

- **`frozen=True` 曾只做到浅冻结。** 已修（§6.3），并由
  `test_a_projection_is_deeply_immutable` 常驻。
- **G1 的名字扫描刻意不含裸词**（`concept` / `embedding` / `index`）。
  一本叫《Concepts of Physics》的书不该让权威门失败——对正确输入失败的门会被
  关掉，那比没有门更糟。所以词表全是标识符（表名、schema 名、服务名），并有
  测试断言裸词不在其中。
- **遍历 tiebreak 无含义。** 见 §4.3。
- **试读语料只有一章五节**，所以 `chapters` 长度为 1、`same_chapter_units`
  等于全部 10 个单元。这是语料的事实，不是视图的限制。
- **`resolve()` 仍扫描 alias 行**（P6 的同一条限制），单元级规模下无关紧要。
- **P7 不修改任何文件以外的 A仓 状态，也不读数据库。** 它经 P6 的确定性重建
  读取 A仓 行，因此"read-only"是结构性的而非承诺性的。

PROJECTION_SPEC=PASS
