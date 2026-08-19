# Stratum 依赖 License 审计

> 日期：2026-08-02 · 范围：运行时依赖（Dockerfile.sl / pyproject.toml / aii uv.lock 主依赖）
> 目的：商业化（付费订阅 SaaS）前识别传染性许可证（AGPL/GPL/SSPL/LGPL），给出替代方案。
> 说明：SaaS 形态不向用户分发软件本体，**GPL/LGPL 不触发传染**（仅 AGPL/SSPL 对网络服务有传染性）；
> 但若未来提供 on-premise / 镜像分发 / 开源本项目，则 GPL 系列全部需要处理。

## 传染性风险（需处理）

| 依赖 | License | 用途 | 现状与处置 |
|------|---------|------|-----------|
| **pymupdf4llm** | **AGPL-3.0** | PDF→MD fallback | 默认路径已被 docling(MIT) 取代；镜像内仍保留作 fallback → 商业化前删除，或加 `STRATUM_PDF_PARSER=docling` 硬切后从镜像移除 |
| **pymupdf (PyMuPDF)** | **AGPL-3.0** | PDF 底层解析（pymupdf4llm/oprim.parse_pdf 依赖） | 同上；docling 不依赖 PyMuPDF（内部用 pdfium），删除 pymupdf4llm 时一并移除 |
| **edge-tts** | GPL-3.0 | TTS（audio_generator） | GPL 非 AGPL → SaaS 可用；不阻塞。若未来开源/分发需换 MIT 方案（如 Kokoro/azure-cognitiveservices-speech） |
| **python-igraph** | GPL-2.0+ | AII 图谱/莱顿聚类（Dockerfile.sl 已装） | GPL 非 AGPL → SaaS 可用；开源分发时需换（igraph C 库是 GPL，替代：networkx + louvain-communities MIT） |
| **leidenalg** | GPL-3.0 | 莱顿社区检测（AII KC 聚类） | 同上；替代：`leidenalg` 无 MIT 平替，可用 `igraph` 内置 leiden 或 community 库 |
| **psycopg2-binary** | LGPL-3.0（带例外） | PG 连接 | LGPL 动态链接 → SaaS/分发均可接受（带例外条款明确允许） |
| **paramiko** | LGPL-2.1 | SSH | LGPL 动态链接 → 可接受 |

## 宽松许可（无风险，主要运行时依赖）

MIT：docling、fastapi、mcp、tantivy、duckdb、fsrs、apscheduler、redis、PyJWT、argon2-cffi、pydantic、typer、rich、paddleocr、faster-whisper、python-frontmatter、alembic、pyclipper、python-docx、edge-tts（见上）…
Apache-2.0：tenacity、structlog、docker、opencv-contrib、google-*-api、lancedb
BSD-3-Clause：httpx、uvicorn、numpy、scipy、pandas、scikit-learn、statsmodels、shapely
MIT/Apache：dashscope、stripe、alipay-sdk-python
Unlicense：yt-dlp

## AII 侧（aii/uv.lock）

主要依赖与上面重叠（fastapi/asyncpg/psycopg/numpy/oprim 等）。`oprim/oskill/omodul/obase/oservi`（3O 平台包）
为内部私有包，license 由其 owner 决定，需在对外发布前确认。

## 行动项

1. [x] 默认 PDF 解析切 docling（MIT）——代码已支持（`services/pdf_to_markdown.py` 三级 fallback，docling 第一）
2. [x] `pyproject.toml` ingest-pdf 组声明 `docling>=2,<3`；`Dockerfile.sl` 安装 docling
3. [ ] 商业化前：从镜像移除 pymupdf4llm + pymupdf（或验证 `STRATUM_PDF_PARSER` 硬切后零依赖）
4. [ ] 开源/分发前：确认 3O 平台包 license；评估 edge-tts / igraph / leidenalg 替代
5. [ ] 复查命令：`uv pip tree` + `pip-licenses`（`pip install pip-licenses && pip-licenses --format=markdown --order=count`）
