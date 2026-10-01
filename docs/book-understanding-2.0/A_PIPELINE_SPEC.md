# A PIPELINE SPEC — A仓固定流水

STATUS=DEFINED
BASELINE=bu2-v2.0-freeze
SCOPE=A仓真实书籍理解流水

## 固定流水

```
INPUT
PDF/EPUB/HTML
    |
    v
INGESTION
文件登记
    |
    v
PARSER
结构解析：book / chapter / section / page
    |
    v
READING_LEDGER
记录：UNSEEN / PARSED / READ / INTERPRETED
    |
    v
EVIDENCE_EXTRACTION
生成：ReadingEvidence
    |
    v
KU_EXTRACTION
生成：KnowledgeUnitCandidate
    |
    v
HUMAN/AGENT_REVIEW
accept / reject
    |
    v
A仓完成
```

## 阶段定义

### S1 — INPUT

- 输入：PDF / EPUB / HTML 文件
- 职责：接收原始文件，不解析内容
- 输出：原始文件 + 基本文件属性（大小、格式、页数探测）

### S2 — INGESTION（文件登记）

- 职责：
  - 登记 BookSource（真实书籍身份）
  - 登记 SourceVersion（checksum 固定版本）
  - 创建 ReadingRun（source_id 指向 SourceVersion）
- 输出：book_source_id / source_version_id / run_id
- 幂等：同 checksum 的 SourceVersion 不重复登记

### S3 — PARSER（结构解析）

- 职责：
  - 解析 book / chapter / section / page 结构
  - 生成 reading_ledger 条目（item_type: chapter/section/page/fragment/figure/table/equation）
  - 初始 status = UNSEEN
- 输出：reading_ledger 行（expected=true 的结构项）
- 记录：parser_version 写入 evidence 链

### S4 — READING_LEDGER（阅读记录）

- 职责：
  - 跟踪每个结构项的阅读状态
  - 状态：UNSEEN -> PARSED -> READ -> INTERPRETED
  - 终态：VERIFIED / UNREADABLE / NEEDS_VISUAL_REVIEW / RECONCILED
- 输出：reading_ledger 状态流转
- 复用：060 已有表，不改 schema

### S5 — EVIDENCE_EXTRACTION（证据抽取）

- 职责：
  - 从 READ/INTERPRETED 的 ledger 项生成 ReadingEvidence
  - 每条证据必须携带：source_version_id / page_locator / chapter_locator / quote_span / context / parser_version / extractor_version
- 输出：reading_evidence 行
- 不变量：evidence 不能脱离 source_version 存在

### S6 — KU_EXTRACTION（候选抽取）

- 职责：
  - 从 ReadingEvidence 生成 KnowledgeUnitCandidate
  - 候选只代表"这本书这里表达了一个知识单元"
  - 初始 status = EXTRACTED
- 输出：ku_candidate 行
- 不变量：candidate 必须挂 reading_evidence；不直接写 B仓 knowledge_claims

### S7 — HUMAN/AGENT_REVIEW（审核）

- 职责：
  - 对 KU Candidate 做 accept / reject
  - 状态：EXTRACTED -> REVIEWED -> ACCEPTED / REJECTED
- 输出：candidate status 终态
- 禁止：批量自动 accept（ONE_BOOK_ONLY pilot 阶段必须人工/agent 逐条）

### S8 — A仓完成

- 完成条件：
  - 100% page accounting（reading_ledger 全覆盖）
  - 每条 KU candidate 可追溯到 reading_evidence
  - 每条 reading_evidence 可追溯到 source_version + page_locator

## 与 BU2 流水线的关系

- A仓流水是 BU2 7-pass 流水的事实基础：
  - S3 PARSER ≈ BU2 Pass 1-2（结构解析 + 深读）
  - S5 EVIDENCE ≈ BU2 Pass 2 证据层
  - S6 KU 候选 ≈ BU2 Pass 3 章节建模的输入
- A仓不做 B仓去重、C仓推理、本性计算
- BU2 runtime authority（065/066）不变；A仓新增表 070+ additive

## 禁止事项

- 不修改 060-066 migration
- 不修改 BU2 foundation schema
- 不修改 runtime authority
- 不修改生产历史数据
- 不执行 destructive migration
- 新能力必须 additive

A_PIPELINE_SPEC=DEFINED
