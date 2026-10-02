# A P5.4 FREEZE REPORT v1.0

TASK=STRATUM_A_P5_4_CONSTRAINT_ANNOTATION_LAYER
BASELINE=P5.3_PAPER=FROZEN (080), 079/078/077/075=FROZEN
IMPLEMENTATION_RECORD=A_P5_4_CONSTRAINT_SCHEMA_REVIEW.md + §5
DECISION=SPAN_ONLY
STATUS=FROZEN
SCHEMA=070..081
PILOT_YIELD=1

---

## 0. 冻结锚点

```
081_a_constraint_candidate.sql
  sha256 = 0e9ebc2ddc443412fe9c0203ab3a7150fd7b02d0034c9368e126483283069f4e

artifacts/a_repository/p5_4_constraint.json
  sha256 = bfa3fd62e32e4dc3776e8f78221b1fc18a414b99703b25784394b865515a5c5c
```

前序冻结锚点继续有效，`git diff HEAD` 为空：

```
077_a_condition_boundary.sql   fe4d613f5bb95508e69cd1f85f4013eb487fd9f6dce33c7f6ecaf59c8d8b7f6f
080_a_paper_source.sql         6215e46078709bc8fc8548ccaa7de218024ba7e44dc917f16ed69f4d6312bfd5
```

DB 侧状态（`stratum_a_p3_staging`）：

```
migrations = 12, newest = 081_a_constraint_candidate.sql
constraint_candidate = 1
baseline units/events/revisions/identities = 11 / 12 / 1 / 11
conditions/boundaries = 6 / 0     mechanisms = 1 / 3     relations = 1
paper = 1 / 4                      ku_relation = 2 (075, 未动)
```

## 1. 冻结契约

### 1.1 产物是什么

一条**约束声明候选**的指纹，其四个引用字段逐字来自书自己的跨度。

```
constraint_id   = cnc_9b4ce2844c0b
constraint_hash = cnh_be4e3f7cc4c15779
source_version  = sv_f548f51a5df5
knowledge_unit  = ku_15a527238f5c
constraint_type = HARD
extractor       = pilot-declared
status          = GENERATED

SPAN : 贷款的利息被限制为不得超过每年8.333%
KU   : 罗马法定利率上限：8.333%/年

subject   利息            predicate 被限制为不得超过
object    每年8.333%      boundary 8.333%
```

### 1.2 QUOTE AUTHORITY（冻结裁定）

```
CONSTRAINT_QUOTE_SOURCE      = READING_EVIDENCE_ONLY
KU_STATEMENT_AS_EVIDENCE     = FORBIDDEN
EXTRACTOR_INFERENCE_AS_CONSTRAINT = FORBIDDEN
```

`subject` / `predicate` / `object` / `boundary` 全部必须是
`reading_evidence` 跨度的字面子串，否则 REJECT。
KU statement 仅供 human context / display / navigation。

理由不是整洁。实测同一个单元的两套用词：

```
KU   : 罗马法定利率上限：8.333%/年          含「上限」「8.333%/年」
SPAN : 贷款的利息被限制为不得超过每年8.333%  两者皆无
```

允许从 KU statement 引用，就等于允许抽取器先改语义、再让约束看起来有证据：

```
raw span   银子贷款按重量计算每年20%          无「上限」，无「不得超过」
extractor  巴比伦法定利率上限：银子贷款20%/年   加了「上限」
=> predicate 不得超过, object 20%, 判 HARD
```

**source declaration 就变成了 extractor assertion。** 所以巴比伦利率上限被
REJECT，记为 LIMITATION-6。

## 2. 被拒绝的约束（实测，逐条记录，不静默丢弃）

```
ku_639e79172556  跨度 银子贷款按重量计算每年20% 只有利率，无上限词
                 -> REJECT：rate fact ≠ constraint
ku_8b366dd7b4d1  如果作弊收取的利息高于法定上限，那么债务的本金就会被免除
                 -> REJECT：条件性后果，不是对利率的限制
ku_5840cc146f9f  索伦法典取消利率上限
                 -> REJECT：记录的是上限被取消，不是本源声明了一个上限
ku_4ccc104bb7a8  高于法定上限的利息将被处以4倍损害赔偿
                 -> REJECT：附属于上限的罚则，不是上限本身
ku_93a979cb6fab  …因而必须进行重大改革
                 -> REJECT：「必须」指向改革，不是信贷约束
```

无冻结 KU、因而写不进去的跨度（§5 要求 `knowledge_unit_id NOT NULL`）：

```
p4  法定利率上限确定为谷物贷款每年33.333%，以实物偿还
p5  所有贷款都必须附有书面合约，并由官员作证
p7  他们减少或者豁免了许多债务…但是禁止个人劳役偿债
```

这三条恰好是全语料最干净的三条禁止性表述。**它们落在从未被冻结的跨度上。**

## 3. KNOWN_LIMITATION（冻结）

1. **抽取质量未证。** 召回率与精确率是未知数，不是「已验证为空」。
2. **软约束的边界取决于来源措辞。** 且本语料 `SOFT` 词汇 0 次命中（§4）。
3. **证据数组的外键只由服务层校验。** `TEXT[]` 无法建 FK。
4. **数据库保证 source/KU 身份，不保证语义有效性。**
5. **任何约束都不得自动晋升到 B仓。**
6. **有些历史上确知的约束进不了 A仓**——当跨度记录的是事实而没有记录那条
   限制规则时。这是**故意的**：A仓 保存的是声明权威，不是推断解释。
7. **DB 层没有状态机守卫。** 直连 SQL 可把 `SUPPORTED` 改回 `GENERATED`；
   合法转移只由 `ConstraintWriter.transition()` 把守。
8. **引用规则不是 DB 保证。** 四个字段是否真在跨度里，
   `CHECK` 表达不了（它要读 `reading_evidence`，PostgreSQL 拒绝），所以是
   writer 的门，并由 `quote_authority_gate()` 读取。

## 4. 类型覆盖：1/3，如实报告

```
HARD         True    <- pilot 覆盖
SOFT         False   <- SOFT_MARKERS 在本语料 0 次命中
SELF_DEFINED False   <- 无可判定样本
```

三个类型都**保留在 CHECK 里**（raw SQL 写不进未声明的类型），
而不是把词表收窄到「今天测得出来的」那一个。
`coverage_gate()` 与 artifact 的 `type_coverage` 每次运行都报覆盖情况。

顺带记录一条实测：077 冻结的 `TIME_LIMIT_MARKERS` 里 `之前` 在 p10 上有假阳性
（`在有文字历史出现之前`，叙事性的「之前」而非「不迟于」）。077 已冻结，
本阶段不动它；它恰好印证提案 §4——关键词只能召回，不能定类。

## 5. 与提案 v1.0 的偏离（Phase 0 三项裁定 + 两项收紧）

**裁定 1 — `DECISION=SPAN_ONLY`。** 见 §1.2。代价是 LIMITATION-6。
**裁定 2 — pilot 只落 1 条诚实行。** 不为凑数而收。
**裁定 3 — 三类型保持闭合，覆盖情况如实上报。** 见 §4。

两项按已验证的漏洞收紧：
- `evidence_ids` **排序后**进 hash（遍历顺序不是声明）。
- `subject`/`predicate`/`object` 加 `length(btrim(...)) > 0`，
  挡掉退化行（真正的门仍是引用规则）。

**未偏离但值得写明**：§8 要求的 `knowledge_unit(id, source_version_id)` UNIQUE
索引**已由 079 建好**（`knowledge_unit_id_source_version_uniq`），
081 **没有对任何冻结表新建索引**——实测 `knowledge_unit` 索引数
从 079 后的 10 到 081 后仍是 10。

## 6. 冻结时的验收状态

```
A_P5_4_CONSTRAINT_SCHEMA        = PASS
A_P5_4_CONSTRAINT_IMPLEMENTATION = PASS

GATE_1_schema / fk_verb / isolation_schema / index_reuse      = PASS
GATE_1_constraints / vocabulary / column_parity / hash_ordering = PASS
GATE_1_banned_fields                                          = PASS
GATE_2_authority / frozen_layers / baseline_unchanged         = PASS
GATE_3_quote_authority / ku_statement_not_evidence           = PASS
GATE_4_trace / coverage                                       = PASS
GATE_5_replay / idempotency / hash_stability                  = PASS
GATE_6_isolation                                              = PASS
GATE_7_negative                                               = PASS  (25 / 25)

constraint_persisted = 1      fields_quoted_from_span = PASS
traceability = 100.0%         source_isolation = PASS
replay_stable = PASS          unauthorised_type_rows = 0
cross_source_candidates = 0   B/C contamination = 0   BU2 = 0
baseline_mutated = 0
```

`tests/architecture/test_a_constraint_authority.py` — 52 passed。
`tests/architecture` 全量 916 passed / 6 skipped。

DB 侧独立验证（不经 Python，直接 psql）：

```
quote_check : subject 利息 = true | predicate 被限制为不得超过 = true
              | object 每年8.333% = true | boundary 8.333% = true
decision    : KU statement 含「上限」 = true，跨度含「上限」 = false
              KU statement 含 8.333%/年 = true，跨度含 8.333%/年 = false

R2 constraint_type=ADVISORY   -> refused (constraint_candidate_constraint_type_check)
R3 status=VERIFIED / APPROVED -> refused (constraint_candidate_status_check)
R4 empty evidence_ids         -> refused (constraint_candidate_evidence_ids_check)
R5 whitespace-only predicate  -> refused (constraint_candidate_predicate_check)
R6 duplicate constraint_hash  -> refused (constraint_candidate_hash_uniq)
R7 跨书 unit                  -> refused (constraint_unit_same_source)
R8 未冻结 unit                -> refused (constraint_unit_same_source)
R9 删除被引用的 unit          -> refused（073 的 ku_freeze_event 先拦下）
两个外键 confdeltype 全部 = r (RESTRICT)；指向 A 仓以外的外键 = 0
```

R7 拦下的正是 079/080 两次实测过的那一类谎话：两边 id 单独看都合法，
合起来描述的是两本不同的书。

重放：同一份 SQL 连跑 3 次，`constraint_candidate` 稳定在 1 行。

## 7. 回归（含一次我自己造成又修掉的失败）

`tests/` 的 failed/errored 集合与 P5.3 冻结时**逐项相同**（217 项，新增集合为空）。

过程中确实出现**一次真实的回归**，记录在此：

```
tests/integration/test_a_authority_freeze.py::
  test_no_knowledge_claims_dependency_in_a_repository
  => AssertionError: constraint_runner.py references B仓 table
```

原因是我在 `forbidden_reference_gate` 的**文档字符串**里写出了那个被禁的表名，
而该集成测试会对 `src/stratum/knowledge/a_repository/*.py` 全文（含 docstring）
做词扫描。这正是本阶段 runner 头部警告的陷阱，我踩了进去。
修法不是改测试，而是**删掉我自己那份多余的检查**——
import 图与 artifact 两道门早已在 `authority_gate` 里（`external_imports()`
与 `artifact_drift()`），P5.0–P5.3 也是这么做的。

教训已写进代码注释：`FORBIDDEN_KG_TABLES` 是**被 import 进来**的，
`projection_builder.py` 自身一个字母都不写，因为「src/ 下的文件一旦写出那个名字，
它本身就是那个测试要抓的违规」。

Ruff 未在本机执行（`ruff` 二进制未安装，`line-length = 100` 已按 pyproject
人工核对：新文件 0 行超长）。

## 8. 本阶段没有证明的事（如实列出）

```
soft_constraint_extraction      本语料无 SOFT 词汇，未检验
self_defined_constraint        无可判定样本，未检验
constraint_completeness        召回率未知，不是「已验证为空」
legal_correctness              未检验，也不属于 A仓
advisory_wording_in_corpus     本语料无建议性措辞，未检验
declaration_by_text_span       不适用：081 引用的是跨度本身
```

前三项写进 artifact 的 `UNTESTED` 字段，第五项（SOFT/SELF_DEFINED 未检验）
由 `type_coverage` 与 `coverage_gate()` 每次运行上报。

## 9. 阶段状态

```
P5_0_CONDITION_BOUNDARY = FROZEN
P5_1_MECHANISM          = FROZEN
P5_2_RELATION           = FROZEN     (PRECEDES_ONLY)
P5_3_PAPER              = FROZEN     (BOOK, 4 declarations)
P5_4_CONSTRAINT         = FROZEN     (HARD only, 1 row)
P5_4_EXTRACTION         = NOT_STARTED（extracted_rows = 0）
075_ku_relation         = FROZEN，未动
077_a_condition_boundary= FROZEN，未动（ku_boundary_candidate 仍为 0 行）
080_a_paper_source      = FROZEN，未动
NEXT                    = 081 已在用；下一件实际工作是
                          「p4/p5/p7 三条禁止性跨度没有冻结 KU」——
                          那属于摄取侧（P4.x），不是 P5.4。
```

## 10. FINAL REPORT

```
TASK             = A_P5_4_CONSTRAINT
MIGRATION_081    = 081_a_constraint_candidate.sql
CONSTRAINT_ROWS  = 1
TRACEABILITY     = 100.0%
REPLAY           = PASS
AUTHORITY_SCAN   = PASS
B_CONTAMINATION  = 0
C_CONTAMINATION  = 0
DB_MUTATION      = 0
BU2_MUTATION     = 0
COMMIT_SHA       = PENDING
TAG              = PENDING
FINAL_STATUS     = PASS
```

`COMMIT_SHA` 与 `TAG` 如实写 `PENDING`：本阶段**没有提交**。

---

FINAL AUTHORITY:

```
STRATUM_A stores what the source states, quoted from its own words.
STRATUM_A does not infer, and does not advise.
```