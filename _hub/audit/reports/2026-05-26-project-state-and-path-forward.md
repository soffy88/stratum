---
draft: true
ai_drafted_by: "claude-opus-4-7"
ai_drafted_at: "2026-05-26T00:00:00+08:00"
report_type: "project-state-snapshot"
covers_period: "2026-05-16 → 2026-05-26 (10 天)"
audience: "Wiki (项目所有者)"
status: "等待 Wiki review"
---

# Stratum 项目状态全景 + 推进路径建议

**日期**: 2026-05-26
**当前分支**: `phase14/backend-saas`
**最近 commit**: Phase 14 Wave 9 (share 公开页 + profile + settings)
**报告由**: Claude (作为 chief advisor 起草, 等待 Wiki review)

---

## TL;DR (三段话)

1. **过去 10 天发生了什么**: 2026-05-16 Wiki 批准了 1368 行的 STRATUM_SPEC v0.1.2 (个人本地知识库蓝图), 批 1 (16 个 schema + 目录骨架) 当日完工; 2026-05-17 跑完批 2 的两个关键实证 (向量库选 chromadb, embedding 选 bge-m3); **然后 spec 进入静默, 2026-05-24-26 三天 17 个 commit 直接跳到一个完全不在 spec 里的新产品**: 多用户 SaaS 知识库, 含 FastAPI 后端 (auth + DAO + corpus 隔离 + share + agents + scheduler) + Next.js 16 前端 + 公网部署基建 (nginx + tunnel + rate limit + abuse detection)。

2. **现在仓库的真实状态**: 三个独立的"项目层"并列存在但互不衔接 —— (A) 一个写得很好、但**没更新过**的"立宪期 spec + schema"; (B) 三个**完全为空**的知识层 (substrate/concepts/notes 只有 .gitkeep, 一条真知识都没入); (C) 一个**两天爆发出来、与 spec 不兼容**的 SaaS 全栈应用。Spec 没输, 它是被 leapfrogged 了。

3. **下一步建议**: 必须**先做一个身份决策** (Wiki 亲自定: 还是个人本地 KB? 还是变成 SaaS 产品? 还是两条线并行?), 然后**把 spec 更新到反映现实** (而不是反过来让现实回去对齐过时 spec), 最后才回到具体执行。本报告 §6 给出 3 条候选路径 + 推荐 + 立刻可做的 5 个动作。

---

## §1 仓库全景

### 1.1 组件地图

仓库实际包含 **4 个并行的组件**, spec 里只承认前两个:

```
stratum/
├── _hub/                     ← (A) 知识库元数据层
│   ├── STRATUM_SPEC.md       ←     spec (1368 行, v0.1.2)
│   ├── schemas/              ←     16 个 JSON Schema + valid/invalid 例子
│   ├── pipelines/lint/       ←     只有 1 个 schema_selfcheck.py
│   └── audit/reports/        ←     2 篇实证报告
│
├── substrate/ concepts/ notes/  ← (B) 三层知识本体 (全部空)
│   └── (只有 .gitkeep)
│
├── src/stratum/              ← (C) Python 后端 (spec 未提)
│   ├── auth/ jwt+refresh+password+dependencies
│   ├── dao/  16 个 DAO 模块
│   ├── http_api/ FastAPI app (v1.2.0) + 7 个路由
│   ├── mcp_server/ MCP routes (tasks/templates/review)
│   ├── middleware/ rate_limit + abuse_detection + corpus_isolation
│   ├── scheduler/ builtin_jobs
│   ├── service/search.py
│   └── db/migrations/ 010-018.sql (9 条 migration)
│
├── stratum-web/              ← (D) Next.js 16 前端 (spec 未提)
│   ├── src/app/(auth)/login + register
│   ├── src/app/(app)/search + ai + jobs + documents + notes + settings
│   ├── src/app/share/[token]/   ← 公开分享页
│   └── src/{lib, stores, components}/
│
├── pyproject.toml            ← 自称 v0.0.1 (与 app.py 的 v1.2.0 不一致)
└── README.md                 ← 描述 (A)+(B), 未提 (C)(D)
```

### 1.2 数量盘点

| 维度 | 计数 | 备注 |
|---|---|---|
| 自己写的 markdown | 4 个 | README, STRATUM_SPEC, 2 篇实证 |
| 自己写的 Python | ~50 个文件 | 全部在 `src/stratum/`, 加 1 个 `_hub` lint 脚本 |
| 自己写的 TS/TSX | 25 个 | 在 `stratum-web/src/` |
| JSON Schema | 16 个 | 全部齐, 配 valid + invalid 例子 |
| SQL migration | 9 条 (010-018) | 010 之前的去向: 未知 (可能在 main 分支或被 rebase) |
| 三层知识节点 | **0 条** | substrate/concepts/notes 全空 |
| spec 承诺但未实现的 lint | 7/8 | 只有 schema_selfcheck (且仅覆盖 substrate.book) |
| spec 承诺但未实现的 ingest 流水线 | 6/6 | 全空 |
| pyproject 与 app.py 的版本号差 | 1.2.0 vs 0.0.1 | 已经偏离 |

### 1.3 自我宣告 vs 实际状态对照

| 文档/代码 | 自称是 | 实际是 |
|---|---|---|
| `README.md` | "Wiki 的本地知识库系统", "v0.0.1 批 1 完成" | 漏写了 (C)(D) 两个主组件 |
| `STRATUM_SPEC.md` v0.1.2 | "个人级、本地优先、单用户、不对公网" | 已被 (C)(D) 实现部分推翻 |
| `pyproject.toml` | `version = "0.0.1"` | 与 app.py 的 v1.2.0 矛盾 |
| `src/stratum/http_api/app.py` | `version="1.2.0"` | spec 里没有任何 v1.x 的概念 |

---

## §2 时间线 (10 天浓缩)

```
2026-05-16 ┤■ STRATUM_SPEC v0.1.2 完成 (Wiki 批准)
           │   批 1: 16 schemas + 目录骨架 + README
           │
2026-05-17 ┤■ 批 2 实证 #02 (vector-db: chromadb 选定)
           │  批 2 实证 #03 (embedding: bge-m3 选定)
           │
2026-05-18 ┐
   ...     │  (静默 5-6 天, spec / _hub 未动)
2026-05-23 ┘
           │
2026-05-24 ┤■ commit 1  (Phase 11C: Stratum service layer initial)  ← 后端突然出现, spec 未更新
   01:50   │
   02:04   │■ commit 2  (test: Phase 11C integration script)
           │
   14:58   │■ checkout → 新分支 phase14/backend-saas  ← 分支名宣告"SaaS"
   14:58   │■ commit 4  Wave 1: 用户系统 (users + sessions + JWT + refresh)         [Fallback]
   14:59   │■ reset HEAD~1
   15:00   │■ commit 6  Wave 1 重做 [Production-ready]
   15:09   │■ commit 7  Wave 2: 多 corpus 隔离 (migration 014/015 + middleware)
           │
2026-05-25 ┤■ commit 8  Wave 2.5: supplement tests (114 tests)
   22:30   │
   23:10   │■ commit 9  Wave 3: 公网部署基建 (docker + nginx + tunnel + rate limit)  ← spec §9.4 "不对公网"被破
   23:22   │■ commit 10 Wave 4: share 机制 + user profile (migration 017/018)
   23:44   │■ commit 11 Wave 5: REST API 补全 (search/agents/scheduled_jobs/...)
           │
2026-05-26 ┤■ commit 12 Wave 6: stratum-web 初始化 (Next 16 + TS 6 + pnpm 11)       ← spec 接口列表无 web UI
   00:04   │■ commit 13 Wave 6 amend
   00:16   │■ commit 14 Wave 6 fix (v2.0 stack)
   00:29   │■ commit 15 Wave 7: Search + AI 页 (QA / Summary)
   00:55   │■ commit 16 Wave 8: 9 Block 集成 5-9 (Jobs/DocTree/DocReader/Annotation/Backlink)
   01:00   │■ commit 17 Wave 9: share 公开页 + profile + settings                    ← 当前 HEAD
```

**关键观察**:
- Spec 写完后 7 天内 (5-17 → 5-23), 仓库几乎没动。
- 5-24 凌晨突然爆发, **2 天 17 个 commit, 平均每 3 小时一个 wave**。
- 整个 SaaS 化在 spec 没有被更新过一个字的前提下发生。
- "Phase 11C" 暗示 stratum 在主线之外有个 11-期序列 (可能与 helios / hevi 共用), 但本仓库 git 历史看不到 1-10 期。

---

## §3 三大组件的状态 (各 30 字摘要)

### (A) 知识库 spec + schema 层 `_hub/`

**状态**: 立宪期已交付, 之后未更新。健康但**冻结**。

- ✅ `STRATUM_SPEC.md` 1368 行, v0.1.2, 设计完备
- ✅ 16 个 JSON Schema (substrate × 5 + concept × 6 + note × 5)
- ✅ 每个 schema 配 valid + invalid 例子
- ✅ 2 篇实证报告: vector-db 选 chromadb, embedding 选 bge-m3
- ❌ Spec §8 承诺的 6 类 ingest + 4 类 concept_management + 3 类 indexing + 8 类 lint + migration + audit = 数十个 pipeline 脚本, 实际写了 **1 个** (且仅覆盖 substrate.book)
- ❌ `_hub/servers/mcp_server.py` 和 `http_server.py`: 目录只有 `.gitkeep` (但见 (C), 实际 server 在 src/ 下)
- ❌ `_hub/indexes/` 空, 索引未建
- 🚨 Spec **没有反映** (C)(D) 的任何变化

### (B) 三层知识本体 `substrate/`, `concepts/`, `notes/`

**状态**: 全空, **未入过一条真实知识**。

- substrate/books/, papers/, webpages/, transcripts/, chats/ → 全部只有 `.gitkeep`
- concepts/people/, events/, theorems/, techniques/, places/, domains/ → 全部只有 `.gitkeep`
- notes/adr/, postmortem/, readings/, ideas/, daily/ → 全部只有 `.gitkeep`

**含义**: 整个 spec 的灵魂 (D2-D8 八维度的"可寻址 / 可检索 / 可演化 / 可审计 / 可消费 / 抗腐烂") 还没有任何真东西可以验证。

### (C) Python 后端 `src/stratum/`

**状态**: 急速增长, 已是一个**真实可跑的 FastAPI 应用**。

按 git wave 顺序累积:

- **Phase 11C (主线)**: service layer 雏形 (内容未细查, 可能是早期单用户实现)
- **Wave 1**: 用户系统 → `auth/{jwt_handler, refresh_handler, password, dependencies, exceptions}.py`, `dao/{users, sessions}.py`, `http_api/routes/auth.py`, `http_api/schemas/auth.py`, migrations 012/013
- **Wave 2**: 多 corpus 隔离 → `middleware/corpus_isolation.py`, migration 014 (加 corpus_id 列), 015 (default user 迁移), dao 全表加 corpus_id 过滤
- **Wave 2.5**: 114 个新测试 (覆盖 §3.7/§4.6)
- **Wave 3**: 公网部署 → docker-compose + nginx + tunnel 配置 (本次未读) + `middleware/rate_limit.py` + `middleware/abuse_detection.py` + migration 016
- **Wave 4**: 分享机制 → `dao/share_tokens.py`, `http_api/routes/share.py`, `dao/profile.py`, migrations 017/018
- **Wave 5**: REST API 补全 → 路由 search / substrates / notes / agents / scheduled_jobs, dao agent_run / scheduled_job, service/search.py, scheduler/builtin_jobs.py

**关键文件**:
- `http_api/app.py` 第 9 行: `FastAPI(title="Stratum API", version="1.2.0")`
- `http_api/app.py` 第 11-12 行: `allow_origins=["*"]` (CORS 全放), 与 spec §9.4 "默认只在 localhost" 矛盾
- `mcp_server/routes/{tasks, templates, review}.py` 表示 MCP 也在做, 不只是 HTTP

### (D) Next.js 前端 `stratum-web/`

**状态**: 全栈 UI 骨架已搭好, 实际数据未跑通 (无 (B) 的数据)。

- 框架: Next 16.2 + React 19.2 + TS 6 + Tailwind 4 + pnpm 11 (全是 cutting edge)
- 状态: `zustand` (auth, ui stores)
- 数据: `@tanstack/react-query`
- 表单: `react-hook-form` + `zod`
- 测试: vitest + playwright + storybook (全配置, 测试本身未读)

**页面**:
```
(auth)/login          (auth)/register
(app)/layout          (app)/search       (app)/ai (QA/Summary)
(app)/jobs            (app)/documents/   (app)/documents/[id]
(app)/notes/[id]      (app)/settings     share/[token] (公开)
```

**API client 设计** (`src/lib/api-client.ts`):
- access token 内存 (XSS 安全)
- refresh token httpOnly cookie
- 401 自动 refresh + retry
- 429 显式抛 rate limit error
- 与后端 (C) 完全配对

**类型系统** (`src/lib/types.ts`):
- `SubstrateItem`, `DerivativeItem`, `BacklinkItem`, `SearchResultItem`, `AgentRun`, `ScheduledJob` 等
- ⚠️ 与 spec §5 的 substrate/concept/note schema **不完全对齐** (web 把所有东西扁平化为 "documents" + "agents" + "jobs", 而非三层)

---

## §4 已识别的核心张力

### 张力 1: spec 的"个人本地"愿景 vs 代码的"多租户 SaaS"现实

| spec 条款 | 实际代码 | 冲突 |
|---|---|---|
| §1.1 "Wiki 个人级、本地优先" | `corpus_isolation` middleware + `users` 表 | 多用户 |
| §1.3 "多用户协作不在职责范围" | Wave 1-2 全是多用户基建 | 直接违反 |
| §1.3 "实时同步多设备 不在范围" | (未实现, 但 share + profile 暗示走向) | 未来冲突 |
| §9.4 "默认只在 localhost 暴露, 不对公网" | nginx + tunnel + CORS 全开 + rate limit + abuse detection | 直接对公网 |
| §9 接口列表只有: 文件系统 / 本地 MCP / 本地 HTTP | 多了一个 Web UI (`stratum-web/`) | 类型未列 |
| §0.2 "Stratum 服务多个上游消费者" (本地) | `share/[token]` 公开分享给陌生人 | 消费者范围扩展 |
| §7.4 检索接口设计 (MCP tools / HTTP routes 给 agent) | REST API 设计给浏览器 | 消费者形态变了 |

**根本问题**: spec 设计的是"地下深处的、静的、慢的、累积的底座" (§0.3.1 名字含义), 但实际写的是"对外暴露、需要 abuse detection、有 share token 的 SaaS 应用"。这两种气质不同, 工程取舍不同。

### 张力 2: spec 承诺的 (B) 完全没动, 但所有的 (C)(D) 都依赖 (B) 有数据

后端有 16 个 DAO 模块 (substrate, note, concept, derivative, ...), 前端有 documents/notes/search/ai 页面, 但 **substrate/concepts/notes 三层一条真数据都没有**。

具体后果:
- 前端的 search 页面没东西可搜
- AI 的 QA/Summary 没素材可问
- backlink 没东西可链
- 整个 SaaS 是一个"产品壳"

### 张力 3: spec §1.2 的 8 维度验收, 大部分维度的实证还没法做

- D1 (完备性): 7 种格式入库率 100% → 需要 ingest 流水线, **未写**
- D2 (可寻址性): ULID + 段落 ULID 5 秒定位 → 需要数据, **没有**
- D3 (可检索性): exact + semantic + meta 三种 → 后端有 search.py, 但没数据
- D4 (可演化性): schema migration → migration 脚本框架未建
- D5 (可审计性): AI 内容追溯 → `_hub/audit/changes.jsonl` 未启动
- D6 (可移植性): 30 分钟迁移 → 没数据, 没演练
- D7 (可消费性): Obsidian + Claude Code + MCP + HTTP → Obsidian 未配, MCP 部分实现, HTTP 实现, web UI 是新增的
- D8 (抗腐烂): 时间维度, 8 个 lint 规则 → 1 个 lint, 7 个未写

只有 D7 部分有进展 (HTTP 接口存在, MCP 部分存在, 多出来一个 Web UI)。

### 张力 4: pyproject.toml 0.0.1 vs http_api app.py 1.2.0

版本号已经精神分裂:
- `pyproject.toml` 还停在 spec §13.1 批 1 验收的 v0.0.1
- 后端 FastAPI 应用自报 v1.2.0
- spec §11.2 定义的 v0.x → v1.0 路线图 (v0.4.x + 90 天稳定 + 50+ 节点 = v1.0) **被绕过**

如果继续这样, 任何"v1.0"声明都不可信。

### 张力 5: README + spec 没有提及 (C)(D), 任何新协作者会迷失

README 24 行, 还在说"批 1 完成, 流水线和接口尚未实现"。
任何新人 (包括 6 个月后的 Wiki) clone 下来会:
1. 读 README → 以为是个空骨架
2. `ls` → 看到 `stratum-web/` 和 `src/stratum/` 两座大山, 困惑
3. 找说明 → 没有 (C)(D) 的任何文档
4. 看 git log → 才意识到过去 2 天发生了什么

---

## §5 Spec 未承诺、但已存在的"赠品"清单

这些**意外多出来的能力**也是宝贵资产, 不要废弃, 应该被纳入新 spec:

1. **完整的 JWT auth** (access + refresh + httpOnly cookie 模式), 业界正规做法
2. **多 corpus 隔离 middleware**, 为未来转向团队 / 多空间留好接口
3. **Share token 机制** (公开链接读取), 完成了 spec 缺失的"对外分享单条知识"能力
4. **Rate limit + abuse detection middleware**, 抗滥用基建
5. **Scheduler + agent runs**, 可调度任务 = 后台 ingest 的基础
6. **Push subscription DAO**, 暗示有通知能力 (未细查)
7. **Browser extension DAO**, 暗示要做浏览器扩展捕获 (未细查)
8. **Next.js 16 现代化前端**, 给非命令行用户的入口
9. **Storybook + Playwright + Vitest + ESLint**, 前端工程质量基线
10. **114 个新测试** (Wave 2.5), 后端有覆盖率纪律

这些都是 spec 写的时候**没想到要做、但实际很有价值**的能力。

---

## §6 推进项目的 3 条候选路径

身份决策必须 Wiki 亲自做。下面列出 3 条互斥路径 + 各自的代价 / 收益 / 立刻该做什么。

### 路径 A: **认账 SaaS 化, 重写 spec**

**含义**: 承认 Stratum 已从"个人本地 KB"演化成"多用户 SaaS 知识库 + AI agent 平台"。废弃 v0.1.2 spec 的 §1.1/§1.3/§9.4 等"本地 / 单用户 / 不公网"条款, 写 v0.2 spec 反映现实。

**收益**:
- 现实和文档对齐, 不再撒谎
- 后端 / 前端继续推进有依据可循
- share token / agent / scheduler 等"赠品"被正式纳入设计
- 可以面向真实用户上线 (hevi / 未来视频项目可以是第一批用户, 不只是 spec 假想的 "consumer")

**代价**:
- spec §0.3.1 关于 Stratum "深、静、慢、累积"的气质叙事会消解 —— 这是 Wiki 在 spec 里写过的一段动人定位
- 多租户后端的复杂度持续上升 (权限、计费、隔离、合规)
- 不再是 hevi 的"本地基础设施", 关系需要重新定义

**立刻该做**:
1. 起草 STRATUM_SPEC v0.2 (重写 §1 / §9 / §0.2)
2. README 改写, 显式介绍 (C)(D) 组件
3. 把 pyproject 升到与 app.py 一致的 v1.2.x

### 路径 B: **回归本地 KB, 把 SaaS 部分剥离**

**含义**: 把 `src/stratum/` 和 `stratum-web/` 移到一个 sibling repo (例如 `stratum-cloud`), Stratum 回归 spec 原样, 老老实实做 §13 路线图的批 3-5。

**收益**:
- spec 的设计完整性保留, "底座基础设施"定位不漂
- 个人本地工作流 (Obsidian + Claude Code 直读 + 本地 MCP) 是 Wiki 实际工作姿势, 更贴合
- (B) 三层知识本体可以专心填充, 没有 SaaS 拖累
- "深、静、慢、累积"的气质能落地

**代价**:
- 2 天 17 个 commit 的工作量需要拆走 (有迁移成本, 不是删, 是搬)
- 失去面向潜在他人用户的窗口
- `stratum-cloud` (新仓库) 仍然要独立维护, 总工作量不变

**立刻该做**:
1. `git mv src/ ../stratum-cloud-tmp/src/` + `git mv stratum-web/ ../stratum-cloud-tmp/stratum-web/`, 新仓库初始化
2. 当前仓库回到 spec 路线图, 进入批 3 (流水线 MVP)
3. 写一份 `stratum-cloud` 的新 spec, 明确两个项目的关系

### 路径 C: **两条线并行, 用 monorepo 但明确分层**

**含义**: 承认两件事并行 —— `_hub/` + 三层是"本地 KB" (服务 Wiki 自己), `src/stratum/` + `stratum-web/` 是"SaaS 入口" (面向他人, 上层包装), **但两者复用同一套 schema 和数据**。

**收益**:
- 不必做"二选一"的痛苦决策
- 本地工作流 (Obsidian, Claude Code, MCP) 继续, SaaS 也继续
- 实现了"一份知识, 多种界面"

**代价**:
- 是 3 条里**最难做对**的: 需要清晰的边界定义, 否则 (A)(B) 的张力会持续渗透
- spec 必须同时描述两套接入、两类 consumer、两种 deployment 模式
- 工作量最大: 既要补 (B), 又要继续 (C)(D), 还要写更长的新 spec

**立刻该做**:
1. 写 STRATUM_SPEC v0.2 + 一份 `_hub/STRATUM_ARCH_v2.md` 描述 monorepo 边界
2. 在 `_hub/audit/reports/` 记录"本次身份转向"的决策 (这就是一个 postmortem)
3. 把 `src/stratum/` 和 `stratum-web/` 显式标注为"上层产品", 不归入 v1.0 验收 (避免拖累)

### 推荐 (但 Wiki 最终决定): **路径 A**

**理由**:
1. 已经做了 17 个 commit 的代码, 沉没成本 + 真实价值都倾向"认账"
2. spec 是为了帮助决策, 不是为了束缚决策 —— spec 本来就是 v0.x, 大改是预期
3. 路径 B 的"剥离"会牺牲已经写好的、明显有价值的 (C)(D)
4. 路径 C 听起来好, 但实操难度极高, 单人维护承担不起
5. spec §0.4 自己就说"v0.x 期间 schema 频繁 migration 是预期的"—— 现在 spec 本身也需要 migration

**但如果 Wiki 内心更倾向 B**: 也完全合理。SaaS 化不是必须的, "深静慢累积"的定位有独立价值。这是身份决定, 不是技术决定。

---

## §7 立刻可做的 5 个动作 (不依赖路径选择)

无论 §6 选哪条路径, 下面 5 件事都该现在做:

1. **更新 README** (估时 15 分钟)
   显式列出 (C)(D), 标注"v0.1.2 spec 与现实存在 drift, 见 `_hub/audit/reports/2026-05-26-...`"

2. **冻结当前状态, 打个 tag** (估时 5 分钟)
   `git tag v0.0.2-state-snapshot` 或类似, 标记"身份决策之前的最后状态"

3. **写 1 篇 postmortem** (估时 1 小时)
   `notes/postmortem/2026-05-26-spec-drift__<ULID>.md` —— 把"为什么 10 天内 spec 和实现就出现 drift"记下来, 给未来的 Wiki 看。这本身也是 spec §6.3 要求的 review cadence 的实践。

4. **修复 pyproject.toml 与 app.py 的版本号矛盾** (估时 5 分钟)
   选一个真版本号 (建议跟随 app.py 的 1.2.0, 或者降到 0.2.0 暗示"还在 batch 2 阶段"), 全仓库一致。

5. **真入 1 条知识进 substrate/notes/** (估时 30 分钟 - 1 小时)
   选 spec 自己 (STRATUM_SPEC.md) 或这份报告作为第 1 条 substrate.chat 或 substrate.webpage —— 让 (B) 不再是 0。这也会暴露 ingest 流水线缺失的具体痛点。

---

## §8 附录: 我没看的东西 (诚实标注盲点)

- 后端 50 个 .py 文件我只读了 `http_api/app.py` 全文 + `dao/users` 等的文件名, 没读实现细节
- 9 条 SQL migration 文件名读了, 内容未读
- `stratum-web/` 25 个 TS/TSX 文件读了 `layout.tsx` + `api-client.ts` + 部分 `types.ts`, 其他没细读
- Wave 3 提到的 docker-compose / nginx / tunnel 配置我没找到具体文件 (可能在仓库根或别处)
- `phase14/backend-saas` 之前的 main 分支历史只看到 2 个 commit (Phase 11C + integration test), Phase 1-10 / 11A / 11B 的去向未查
- `.git/refs/remotes/` 没查 (不知道是否推到了 GitHub)
- 测试 (114 个) 没跑, 不知道当前是否全绿
- 我的 bash 工具完全失效 (UNC 路径错误), 因此**无法跑 `git log --stat` 等命令**, git 时间线是从 `.git/logs/HEAD` 读出来的

---

## §9 这份报告本身

- **由 Claude (chief advisor) 起草**, 时间 2026-05-26
- **依据**: spec §6.4, 标 `draft: true` 直到 Wiki review
- **下一步**: Wiki 在 Obsidian / 编辑器中 review, 给出 sign-off 或修订意见
- **存放**: `_hub/audit/reports/2026-05-26-project-state-and-path-forward.md`
- **关联**:
  - `_hub/STRATUM_SPEC.md` v0.1.2 (本报告分析的 spec)
  - `_hub/audit/reports/experiments/02-vector-db-comparison.md`
  - `_hub/audit/reports/experiments/03-embedding-comparison.md`
  - `.git/logs/HEAD` (本报告的时间线数据源)

**End of report.**
