# A REPOSITORY SPEC — Stratum A仓真实书籍理解事实仓

STATUS=DEFINED
BASELINE=bu2-v2.0-freeze
SCOPE=A仓（原始书籍理解事实仓）

## 1. A仓定位

A仓 = 原始书籍理解事实仓。

保留：
- 原始来源（BookSource / SourceVersion）
- 阅读证据（ReadingEvidence）
- 页面/章节结构（reading_ledger 已有）
- KU抽取证据链（KnowledgeUnitCandidate -> ReadingEvidence）
- provenance（parser_version / extractor_version / locator）

不做：
- B仓概念去重
- C仓推理生成
- 本性(emergent essence)计算

## 2. 核心对象模型

```
BookSource
    |
    +-- SourceVersion
            |
            +-- ReadingRun
                    |
                    +-- ReadingEvidence
                            |
                            +-- KnowledgeUnitCandidate
```

关系基数：
- BookSource 1:N SourceVersion（一本书多个版本：PDF v1 / EPUB v2 / OCR修正版）
- SourceVersion 1:N ReadingRun（一个版本可被多次阅读/重读）
- ReadingRun 1:N ReadingEvidence（一次阅读产生多条证据）
- ReadingEvidence 1:N KnowledgeUnitCandidate（一条证据可产生多个候选）

## 3. 对象定义

### 3.1 BookSource

职责：真实书籍身份。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 书籍身份标识 |
| title | TEXT | 书名 |
| author | TEXT | 作者 |
| publisher | TEXT | 出版社 |
| isbn | TEXT (optional) | ISBN |
| language | TEXT | 语言 |
| source_type | TEXT | 来源类型（book/textbook/monograph/...） |
| created_at | TIMESTAMPTZ | 登记时间 |

### 3.2 SourceVersion

职责：版本固定。

例如：PDF v1 / EPUB v2 / OCR修正版。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 版本标识 |
| book_source_id | TEXT FK -> BookSource | 所属书籍 |
| checksum | TEXT | 文件 checksum（版本固定） |
| format | TEXT | PDF / EPUB / HTML / OCR_TEXT |
| page_count | INTEGER | 页数 |
| metadata | JSONB | 版本级元数据 |

### 3.3 ReadingRun（已有，060）

已有表 `stratum.book_reading_run`，A仓复用：
- source_id 指向 SourceVersion（语义约束，不改 schema）
- status 使用 065 authority 的 10 状态机
- coverage_json / open_gaps_json 已有

### 3.4 ReadingEvidence（新增）

职责：A仓核心。每条 KU 必须可追溯。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 证据标识 |
| run_id | TEXT FK -> book_reading_run | 所属阅读运行 |
| source_version_id | TEXT FK -> source_version | 证据来源版本 |
| page_locator | TEXT | 页面定位（页码/锚点） |
| chapter_locator | TEXT | 章节定位 |
| quote_span | TEXT | 原文引用/span |
| context | TEXT | 上下文窗口 |
| parser_version | TEXT | 解析器版本 |
| extractor_version | TEXT | 抽取器版本 |
| created_at | TIMESTAMPTZ | 生成时间 |

不变量：
- evidence 不能脱离 source_version 存在（FK NOT NULL）
- evidence 必须属于某个 reading_run（FK NOT NULL）

### 3.5 KnowledgeUnitCandidate（新增）

职责：从阅读证据产生。

注意：KU Candidate != B仓 KU。只代表："这本书这里表达了一个知识单元"。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TEXT PK | 候选标识 |
| reading_evidence_id | TEXT FK -> reading_evidence | 来源证据 |
| content | TEXT | 候选知识单元内容 |
| concept_hint | TEXT | 概念提示（非B仓概念） |
| confidence | REAL | 抽取置信度 |
| status | TEXT | EXTRACTED / REVIEWED / ACCEPTED / REJECTED |
| created_at | TIMESTAMPTZ | 生成时间 |

status 状态机：
```
EXTRACTED -> REVIEWED -> ACCEPTED
                     \-> REJECTED
```

不变量：
- KU candidate 必须挂 reading_evidence（FK NOT NULL）
- 禁止直接挂 knowledge_claims（B仓对象）——A仓候选不直接成为B仓KU

## 4. 与已有 BU2 表的关系

| 已有表 | A仓关系 |
|--------|---------|
| book_reading_run (060/065) | 复用为 ReadingRun；source_id 语义指向 SourceVersion |
| reading_ledger (060) | 页面/章节结构记录，不变 |
| evidence_trajectory (061) | B仓 claim 级证据链，A仓不直接使用 |
| knowledge_claims (020) | B仓 KU 权威，A仓候选不直接写入 |

## 5. 禁止事项

- 不修改 060-066 migration
- 不修改 BU2 foundation schema
- 不修改 runtime authority
- 不修改生产历史数据
- 新能力必须 additive（新表 070+）

A_MODEL_SPEC=DEFINED
