# STRATUM_API_v1_WRITING_INSTRUCTIONS_v0.1.md

**任务**: 撰写 STRATUM_API_v1.md (Stratum v1.0 完整 API 契约文档)
**执行者**: CC FULL AUTO
**工程量**: 5-7 天
**输出**: `~/projects/stratum/docs/STRATUM_API_v1.md`
**受众**: Helios 前端架构组 + 任何 Stratum 客户端开发者

---

## §0 大背景

Stratum v1.0 已完工 (Phase 1-13 + 11B). 现在写完整 API 契约文档给 Helios 前端组 (他们等着 8-10 周 Block 实施).

之前 advisor 跟 Helios 6 轮对接已锁定:
- 21 Block 终稿
- snake_case 数据契约双签 ADR
- 5 view yaml + 5 Lock 字段差异
- OSemanticSearchResult v1.1
- 8 项前端 lint / utility / feature flag 需求

CC 在本任务里**不重新设计契约**, 只是把代码事实 + 上面已锁的决策**结构化写进文档**.

---

## §1 输入资源 (写文档时引用)

### 1.1 已有材料 (advisor 已写)
- `/home/claude/api-v1/STRATUM_API_v1_OUTLINE.md` (466 行大纲, 15 章 + 4 附录)
- `/home/claude/4o-v0.2/DECISION_LOG.md` (22 ADR + 治理决策)
- `~/projects/stratum/docs/decisions/ADR-001~022.md`
- `~/projects/stratum/docs/DEPLOYMENT.md`

### 1.2 advisor 跟 Helios 对接 5 轮全文 (用作字段命名 / Block 边界 / lock 决策参考)
- `/mnt/user-data/outputs/helios-kb-reply/STRATUM_REPLY_TO_HELIOS_v2.md` (确认 21 Block + 主题 + 时序)
- `/mnt/user-data/outputs/helios-kb-reply/STRATUM_REPLY_TO_HELIOS_v3.md` (5 yaml 原文 + 5 Lock 字段差异)
- `/mnt/user-data/outputs/helios-kb-reply/STRATUM_REPLY_TO_HELIOS_v4.md` (5 Agent output + Push metadata + OpenAPI 工具链)
- `/mnt/user-data/outputs/helios-frontend-requirements/STRATUM_REQUIREMENTS_TO_HELIOS_v1.md` (8 项前端需求)
- `/mnt/user-data/outputs/aegis-cross-project/STRATUM_REPLY_TO_AEGIS_v1.md` (跨项目治理 4 项决议)

(如果上面路径不存在, 跳过, 从代码 + ADR 自己重新生成)

### 1.3 代码 ground truth (主要参考)
- `~/projects/platform/oprim/` (基础原语 v2.8.0)
- `~/projects/platform/oskill/` (业务技能 v2.9.0)
- `~/projects/platform/omodul/` (业务模块 v1.8.0)
- `~/.stratum/meta.duckdb` (用 PRAGMA table_info 取真实表 schema)
- `~/.stratum/index/lance/vectors_text.lance/` (LanceDB)

---

## §2 撰写规则 (R-1 ~ R-6)

### R-1: 失败/不存在不静默
- 任何字段引用必须基于真实代码, 不脑补
- 如果文档某节需要某字段但代码里没有, **明确写 "v1.0 未实施, v1.1 评估"**, 不假装存在
- 例: char_start / char_end 字段不存在, 必须写 "v1.0 仅 chunk-level fragment_id, 无 char-level"

### R-2: SPEC 是真理源
- 字段命名严格 snake_case (ADR_STRATUM_SNAKE_CASE.md 双签)
- TypeScript interface 字段名 = Python 字段名 = JSON key, 1:1
- 不为 "前端友好" 改字段名

### R-3: 真实示例强制
- 每个 API 节必须含**真实跑通**的示例 (输入 + 输出 JSON)
- 用 Phase 1-13 实际数据 (substrate_id `01KS2MD25C3FAAAD7B9KTF9ZM9` 等真实 ULID)
- 不许编例: 不写 `substrate_id: "abc123"` 这种假数据
- 没真数据的节标 "v1.0 测试数据不足, 示例待补"

### R-4: 严格范围
- 仅写 v1.0 (Phase 1-13 + 11B 完工范围)
- v1.1+ 功能在 §15.2 / §15.3 列, 不在主体写 schema
- 不写未来的 fragment 表 / wechat push 等 v2.0 内容

### R-5: namespace 隔离
- 只动 `~/projects/stratum/docs/STRATUM_API_v1.md` (新建)
- 同时新建 `~/projects/stratum/docs/openapi.json` (FastAPI 自动导出)
- 不动其他文档 (DEPLOYMENT.md / ADR / DECISION_LOG.md)

### R-6: 破坏性操作必须 Wiki sign-off
- 不删除任何已有文件 / DB / 代码
- 不重命名既有 module / function
- 写文档不 modify 代码 (除非 docstring 补全)

---

## §3 撰写顺序 (按依赖关系)

### Wave 0: 收集真实代码 + DB schema (0.5 天)
- 用 DuckDB PRAGMA 取 8 表完整 schema
- LanceDB 取 vectors_text schema + sample 数据
- grep 所有 dataclass / Pydantic model:
  - oprim/embedding/* (embed_text / Qwen3DashscopeEmbedder)
  - oskill/knowledge/hybrid_search.py (SearchResult / Citation)
  - oskill/knowledge/ingest_substrate.py (Substrate)
  - oskill/knowledge/translate_substrate.py (TranslateResult)
  - omodul/knowledge/agents/base.py (Agent / AgentResult / AgentStep / Citation)
  - omodul/knowledge/scheduler/job_store.py (ScheduledJob / ScheduledJobRun)
  - omodul/knowledge/browser_extension/server.py (IngestRequest / IngestResponse / SidebarSearchRequest)
  - omodul/knowledge/views/* (View)
  - oprim/push/dispatcher.py (PushRequest / PushResult)
- 跑端到端 demo 拿真实 JSON 输出 (substrate_id / derivative_id / agent_run_id 等)
- 输出到 `~/projects/stratum/docs/_drafts/ground_truth_data.md` (临时)

### Wave 1: §1 数据模型 (1-1.5 天)
- §1.1 substrate (含 is_pinned / pinned_at / meta_json 真实字段)
- §1.2 fragment ⚠️ **强调 chunk-level string anchor, 无独立表**
- §1.3 derivative (translation / summary / note / tag enum)
- §1.4 note
- §1.5 concept (字段定义 + v1.0 弱关联说明)
- §1.6 view (5 预置 yaml 原文)
- §1.7 agent_run (含 status enum: running/completed/failed/timeout)
- §1.8 scheduled_job
- §1.9 scheduled_job_run
- §1.10 push (含 4 channels)
- §1.11 changefeed_event (Phase 2 同步)
- 每个实体: Python dataclass + DuckDB schema + TypeScript interface (附录 A 对应) + 真实示例

### Wave 2: §2 MCP Server (1 天)
- §2.1 启动方式 (Claude Desktop / Hermes mcp.json 配置)
- §2.2 8 个 tool 完整定义:
  - stratum.search
  - stratum.fetch_substrate
  - stratum.list_notes
  - stratum.recent_changes
  - stratum.pin_substrate
  - stratum.unpin_substrate
  - stratum.list_views
  - stratum.set_default_view
- 每个 tool: name / description / input JSON Schema / output JSON Schema / 真实调用示例
- §2.3 错误处理 + token 鉴权 (默认无鉴权, env STRATUM_USER_ID)

### Wave 3: §3 HTTP REST API (1 天)
- §3.1 服务启动 (localhost:14567)
- §3.2 3 个端点:
  - POST /api/v1/browser-extension/ingest
  - POST /api/v1/browser-extension/sidebar-search
  - GET /api/v1/browser-extension/health
- 每个含 OpenAPI 风格 (method / path / request / response / 错误码)
- §3.3 CORS + Token 鉴权 (X-Stratum-Token)
- §3.4 v1.1+ Web API 预留 (port 14568, namespace /api/v1/web/*)
- 用 FastAPI app.openapi() 导出 openapi.json (放 docs/openapi.json)

### Wave 4: §4-5 Agent + Scheduler (1.5 天)

§4 Agent 系统:
- §4.1 调用契约 (AgentRunner.run + AgentResult)
- §4.2 5 个 builtin Agent (knowledge_curator / reading_companion / daily_digest / translation_worker / lint_bot)
  - 每个: allowed_tools / params schema / output schema (真实结构) / 真实跑通示例
- §4.3 AgentResult 详细 schema (elapsed_seconds 秒 / trace 平铺 array / citations array)
- §4.4 AgentTracer + agent_runs 表 (含 list_runs 精简列说明)
- §4.5 Registry (@register_agent + v1.0 不开放用户自定义)

§5 Scheduler:
- §5.1 Cron Engine (APScheduler + Redis lock + Asia/Shanghai timezone)
- §5.2 Job CRUD API (create / get / list / update / delete / run_now / install_builtin_jobs)
- §5.3 4 builtin jobs (daily_inbox_process / daily_digest / weekly_lint / nightly_translation)
  - 加 nightly_audio_gen (Phase 11B 加, default disabled, "TTS v1.0 unavailable")
- §5.4 通知 (notify_on_completion / notify_on_failure → oprim.push)
- §5.5 缺失字段: next_run_at / last_run_at 不存, 前端 cron-parser 算

### Wave 5: §6-9 推送 / 检索 / 浏览器扩展 / 同步 (1.5 天)

§6 Push:
- §6.1 PushDispatcher.push 入参 (含 body / channels_preference / deep_link / metadata 3 known key)
- §6.2 4 channels (web VAPID / email SMTP / wechat placeholder / system)
- §6.3 用户订阅 push_subscriptions 表
- §6.4 Deep link 4 格式 (substrate / substrate_fragment / agent_run / digest)

§7 hybrid_search:
- §7.1 Python API 签名 (含 user_id / view_id / mode / pinned_boost / return_citations)
- §7.2 mode strict vs augmented (v1.0 augmented 等于 strict, Phase 11+ 加 LLM 兜底)
- §7.3 排序 (RRF + pinned_boost)
- §7.4 跨语种 (matched_language / 翻译 derivative 桥接)
- §7.5 embedding provider: qwen3_dashscope 硬编码 (v1.1+ 加 fallback)

§8 浏览器扩展 (Phase 4):
- §8.1 安装步骤 (后端 serve + 前端加载 + token 配置)
- §8.2 3 场景 (一键保存 / selection / sidebar)
- §8.3 URL 去重 (normalize_url + browser_ext_url_index)
- §8.4 网页 substrate 存储 (临时 html + ingest_substrate, source 平铺无嵌套)

§9 Sync (Phase 2):
- §9.1 ChangeFeed (changefeed_events 表 + per-user seq + append-only)
- §9.2 GoogleDrive (OAuth + WSL2 proxy 适配 + 9 测试)
- §9.3 4 sync skill (flush_outbox / apply_remote_events / snapshot_backup / restore_from_snapshot)
- §9.4 bg_sync (3 并发 + 30s flush)
- §9.5 LWW 冲突解决

### Wave 6: §10-12 + §13 错误 + §14 部署 (0.5 天)

§10 View (Phase 13):
- 5 预置 yaml 原文 (跟 §1.6 不重复, 这里讲 CRUD + applier)
- view_id 真正生效 (hybrid_search 自查 views 表, 不反向 import omodul)

§11 Pin (Phase 1.5):
- pin/unpin/list_pinned API
- pinned_boost 1.5x

§12 Translation (Phase 10):
- translate_substrate skill
- 3 providers (DeepSeek / Claude / Qwen3 dashscope)
- async 实施
- 翻译 derivative 跟 substrate 关系 + 跨语种 embed

§13 错误处理:
- StratumError 类树 (AgentError / AgentToolNotAllowedError / SubstrateNotFoundError / ProviderUnavailableError / CircuitBreakerOpen / ExternalToolError 等)
- HTTP 错误码映射
- MCP 错误响应

§14 部署:
- 单机 (Win11 + WSL2 Ubuntu 24.04)
- 端口清单 (Postgres/Redis/RabbitMQ/Ollama/browser_extension + Phase 11B 9301-9304)
- 用户配置 ~/.stratum/config.yaml + ~/.config/keys/.env (不披露具体路径)

### Wave 7: §15 限制 + §16 roadmap + 附录 + Gate (0.5 天)

§15 v1.0 已知限制:
- §15.1 限制清单:
  - mode=augmented 实际未实施 LLM 兜底 (Phase 11+ 修)
  - 单用户场景 (多用户 Phase 14+)
  - 无 wechat push (placeholder)
  - 无 vision LLM 本地 (走 Claude API, Aegis 接管 ollama 后切回本地)
  - TTS / audio_generator v1.0 不可用 (上游 image broken)
  - char-level fragment 不可 (chunk-level only)
  - 全非流式 (v1.1+ 加 SSE)
  - list_substrates 仅 Python SDK + MCP, REST 留 v1.1
  - dashscope embedding 硬编码 (v1.1+ 加 fallback)

§15.2 v1.1:
- Phase 11B 完整 (TTS 自写 wrapper 或换 image)
- audio_generator Agent
- web_search_augmented 增强
- SSE 流式
- mode=augmented 真实施 LLM 兜底
- list_substrates REST 端点

§15.3 v2.0 (商业化期):
- 多用户 / 多租户
- 付费层
- 微信小程序集成
- char-level fragment 表

§15.4 跨项目治理 (Aegis):
- "Aegis 接管路线已确认, 2026-Q4 MVP, 当前 Stratum 内部 GpuLock 自治"
- 不写时间表

### 附录 A: TypeScript 接口定义 (供 Helios 前端用)
- 严格 snake_case
- 跟 src/types/stratum.ts (Helios v1.2.11) 对齐
- 含 WithCitations<T> / StratumFeature flag 引用
- 不重复定义 helios/blocks 已有 (引用即可)

### 附录 B: 真实示例数据
- substrate_id `01KS2MD25C3FAAAD7B9KTF9ZM9` (test_rag_paper.md)
- derivative_id `01KS2MQHTQN7D0G6H3A8ZYWQHA` (zh-CN 翻译)
- agent_run_id 4 个 (Phase 11A E2E demo 真实)
- 9 GDrive 集成测试输出 (Phase 2 闭环)
- LanceDB 2 条 vector record
- hybrid_search 真实 trace (757ms / 3 results)

### 附录 C: Cron 表达式参考
- 5 字段标准 + 常用模式

### 附录 D: medium / domain / language enum
- 从 Phase 1 classifier 实际输出枚举
- 用 SELECT DISTINCT medium FROM substrate 取真实值

### Gate (Wave 8, 0.5 天)
- 全文 review (字段命名一致 / 真实示例 / R-1 不静默)
- openapi.json 跟 §3 一致性验证
- commit + tag stratum-api-v1.0
- 报告 advisor review

---

## §4 输出文件结构

```
~/projects/stratum/docs/
├── STRATUM_API_v1.md        (主文档, 估计 2000-3000 行)
├── openapi.json             (FastAPI 自动导出, 浏览器扩展 API 部分)
└── _drafts/                 (撰写期临时文件)
    └── ground_truth_data.md (Wave 0 收集数据)
```

撰写完后 `_drafts/` 不删, 留作 Wave 1-7 引用追溯.

---

## §5 验收 (Gate)

### 5.1 必过项
- §1-§14 主体完整, 字段命名 snake_case 100%
- 每个 API 节有真实示例 (R-3)
- v1.0 限制清单完整 (§15.1)
- TypeScript interface (附录 A) 跟 Helios v1.2.11 stratum.ts 对齐
- openapi.json 自动导出成功
- 没编字段 (fragment.char_start 之类脑补)
- 没 v2.0+ 内容混入主体

### 5.2 建议项 (非阻塞)
- 每节配 mermaid 图 (如需)
- 错误码映射表完整 (§13)

### 5.3 完工报告格式
```
STRATUM_API_v1.md Gate ✅

文档:
- 主文档: <line count> 行
- openapi.json: <byte count>
- 真实示例数: <count>
- 已知限制: <count>

提交: <commit hash> on <branch>
Tag: stratum-api-v1.0

advisor review pending.
```

---

## §6 异常处理

立即停止 + 报告 advisor:
- 代码事实跟 advisor 5 轮对接答复 (helios-kb-reply v2-v4) 矛盾 → 优先代码事实, 报告矛盾点
- 跑端到端 demo 取真实示例失败 (API key 缺 / DB 损坏) → 用 Phase 11A 已记录数据, 不重跑
- 某节字段 ground truth 找不到 → 明确写 "v1.0 未实施", 不脑补

非阻塞 (继续):
- 个别 enum 枚举不全 (用 SELECT DISTINCT 补)
- mermaid 图渲染问题

---

## §7 进度报告

每完成 1 个 Wave 报告:
```
Wave <N> 完成
- 章节: <list>
- 行数: <delta>
- 真实示例数: <count>
- commit: <hash>
- 下一步: Wave <N+1>
```

advisor 接到 Wave 报告做轻量 review, 不阻塞下一 Wave.

---

**End**
