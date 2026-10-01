# A FIRST BOOK PILOT — 单书试点设计

STATUS=READY
BASELINE=bu2-v2.0-freeze
SCOPE=ONE_BOOK_ONLY

## 试点书籍

- Book: 利率史（第四版）
- Author: [美] 悉尼·霍默 (Sydney Homer) / 理查德·西勒 (Richard Sylla)
- Translator: 曹建海
- ISBN: 9787508617497
- Publisher: 中信出版社
- Language: zh

## Input Format

- 格式：PDF（中文扫描版或电子版）
- 本地已有 markdown 抽取稿：`wiki_kb/raw/02_经济学_(NEW)利率史(第4版).md`（9759 行，可作 parser 验证基准）
- 原始 PDF 需从合法来源获取并登记 checksum

## Pages

- 全书约 400 页（估计，以实际 PDF 为准）
- Pilot 范围：第 1 章（约 30-50 页）

## Expected Chapters

- 第 1 章：利率的早期历史（古代至中世纪）
  - 1.1 古代利率
  - 1.2 中世纪利率
  - 1.3 高利贷与宗教

## Extraction Target

- 第 1 章内所有可识别的知识单元：
  - 利率水平事实（时间/地点/利率值）
  - 利率决定因素（风险/流动性/货币供给）
  - 制度事实（法律/宗教/政策对利率的约束）
  - 关键人物与著作
- 目标 KU 候选数：20-50 条（第 1 章）

## Acceptance

1. **100% page accounting**
   - 第 1 章所有页在 reading_ledger 中有对应条目
   - 每页 status 不为 UNSEEN

2. **reading ledger coverage**
   - 第 1 章所有 chapter/section/page 结构项已登记
   - item_type 覆盖 chapter / section / page

3. **evidence provenance**
   - 每条 ReadingEvidence 可追溯到 source_version_id + page_locator
   - quote_span 非空且与原文匹配

4. **KU candidate traceability**
   - 每条 KnowledgeUnitCandidate 挂 reading_evidence_id
   - 每条候选可回溯到具体页码 + 原文引用

## 禁止

- 禁止批量导入（仅此一本书）
- 禁止自动 accept 所有候选（必须逐条人工/agent 审核）
- 禁止修改 060-066 migration
- 禁止修改 BU2 foundation schema
- 禁止修改 runtime authority

## 试点成功标准

- 第 1 章 100% 页面覆盖
- ≥20 条 KU 候选，每条有完整 provenance
- 人工审核完成，accept/reject 决定有记录
- 无 B仓/C仓副作用（不去重、不推理、不计算本性）

PILOT_SPEC_READY
