# BATCH2 实证期汇报 — 阶段报告
**日期**: 2026-05-17  
**状态**: 部分完成 — #1 marker-pdf INFRA_FAIL，#2/#3 未启动

---

## 实证项状态总览

| # | 实证问题 | 状态 | 结论 |
|---|---------|------|------|
| 01 | PDF解析器选型 | ⚠️ PARTIAL | pymupdf4llm ✅，unstructured ✅，docling ✅，**marker-pdf INFRA_FAIL** |
| 02 | 向量数据库选型 | ⏸️ 未启动 | 因#01 marker INFRA_FAIL 停止 |
| 03 | Embedding模型选型 | ⏸️ 未启动 | 因#01 marker INFRA_FAIL 停止 |
| 05 | MCP框架选型 | ✅ COMPLETE | 推荐 fastmcp |
| 06 | 段落Anchor验证 | ✅ COMPLETE | PASS（已知大纲污染，CSS可缓解）|

---

## #01 PDF解析器 — 关键数字

**推荐: pymupdf4llm**

| 解析器 | 全部5样本总耗时 | 峰值内存 | CJK支持 | marker状态 |
|--------|--------------|---------|---------|-----------|
| pymupdf4llm 0.3.4 | **11.2s** | 99.7 MB | ✅ | — |
| unstructured 0.18.32 | 8.5s | ~50 MB | ✅ | — |
| docling 2.93.0 | 1084s | >500 MB | ❌ | — |
| marker-pdf 1.10.2 | — | — | — | ❌ INFRA_FAIL |

marker INFRA_FAIL 原因：surya-ocr 依赖 Pillow<11，系统 Pillow=12.2.0 无法降级。

## #05 MCP框架 — 关键数字

**推荐: fastmcp**

| 框架 | 代码行数 | 冷启动 | Schema生成 |
|------|---------|-------|-----------|
| anthropic SDK | 64行 | 1046ms | 手动JSON |
| fastmcp | **28行** | 1455ms | Pydantic自动 |

## #06 段落Anchor — 关键数字

`## para-[A-Z0-9]{6}` 验证结果：5项检查 4 PASS + 1 KNOWN_ISSUE（大纲污染）

---

## SPEC 反馈累积 (本批不改 SPEC，记录于此)

1. **#01**: S2类旧Type1字体PDF（1990s-2000s arxiv）所有解析器均有不同程度乱码；STRATUM_SPEC 应在 substrate.paper.ingestion_notes 字段记录 parser 版本和 font_issue 标志。
2. **#01**: docling 的 `<!-- formula-not-decoded -->` 占位符在 Stratum 节点存储时需要过滤或保留决策，SPEC 未明确。
3. **#06**: Obsidian 大纲污染 CSS 缓解方案应列入 Stratum setup guide（Batch 4）。

---

## 下一步（待 Wiki 处理）

1. **marker-pdf 恢复**: 建议 conda env (Python 3.10 + Pillow 10.x) 或 Docker，由 Wiki 决定
2. **#02 向量DB**: 待 marker 问题决策后，需决定是否用 marker 数据或跳过 marker、仅用其他3个解析器的输出
3. **#03 Embedding**: 同上，另需 HuggingFace token（MIRACL-zh 下载）

---

## 已完成文件

```
_hub/audit/reports/experiments/
├── 01-pdf-parser-comparison.md    ← #01 完整报告
├── 05-mcp-framework-comparison.md ← #05 完整报告  
├── 06-paragraph-heading-verification.md ← #06 完整报告
└── BATCH2_SUMMARY.md              ← 本文件

experiments/02-batch/
├── samples/pdf/          # 5个测试PDF（.gitignore）
├── parsed/               # 解析结果（.gitignore）
│   ├── S{1-5}/pymupdf4llm.md + .meta.yaml
│   ├── S{1-5}/unstructured.md + .meta.yaml
│   └── S{1-5}/docling.md + .meta.yaml
├── mcp-samples/          # MCP服务器实现对比
│   ├── anthropic-sdk-server.py (64行)
│   └── fastmcp-server.py (28行)
├── run_parser_eval.py
├── run_remaining_parsers.py
└── run_unstructured.py
```
