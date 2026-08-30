# AII Technical Debt

Last updated: 2026-08-30 — **AII 10/10 Architecture Closure**

> 本文件只描述**当前事实**。历史债务已归档至 `docs/history/`。
> 分类：`still_open` | `already_fixed` | `obsolete` | `superseded`
> 每条必须有 owner/priority/trigger（无 trigger 不允许长期保留）。

Legend: `[ ]` still_open · `[x]` already_fixed · `[~]` obsolete/superseded

---

## still_open

- [ ] **P2** `dao/concept.py` 是 DuckDB 时代遗留兼容 DAO，无 active route 引用，仅被 `tests/dao/test_corpus_isolation.py` 使用。保留至测试迁移后再删。Owner: knowledge. Trigger: 下次清理 sprint 迁移测试后删除。
- [ ] **P2** `audio_generator` 依赖 `omodul/obase` + 真实 TTS provider，本地可选依赖不完整，未验证真实音频生成与成本回滚。Owner: platform/deploy. Trigger: TTS provider 配置后执行一次真实 smoke test。
- [ ] **P2** monorepo 物理收敛（`aii/` 子树独立命名空间 vs `src/stratum/`）。`MONOREPO.md` P0-P4 已完成逻辑合并，物理目录收敛排期待 `KNOWLEDGE_MODEL.md §4` 评估。Owner: arch. Trigger: v1.1 后评估，不做大爆炸重构。
- [ ] **P2** oskill `ingest_substrate.py` 历史 `ulid` 列问题（外部包，不在本仓）。Owner: oskill 上游. Trigger: 下次确认 oskill 版本号变化时复核。
- [ ] **P2** `docs/yiwancheng/` pre-Phase 14 设计笔记未归档。Owner: docs. Trigger: 下次文档清理顺手归档至 `docs/history/`。
- [ ] **P2** license audit（Docling MIT vs pymupdf4llm AGPL 商业化风险）`docs/LICENSE_AUDIT.md` 已存在，需商业化排期前复核。Owner: legal. Trigger: 商业化前。

---

## already_fixed (本轮归档，保留指针)

- [x] DuckDB JSON列 / `ON CONFLICT` / `query()` UPDATE 防御 — P1.2 切 PostgreSQL 整库替换，已不存在（`src/stratum/db/__init__.py`）
- [x] `agents.py` AGENT_REGISTRY 缺 workflow — 3/4 已接入真实 Agent-class（`src/stratum/api/routers/agents.py`），仅 `audio_generator` 保留为 P2
- [x] `stratum-sl` 未生产化 — `deploy/docker-compose.yml` 中 `stratum-sl:9304` 已是生产主入口（MONOREPO.md P2/P4）
- [x] SPEC1/2 WS token / SSRF TOCTOU — 已修复
- [x] CORS 宽松 — legacy `:9302` 已用显式 `STRATUM_CORS_ALLOWED_ORIGINS` allowlist
- [x] JWT `JWT_SECRETS=new,old` 有序轮换 — 首个签发全部验证，生产校验 key 长度
- [x] legacy `:9302` NoteDAO 优先 `notes_sl` + `corpus_id→user_id` 映射 — 代码面完成，待部署 PG 验收

## obsolete / superseded (AII Closure 10/10 已收敛，不再作为当前债务)

- [~] **LanceDB 作为 canonical dense store** — 已由 `stratum.substrate_chunk.embedding vector(1024)` + pgvector 替代；`src/stratum/api/search_utils.py:get_lancedb_mgr` 仅作 rebuildable projection fallback。见 `docs/AII_ARCHITECTURE_CONTRACT.md §5`
- [~] **DuckDB 作为在线 store** — 已迁移至 `aii_kg` pgvector；`tests/conftest.py` 的 DuckDB fixture 仅供单测隔离，不再是 authority。`src/stratum/db/__init__.py.duckdb-backup` 保留回滚
- [~] **Tantivy 作为 canonical lexical store** — 保留为可选 projection/index，可从 PostgreSQL 全量重建；DB 是 authority。见 `docs/AII_ARCHITECTURE_CONTRACT.md §5`
- [~] **Concept 四表 / Relation 三表并存为 canonical** — 已收敛至 `stratum.concepts` / `stratum.concept_relations` 为唯一写入面，遗留表只读（`KNOWLEDGE_MODEL.md §4` → `docs/AII_ARCHITECTURE_CONTRACT.md`）
- [~] **Stratum 作为产品名** — 已收敛至 **AII / aiinote.com**；`README.md`、`docs/AII_ARCHITECTURE_CONTRACT.md`、`src/stratum/api/main.py` 已统一，`scripts/check_aii_naming.py` CI 门禁
- [~] **旧 AII/Stratum merge 阶段记录对当前架构的误导** — 已归档至 `docs/history/`

---

## 参考

- 架构宪法: `docs/AII_ARCHITECTURE_CONTRACT.md`
- 机器可读契约: `src/stratum/knowledge/contract.py`
- 唯一检索平面: `src/stratum/services/knowledge_view.py`
- 知识对象模型: `KNOWLEDGE_MODEL.md`
- 当前现状: `CURRENT_STATE.md`
- 历史: `docs/history/` + `CHANGELOG.md`
