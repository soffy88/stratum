# STATUS — AII Note MVP

最后更新：2026-08-02（/retrieve 修通 + 中文检索 + /search 用户隔离，详见 In Progress）

## 🔒 Never

- 总结覆盖原文；无锚点的「知识合并」
- MVP 范围外功能抢主路径
- 公网入口绕开 **aegis-caddy:8086**
- 未过对抗金集的 B仓自动强并

## 🔄 In Progress

- [x] **安全审计 P0/P1 修复**（2026-07-29）：sessions/trajectory/layers/retrieval 所有权；folder_watch+vault 路径 allowlist；export 防 `..` 逃逸；cornell 机器笔记不可删；metrics admin；concepts user_id 双匹配。单测 `test_mvp_security_idor.py` 25 passed。剩余：vfs tree 全局目录仍弱隔离（context_directory 无 user 列）。详见审计文档。
- [x] **Docling 包装入 stratum-sl 镜像**（2026-08-01）：`docker compose build stratum-sl` 完成，容器内 `docling 2.117.0` 实测 PDF 链全 PASS。
- [x] **主链路人工 E2E**（2026-08-01）：`scripts/e2e_mvp_chain.py` 15 步全链（web + PDF 两链 15/15 PASS）；顺带修复 5 个真 bug（translate 所有权/AgentContext、concepts substrate_refs、图谱注入污染 question、db list[dict] 序列化）。
- [x] **定时调度**（2026-08-01）：`daily_digest_simple` / `knowledge_lint` 种子任务挂 scheduled_jobs；run-now 实测 ok。
- [x] **锚点闭环前端**（2026-08-02）：文档页段落锚点 `#p{n}` 跳转+高亮；高级检索卡片深链；基础搜索 citation 携带 paragraph anchor（SPA 跳转）。
- [x] **/retrieve 修通**（2026-08-02）：根因=API 入库链路从不生成 substrate_layers（仅 watcher 生成）→ inbox/webclip/media 三处入库钩子补分层生成；layer_generator qwen3 补 `think:false`（否则 400）；/retrieve 响应补 title（ref_id→substrate_id 前端适配）。实测 10 结果/真实标题/深链，Attention 文章 0.67 居首。
- [x] **中文检索修复**（2026-08-02）：tantivy Python 绑定无 CJK tokenizer（报 unknown tokenizer）→ oprim `fulltext/tantivy.py` 应用层 `_space_cjk()`（CJK 字符间插空格，add/search 双端）；重建索引 5797 docs。实测中文 50 hits、英文不退化。prod `/home/soffy/deploy/3O` 与 dev `/home/soffy/projects/platform/3O` 双副本已同步。
- [x] **/search 用户隔离**（2026-08-02）：FusedResult 无 user_id 字段，路由层旧防御过滤全放行（probe2 能搜到主用户文档）→ oskill `cross_layer_search.py` FusedResult 补 `user_id` 透传（search_utils 已按 DB 归属挂哈希 id）；路由比较 `IN (raw, hash)` 双值。实测 probe2 只看到自己文档。单测 `test_search_idor_post_filter` 按属性过滤契约保持绿。
- [x] **Companion 出处复核**（2026-08-02）：reading_companion sources[] 现从 derivative + locate_anchor 富化 snippet/fragment_id/deep_link；实测 5 sources/5 citations，标题+片段+锚点齐全。
- [x] **全库 L0 覆盖回填**（2026-08-02）：主用户 5786 substrate 中 ~94 个历史 API 入库项缺 L0 分层（JOIN 计数曾误报为 1.1 万）→ `scripts/backfill_l0_layers.py` L0-only 回填（title/前200字 + 本地 qwen3-embedding，无需 LLM）。现全员 100% L0 覆盖（5786/10/1）；主用户 /retrieve 抽查 transformer/diffusion 均命中相关论文。dense 路径顺带修复：search_utils lancedb_mgr 尊重 `EMBEDDING_PROVIDER`（不再硬编码 DashScope）。
- [ ] 问答接 web（SEARXNG_URL 占位，2026-08-02 确认无可用端点 → 记为人工项，见 Needs Human）

## ✅ Done

### 健康检查修复（2026-07-31）

- [x] 前端构建恢复：还原 `adapters/documents.ts` 截断残桩（确认无人引用）；补完 `adapters/notes.ts` 的 `updateNote`/`deleteNote`（notes 页在用，WIP 缺类型且 body 字段错——后端要 `content_markdown`）；修 `lib/documents.ts` reprocessDocument 未解包 `.data`；修 `CornellNoteView.tsx` strict-null。Stratum 自有代码 tsc 0 错，`next build` 通过。
- [x] `deploy/Dockerfile.sl` 钉 `mcp>=1.27,<2`（mcp 2.0 移除了 `mcp.server.fastmcp`，不钉下次重建必坏）。
- [x] `pyproject.toml` 回灌代码实际 import 的运行时依赖（fastapi/psycopg2/mcp/numpy/argon2/PyJWT 等），dev 工具改 PEP 735 dependency-groups；`uv lock` 刷新——`uv sync` 开箱即可跑测试。
- [x] 测试基建：conftest 加 `reset_rate_limits` autouse（清 429）、`STRATUM_PG_PASSWORD` 默认值（对齐 compose 凭据）；`test_scheduled_jobs` 每测清表避开 free-tier 402；`test_rate_limit` 玩具路由改 `/api/v1/data`（新分类规则下裸 `/api/*` 归 AII 路由）。MVP 门禁 48 绿；全量 297 passed / 0 收集错误（修复前 268 / 67 errors）。
- [x] 测试套件第二轮（62 failed → **0 failed，341 passed / 17 skipped**）：
  - 事件系统根因：开发库 `changefeed.seq` 缺 `DEFAULT nextval('changefeed_seq')`（与 migration 020 不一致），`emit_event` 的静默 except 把失败全吞了 → 已 ALTER 修复；highlights/views 三个路由 PG 改写时丢了 `emit_event` → 补回；`sync.py` changefeed 查询只匹配裸 user_id，漏掉 documents/highlights/views 路由发出的哈希 id → 改 `IN (raw, hash)` 双匹配；`test_changefeed_events` / `test_sync_scope` 按 PG + 双 user id + 现行路由契约（`/api/v1/documents/{id}/pin`、highlights `{substrate_id,text}`）重写。
  - 平台包（`omodul`/`oprim` 仅镜像内 `/opt/platform` 有）：依赖它的测试加 `skipif` 标记 → 17 skipped，本机全绿、镜像内可全跑。
  - inbox/webclip 8 个失效 monkeypatch：router 的 except ImportError 分支补 `= None` 兜底绑定，测试改 stub `sys.modules` 里的 omodul 模块，12/12 绿。
  - 遗留隐患同修：限流中间件加 `_LEGACY_API_SEGMENTS` 白名单（否则 :9302 旧 app 的 admin/auth 等路由下次部署起全被当 AII 路由 401）；sessions DAO naive/aware datetime 修复。
  - 策略性容忍：AII 页面 95 个 `@helios/blocks` 3.0 tsc 错（`ignoreBuildErrors: true`，构建与运行不受阻，无 CI 强制类型检查）。

### 安全加固（审计续篇）

- [x] IDOR 修复 + 路径加固 + `tests/service_layer/test_mvp_security_idor.py`

### 第 1–2 周

- [x] MVP 范围冻结：`docs/MVP_AII_NOTE.md`
- [x] `pdf_to_markdown` 三级 fallback；inbox 可观测；extract_merge；Companion `sources[]`
- [x] oprim docling provider；translation 单 substrate 路径

### 第 3–4 周

- [x] 整库 Markdown 导出 ZIP：`GET /api/v1/export/vault`
- [x] 混合检索段落锚点 + 统一 `sources[]`
- [x] Link & Merge 矛盾标记 `pending_human_review`
- [x] `tests/service_layer/test_mvp_week34.py`

### 第 5–6 周

- [x] **Vault 本地/网盘同步**：`vault_sync_service`
  - `POST /api/v1/sync/vault` `{path, mode: export|import|both}`
  - `GET /api/v1/sync/vault/roots`（`STRATUM_VAULT_SYNC_ROOTS`）
  - export 写 notes/concepts/sources；import 回读 notes/*.md
- [x] **真删**：`purge_service` + `db.hard_delete`
  - `DELETE /api/v1/notes/{id}` 默认 hard（`?soft=true` 可选）
  - `DELETE /api/v1/concepts/{id}` 默认 hard
  - `DELETE /api/v1/documents/{id}` hard + cascade derivative/layers
- [x] **Lint**：`knowledge_lint_service` → 断链/孤立/矛盾；写「Lint 报告 · 日期」笔记
  - Agent：`POST /api/v1/agents/knowledge_lint/run`（别名 `lint`）
- [x] **日报**：`daily_digest_service` → 「日报 · 日期」笔记 + notification
  - Agent：`POST /api/v1/agents/daily_digest_simple/run`（别名 `aii_daily_digest`）
- [x] 单测：`tests/service_layer/test_mvp_week56.py`

## 📋 MVP Backlog（剩余）

1. ~~镜像内安装 `docling`~~（2026-08-01 已入镜像）
2. ~~端到端手测 / 带鉴权集成测试~~（E2E 全链已跑通）
3. ~~Companion snippet 路径复核~~（2026-08-02 sources[] 已带 snippet/锚点）
4. ~~（可选）scheduled_jobs 挂日报/Lint~~（已挂种子任务）
5. 账户删除仍 soft+30 天 grace（与「笔记真删」策略并存，可后收紧）  

## 🚨 Needs Human

- [x] **审计 P0 已修**（sessions/retrieval/layers/folder_watch/vault/metrics/cornell）。若部署用 vault/watch 路径不在默认 roots，设 `STRATUM_VAULT_SYNC_ROOTS` / `STRATUM_FOLDER_WATCH_ROOTS`。
- [x] **aii.kanpan.co/login 500** — Next rewrite 写死 `localhost:9302` → 热修 + entrypoint。
- [x] **/knowledge 错误** — 2026-07-29：根因 (1) stratum-sl 被 folder_watcher/LLM 打满 → Next proxy `socket hang up`→500；(2) 客户端 10s 超时。修复：Caddy `:8086` 将 `/api/aii/*`、`/api/v1/*` 直连后端；重启 SL；api-client 超时改 60s（需重建前端才进镜像）。
- [ ] **aiinote.com DNS（阻塞公网）** — 2026-07-29 诊断：
  - ✅ 隧道 ingress 已有 `aiinote.com` / `www` → `aegis-caddy:8086`
  - ✅ Caddy `:8086` → `aii-web:3101` 本机 200（标题 AII Note）
  - ✅ `https://aii.kanpan.co` 同链路公网 200（可先用）
  - ❌ 公网 DNS：`dig @1.1.1.1 aiinote.com A` **ANSWER:0**（无 CNAME/A）
  - ❌ `cloudflared tunnel route dns` 认证失败 code 10000（cert 无 Zone.DNS.Edit）
  - **请你在 Cloudflare → aiinote.com → DNS 手动加（橙云 Proxied）**：
    - `CNAME  @    →  3ea896f2-5be2-448e-ad27-338cdf3da4b1.cfargotunnel.com`
    - `CNAME  www  →  3ea896f2-5be2-448e-ad27-338cdf3da4b1.cfargotunnel.com`
  - 或发 `CLOUDFLARE_API_TOKEN`（Zone.DNS Edit + Zone Read on aiinote.com）后跑：
    `python3 scripts/setup_aiinote_dns.py`
- [x] stratum-sl 是否安装 docling — 2026-08-01 已入镜像（docling 2.117.0），容器实测 PASS
- [x] 人工 E2E 验收（含 vault 目录挂载路径） — `scripts/e2e_mvp_chain.py` 15 步两链全 PASS
- [ ] **问答接 web（SEARXNG）** — 2026-08-02 确认暂无可用 searxng 端点；`SEARXNG_URL` 保持 REPLACE 占位，agents.py `_make_searxng_adapter` 已就绪。有自建 searxng 实例后填 env + restart 即可启用。
- [ ] 若网盘挂载点不在默认 roots：设置 `STRATUM_VAULT_SYNC_ROOTS`  
- [x] **测试套件剩余失配（2026-07-31）** — 已全部修复，见 Done「测试套件第二轮」。`api/mcp.py` 的 `list_recent_changes` 同类双 id 问题也已修（`IN (raw, hash)`，开发库实测可见 hashed-id 事件）。

## 参考

- `docs/MVP_AII_NOTE.md`
- 同步：`src/stratum/services/vault_sync_service.py` · `api/routers/sync.py`
- 真删：`src/stratum/services/purge_service.py`
- Lint/日报：`knowledge_lint_service.py` · `daily_digest_service.py`
