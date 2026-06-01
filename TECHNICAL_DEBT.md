# Stratum Technical Debt

Last updated: 2026-06-01 (Phase 14 SPEC 1/2 sign-off + Phase 14.5 sign-off)

Legend: `[ ]` open · `[x]` resolved · priority: **P0** blocker / **P1** soon / **P2** eventually

---

## DB 合并 §M3 — DuckDB 迁移后技术债

- [ ] **P1** `db/__init__.py` JSON 列反序列化: DuckDB JSON 列返回原始字符串 (不像 psycopg2
  自动 parse JSONB → dict). 现有路由将 anchor / payload / meta_json 等字段作为字符串返回给
  前端, 导致 `"anchor": "{\"char_start\":0,...}"` 双序列化问题.
  触发: §M4 REDLINE 测试, highlights / changefeed / notes_sl payload 读取失败.
  方案: 在 `_rows()` 内对 JSON 类型列自动 `json.loads()` (通过 DuckDB `cursor.description`
  type_code 识别, 或启发式: str 以 `{` / `[` 开头时尝试 parse).

- [ ] **P1** `db/write()` ON CONFLICT 依赖唯一约束: DuckDB 支持 `ON CONFLICT ... DO UPDATE`
  语法, 但要求目标列有 PRIMARY KEY 或 UNIQUE 索引. 若某表 `conflict_on` 列无约束,
  运行时报 `ConstraintException`. 触发: §M4 write() 调用路径 REDLINE.

- [ ] **P2** `query()` UPDATE 语句防御: `query()` 语义是 SELECT, 但若误传 UPDATE/DELETE,
  `cursor.description` 为 None → 返回 `[]` 而非报错. 应在函数顶加 assert 检查 SQL 前缀.

---

## Phase 14.5 — 前端装配

- [ ] **P1** `TextHighlighter` 跟 sanitized HTML 渲染冲突: `content/[id]/page.tsx` 用
  `TextHighlighter` 包裹 body 后，`sanitizeHtml()` 输出的 HTML 标签以纯文本渲染，
  丢失富文本格式 (alpha 期 `platform_content` 空, 影响为零; Hevi 内容灌入前必修)。
  方案: 新建 `ContentBody` wrapper client component，内部同时持有
  `dangerouslySetInnerHTML={{ __html: sanitizeHtml(html, SAFE_OPTIONS) }}` 渲染
  + `onMouseUp` highlight 逻辑，替代当前 `TextHighlighter` 直接包裹方式。
  ⚠️ 安全: `dangerouslySetInnerHTML` 必须配合 `sanitize-html` (已有 SAFE_HTML_OPTIONS
  allowlist)，不得裸传 `body_html`。触发: `platform_content` 有真实数据 / Hevi 内容接入前。

---

## SPEC 1/2 Service Layer (Phase 14 SaaS)

### DB Layer

- [ ] **P1** `SPEC 1 §S0.6 deviation`: `src/stratum/db/__init__.py` uses direct `psycopg2`
  instead of `oprim.db_insert / db_read / db_query / db_write / db_update / db_soft_delete`.
  oprim 1.14.0 **does** export these (signatures: `db_insert(*, dsn, table, data, returning)`),
  but they require `dsn` per-call rather than a connection-pool, and lack JSONB dict serialisation
  and TEXT[] array pass-through that our current impl provides (bug fixed in `5bd04740`).
  Switch back when oprim adds connection-pooled wrappers or when Stratum moves to psycopg3.
  Tracked: `src/stratum/db/__init__.py` ↔ `oprim.{db_insert, db_read, db_query, db_write, db_update, db_soft_delete}`

- [ ] **P1** `IngestResult.substrate_id` stores `str(IngestResult(...))` repr instead of
  bare ULID — omodul 1.14.0 bug. Workaround: `_extract_id()` regex in `inbox.py` (`159f1cb0`).
  Fix upstream in omodul; remove `_extract_id` when fixed.

### Service Layer Process

- [ ] **P0** `stratum-sl` Docker service added (`deploy/docker-compose.yml`) but not yet
  promoted to production — `docker-compose up -d stratum-sl` required after next deploy.
  The bare-process fallback (pid ~3541718) is still running and will die on reboot.

### Tests

- [ ] **P1** New service layer routes (PG-backed, `src/stratum/api/routers/`) have no CI
  integration tests — only REDLINE manual verification. Unit tests added in
  `tests/service_layer/` cover: notes CRUD+isolation, agents, inbox, search IDOR,
  WebSocket CSWSH. Needs DB fixture pointing at test PG instance for full CI coverage.

---

## Phase 14 — SaaS Backend

### Search & Indexing

- [ ] **P1** `oskill.hybrid_search` accepts `corpus_id` but does not filter at BM25/vector index level.
  Service layer post-filters in Python (correct but slower for large corpora).
  Target: physical partition or index-level filtering in oskill/oprim v1.2+. (Wave 2)

- [ ] **P2** `oskill` not installed in primary venv — tests use `SimpleNamespace` mocks.
  Full integration requires `pip install oskill` or wheels build in CI. (Wave 12)

### Agent & Job Stubs

- [ ] **P1** Agent runner (`POST /api/agents/run`) stores a stub record but does not execute real
  agent logic. Wired to `oskill` stub via `OScheduledJobsManager`. (Wave 5 / Wave 8)

- [ ] **P1** `OAnnotationLayer` block is display-only; annotation write-back to substrate is not
  implemented. Requires `/api/substrates/:id/annotations` endpoint. (Wave 8)

### Third-party Integrations (deferred to v1.1+)

- [ ] **P2** `dashscope_rerank` integration referenced in `oprim` — not activated.
  Planned for oprim v1.1+ once dashscope API key policy confirmed. (Wave 5)

- [ ] **P2** TTS service (`services/tts/`) scaffolded, no real implementation.
  Planned for oprim v1.1+ after TTS provider selection. (Wave 5)

- [ ] **P2** SMTP email delivery not wired. Reset-password and email-verification flows show
  placeholder UI only. Planned for v1.1+. (B-3)

### Auth & Security

- [ ] **P2** JWT secret read from `STRATUM_JWT_SECRET` env var; no rotation mechanism.
  Rotation requires session invalidation strategy. (Wave 1)

- [ ] **P2** CORS wildcard + credentials allowed in dev config (`app.py:31-37`). Must lock
  to explicit origin list before public launch. Pre-existing; not introduced by Phase 14.

### Profile & Sessions

- [x] **P1** `GET /api/users/by-username/:username` public profile endpoint. (Wave 10 Task 2)
- [x] **P1** `GET /api/users/me/sessions` + `DELETE /api/users/me/sessions/:id`. (Wave 10 Tasks 1–2)
- [x] **P1** Profile settings page wired to real API. (Wave 10 Task 4)

---

## v1.1 PDF ingest 改进 + license audit

**背景**: book-to-skill (MIT, virgiliojr94/book-to-skill) benchmark 显示 Docling (IBM Research, MIT) 在 PDF 技术书解析上:
- 103 页样本: 保留 48 表格 + 36 代码块 (pymupdf4llm 无法)
- 同 token 量, 时间 0.1s vs 164s (pymupdf4llm 快但损失结构)
- 适合 Stratum 用户上传技术书 / 论文场景

**License 隐患**:
- 当前 pymupdf4llm 是 AGPL → 商业 SaaS (beta 付费层) 衍生作品需开源
- Docling MIT → 无商业限制

**v1.1 任务**:
1. PDF ingest 切 Docling (替代 pymupdf4llm)
2. 整体 license audit (所有 Python deps + npm deps), 标记任何 AGPL/GPL/SSPL 依赖, 给商业化备选方案
3. benchmark Docling vs pymupdf4llm (表格 / 代码块 / 总 token / 时间) 用 Stratum 真实用户 PDF
4. R-4 范围决定: 影响 oprim 还是仅 Stratum 服务层 (oprim.pdf_to_substrate 改 Docling 需 Phase 11D 启动后, Stratum 服务层临时实施可走非 oprim 路径)

**优先级**: v1.1 (Phase 14 alpha 100+ 用户后真用过技术书 ingest 评估)
**触发**: 用户反馈 PDF 解析质量不够 / 商业化前 license 清理

---

## Repo 结构 (monorepo vs 独立 repo)

- [ ] **P2** monorepo vs 独立 repo 整体策略待 v1.1 评估。
  当前状态: Phase 14 SaaS 主体在 `stratum/`; CLI 在 `~/projects/stratum-cli` (独立 repo);
  extension 在 `~/projects/stratum-extension` (独立 repo); `@helios/blocks` 在 Helios 独立 repo。
  决策点: 是否合并为 pnpm/uv workspace monorepo, 或保持独立 repo + CI 依赖管理。

---

## Phase 11 (pre-Phase 14 carryover)

- [ ] **P1** `omodul` Wissen knowledge submodules still at historical path.
  Target: flatten to `omodul/` in Phase 11D. (Phase 11D not yet started)

- [ ] **P2** `oprim` stubs for `tts`, `sd`, `whisper` need real implementations or standard
  mock interface. Blocked until provider selection in Phase 11D.

- [ ] **P2** `hybrid_search` path migration left `oskill/knowledge/` placeholder.
  Remove in Phase 11D.

---

## Phase 1–13 (earlier carryover)

- [ ] **P2** `task_dao` and `template_dao` minimal — no pagination, no search.
  Full DuckDB implementation deferred to Phase 15.

- [ ] **P2** `weekly_review_workflow` prompt basic; lacks detailed activity context.
  Needs enrichment when workflow engine productionized in Phase 15.

- [ ] **P2** `docs/yiwancheng/` contains outdated design notes from pre-Phase 14 era.
  Should be archived or removed before v1.0 release docs freeze.

---

## Part 2 Audit — items verified complete as of Phase 14

| Item | Status | Verified in |
|------|--------|-------------|
| `GET /api/users/by-username/:username` | ✅ Done | Wave 10 Task 2 |
| Sessions list/revoke endpoints | ✅ Done | Wave 10 Tasks 1–2 |
| Profile page real API wiring | ✅ Done | Wave 10 Task 4 |
| Share token `share_tokens` key naming | ✅ Done | Phase 14 B-6 |
| Corpus isolation post-filter | ✅ Done | Wave 2 (service layer) |
| Migration 014 index coverage | ✅ Done | Phase 14 Z-3 EXPLAIN |
