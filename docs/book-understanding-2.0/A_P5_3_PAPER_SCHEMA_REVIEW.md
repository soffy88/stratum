# A_P5_3_PAPER SCHEMA REVIEW

TASK=A_P5_3_PAPER_IMPLEMENTATION
PHASE=0 (schema review) — **STOPPED BEFORE WRITING 080**
BASELINE=P5.2_RELATION=FROZEN (079), 078/077/075=FROZEN
STATUS=BLOCKED_PENDING_DECISION

---

## 0. 一句话结论

`080` 还没写。Phase 0 实测发现 **本语料里没有任何一个证据跨度声明过来源元数据**：
作者、ISBN、出版年、出版社在 A仓 全部文本中出现 **0 次**。
把 `paper_evidence.evidence_ids` 指向某个跨度，等于**伪造可追溯性**——
而这正是 P5.0「absence != verified-empty」纪律要防的事。

其余 7 条是可实现的偏离，逐条给出实测证据。

## 1. F1 — 语料无法供给 evidence-linked source annotation（BLOCKER）

实测 `stratum_a_p3_staging`：

```
reading_evidence            17 行，content 全部非空，合计 671 字符（均 ~39 字）
ku_candidate.content       合计 420 字符
knowledge_unit.statement   合计 262 字符

在上述全部文本中：
  出现「霍默」（作者姓氏）        0 次
  出现「理查德」（第二作者）      0 次
  出现「中信」（出版社）          0 次
  出现「9787」（ISBN 前缀）       0 次
  出现任何 4 位年份              0 次
  出现「作者/出版/译者/版权」      0 次
```

来源元数据只存在于 `book_source` 这一行目录记录里：

```
title=利率史（第四版）  author=[美]悉尼·霍默 理查德·西勒
publisher=中信出版社    isbn=9787508617497    language=zh
metadata={"edition":"第四版","translator":"曹建海"}
```

即：**书目来自编目记录（manifest），不来自正文。**
摄取只覆盖了第一章正文，没有版权页、没有扉页、没有题名页。

后果，按 `statement_type` 逐条看：

```
statement_type   语料里能否找到声明该事实的跨度
AUTHOR           否   —— 0 次提到作者
TITLE            否   —— 0 次提到书名（跨度全是信贷史的句子）
PUBLICATION      否   —— 0 次提到出版社
YEAR             否   —— 0 个年份
IDENTIFIER       否   —— 0 次 ISBN
```

**五个 statement_type 全部无法被真实证据支撑。**
§16 要求的 `traceability=100%` 若靠把 `reading_evidence` 的 id 挂上去达成，
那不是可追溯，是编造。

## 2. F2 — `book_source` 已经持有 4 个同名列

```
book_source: id, title, author, publisher, isbn, language, metadata, created_at
paper_source_candidate 将要新增: title, authors, publisher, isbn
```

`title` / `publisher` / `isbn` 是**同一份数据的第二份副本**，
只有 `authors`（数组化）和新增的 `source_type` / `publication_year` / `doi`
是新信息。

要问的是：080 是**注释层**还是**副本**？
如果是副本，就多了一份要同步的数据，而且没有任何外键把两者绑在一起——
`paper_source_candidate` 只 FK 到 `source_version`，不 FK 到 `book_source`，
改 `book_source.title` 不会、也无法让 `paper_source_candidate.title` 失效。

顺带实测：`source_type` 这个概念在 A仓 **完全不存在**
（全库 0 个 `source_type` 列），`book_source` 只靠表名暗示是书。
所以 `source_type` 确实是新信息。

## 3. F3 — `publication_year` 与 `doi` 在本语料无来源

```
book_source 的年份/日期列 = 0 个
全库 doi 列                = 0 个
metadata 的键             = edition, translator（无年份、无 DOI）
```

两列都是 nullable，pilot 里会全是 NULL。后果：
**YEAR 与 IDENTIFIER 两个 statement_type 无法被 pilot 覆盖**，
而它们恰恰是 `statement_type` 词表的一半。

## 4. F4 — §5 公式漏掉 `publisher`

```
列:            title, authors, publication_year, publisher, doi, isbn
§5 哈希输入:   source_version_id, source_type, title, authors,
               publication_year, doi, isbn, extractor_version
                                  ^^^^^^^ publisher 不在公式里
```

改出版社不改变 `paper_hash`。这与 077–079 每一张表的做法相反：
那些表的 hash 覆盖该行的全部身份字段。要么把 `publisher` 加进公式，
要么明确写下「出版社不是身份的一部分」——后者是个需要理由的决定。

## 5. F5 — §5 公式不含 evidence，§9 却把 evidence 列为重放键

```
§5  paper_hash = sha256(source_version | source_type | title | authors |
                          publication_year | doi | isbn | extractor_version)
§9  "Same: source_version, metadata, evidence, extractor_version → NOOP"
```

两处不一致。若按 §5，**换了证据不会产生新 candidate**（hash 不变 → NOOP）；
若按 §9，应该产生。P5.1 的做法是把证据**传递地**纳入 hash
（`node_id` 含 evidence → `mechanism_hash` 含 node_id），
079 没有证据列所以不涉及。080 的 `paper_evidence` 是独立表，
§5 的公式对它**完全没有覆盖**。

需要决定：证据是身份的一部分，还是挂在身份之外的追加层？

## 6. F6 — `paper_evidence` 没有任何唯一约束

对比同一条链上的前两阶段：

```
078  mechanism_node   UNIQUE (mechanism_id, sequence_order)
079  relation_candidate 复合 FK + 两侧各一列
080  paper_evidence   （无）
```

后果：同一 `(paper_id, statement_type)` 可以无限追加证据行，
重放时也没有任何键可以判断「这条证据是否已存在」。

**建议**：加 `evidence_hash TEXT NOT NULL UNIQUE`
（对 `evidence_ids` 排序后取 sha256），与 A仓 其它表的做法一致。

## 7. F7 — `evidence_ids` 缺 cardinality 检查

077 实测过 `array_length(ARRAY[]::text[],1)` 是 NULL 且 CHECK 在 NULL 上通过，
所以 078/079 都改用 `cardinality(...) >= 1`。§4 只写了
`evidence_ids TEXT[] NOT NULL`，没有这条 CHECK。**建议补上**。

## 8. F8 — `paper_evidence` 没有书级隔离

`paper_evidence` 只有 `evidence_ids TEXT[]`，**没有 `source_version_id`**，
所以 079 那种复合外键在这里**不可能建**：
跨书的证据 id 可以挂到任何 paper 上，DB 层挡不住，只有 writer 能挡。

如果按 F1 的结论把书目证据锚定到编目记录而非正文跨度，
那么 `paper_evidence` 需要的是**指向编目记录**的引用，
而不是 `TEXT[]` 跨度数组——这会改变表设计。

## 9. F9 — `authors` 排序规则未定义，且拆分作者名属于越权

`book_source.author` 是**一个字符串**：

```
author = "[美]悉尼·霍默 理查德·西勒"     -> 按空白切分得到 2 个 token
```

把它切成 `["[美]悉尼·霍默", "理查德·西勒"]` 是**一次作者身份解析**，
而 §14 LIMITATION-2 明写「Author identity resolution is not performed」。
所以 pilot 应当**原样存单元素数组**，不切分。

另外：作者顺序**是有意义的**（第一作者/通讯作者），进 hash 时**不能排序**；
而 `evidence_ids` 的顺序只是遍历顺序，**应当排序**。
两条规则不同，§5 需要写明用哪一条。

## 10. 需要你决定的五件事

1. **F1（关键）**：本语料无法提供真实的来源元数据证据。三条出路——
   (a) pilot 只验证**编目记录**层，把 `paper_evidence` 指向
   `book_source` / `source_version.file_hash` 而不是正文跨度，
   并把「正文跨度声明来源元数据」如实记为**未经检验**；
   (b) 承认本阶段无法验证 traceability，pilot 只落 candidate 不落 evidence，
   `traceability` 如实写 UNKNOWN 而非 100%；
   (c) 先扩摄取（版权页/扉页/题名页），再评估 P5.3。
2. **F2**：080 是注释层还是 `book_source` 的副本？是否 FK 到 `book_source`？
3. **F4/F5**：`publisher` 是否进 hash？证据是否进 hash（身份 vs 追加层）？
4. **F6/F7**：是否照建议加 `evidence_hash UNIQUE` 与 `cardinality >= 1`？
5. **F9**：确认 pilot 原样存单元素 `authors`、不切分作者名。