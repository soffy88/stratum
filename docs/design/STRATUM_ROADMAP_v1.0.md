# Stratum 整体设计 + 实施路线图

**版本**: v1.0
**日期**: 2026-05-18
**整合来源**: ADR-001 ~ ADR-019 + STRATUM_SPEC v0.5/v0.6 PATCH + 4O 清单 v0.2/v0.3 PATCH + anything-llm 嫁接评估 + 翻译选型实证 + Phase 1 完工报告
**性质**: 工程路线图, 不阐述

---

## PART I: 整体设计

---

## §1 产品定位 (一句话)

**Stratum = 中文用户的 AI 知识管家**

- 知识 IN (input): 多来源 substrate 入库
- 知识 OUT (search): 融合检索 + AI 增强
- 主动服务: Agent + Scheduled Jobs + 推送
- 内容生产闭环: Stratum → hevi → 发布 (Phase 14+, 不在 v1.0)

**差异化 vs 竞品**:
- vs obsidian/notion: 有 AI 增强 (翻译/TTS/Agent)
- vs anything-llm: 中文优先 + 三 souls 框架 + substrate 语义分层
- vs 得到/喜马拉雅: 用户上传任意英文资料 + 自动中文化 (翻译 + TTS)

---

## §2 三个 Souls (核心架构)

```
┌─────────────────────────────────────────────────────────┐
│  Soul 1: 12-dim 信息面板 (Eyes)                          │
│  - substrate / concept / note 全维度展示                 │
│  - hybrid_search (vector + fulltext + RRF)              │
│  - Views (检索视角)                                       │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  Soul 2: 融合评分 (Brain)                                │
│  - AI Agent 系统 (主动决策)                              │
│  - Scheduled Jobs (定时推送)                             │
│  - 翻译 / TTS / 元搜索 等 AI 增强                        │
└─────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────┐
│  Soul 3: 回测验证 (Truth)                                │
│  - Decision Trail (审计跟踪)                             │
│  - Citation 强制 (每个 LLM 输出可追溯)                   │
│  - 抗腐烂 (lint 检查)                                    │
└─────────────────────────────────────────────────────────┘
```

---

## §3 整体架构 (Layer 视图)

```
┌──────────────────────────────────────────────────────────────────┐
│  Layer 5: 端 (Multi-end)                                          │
│  Desktop (WSL2 主) / 微信小程序 / 浏览器扩展 / Mobile             │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│  Layer 4: omodul (业务模块)                                       │
│  process_inbox / start_mcp_server / agents.* / scheduler /        │
│  views / browser_extension / sync.bg_sync                         │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│  Layer 3: oskill (业务技能)                                       │
│  knowledge.* (ingest / search / translate / audio / 等)           │
│  sync.* (flush_outbox / apply_remote / snapshot)                  │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│  Layer 2: oprim (原子操作)                                        │
│  classifier / parser / embedding / vector_db / fulltext /         │
│  meta_db / llm / mcp / storage / changefeed / push /              │
│  translate / external.* / input.*                                 │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│  Layer 1: obase (基础设施)                                        │
│  logging / errors / config / metrics                              │
└──────────────────────────────────────────────────────────────────┘
                            ↕
┌──────────────────────────────────────────────────────────────────┐
│  Layer 0: 数据 (Data)                                             │
│  PostgreSQL (平台) / LanceDB (向量) / Redis (cache) /             │
│  RabbitMQ (事件) / SQLite (用户 meta) /                           │
│  用户网盘 (substrate 原文 + changefeed.log)                       │
└──────────────────────────────────────────────────────────────────┘

外挂 (Phase 11+, 独立 Docker 容器, 同 network):
├── whisper.cpp / F5-TTS / fish-speech / SD-webui / searxng /
├── hevi (动画) / screenpipe (屏幕历史, 反向输入)
```

---

## §4 数据架构

### 4.1 substrate (原始知识资料)

```
substrate ← 用户上传的 paper / book / podcast / web / note / screen_event
   ├── fragments (段/章/句 — embedding 单位)
   ├── derivatives (markdown / translation / audio / chapters / summary / 等)
   └── lineage (跟 concept 关联)

字段:
- id (ULID), title, medium, format, language
- is_pinned, pinned_at
- source_url, source_path
- has_derivatives (list)
- created_at, updated_at
```

### 4.2 concept (语义实体)

```
concept ← 跨 substrate 出现的实体 (人名 / 术语 / 主题)
   ├── related_substrates
   ├── related_concepts
   └── canonical_name + aliases
```

### 4.3 note (用户产出)

```
note ← Wiki 自己写的笔记 / 评论 / 思考
   ├── references_substrates
   ├── references_concepts
   └── priority
```

### 4.4 derivative (派生物, Phase 10+)

```
derivative ← AI 加工产物
   ├── type: markdown / translation / summary / audio_narration / illustration /
   │         video_lecture (hevi 回流) / chapters / key_quotes
   ├── source_substrate_id (lineage)
   └── metadata (provider / tokens / cost)
```

### 4.5 存储分层

```
平台内容 (运营方提供, pgvector + PostgreSQL):
- platform_content / platform_content_chunk
- 用户付费看 (得到模式)

用户内容 (用户自有, LanceDB + SQLite + 用户网盘):
- substrate / fragment / concept / note / derivative
- 用户自己拥有, 跨设备同步走自己的网盘
```

---

## §5 关键技术栈选型 (Phase 1 已实施)

| 组件 | 选型 | 来源 |
|---|---|---|
| 向量库 (用户) | **LanceDB** | 实证 #2 |
| 向量库 (平台) | pgvector + PostgreSQL | 选型 |
| 关系库 (平台) | PostgreSQL 18 + uuidv7 | 选型 |
| 元数据 (用户) | SQLite (meta.duckdb) | 选型 |
| Fulltext | tantivy + jieba | 选型 |
| Embedding | Qwen3-Embedding (DashScope, 1024 维) | 实证 #3 |
| LLM | DeepSeek V3.2 (主) / Claude (备) / Qwen3-Max (备) | 翻译选型实证 |
| PDF 解析 | unstructured + pdfplumber + PyMuPDF | 实证 #1 |
| 分类 (Layer 1) | 规则 + heuristics | 实证 |
| 分类 (Layer 2) | 嵌入分类器 | 实证 |
| 事件队列 | RabbitMQ | 选型 |
| 缓存 | Redis | 选型 |
| MCP 协议 | mcp Python SDK | 实证 #4 |
| 翻译 (Phase 10) | DeepSeek V3.2 主 + Claude + Qwen3 | 翻译选型实证 |

---

## §6 部署拓扑 (校准后)

### 6.1 设备角色 (2026-05-18 校准)

| 设备 | 配置 | 当前角色 | Stratum 用途 |
|---|---|---|---|
| **笔记本** | i7 24G / 4G GPU | **Stratum 主开发 + 部署** ⭐ | Phase 1-10 部署 |
| **主力 Win11** | 32G / 10G GPU | Helios / Helixa / Selene | Phase 11+ 外挂 GPU 资源 |
| **备机 Win11** | 24G / 无独显 | Selene A/B | 不用于 Stratum |
| **Surface Pro 7** | - | Parsec 客户端 | 不用于 Stratum |
| **Singapore VPS** | Ubuntu 26.04 | sing-box 代理 | 外挂部署候选 |

### 6.2 Stratum 主体部署 (笔记本)

```
笔记本 (24G RAM / 4G GPU)
└── Docker stratum-network
    ├── stratum-main      (Python, 1-2G)
    ├── stratum-postgres  (1-2G)
    ├── stratum-redis     (0.5G)
    ├── stratum-rabbitmq  (0.5G)
    └── (Phase 11+) 轻外挂: searxng / whisper.cpp small

总占用: < 7G RAM, GPU 不用 → 笔记本完全够
```

### 6.3 外挂部署 (Phase 11+, 跨机)

```
主力机 (10G GPU)               笔记本 (Stratum 主体)
├── ollama (qwen3:14b)         ├── stratum-main
├── F5-TTS                     │
├── fish-speech (评估)         │
├── SD-webui (1.5/2.1)         │
└── hevi (评估)                │
        │                       │
        └──── Tailscale ──────→ 调用 (HTTP / MCP)
```

跨机通信: Tailscale Magic DNS → ADR-019 修订 (Phase 11 启动前)

---

## PART II: 实施路线图

---

## §7 Phase 列表 (完整)

| Phase | 名称 | 状态 | 工程量 | 启动条件 |
|---|---|---|---|---|
| **Phase 1** | 4O 基础 (oprim + oskill + omodul) | ✅ **完工** | (已完成) | - |
| **Phase 1.5** | 嫁接 (is_pinned / mode / citation) | 待启动 | 1-2 周 | Phase 1 ✅ |
| **Phase 2** | 网盘 + 同步 (CC-A) | 待启动 | 6 周 | GDrive OAuth |
| **Phase 4** | 微信 MVP + 浏览器扩展 | 待启动 | 3-4 周 | Phase 2 ✅ |
| **Phase 5** | 付费系统 | 待规划 | 4 周 | Phase 4 ✅ |
| **Phase 6** | 融合检索 | 待规划 | 3 周 | Phase 5 ✅ |
| **Phase 7-9** | 增强抗腐烂 + 多语种 | 待规划 | 4-6 周 | Phase 6 ✅ |
| **Phase 10** | Translation (CC-B) | 指令书 ready | 4 周 | DeepSeek key ✅ |
| **Phase 11** | Agent + Scheduled Jobs + 外挂 | 待规划 | 8-10 周 | Phase 10 + ADR-020 |
| **Phase 12** | hevi + screenpipe 集成 | 待规划 | 3-4 周 | Phase 11 ✅ |
| **Phase 13** | Views (检索视角) | 待规划 | 1-2 周 | Phase 11 ✅ |
| **Phase 14+** | 发布闭环 (Stratum→hevi→平台) | 锚定方向, 不写 | TBD | v2.0 评估 |

**v1.0 范围**: Phase 1 ~ Phase 13 (~9 个月)
**v2.0 范围**: Phase 14+ (商业化期)

---

## §8 当前执行计划 (并行)

### 8.1 当前 Wave (2026-05-18 起)

```
当前已分派给 CC:
├── 4O v0.3 PATCH 整体执行 (已发, 范围待 CC 反馈)
│
当前可并行启动:
├── Phase 10 (CC-B): Translation
│   ├── 指令书 ready (1557 行)
│   ├── DeepSeek + Anthropic + DashScope key ready
│   └── 等 Wiki 发给 CC-B
│
├── Phase 2 (CC-A): 网盘 + 同步
│   ├── 指令书 待写
│   └── 等 Wiki 申请 GDrive OAuth
│
我并行做:
└── Phase 2 (CC-A) 实施指令书撰写
```

### 8.2 启动顺序

```
第 1 步: 发 Phase 10 给 CC-B → CC-B 启动
第 2 步: Wiki 申请 GDrive OAuth (并行)
第 3 步: 我写 Phase 2 指令书 (并行)
第 4 步: GDrive OAuth ready → 发 Phase 2 给 CC-A → 并行实施
第 5 步: CC-A + CC-B 并行执行 (namespace 隔离, R-5)
第 6 步: Phase 10 完工 → Phase 1.5 嫁接给当前 CC
第 7 步: Phase 2 + Phase 10 + Phase 1.5 全部完工 → Phase 4 微信 MVP
```

### 8.3 namespace 隔离矩阵 (R-5)

| Sub-package | CC-A (Phase 2) | CC-B (Phase 10) | CC-others (1.5) |
|---|---|---|---|
| oprim/storage/* | ✅ 改 | ❌ 禁 | ❌ 禁 |
| oprim/changefeed/* | ✅ 改 | ❌ 禁 | ❌ 禁 |
| oprim/push/* | ✅ 改 | ❌ 禁 | ❌ 禁 |
| oprim/translate/* | ❌ 禁 | ✅ 改 | ❌ 禁 |
| oprim/meta_db schema (is_pinned) | ❌ 禁 | ❌ 禁 | ✅ 改 |
| oskill/sync/* | ✅ 改 | ❌ 禁 | ❌ 禁 |
| oskill/knowledge/translate_substrate | ❌ 禁 | ✅ 改 | ❌ 禁 |
| oskill/knowledge/hybrid_search (mode 参数) | ❌ 禁 | ❌ 禁 | ✅ 改 |
| omodul/sync/* | ✅ 改 | ❌ 禁 | ❌ 禁 |

---

## §9 各 Phase 详细规范

### 9.1 Phase 1.5 — 嫁接 (低成本快速做)

**目标**: 把 anything-llm 评估中的 3 个低成本嫁接点做掉

**范围**:
- substrate.is_pinned 字段 + pin/unpin MCP tool
- oskill.knowledge.hybrid_search 加 mode 参数 (strict / augmented)
- search 接口加 citation 强制规范

**4O 元素**: 见 4O v0.3 PATCH §A

**Gate 验收**:
- substrate pin/unpin 端到端通
- hybrid_search mode=strict 在无命中时不调 LLM
- 所有 search 输出含 citation

**工程量**: 1-2 周, 由 omodul 完工的当前 CC 继续做

---

### 9.2 Phase 2 — 网盘 + 同步 (CC-A)

**目标**: 用户数据上 Google Drive + 多端同步

**范围**:
- oprim.storage.gdrive (主) + storage.local (备)
- oprim.changefeed (event log + reader + compactor + snapshot)
- oprim.push (web push + email)
- oskill.sync.* (flush_outbox / apply_remote_events / snapshot_backup / restore)
- omodul.sync.bg_sync (守护进程)

**4O 元素**: 见 4O v0.3 PATCH §B

**关键决策**:
- 主网盘 = Google Drive (Wiki 拍板)
- 跳过阿里云盘 (Q2 凭证未解决)
- snapshot 频率: 每 24 小时
- 冲突解决: last-write-wins (按 created_at)

**Gate 验收**:
- 设备 A 创建 substrate → GDrive → 设备 B 拉到 → 能搜
- 离线创建 → 联网 flush 不丢
- 中断 + restore 等价于 full replay

**工程量**: 6 周

**准入**:
- ✅ Phase 1 完工
- ⏳ Wiki 申请 GDrive OAuth client_id + secret

---

### 9.3 Phase 4 — 微信小程序 MVP + 浏览器扩展

**目标**: Stratum 上微信 + 浏览器多端

**范围**:
- 微信小程序 (前端, 不在 4O)
- omodul.knowledge.browser_extension (Chrome / Firefox / Edge)
  - 一键保存网页到 inbox
  - 选中文本 → fragment + note
  - Sidebar 显示相关 substrate

**4O 元素**: 见 4O v0.3 PATCH §C

**关键决策**:
- 微信小程序 = 只读浏览 + 微信内分享 substrate (V1)
- 浏览器扩展 = 写入 + 检索 (V1)

**Gate 验收**:
- 微信小程序登录 + 查询 + 浏览 OK
- 浏览器扩展安装 + 一键保存 + 去重 OK

**工程量**: 3-4 周

---

### 9.4 Phase 5 — 付费系统

**目标**: 接入支付 + 订阅档位生效

**范围**:
- 微信支付 + 支付宝
- 订阅档位: Free / Plus ¥299 / Pro ¥999 / 学生 ¥149
- 配额管理 (substrate 数 / 翻译 token / TTS 时长)

**4O 元素**: omodul.billing 新增 (规范待细化)

**Gate 验收**:
- 完整支付 → 订阅生效 → 配额生效
- 续费 / 退费 / 升降级 流程

**工程量**: 4 周

---

### 9.5 Phase 6 — 融合检索

**目标**: 平台内容 + 用户内容 + 网络搜索 融合

**范围**:
- 平台内容索引 (pgvector + PostgreSQL FTS)
- 用户内容索引 (LanceDB + tantivy)
- RRF 跨源融合
- 用户付费可见平台内容 (跟 Phase 5 配合)

**Gate 验收**:
- 跨源融合检索精度 ≥ 单源
- 付费用户跟非付费用户检索结果差异 (平台内容)

**工程量**: 3 周

---

### 9.6 Phase 10 — Translation (CC-B) ⭐

**目标**: 中文知识桥梁能力上线

**范围**:
- oprim.translate (provider_protocol + chunker + checkpoint + router + terminology + format)
- 3 provider: DeepSeek (主) + Claude (高质量) + Qwen3 (国内)
- format 保留: markdown / plaintext / epub
- oskill.knowledge.translate_substrate 端到端
- 默认 embed 翻译 (中文 query 跨语种检索)

**4O 元素**: 见 4O v0.3 PATCH §D, 详细实施见 Phase 10 指令书

**关键决策**:
- DeepSeek 默认 (ADR-018 + 翻译选型实证)
- 翻译 derivative 默认 embed (Wiki 拍板, "长期主义 / 质量为王 / 功能至上")
- 不直接 fork hydropix (AGPL)
- 不实施 Gemini (Phase 11+)

**Gate 验收**:
- 3 provider × 3 corpus 实测全通过
- 一本 80K word 英文书翻译完成, 格式保留
- 中断 + resume 正确
- 单 substrate 翻译成本 < $0.10 (DeepSeek)

**工程量**: 4 周

**准入**:
- ✅ Phase 1 完工
- ✅ DeepSeek + Anthropic + DashScope key

---

### 9.7 Phase 11 — Agent + Scheduled Jobs + 外挂集成 ⭐⭐

**目标**: Stratum 从 "工具" 升级到 "知识管家" (anything-llm 嫁接报告核心)

**范围**:

A. **Agent 系统** (omodul.knowledge.agents.*)
- 6 个 builtin Agent:
  - Knowledge Curator (每日 inbox 处理)
  - Reading Companion (对话式陪读)
  - Daily Digest (每日摘要)
  - Translation Worker (批翻译)
  - Audio Generator (TTS)
  - Lint Bot (定期 lint)
- Agent 调用接口 + trace 持久化

B. **Scheduled Jobs** (omodul.knowledge.scheduler)
- cron 引擎 (APScheduler) + Redis 锁
- 4 个 builtin job: daily_inbox / daily_digest / weekly_lint / nightly_translation
- 推送通道: web / email / 微信小程序

C. **外挂集成** (oprim.external.*, oskill.knowledge.*)
- MCP client + HTTP client + circuit breaker + retry
- whisper.cpp / F5-TTS / SD-webui / searxng 接入
- 新 derivative: audio_narration / illustration / transcript
- 新 oskill: generate_audio_narration / generate_illustration / web_search_augmented / transcribe_audio_substrate

D. **Multi-modal LLM** (oprim.llm.vision)
- Qwen-VL / Claude vision

**4O 元素**: 见 4O v0.3 PATCH §E (10 oprim + 4 oskill + 8 omodul)

**关键决策 (Phase 11 启动前必须做)**:
- **ADR-020**: 跨机部署拓扑 (笔记本 + 主机 GPU + Singapore VPS) + 修订 ADR-019 同 network 约束
- 外挂选型最终决定 (TTS: F5 还是 fish-speech, SD: 1.5 还是 XL)
- 用户 LLM 路由策略 (远程 API vs 本地 Ollama)
- 翻译质量评估 Agent (back-translation? 用户标记?)

**Gate 验收**:
- 6 个 builtin Agent 跑通
- daily_digest cron 跑通 + 推送
- whisper / TTS / searxng 端到端
- citation 在 Agent 输出强制

**工程量**: 8-10 周, 建议拆 4 个 CC 并发:
- CC-C1: oprim.external.* (基础)
- CC-C2: omodul.knowledge.agents.*
- CC-C3: omodul.knowledge.scheduler
- CC-C4: 4 个新 oskill

---

### 9.8 Phase 12 — hevi + screenpipe

**目标**: hevi 外挂 + screenpipe 反向输入

**范围**:
- oprim.external.hevi_client (调用 hevi 生成动画)
- oprim.input.screenpipe.* (读 screenpipe SQLite)
- 新 substrate medium: screen_event
- 新 derivative type: video_lecture (hevi 回流)

**4O 元素**: 见 4O v0.3 PATCH §F

**关键决策**:
- hevi 经理人独立, Stratum 只规范接入
- screenpipe 数据导入策略 (全量 vs 用户标记的事件)

**Gate 验收**:
- Stratum → hevi 请求 → 视频回流 OK
- screenpipe SQLite 读取 + 入库 OK

**工程量**: 3-4 周

---

### 9.9 Phase 13 — Views (检索视角)

**目标**: anything-llm workspace 概念的 Stratum 版本

**范围**:
- omodul.knowledge.views (CRUD + applier + preset_loader)
- 5 个预置 view: 通用 / 中文文学 / 量化金融 / 技术阅读 / 工作日志
- hybrid_search 接口加 view_id 参数

**4O 元素**: 见 4O v0.3 PATCH §G

**Gate 验收**:
- 预置 view 加载 + 编辑保存
- search 应用 view filter 正确

**工程量**: 1-2 周

---

### 9.10 Phase 14+ — 发布闭环 (v2.0 锚定方向, 不写)

**目标**: Stratum → hevi → 多平台自动发布

**范围 (锚定方向)**:
- Stratum 提供素材给 hevi → hevi 生成视频 → 回流 Stratum 管理
- Stratum 调发布外挂 → B站 / YouTube / 抖音 / 小红书 / 公众号视频号
- 各平台独立发布外挂, 各经理人

**关键决策**:
- 不在 v1.0 实施
- v2.0 商业化期评估

**工程量**: TBD

---

## §10 v1.0 完工后状态 (Phase 13 完工时)

### 10.1 功能完整度

```
✅ 知识 IN: PDF / markdown / web / podcast / 屏幕历史 / 微信分享
✅ 知识 OUT:
   - hybrid_search (vector + fulltext + RRF)
   - mode 参数 (strict / augmented)
   - 强制 citation
   - Views 视角
✅ AI 增强:
   - 翻译 (英文资料 → 中文 derivative)
   - TTS (中文音频朗读)
   - 图像生成 (concept illustration)
   - 元搜索 (substrate + web)
   - Multi-modal (图片问答)
✅ 主动服务:
   - 6 个 builtin Agent
   - 4 个 builtin Scheduled Job
   - 推送 (web / email / 微信)
✅ 多端: Desktop + 微信小程序 + 浏览器扩展
✅ 同步: Google Drive + 多设备
✅ 付费: Free / Plus / Pro / 学生 4 档
```

### 10.2 部署形态

```
笔记本 (Stratum 主体): 单用户 Wiki 自用
主力机 (10G GPU): 外挂 (TTS / SD / Ollama)
Singapore VPS: 代理 / 备份
用户网盘 (Google Drive): substrate + changefeed
```

### 10.3 商业化基础

- 4 档订阅就位 (Phase 5)
- 配额机制 (substrate 数 / 翻译 token / TTS 时长)
- 多端引流 (微信 + 浏览器扩展 + Web)
- 内容平台分层 (用户内容 vs 平台内容, 平台内容 Phase 6 通)

---

## §11 关键风险 + Wiki 决策点

### 11.1 当前 Wiki 待决项 (按紧急度)

| 紧急度 | 决策点 | 当前状态 |
|---|---|---|
| 🔴 立即 | 发 Phase 10 给 CC-B | 指令书 ready, 等 Wiki 发送 |
| 🔴 立即 | 申请 GDrive OAuth client | Phase 2 准入 |
| 🟡 本周 | sign-off SPEC v0.6 PATCH | 不阻塞但需要 |
| 🟡 本周 | sign-off 4O v0.3 PATCH | 已发 CC, 需 Wiki 确认范围 |
| 🟢 Phase 4 前 | 微信小程序开发者账号 | 商业化期需要 |
| 🟢 Phase 11 前 | ADR-020: 跨机部署拓扑 | 笔记本 + 主机 + VPS |

### 11.2 已知风险

| 风险 | 影响 Phase | 缓解 |
|---|---|---|
| GDrive 国内访问慢 | Phase 2 | Tailscale + Singapore VPS 代理 |
| Phase 11 外挂 GPU 不够 | Phase 11+ | 跨机 (主机 10G) + 选轻量模型 |
| 翻译成本失控 | Phase 10 | Scheduled Job 夜间批 + 用户配额 |
| 微信小程序审核 | Phase 4 | 内容平台合规审查 |
| 商业化 (v2.0) 转型 | Phase 14+ | 不在 v1.0 范围, 不影响 |

---

## §12 项目治理

### 12.1 角色

```
Wiki (项目主)
├── 拍板架构决策
├── API key 申请
├── 验收 sign-off
└── 跨经理人协调 (转贴)

Claude (Stratum chief advisor) [本会话]
├── SPEC / 4O / ADR 维护
├── 写实施指令书
├── 翻译选型 / anything-llm 评估
└── 跟 Wiki 单线沟通 (转贴)

CC (Claude Code, 执行)
├── 按指令书全自动实施
├── Wave 完工报告
└── R-1/R-2/R-4/R-5 红线遵守

其他项目经理人 (独立)
├── hevi advisor (动画化)
├── obase 经理人 (基础设施)
├── whisper / TTS / SD / searxng / screenpipe 等外挂 (Phase 11+)
└── 各自独立工作
```

### 12.2 治理纪律

- **R-1**: 失败不静默 (Phase 1 教训, 见 SPEC §2.5)
- **R-2**: SPEC 是真理源 (冲突停止报告)
- **R-3**: 完整调用链, 不创造接口
- **R-4**: 禁止扩大范围 (每 Phase 严格界限)
- **R-5**: namespace 隔离 (并行 CC 不撞)

### 12.3 文档真理源

```
顶层 (战略):
├── ADR-001 ~ ADR-019 (19 个决策)
├── STRATUM_SPEC v0.5 + v0.6 PATCH
└── 本路线图

中层 (设计):
├── 4O 清单 v0.2 + v0.3 PATCH
├── anything-llm 嫁接评估报告
└── 翻译选型实证报告

底层 (实施):
├── Phase 1 完工报告 (已完成)
├── Phase 10 实施指令书 (ready)
└── Phase 2 / 1.5 实施指令书 (待写)
```

---

## §13 时间线 (估计)

```
2026-05 (本月):
├── ✅ Phase 1 完工
├── 🔄 Phase 10 (CC-B) 启动
├── 🔄 Phase 2 (CC-A) 启动 (GDrive OAuth ready 后)
└── 🔄 Phase 1.5 嫁接 (当前 CC 继续)

2026-06:
├── Phase 10 完工 (~4 周)
├── Phase 2 完工 (~6 周, 跨月)
├── Phase 1.5 完工 (~2 周)
└── 开始 Phase 4 (微信 + 扩展)

2026-07:
├── Phase 4 完工
└── Phase 5 (付费) 启动

2026-08:
├── Phase 5 完工
├── Phase 6 (融合检索) 启动
└── 准备 Phase 11 (ADR-020 等)

2026-09:
├── Phase 6 完工
└── Phase 11 启动 (4 CC 并发)

2026-10:
└── Phase 11 进行中

2026-11:
├── Phase 11 完工
├── Phase 12 (hevi + screenpipe) 启动
└── Phase 13 (Views) 启动

2026-12:
├── Phase 12 完工
├── Phase 13 完工
└── ✅ Stratum v1.0 完整功能上线

2027-01+:
└── Phase 14+ 评估 (商业化 + 发布闭环)
```

**总时长**: 2026-05 → 2026-12 ≈ 8 个月到 v1.0

---

## §14 Wiki 自用 MVP 里程碑

不等 v1.0 完工, Wiki 可以提前用上的版本:

| 里程碑 | 时间 | 可用功能 |
|---|---|---|
| **MVP-1** | 现在 (Phase 1 完工) | inbox 入库 + hybrid_search + MCP server |
| **MVP-2** | Phase 1.5 完工 | + pinned + mode + citation |
| **MVP-3** | Phase 10 完工 (~6-7 月) | + 中英双语检索 (Stratum 中文桥梁) |
| **MVP-4** | Phase 2 完工 (~6-7 月) | + 多端同步 (Wiki 多机切换) |
| **MVP-5** | Phase 11 完工 (~10-11 月) | + Agent + Scheduled + 外挂 (Wiki 知识管家) |
| **v1.0** | Phase 13 完工 (~12 月) | 完整产品 |

---

**End of Stratum 整体设计 + 实施路线图 v1.0**
