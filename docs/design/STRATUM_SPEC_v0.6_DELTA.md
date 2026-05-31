# STRATUM_SPEC v0.6 修订增量

**版本**: v0.6 (增量 over v0.5)
**日期**: 2026-05-18
**前置**: v0.5, ADR-018 (translation), ADR-019 (外挂架构), anything-llm 嫁接评估
**性质**: diff over v0.5, 不重写整体, 只列修改

---

## §A 章节结构变更

### A.1 原 §17/§18 重新编号

| v0.5 | v0.6 |
|---|---|
| §17 关键技术决策来源 | §20 关键技术决策来源 |
| §18 未决问题 | §21 未决问题 |

### A.2 新增章节

| 编号 | 标题 | 位置 |
|---|---|---|
| §17 | Agent 系统 | 在 §16 实施路线后 |
| §18 | Scheduled Jobs | 在 §17 后 |
| §19 | Views (检索视角) | 在 §18 后 |

---

## §B 字段级修订

### B.1 substrate schema (§5.1 引用的 v0.3 §3.1 字段)

新增字段:
```
is_pinned: bool = False           # 用户置顶, 优先参与检索/Agent 上下文
pinned_at: datetime | None        # pin 时间戳, NULL = 未 pin
pin_priority: int = 0             # 0-10, 越高越优先, 0 = 未 pin
```

约束:
- `is_pinned=True` 时 `pinned_at` 必须非空
- `pin_priority > 0` 隐含 `is_pinned=True`
- changefeed event 必须记录 pin/unpin

### B.2 derivative type 枚举 (§5.2 引用的 v0.3 §3.3)

新增类型:
```
translation         # 翻译 (ADR-018)
audio_narration     # TTS 朗读 (ADR-019 外挂)
illustration        # 图像生成 (ADR-019 外挂)
```

新增 derivative 通用字段:
```
generation_source: str            # "rule" / "agent" / "manual"
generated_by_agent_id: str | None # 触发 Agent 的 ID
parent_substrate_id: str          # 已有, 必填
quality_indicators: dict          # 已有, 扩展键见 B.3
```

### B.3 derivative.quality_indicators 扩展键

translation 类型必填:
```
source_language: str              # ISO 639-1, e.g. "en"
target_language: str              # ISO 639-1, e.g. "zh"
translator_provider: str          # "qwen3" / "claude" / "gemini" / "deepseek"
translator_model: str             # 具体型号
chunk_count: int
translation_strategy: str         # "literal" / "literary" / "technical"
```

audio_narration 类型必填:
```
tts_provider: str                 # "f5_tts" / "fish_speech" / "edge_tts"
voice_id: str
duration_seconds: float
sample_rate: int
emotion_tags_used: list[str]      # fish-speech 用; 其他 provider 空列表
```

illustration 类型必填:
```
image_provider: str               # "sd_webui" / "dalle" / "gemini_imagen"
model_name: str
prompt: str
negative_prompt: str | None
seed: int | None
resolution: str                   # "1024x1024"
```

### B.4 medium 枚举 (§5.1 引用的 v0.3 §3.1)

新增 medium:
```
screen_event      # 来自 screenpipe 输入源 (ADR-019)
chat_log          # 用户跟外部 AI 对话历史
web_clip          # 浏览器扩展剪藏 (§19.x)
```

screen_event 字段:
```
source: str = "screenpipe"
captured_at: datetime
app_name: str
window_title: str
ocr_text: str
audio_transcript: str | None
related_files: list[str]
```

---

## §C 接口修订

### C.1 §10.1 search 接口修订

POST `/api/v1/search` Request 新增字段:
```
mode: str = "augmented"           # "strict" | "augmented"
                                  # strict: 只返回 substrate/concept 命中
                                  # augmented: 命中 + LLM 通用知识补充
view_id: str | None               # 指定 view (见 §19), null = 全局
include_pinned_first: bool = True # pinned substrate 优先
citation_format: str = "inline"   # "inline" | "structured" | "none"
```

Response 新增字段:
```
citations: list[Citation]         # mode != "none" 时必填
  Citation = {
    substrate_id: str
    fragment_id: str | None
    score: float
    text_excerpt: str             # ≤ 200 字
    source_type: str              # "user_substrate" / "platform_content" / "concept"
  }
llm_augmentation: str | None      # mode="augmented" 时, LLM 补充内容
augmentation_confidence: float    # 0-1
```

### C.2 §10 新增接口

#### POST `/api/v1/agent/invoke`
```
Request:
{
    "agent_id": str,              # 见 §17.1 预定义 Agent
    "input": str,                 # 用户 query
    "view_id": str | None,
    "tools_allowed": list[str],   # MCP tool 白名单
    "max_steps": int = 10,
    "stream": bool = False
}

Response (stream=false):
{
    "run_id": str,
    "status": "completed" | "failed" | "timed_out",
    "final_response": str,
    "trace": list[Step],          # 思考 + tool 调用记录
    "citations": list[Citation],
    "files_generated": list[str], # 文件路径
    "duration_ms": int
}
```

#### POST `/api/v1/jobs/create`
```
Request:
{
    "name": str,
    "cron_expression": str,       # 标准 cron, e.g. "0 8 * * *"
    "agent_id": str,
    "input_template": str,        # 可含 {date} {week} 变量
    "tools_allowed": list[str],
    "enabled": bool = True,
    "notification": {
        "on_complete": bool,
        "on_fail": bool,
        "channel": str            # "browser_push" / "wechat" / "email"
    }
}
Response:
{ "job_id": str, "next_run_at": datetime }
```

#### GET `/api/v1/jobs/runs/{job_id}`
```
Response:
{
    "runs": list[Run],
    Run = {
        "run_id": str,
        "started_at": datetime,
        "duration_ms": int,
        "status": str,
        "final_response": str,
        "trace_summary": str,
        "continue_thread_token": str  # 用于"在对话中继续"
    }
}
```

#### POST `/api/v1/views/create`
```
Request:
{
    "name": str,
    "filters": {
        "medium": list[str],
        "domain": list[str],
        "language": list[str],
        "tags": list[str],
        "pinned_only": bool
    },
    "default_llm": str,
    "default_system_prompt": str,
    "default_agents": list[str],
    "default_derivative_preferences": dict
}
Response:
{ "view_id": str }
```

### C.3 §9.3 MCP tools 修订 (作为 Server)

现有 4 个 tool 输出必须含 citation:
- `stratum.search` → response.results 每条加 `citation: Citation`
- `stratum.fetch_substrate` → 返回时附带 `pinned_status`
- `stratum.list_notes` → 不变
- `stratum.recent_changes` → 不变

新增 tool:
- `stratum.invoke_agent` (映射 C.2 agent/invoke)
- `stratum.list_views` (列出可用 view)

### C.4 §11 新增 MCP Client 子节

新增 §11.x "MCP Client (Stratum 调外挂)":

```
Stratum 作为 MCP client, 调用外挂 MCP server:
- whisper.cpp MCP        → 音频转录
- F5-TTS / fish-speech MCP → TTS 合成
- stable-diffusion MCP   → 图像生成
- searxng MCP            → 网络元搜索
- hevi MCP              → 教学动画化
- screenpipe MCP         → 屏幕历史 (作为新 substrate 来源)
- 任意第三方 MCP server  → 通过配置加入

通信:
- 协议: MCP over stdio (本地) / SSE (远程容器)
- 网络: 同 Docker network "stratum_net"
- 发现: ~/.stratum/external_mcp.yaml 配置
- 重试: 指数退避, 最多 3 次
- 超时: 默认 30s, 可按 tool 覆盖
- 失败处理: 跌落到 fallback chain (如 fish-speech 失败 → F5-TTS → edge_tts)
```

---

## §D 新增章节内容

### §17 Agent 系统 (Phase 11+)

#### §17.1 预定义 Agent

| Agent ID | 名称 | 触发 | 工具集 |
|---|---|---|---|
| `agent.curator` | Knowledge Curator | 定时 / 触发 | classify, ingest, lint, generate_derivative |
| `agent.companion` | Reading Companion | 用户阅读时 | hybrid_search, fetch_substrate |
| `agent.digest` | Daily Digest | 定时 (cron) | hybrid_search, summarize, recent_changes |
| `agent.translator` | Translation Agent | 触发 (新 substrate 是英文) | translate, generate_derivative |
| `agent.narrator` | Audio Narrator | 触发 (用户请求 audio derivative) | tts_external, generate_derivative |
| `agent.illustrator` | Concept Illustrator | 触发 (concept 需要可视化) | image_external, generate_derivative |
| `agent.researcher` | Deep Research | 用户请求 | web_search_external, hybrid_search, summarize |

#### §17.2 Agent 执行模型

```
1. Agent 接收 input + context
2. LLM 规划 (thinking) → 选择 tool
3. 调用 tool (内置 skill 或外挂 MCP)
4. tool 返回 → LLM 判断是否完成
5. 重复 2-4 直到完成 / 达到 max_steps
6. 输出 final_response + trace + citations

约束:
- 每次 tool 调用必须记录到 trace
- 引用 substrate 必须生成 citation
- max_steps 默认 10, Agent 可配置覆盖
- 超时按 tool 累计 (默认 5 分钟)
```

#### §17.3 Agent 上下文构造

```
context = {
    "user_pinned_substrates": [...],   # is_pinned=True, 优先注入
    "active_view": view_id,
    "recent_substrates": [...],        # 最近 7 天
    "user_preferences": {...},         # ~/.stratum/config.yaml
    "available_tools": [...],          # tools_allowed
}
```

#### §17.4 Custom Agent (用户自定义, v2.x)

```
~/Stratum/agents/{agent_id}.yaml:
  id: str
  name: str
  system_prompt: str
  default_tools: list[str]
  default_llm: str
  trigger:
    - type: "cron" | "event" | "manual"
      config: {...}
```

v1.x 仅预定义 Agent, v2.x 开放自定义。

---

### §18 Scheduled Jobs (Phase 11+)

#### §18.1 Job 数据结构

存储位置: `~/.stratum/cache/meta.duckdb` 表 `scheduled_jobs`

```sql
CREATE TABLE scheduled_jobs (
    job_id TEXT PRIMARY KEY,           -- ULID
    name TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    input_template TEXT NOT NULL,
    tools_allowed JSON NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    notification JSON,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    last_run_at TIMESTAMP,
    next_run_at TIMESTAMP
);

CREATE TABLE job_runs (
    run_id TEXT PRIMARY KEY,
    job_id TEXT REFERENCES scheduled_jobs(job_id),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    status TEXT,                       -- queued/running/completed/failed/timed_out
    final_response TEXT,
    trace JSON,
    citations JSON,
    files_generated JSON,
    error TEXT,
    continue_thread_token TEXT
);
```

#### §18.2 调度引擎

实现位置: `omodul.knowledge.scheduler`

```
组件:
- cron parser: croniter (Python)
- scheduler loop: 每 30s tick, 检查 next_run_at <= now 的 enabled jobs
- executor: 队列 + worker pool (max_concurrent_jobs=3, 可配置)
- timeout: 默认 10 分钟, job 可覆盖
- 单例锁: ~/.stratum/scheduler.lock (避免多进程重复执行)
```

#### §18.3 模板变量

input_template 支持的变量:
```
{date}        -- YYYY-MM-DD
{datetime}    -- ISO 8601
{week_start}  -- 本周一日期
{week_end}    -- 本周日日期
{yesterday}   -- YYYY-MM-DD
{run_id}      -- 当前 run_id
```

#### §18.4 通知通道

| channel | 实施 |
|---|---|
| `browser_push` | Web Push API (需用户授权) |
| `wechat` | 微信小程序 push (Phase 4 后可用) |
| `email` | SMTP, 可选 |
| `none` | 仅记录, 不推送 |

#### §18.5 默认 Job 模板

首次启动 Stratum 时预创建 (用户可禁用):

```yaml
- name: "每日 inbox 处理"
  cron: "0 8 * * *"
  agent_id: agent.curator
  input_template: "处理 {date} 的 inbox 文件"
  
- name: "每日摘要"
  cron: "0 21 * * *"
  agent_id: agent.digest
  input_template: "总结今天 {date} 新增的 substrate"

- name: "每周 lint 检查"
  cron: "0 10 * * 1"
  agent_id: agent.curator
  input_template: "扫描孤儿 substrate 和失链 note"
```

---

### §19 Views (检索视角)

#### §19.1 概念

View 是检索 + 呈现的 lens, 不是数据隔离。同一 substrate 库, 不同 view 看到不同子集 + 不同默认行为。

#### §19.2 View 数据结构

存储位置: `~/Stratum/views/{view_id}.yaml`

```yaml
view_id: str                       # ULID
name: str
description: str | null
filters:
  medium: list[str] | null
  domain: list[str] | null
  language: list[str] | null
  tags: list[str] | null
  date_range: {from, to} | null
  pinned_only: bool = false
defaults:
  llm_provider: str | null
  llm_model: str | null
  system_prompt: str | null
  agents_enabled: list[str]
  derivative_preferences:
    auto_translate: bool
    auto_narrate: bool
    translation_target_language: str
created_at: datetime
updated_at: datetime
```

#### §19.3 预设 View

首次启动时预创建:

```
view.all                  -- 默认, 无 filter
view.quant_finance        -- domain: [investing, quant]
view.tech_reading         -- domain: [tech, ai, programming]
view.chinese_literature   -- domain: [literature], language: [zh]
view.current_focus        -- pinned_only: true
```

#### §19.4 View 切换

UI 顶部 view selector, 切换后影响:
- 默认 search scope
- Agent 调用的 context
- inbox 处理的默认分类规则
- 推送的过滤

view_id 是软状态, 不影响存储, 不写 changefeed。

---

## §E 既有章节修订

### E.1 §1 产品本质 修订

在"核心差异化"列表末尾新增:

```
- **主动性**: Stratum 通过 Agent + Scheduled Jobs 主动服务用户, 
  不只被动等用户查询 (跟 obsidian/notion 等被动工具的根本差异)
```

### E.2 §3 用户可见接口 修订

新增条目:
```
- 视图切换 (View) — 切换检索视角和默认行为
- 任务面板 (Scheduled Jobs) — 查看 / 创建 / 禁用定时任务
- Agent 调用入口 — 显式调用 Agent 处理任务
- 通知中心 — Agent / Job 完成推送
- 引用面板 — 任何 LLM 输出可展开看 citation
- 浏览器扩展入口 (Phase 4)
```

### E.3 §11 流水线 修订

§11 新增小节 §11.x "MCP Client 子系统" (内容见 §C.4)

§11 现有 inbox 流水线说明加入:
```
inbox 处理可由 Agent.curator 触发 (定时或事件), 不再仅手动
```

### E.4 §13 隐私与安全 修订

新增 §13.x "Telemetry 策略":

```
默认: 完全关闭
可选开启: 用户在设置中明确启用 (商业化期 Pro 用户激励)
永不收集:
  - substrate 内容 / 摘要 / 翻译结果
  - note / highlight 文本
  - LLM 输入输出
  - 用户 query
仅收集 (启用时):
  - 功能调用计数 (匿名)
  - 报错堆栈 (脱敏)
  - 性能 metric
传输: HTTPS, 加密
保留: 90 天后聚合, 单条删除
opt-out: 一键关闭, 立即停止
```

### E.5 §14 微信集成 修订

补充 "通知通道" 角色: 微信小程序作为 Scheduled Job notification 的 channel 之一 (Phase 4 后可用)

### E.6 §15 付费系统 修订 → 更名 §15 商业化模型

新增 §15.x "多端策略":

| 端 | Phase | 状态 |
|---|---|---|
| WSL2 / 桌面 (主) | Phase 1 | ✅ |
| 微信小程序 (MVP) | Phase 4 | 计划 |
| 浏览器扩展 (Chrome/Firefox/Edge) | Phase 4 | 计划 |
| Embeddable Chat Widget | v2.x | 计划 |
| Mobile App | v2.x | 计划 |

浏览器扩展 (Phase 4) 能力:
```
- 一键 "保存当前网页到 Stratum inbox" (创建 medium=web_clip substrate)
- 一键 "高亮选中文本" → 创建 highlight + 关联到 web_clip substrate
- 边栏: 当前页面相关 substrate 推荐 (基于 URL 域 + 文本相似度)
- 配置: 跟桌面端同步 (走用户网盘)
```

### E.7 §16 实施路线 修订

各 Phase 追加内容:

**Phase 1.5** (新增, 在 Phase 1 完工后, Phase 2 启动前):
- substrate.is_pinned 字段实施
- hybrid_search 加 mode 参数 (strict/augmented)
- search response 加 citation 字段
- 工程量: ~ 1-2 周

**Phase 4** 追加:
- 浏览器扩展 (Chrome/Firefox/Edge)
- medium=web_clip 入库流水线
- 跟微信小程序同期实施

**Phase 10** 追加:
- agent.translator 实施
- agent.narrator 实施 (TTS 外挂集成)
- derivative.translation / audio_narration 流水线

**Phase 11** (新增, 在 Phase 10 后):
- Agent 系统完整实施 (§17)
- Scheduled Jobs 实施 (§18)
- Views 实施 (§19)
- MCP Client 子系统 (调外挂)
- 工程量: 8-10 周

**v2.x** 追加:
- Custom Agent (用户自定义)
- Multi-user permissioning
- Embeddable Chat Widget
- Agent Flows visual editor (评估)

---

## §F 4O 清单 v0.3 同步修订

### F.1 oprim 层新增 sub-packages

```
oprim/
├── translate/              # ADR-018, Phase 10
│   ├── provider_base.py
│   ├── qwen3_translator.py
│   ├── claude_translator.py
│   ├── gemini_translator.py
│   ├── deepseek_translator.py
│   └── chunking.py
├── external/               # ADR-019, Phase 11+
│   ├── mcp_client.py
│   ├── whisper_client.py
│   ├── tts_client.py
│   ├── sd_client.py
│   ├── searxng_client.py
│   ├── hevi_client.py
│   └── fallback_chain.py
├── input/                  # 新 substrate 输入源, Phase 11+
│   ├── screenpipe_reader.py
│   └── web_clip_parser.py
└── llm/                    # 既有, 扩展
    ├── vision.py           # multi-modal, Phase 11+
    └── streaming.py        # streaming 输出, Phase 11+
```

### F.2 oskill 层新增 sub-packages

```
oskill/knowledge/
├── translate_substrate.py        # Phase 10
├── generate_audio_narration.py   # Phase 10
├── generate_illustration.py      # Phase 11+
├── web_search_augmented.py       # Phase 11+
├── citation_builder.py           # Phase 1.5
└── pin_substrate.py              # Phase 1.5
```

### F.3 omodul 层新增 sub-packages

```
omodul/knowledge/
├── agents/                       # §17, Phase 11+
│   ├── base.py
│   ├── curator.py
│   ├── companion.py
│   ├── digest.py
│   ├── translator.py
│   ├── narrator.py
│   ├── illustrator.py
│   ├── researcher.py
│   └── runner.py
├── scheduler/                    # §18, Phase 11+
│   ├── engine.py
│   ├── cron_parser.py
│   ├── executor.py
│   └── notification.py
├── views/                        # §19, v1.x P1
│   ├── view_manager.py
│   └── filter_apply.py
└── browser_extension/            # E.6, Phase 4
    ├── api_server.py
    └── web_clip_handler.py
```

---

## §G 未决问题更新 (§21)

### G.1 v0.5 → v0.6 已解决

| v0.5 Q | 状态 |
|---|---|
| (无 — translation/Agent 在 v0.5 没列) | — |

### G.2 v0.6 新增未决问题

```
Q9: 翻译 provider 选型 — Qwen3 vs Claude vs Gemini vs DeepSeek
    实证驱动 (Claude 当前正在做选型实证), Phase 10 启动前必决

Q10: TTS provider 选型 — fish-speech (商业 license) vs F5-TTS vs edge_tts
    Phase 10 启动前实证

Q11: Agent 上下文窗口策略 — pinned 注入全文还是摘要?
    跟 LLM provider 选型相关 (长 context 模型放全文, 短 context 放摘要)

Q12: Scheduled Jobs 在用户离线时怎么办?
    选项 A: 本地 scheduler 启动时补跑漏掉的任务
    选项 B: 漏掉就漏掉, 不补
    选项 C: 看 job 类型决定 (digest 不补, lint 补)

Q13: Views 数量上限?
    用户可创建无限 view? 还是软上限 20 防混乱?

Q14: 浏览器扩展跟桌面端如何认证?
    OAuth flow 还是本地 token 共享?

Q15: Agent 失败的处理策略
    自动重试? 通知用户? 写入 job_runs.error 后静默?

Q16: 外挂 MCP server 跟 Stratum 主体的版本兼容性管理
    schema 兼容检查 / 版本协商
```

---

## §H 跟既有 ADR 的关联

| 章节 | 关联 ADR |
|---|---|
| §17 Agent | ADR-019 (外挂架构) |
| §18 Scheduled Jobs | (新, 待写 ADR-020) |
| §19 Views | (新, 待写 ADR-021) |
| §11.x MCP Client | ADR-019 |
| §B.2 derivative.translation | ADR-018 |
| §B.2 audio_narration / illustration | ADR-019 |
| §B.4 medium=screen_event | ADR-019 |
| E.4 Telemetry 策略 | ADR-017 (E2EE 不做的延伸) |

需新增 ADR:
- **ADR-020**: Scheduled Jobs 必要性 (跟 obsidian 的根本差异)
- **ADR-021**: Views 不是 Workspace (跟 anything-llm 哲学差异)

---

## §I 生效顺序

v0.6 修订**不是一次性全部实施**, 按 Phase 推进:

1. **当前 (Phase 1 进行中)**: v0.6 锁文档, 不实施任何修订
2. **Phase 1 完工后**: Phase 1.5 实施 §B.1 (is_pinned) + §C.1 mode 参数 + §C.3 citation 输出
3. **Phase 2 (CC-A)**: 不实施 v0.6 内容, 专注网盘 + 同步
4. **Phase 4**: §E.6 浏览器扩展
5. **Phase 10 (CC-B)**: §B.2 translation/audio_narration derivative, agent.translator/narrator
6. **Phase 11**: §17/§18/§19 完整实施, MCP client 子系统
7. **v2.x**: Custom Agent / Multi-user / Embeddable Widget

---

**End of STRATUM_SPEC v0.6 修订增量**
