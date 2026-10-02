# A SCHEMA GAP REPORT

STATUS=AUDITED
BASELINE=bu2-v2.0-freeze
DB=aii_kg
SCHEMA=060-066

## 1. 已有覆盖（BU2 现有表）

| 表 | Migration | A仓用途 | 覆盖情况 |
|----|-----------|---------|----------|
| book_reading_run | 060 (065 状态机) | ReadingRun | 已有：run 级状态机、coverage_json、open_gaps_json；source_id 列可语义指向 SourceVersion |
| reading_ledger | 060 | 页面/章节结构记录 | 已有：item_type / item_identifier / status(UNSEEN..VERIFIED) / locator_json / page_number / expected |
| evidence_trajectory | 061 | B仓 claim 级证据链 | 已有但属 B仓：claim_id FK -> knowledge_claims；A仓不直接使用 |
| knowledge_claims | 020 | B仓 KU 权威 | 已有但属 B仓：A仓候选不直接写入 |

## 2. 缺失对象

| 缺失表 | 职责 | 验证方式 |
|--------|------|----------|
| book_source | 真实书籍身份（title/author/publisher/isbn/language/source_type） | `rg "book_source" src/stratum/db/pg_migrations/*.sql` → 无 CREATE TABLE |
| source_version | 版本固定（checksum/format/page_count/metadata） | `rg "source_version" ...` → 仅列引用，无 CREATE TABLE |
| reading_evidence | A仓核心证据（page_locator/chapter_locator/quote_span/context/parser_version/extractor_version） | `rg "reading_evidence" ...` → 无 CREATE TABLE |
| ku_candidate | KU 候选（content/concept_hint/confidence/status） | `rg "ku_candidate" ...` → 无 CREATE TABLE |

## 3. 差距分析

### 3.1 book_reading_run.source_id 语义缺口

- 现状：`source_id TEXT REFERENCES stratum.substrates(id)`（060）
- A仓需要：source_id 语义上指向 SourceVersion
- 方案：不改 schema（约束禁止）；在 A仓 service 层维护
  `run_id -> source_version_id` 映射（reading_evidence.source_version_id
  提供该链接）

### 3.2 reading_ledger 证据链缺口

- 现状：reading_ledger 有 locator_json / trace_json，但无独立证据行
- A仓需要：每条 KU 必须可追溯 quote_span + context
- 方案：新增 reading_evidence 表（070+），通过 run_id + item_identifier
  与 reading_ledger 关联

### 3.3 KU 候选隔离缺口

- 现状：knowledge_claims 是 B仓权威
- A仓需要：候选不直接成为 B仓 KU
- 方案：新增 ku_candidate 表（070+），FK -> reading_evidence，
  禁止 FK -> knowledge_claims

## 4. 新增 Schema 规则

如果新增 schema：

必须：
- migration 编号 070+
- 新表 additive，不修改 060-066 任何内容
- FK 方向：ku_candidate -> reading_evidence -> source_version -> book_source
- 所有新表 created_at/updated_at 默认 NOW()

禁止：
- 修改 060-066 migration
- 修改 BU2 foundation schema
- 修改 runtime authority
- 修改生产历史数据
- destructive migration

## 5. 建议新增 Migration（尚未执行，仅设计）

| 编号 | 表 | 说明 |
|------|-----|------|
| 070 | book_source | 书籍身份 |
| 071 | source_version | 版本固定（FK -> book_source） |
| 072 | reading_evidence | 阅读证据（FK -> book_reading_run, source_version） |
| 073 | ku_candidate | KU 候选（FK -> reading_evidence） |

SCHEMA_EXTENSION_REQUIRED=yes
