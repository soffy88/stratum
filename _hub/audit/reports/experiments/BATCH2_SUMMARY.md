# BATCH2 实证期汇报 — 最终报告
**日期**: 2026-05-17  
**状态**: 进行中 — #03 Embedding 评测运行中（qwen3-embedding-0.6B 编码中）

---

## 实证项状态总览

| # | 实证问题 | 状态 | 结论 |
|---|---------|------|------|
| 01 | PDF解析器选型 | ⚠️ PARTIAL | pymupdf4llm ✅，unstructured ✅，docling ✅，**marker-pdf INFRA_FAIL** |
| 02 | 向量数据库选型 | ✅ COMPLETE | 推荐 **chromadb**（p50=1.96ms，最快查询）|
| 03 | Embedding模型选型 | 🔄 进行中 | bge-m3 ✅，qwen3-embedding-0.6B 评测中 |
| 05 | MCP框架选型 | ✅ COMPLETE | 推荐 fastmcp |
| 06 | 段落Anchor验证 | ✅ COMPLETE | PASS（已知大纲污染，CSS可缓解）|

---

## #02 向量数据库 — 关键数字

**推荐: chromadb**

| 数据库 | 插入速率 (vps) | 向量查询 p50 | 过滤查询 p50 | RSS |
|--------|--------------|------------|------------|-----|
| pgvector | INFRA_SKIP | — | — | — |
| qdrant 1.14.1 | 3,232 | 106.62 ms | 154.19 ms | 305 MB |
| **chromadb 1.0.8** | 1,513 | **1.96 ms** | 13.25 ms | 343 MB |
| lancedb 0.22.0 | **15,787** | 17.16 ms | 26.05 ms | 1,230 MB |

pgvector INFRA_SKIP 原因：WSL2 无 systemd，PostgreSQL 服务无法启动。  
chromadb 选型原因：向量查询 p50 最快（1.96ms），PersistentClient API 简洁，适合单机自托管。

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
4. **#02**: pgvector 在无 systemd WSL2 环境中不可用；SPEC 若要支持 pgvector 需说明 PostgreSQL 部署要求。
5. **#03**: SPEC 应明确向量存储的 embedding 模型约束，建议添加 "最低 CPU 编码率 >1 text/s" 的选型约束（bge-m3 满足，decoder-only 模型通常不满足）。

---

## 下一步

1. **marker-pdf 恢复（可选）**: 建议 conda env (Python 3.10 + Pillow 10.x) 或 Docker
2. **#03 收尾**: qwen3-embedding-0.6B 评测完成后 → 更新 03-embedding-comparison.md + YAML → commit + tag v0.1.0

---

## 已完成文件

```
_hub/audit/reports/experiments/
├── 01-pdf-parser-comparison.md             ← #01 完整报告
├── 02-vector-db-comparison.md              ← #02 完整报告
├── 02-vector-db-comparison.yaml            ← #02 机器可读结果
├── 03-embedding-comparison.md              ← #03 报告（bge-m3完成，qwen3待填入）
├── 05-mcp-framework-comparison.md          ← #05 完整报告
├── 06-paragraph-heading-verification.md    ← #06 完整报告
└── BATCH2_SUMMARY.md                       ← 本文件

experiments/02-batch/
├── samples/pdf/              # 5个测试PDF（.gitignore）
├── parsed/                   # 解析结果（.gitignore）
├── benchmarks/               # 基准测试数据（.gitignore）
│   ├── embedding_results.json
│   ├── vector_db_results.json
│   └── embeddings_bge_m3.npy
├── mcp-samples/              # MCP对比实现
├── generate_embeddings.py
├── run_vector_benchmark.py
├── run_embedding_benchmark.py
├── run_qwen3_eval.py
├── patch_qwen3_heuristic.py
└── run_bgem3_partb.py
```
