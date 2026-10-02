# A P5.3 FREEZE REPORT v1.0

TASK=STRATUM_A_P5_3_PAPER_SOURCE_ANNOTATION_LAYER
BASELINE=P5.2_RELATION=FROZEN (079), 078/077/075=FROZEN
IMPLEMENTATION_RECORD=A_P5_3_PAPER_SCHEMA_REVIEW.md + 本报告 §5
STATUS=FROZEN
SCHEMA=070..080
SOURCE_TYPE=BOOK

---

## 0. 冻结锚点

```
080_a_paper_source.sql
  sha256 = 6215e46078709bc8fc8548ccaa7de218024ba7e44dc917f16ed69f4d6312bfd5

artifacts/a_repository/p5_3_paper.json
  sha256 = 945d206e53c2ffa60e7484c5648d0678e6b4fbaa8a4cf9e4dfd0eeac1a216fca
```

前序冻结锚点继续有效，`git diff HEAD` 为空：

```
075_a_ku_evolution.sql        b29432e8340faedc94919811a4b76e8776c81c21e27b936245b4836a747dd7bd
079_a_relation_candidate.sql  58910b307ea79b1f571415a613a8cae80a6384c07067d45e42d6c368d7307d2f
```

DB 侧状态（`stratum_a_p3_staging`）：

```
migrations = 11, newest = 080_a_paper_source.sql
paper_source_candidate = 1    paper_evidence = 4
baseline units/events/revisions/identities = 11 / 12 / 1 / 11
baseline conditions = 6    mechanisms = 1 / 3    relations = 1
ku_relation = 2 (075, 未动)    book_source = 1    source_versions = 1
```

## 1. 冻结契约

### 1.1 产物是什么

一条**来源声明候选**的指纹，加上做出每个声明的那份记录。

```
paper_id   = psc_5a3d1a1cab6d
paper_hash = psh_dcb32e790d9f046a
source_version = sv_f548f51a5df5
book_source    = bs_04a94146a35f
source_type    = BOOK
extractor      = pilot-declared
status         = GENERATED
```

四条声明，全部 `declared_in = BOOK_SOURCE_CATALOG`：

```
AUTHOR       [美]悉尼·霍默 理查德·西勒
TITLE        利率史（第四版）
PUBLICATION  中信出版社
IDENTIFIER   9787508617497
```

`authors` 原样存为**单元素数组**，未切分。

### 1.2 产物不是什么

- 不是对来源的评价。`importance` / `quality` / `credibility` /
  `ranking` / `significance` 全部在 `PAPER_BANNED_FIELDS` 里，
  且 `rate_source` / `rank_sources` / `approve` 三个方法直接抛异常。
- 不是 `UNKNOWN`。词表只有 BOOK/PAPER/ARTICLE/REPORT/ARCHIVE；
  读不出来是一种**读取状态**，不是一个关于世界的事实。
  允许它进表，就等于让「我们无法判断」被存成「它是一本书」。
- 不是抽取结果。`extracted_rows = 0`：本阶段不含抽取器。
- 不是贡献判断。「作者A提出方法B」是原文声明（可存），
  「作者A贡献最大」是系统生成的判断（不可存）。

## 2. Phase 0 的核心发现：语料无法供给 span 证据

实测本语料全部文本：

```
reading_evidence  17 行，content 合计 671 字符
出现「霍默」/「理查德」（两位作者）   0
出现「中信」（出版社）                 0
出现「9787」（ISBN 前缀）             0
出现任何 4 位年份                     0
出现「作者/出版/译者/版权」            0
```

书目数据只存在于 `book_source` 这一行**编目记录**里。
摄取只覆盖第一章正文——没有扉页、没有版权页。

于是 `statement_type` 的五个值**全部**没有可支撑它的跨度。
若仍按提案把 `evidence_ids` 指向 `reading_evidence`，
`traceability=100%` 就是编造而不是测量。

**已按 F1 决策改为锚定编目记录**：`paper_evidence.catalog_source_id`
是到 `book_source` 的外键，每条 `declared_value` 由
`declaration_matches_catalog()` 与它所声称的字段**逐字比对**。
声明的值不是调用方给的，而是从记录里读出来的——所以伪造的引用
根本写不出来。

**遗留限制（如实冻结）**：`declaration_by_text_span` **未经检验**。
`declared_in` 为 `TITLE_PAGE` / `COPYRIGHT_PAGE` / `CIP_RECORD` 留了位置，
若将来摄取前置页有地方记录，但三个都未被使用。

## 3. KNOWN_LIMITATION（冻结）

以下均为**实测**，不是推测。

1. **DB 层没有状态机守卫。** 直连 SQL 可以把 `SUPPORTED` 改回
   `GENERATED`（079 已实测过同类）。合法转移只由
   `PaperWriter.transition()` 把守。
2. **DB 层不保证 `declared_value` 就是记录所说的内容。** 外键证明记录存在，
   不证明关于它的句子为真。这是 writer 的职责，由 `declaration_fidelity` 门读取。
3. **R10 实测到一个真实缺口：声明可以指向不属于其 candidate 的编目记录。**

   ```
   INSERT INTO paper_evidence (... catalog_source_id = 'bs_probe' ...)
   => INSERT ACCEPTED（被 paper_evidence_catalog_source_id_fkey 接受，
      因为 bs_probe 确实存在）
   ```

   `paper_evidence` 没有自己的 `book_source_id` 列，因此
   `candidate.book_source_id` 与 `declaration.catalog_source_id`
   之间的相等性**在 DB 层无法表达**。它由服务层拦住
   （`DECLARATION_OTHER_CATALOG_ROW`），测试
   `test_a_declaration_cannot_be_written_for_another_record` 读它。

   修法是存在的——复合外键
   `(paper_id, catalog_source_id) → paper_source_candidate(id, book_source_id)`
   加上一个 `UNIQUE (id, book_source_id)` 索引，与 079/080 的做法一致。
   但 **080 已经应用**，而本项目从 070 起就有一条硬规矩：
   **绝不改已应用的迁移**。所以这条留作已知限制，修它是 **081** 的事，
   不是回改 080。

4. **`publication_year` 是无界 INTEGER。** A仓 没有任何年份可供核对，
   凭空加一个界就是凭空造一个事实。
5. **抽取质量未测。** 召回率与精确率是未知数，不是「已验证为空」。

## 4. 冻结时的验收状态

```
A_P5_3_PAPER_SCHEMA        = PASS
A_P5_3_PAPER_IMPLEMENTATION = PASS

GATE_1_schema / fk_verb / isolation_schema / frozen_index = PASS
GATE_1_constraints / vocabulary / not_null / column_parity = PASS
GATE_1_hash_formula / banned_fields                          = PASS
GATE_2_authority / frozen_layers / baseline_unchanged        = PASS
GATE_2_catalog_untouched                                      = PASS
GATE_3_trace / declaration_fidelity                           = PASS
GATE_4_replay / idempotency / hash_stability                  = PASS
GATE_5_isolation                                              = PASS
GATE_6_negative                                               = PASS  (23 / 23)

candidate_persisted = 1      declarations_persisted = 4
traceability = 100.0%        declaration_fidelity = PASS
replay_stable = PASS         unauthorised_type_rows = 0
orphan_declarations = 0      unsourced_declarations = 0
B/C contamination = 0        BU2 = 0    baseline_mutated = 0
```

`tests/architecture/test_a_paper_authority.py` — 58 passed。
`tests/architecture` 全量 864 passed / 6 skipped。

DB 侧独立验证（不经 Python，直接 psql）：

```
fidelity  : candidates=1 declarations=4
            all_match_record=true  all_from_own_catalog=true
authors   : cardinality=1，原样未切分

R1  UNKNOWN_AS_FACT        -> refused (paper_candidate_source_type_check)
R2  MANUSCRIPT            -> refused (同上)
R3  status='APPROVED'     -> refused (paper_candidate_status_check)
R4  empty authors         -> refused (paper_candidate_authors_check)
R5  duplicate paper_hash  -> refused (paper_candidate_hash_uniq)
R6  duplicate evidence_hash -> refused (paper_evidence_hash_uniq)
R7  statement_type=CONTRIBUTION -> refused (paper_evidence_statement_type_check)
R8  declared_in=AUTHOR_INTERVIEW -> refused (paper_evidence_declared_in_check)
R9  跨编目记录（id 全部真实）    -> refused (paper_candidate_same_source)
R10 声明指向别人的编目记录        -> **被接受**，见 §3.3
R11 删除被引用的 book_source     -> refused (paper_candidate_book_fkey)
四个外键 confdeltype 全部 = r (RESTRICT)；指向 A 仓以外的外键 = 0
```

R9 拦下的正是 079 实测过的那一类谎话：两边 id 单独看都合法，
合起来描述的是两本不同的书。

重放：同一份 SQL 连跑 3 次，`paper_source_candidate` / `paper_evidence`
稳定在 1 / 4。

回归：`tests/` 的 failed/errored 集合与 P5.2 冻结时**逐项相同**
（217 项，新增集合为空）。`tests/architecture` 从 806 增至 864。
P5.3 的代码只被自己的测试文件 import。

Ruff 未在本机执行（`ruff` 二进制未安装，`line-length = 100` 已按
pyproject 人工核对：新文件 0 行超长）。

## 5. 决策记录：与提案 v1.0 的偏离

Phase 0 停下后测出 7 条，其中 3 条需要你决定，均已决定并落地。

**F1 — 证据锚定为编目记录（已决策）。**
见 §2。代价是 `declaration_by_text_span` 未经检验，如实记为限制。

**F2 — 新增 `book_source_id` 外键（已决策）。**
提案只 FK 到 `source_version`，却逐字复制 `title` / `publisher` / `isbn`。
没有这个外键，改 `book_source` 会让 candidate 静默过期且无人能察觉。
080 用复合外键把「这条注解的编目记录，必须是它自己那个版本的编目记录」
变成 DB 保证（R9 实测）。

**F4/F5/F6/F7 — 五项收紧全部采纳。**
`publisher` 进入 `paper_hash`（提案 §5 漏了它，改出版社不改指纹）；
证据**不**进 `paper_hash`，作为 candidate 之下的可追加层，
其重放键是 `evidence_hash`（这解决了提案 §5 与 §9 的自相矛盾：
§9 把证据列为重放键，§5 的公式却不含证据，本阶段按 §5 执行并写明理由）；
新增 `evidence_hash UNIQUE`（提案对 `paper_evidence` 没有任何唯一约束）；
新增 `cardinality(authors) >= 1` 与 `statement_type` CHECK。

**另外两项收紧（非提案所列，按已验证的漏洞执行）：**
`authors` 进哈希时**不排序**（作者次序是第一作者/通讯作者的事实）；
pilot **原样存单元素** `authors`，因为把
`[美]悉尼·霍默 理查德·西勒` 切成两个名字属于作者身份解析，
而 §14 LIMITATION-2 明写不做这件事。

## 6. 三件本阶段没有证明的事（如实列出）

```
declaration_by_text_span          未检验：语料无跨度声明来源元数据
publication_year_and_doi          未检验：A仓 无年份、无 DOI，两列均为 NULL
author_identity_resolution        未做：作者字段原样存，未切分、未归一
```

这三项写进 artifact 的 `UNTESTED` 字段，并有测试读取
（`test_the_untested_things_are_declared_not_hidden`）。
**「未经检验」与「已验证为空」是两件事**：前者是本报告的结论，
后者不是——本阶段对这三项既没有验证通过，也没有验证失败。

`declaration_coverage` 也会如实显示 YEAR 为 `False`：
词表里有 YEAR，但编目记录没有年份字段，没有可比对的字段，
所以 YEAR 声明写不出来。四个 statement_type 被覆盖，第五个不是缺口，
是**可证明的不可写**。

## 7. 阶段状态

```
P5_0_CONDITION_BOUNDARY = FROZEN
P5_1_MECHANISM          = FROZEN
P5_2_RELATION           = FROZEN     (PRECEDES_ONLY)
P5_3_PAPER              = FROZEN     (BOOK, 4 declarations)
P5_3_EXTRACTION         = NOT_STARTED（extracted_rows = 0）
075_ku_relation         = FROZEN，未动
079_relation_candidate  = FROZEN，未动
NEXT                    = 081：补 paper_evidence 的复合外键（§3.3）
                          或先摄取前置页，让 TITLE_PAGE 声明成为可能
```

## 8. FINAL REPORT

```
TASK             = A_P5_3_PAPER
MIGRATION_080    = 080_a_paper_source.sql
SOURCE_TYPE      = BOOK
PAPER_ROWS       = 1
EVIDENCE_ROWS    = 4
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
runner 读 `A_P5_3_COMMIT_SHA` / `A_P5_3_TAG`，提交时再填。
冻结报告自己编一个 commit id 比没有更糟。

---

FINAL AUTHORITY:

```
STRATUM_A stores what a source record declares about itself.
STRATUM_A does not judge the source.
```