# STRATUM_SPEC v0.6 修订增量 (PATCH)

**版本**: v0.6 (基于 v0.5 增量)
**日期**: 2026-05-18
**性质**: PATCH — 不重写 SPEC, 只列出修订点
**触发**: ADR-018 (Translation) + ADR-019 (外挂架构) + anything-llm 嫁接评估
**应用**: 应用此 patch 到 v0.5 → 得到 v0.6

---

## P1 章节编号变化

```
v0.5 编号        v0.6 编号        变化
§1-§13          §1-§13           不变
§14 微信集成     §17 微信集成     右移 3
§15 付费系统     §18 付费系统     右移 3
§16 实施路线     §19 实施路线     右移 3
§17 决策来源     §20 决策来源     右移 3
§18 未决问题     §21 未决问题     右移 3
                §14 Agent 系统    新增
                §15 Scheduled Jobs 新增
                §16 Views         新增
```

新增章节插在 §13 之后, §14 之前。

---

## P2 §3.2 substrate schema 修订

### 位置
v0.5 §3 用户可见接口 substrate 字段定义处。

### 修订
substrate 表新增字段:

```
is_pinned: BOOL DEFAULT FALSE    -- 用户标记为高优先
pinned_at: TIMESTAMP NULL        -- pin 时间, 用于 unpin LRU
```

索引:
```
CREATE INDEX idx_substrate_pinned ON substrate(user_id, is_pinned, pinned_at DESC)
WHERE is_pinned = TRUE;
```

### 接口
```
POST /api/v1/substrate/{id}/pin
POST /api/v1/substrate/{id}/unpin
```

### changefeed event 新类型
```
substrate.pinned   { substrate_id, pinned_at }
substrate.unpinned { substrate_id, unpinned_at }
```

---

## P3 §10.1 search 接口修订

### 位置
v0.5 §10.1 POST /api/v1/search Request 字段定义。

### 新增字段
```
"mode": "strict" | "augmented"   -- 默认 "augmented"
    strict:    只返回 substrate / platform_content 命中, 不用 LLM 通用知识
    augmented: substrate + LLM 通用知识合成

"pinned_boost": float            -- 默认 1.5, pinned substrate 分数乘数

"return_citations": bool          -- 默认 true, 是否在 response 含 citation 字段
```

### Response 字段补充
每条 result 新增:
```
"citation": {
    "substrate_id": "01HZ...",
    "fragment_id": "01HZ...#chunk_47",
    "anchor": {
        "section": "...",
        "char_start": 1234,
        "char_end": 1267
    },
    "deep_link": "stratum://substrate/01HZ.../#chunk_47"
}
```

### RRF 融合修改 (§10.2)
```python
def fuse_results(platform_results, user_results, k=60, pinned_boost=1.5):
    scores = {}
    for rank, item in enumerate(platform_results):
        scores[item.id] = scores.get(item.id, 0) + 1.0 / (k + rank + 1)
    for rank, item in enumerate(user_results):
        s = 1.0 / (k + rank + 1)
        if getattr(item, "is_pinned", False):
            s *= pinned_boost
        scores[item.id] = scores.get(item.id, 0) + s
    return sorted(items, key=lambda x: scores[x.id], reverse=True)
```

---

## P4 §11 部署架构修订

### 位置
v0.5 §11 流水线末尾, 新增小节 §11.4。

### §11.4 外挂能力集成 (Phase 11+)

```
docker-compose.yml 拓扑:

stratum-network (bridge):
├── stratum-main          # Stratum 主体 (本规范)
├── stratum-postgres
├── stratum-redis
├── stratum-rabbitmq
│
├── whisper-cpp           # 外挂 (独立项目, 独立经理人)
├── f5-tts | fish-speech  # 外挂
├── sd-webui              # 外挂
├── searxng               # 外挂
├── hevi                  # 外挂 (ADR-011)
└── anything-llm          # 不集成, 仅参考

通信:
- 优先: MCP 协议 (stdio over docker exec / SSE)
- Fallback: HTTP REST
- 同 docker network → 内网延迟 < 5ms
```

### 外挂能力接入清单 (按 Phase)

| Phase | 外挂 | Stratum 侧 sub-package | 用途 |
|---|---|---|---|
| Phase 10 | (无外挂, 用 API) | oprim.translate | 翻译 |
| Phase 11 | whisper.cpp | oprim.external.whisper_client | ASR derivative |
| Phase 11 | F5/fish-speech | oprim.external.tts_client | audio_narration |
| Phase 11 | sd-webui | oprim.external.sd_client | illustration |
| Phase 11 | searxng | oprim.external.searxng_client | web_search_augmented |
| Phase 12 | hevi | oprim.external.hevi_client | 教学动画 |
| Phase 12 | screenpipe | oprim.input.screenpipe | 新 substrate medium: screen_event |

### oprim.external.* 接口契约
所有外挂客户端实现统一接口:
```python
class ExternalToolClient(Protocol):
    async def health_check() -> dict
    async def invoke(payload: dict) -> dict
    async def stream(payload: dict) -> AsyncIterator[dict]  # 长任务

    timeout_seconds: int = 300
    retry_policy: RetryPolicy
    circuit_breaker: CircuitBreaker
```

---

## P5 §13 安全与隐私修订

### 13.4 用户数据隐私 - 扩充

新增条目:
```
- 外挂能力通信全程内网 (stratum-network), 不出 docker host
- 外挂调用的临时数据 (transcribe 中间结果 / TTS 输入 / SD prompt)
  不持久化, 任务完成后清除
- 外挂日志只记元数据 (任务 id / 耗时 / 状态), 不记内容
```

### 13.8 (新增) Telemetry 透明度

```
v1.0 不收集 telemetry (单用户本地实例)

v2.0+ 商业化期可选 telemetry:
- 默认关闭, 用户主动启用
- 透明列举收集字段:
  * 功能使用计数 (哪个 skill 用了几次)
  * 错误事件 (含 stack trace, 不含用户内容)
  * 性能指标 (检索耗时 / embedding 耗时)
- 永远不收集:
  * substrate 内容 / fragment 内容
  * concept 名称 / note 内容
  * search query 原文
  * 用户身份关联信息
- 用户可随时关闭 + 导出已收集的本人数据
```

---

## P6 §14 Agent 系统 (新增章节)

### 14.1 概念
Agent 是 Stratum 主动执行任务的实体, 区别于被动 MCP tool。

- Agent 有: name / system_prompt / 允许调用的 tool 集合 / 触发方式
- Agent 调用 oskill.knowledge.* + oprim.external.* (外挂) 完成工作
- Agent 输出含 citation, 跟 §10 接口对齐

### 14.2 预定义 Agent (v1.0 Phase 11+)

| Agent name | 触发 | 调用的 oskill / oprim | 输出 |
|---|---|---|---|
| Knowledge Curator | scheduled (每日) | classify_inbox_file, ingest_substrate, generate_derivative | inbox 处理报告 |
| Reading Companion | 用户主动 (chat) | hybrid_search, llm.llm_call | 对话 + citation |
| Daily Digest | scheduled (每日早 8 点) | hybrid_search(time_range=24h), llm.summarize | digest note + push |
| Translation Worker | scheduled / 触发 | oprim.translate, generate_derivative(type=translation) | translation derivative |
| Audio Generator | 触发 (用户标记) | oprim.external.tts_client, generate_derivative(type=audio_narration) | audio_narration derivative |
| Lint Bot | scheduled (每周) | lint, detect_duplicate_substrate | 健康报告 |

### 14.3 Agent 定义 schema

```yaml
# agent.yaml (Stratum 内置, 不允许用户自定义 v1.0)
name: knowledge_curator
system_prompt: |
  You are a knowledge curator for Wiki's Stratum library.
  Process new files in inbox, classify them, ingest as substrate.

allowed_tools:
  - oskill.knowledge.classify_inbox_file
  - oskill.knowledge.ingest_substrate
  - oskill.knowledge.detect_duplicate_substrate
  - oskill.knowledge.generate_derivative

llm:
  provider: dashscope
  model: qwen3-max
  temperature: 0.2

triggers:
  - type: scheduled
    cron: "0 6 * * *"  # 每天早 6 点
  - type: event
    event: substrate.ingested  # 新 substrate 入库时

output:
  format: markdown
  store_as: note            # 输出存为 note
  notify: true              # 推送给用户
```

### 14.4 Agent 调用接口

```
POST /api/v1/agents/{agent_name}/invoke
Request:
{
    "params": { ... },           # Agent-specific
    "async": true                # 长任务异步
}

Response (async=true):
{
    "run_id": "01H...",
    "status": "queued"
}

GET /api/v1/agents/runs/{run_id}
Response:
{
    "run_id": "...",
    "agent_name": "...",
    "status": "running" | "completed" | "failed",
    "trace": [                   # 完整执行 trace
        {"step": 1, "tool": "classify_inbox_file", "input": {...}, "output": {...}, "duration_ms": 234},
        ...
    ],
    "result": { ... },           # 最终输出
    "citations": [...],
    "started_at": "...",
    "completed_at": "..."
}
```

### 14.5 omodul.knowledge.agents 实现

```
omodul/knowledge/agents/
├── __init__.py
├── base.py                  # Agent 基类
├── runner.py                # 执行 Agent (含 trace 记录)
├── registry.py              # Agent 注册表
├── tracer.py                # Trace 存储 (postgres)
└── builtin/
    ├── knowledge_curator.py
    ├── reading_companion.py
    ├── daily_digest.py
    ├── translation_worker.py
    ├── audio_generator.py
    └── lint_bot.py
```

---

## P7 §15 Scheduled Jobs (新增章节)

### 15.1 概念
Scheduled Job = cron 表达式 + Agent invocation + 结果归档 + 推送。

### 15.2 Job 定义 schema

```sql
CREATE TABLE scheduled_jobs (
    id ULID PRIMARY KEY,
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    agent_name TEXT NOT NULL,              -- 调用哪个 Agent
    agent_params JSONB NOT NULL DEFAULT '{}',
    cron_expression TEXT NOT NULL,         -- "0 8 * * *"
    timezone TEXT NOT NULL DEFAULT 'Asia/Shanghai',
    enabled BOOL NOT NULL DEFAULT TRUE,
    notify_on_completion BOOL NOT NULL DEFAULT TRUE,
    notify_on_failure BOOL NOT NULL DEFAULT TRUE,
    max_runtime_seconds INT NOT NULL DEFAULT 1800,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

CREATE TABLE scheduled_job_runs (
    id ULID PRIMARY KEY,
    job_id ULID REFERENCES scheduled_jobs(id),
    agent_run_id ULID REFERENCES agent_runs(id),
    status TEXT NOT NULL,                  -- queued|running|completed|failed|timeout
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    error_message TEXT
);
```

### 15.3 内置 Job (v1.0 Phase 11+ 默认开启)

| Job name | cron | agent | 描述 |
|---|---|---|---|
| daily_inbox_process | `0 6 * * *` | knowledge_curator | 每日 6 点处理 inbox |
| daily_digest | `0 8 * * *` | daily_digest | 每日 8 点发送昨日新增摘要 |
| weekly_lint | `0 7 * * 1` | lint_bot | 每周一 7 点 lint 检查 |
| nightly_translation | `0 2 * * *` | translation_worker | 每夜 2 点批翻译未译英文 substrate (用户开启时) |

### 15.4 Scheduler 实现

```
omodul/knowledge/scheduler/
├── __init__.py
├── scheduler.py             # APScheduler 包装
├── trigger.py               # cron 解析 + 触发
├── notifier.py              # 推送结果给用户 (邮件 / 微信 / web push)
└── runner.py                # 调用 Agent + 记录 run
```

技术选型: APScheduler (Python) + Redis (锁防止多实例重复执行) + Postgres (run 历史)

### 15.5 推送通道

| 通道 | v1.0 | v2.0 |
|---|---|---|
| Web push (浏览器通知) | ✅ | ✅ |
| 邮件 | ✅ | ✅ |
| 微信小程序订阅消息 | Phase 4 后 | ✅ |
| Telegram bot | ❌ | 评估 |

### 15.6 接口

```
POST /api/v1/scheduled-jobs
GET  /api/v1/scheduled-jobs
GET  /api/v1/scheduled-jobs/{id}
PUT  /api/v1/scheduled-jobs/{id}
DELETE /api/v1/scheduled-jobs/{id}
POST /api/v1/scheduled-jobs/{id}/run-now    -- 立即触发
GET  /api/v1/scheduled-jobs/{id}/runs       -- 执行历史
```

---

## P8 §16 Views (新增章节)

### 16.1 概念
View = substrate 库的不同**检索视角**, 不是隔离 workspace。

substrate / concept / note 全局共享, View 只影响默认 filter / LLM 配置 / system prompt。

### 16.2 View schema

```sql
CREATE TABLE views (
    id ULID PRIMARY KEY,
    user_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    default_filter JSONB,         -- {"medium": ["book", "paper"], "domain": ["quant"]}
    default_llm JSONB,            -- {"provider": "anthropic", "model": "claude-opus-4-7"}
    default_system_prompt TEXT,
    icon TEXT,
    is_default BOOL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL
);
```

### 16.3 预设 View (v1.0 用户可编辑)

| View name | filter | LLM | 用途 |
|---|---|---|---|
| 通用 (default) | 无 | Qwen3-Max | 默认全局检索 |
| 中文文学 | medium=book, language=zh | Claude (擅长文学) | 文学阅读 |
| 量化金融 | medium=paper+article, domain=quant | DeepSeek (技术强) | 金融研究 |
| 技术阅读 | medium=paper, domain=tech | Claude / GPT-5 | 技术论文 |
| 工作日志 | medium=note, time=last_30d | Qwen3 | 复盘 |

### 16.4 search 接口扩展

```
POST /api/v1/search
Request:
{
    "view_id": "01H...",          -- 可选, 应用该 View 的默认 filter
    "query": "...",
    ...                            -- 其他参数覆盖 View 默认
}
```

### 16.5 接口

```
POST /api/v1/views
GET  /api/v1/views
GET  /api/v1/views/{id}
PUT  /api/v1/views/{id}
DELETE /api/v1/views/{id}
POST /api/v1/views/{id}/set-default
```

---

## P9 §17 微信集成 (原 §14, 编号右移)

### 17.x 新增: 浏览器扩展

(在原 §14 末尾追加)

#### 17.4 浏览器扩展 (Chrome / Firefox / Edge)

实施: Phase 4 (跟微信 MVP 一起)

功能:
- 一键保存当前网页 → Stratum inbox (走 ingest_substrate)
- 选中文本 → 创建 substrate fragment + note (annotation)
- Sidebar 显示当前网页相关 Stratum 内容 (hybrid_search by page URL/title)
- 引用图标点击 → 跳转 Stratum 原文

技术栈:
- Manifest V3
- 后端通过 localhost:port 跟 stratum-main 容器通信 (用户允许 + token 鉴权)

新增 omodul: `omodul.knowledge.browser_extension`
- 处理来自扩展的 ingestion 请求
- 鉴权 token 管理
- 网页 URL 去重

---

## P10 §19 实施路线修订 (原 §16)

### 修订 Phase 列表

```
Phase 1  4O 基础                       [当前在做]
  oprim 8 sub-packages
  oskill 6 sub-packages
  omodul process_inbox + start_mcp_server

Phase 1.5  低成本嫁接 [新增]
  - substrate.is_pinned 字段 (P2)
  - hybrid_search mode 参数 (P3)
  - search 接口 citation 强制 (P3)
  工程量: 1-2 周

Phase 2   网盘 + 同步 (Google Drive)   [并行 CC-A]
Phase 3   (跳过, hevi 解耦)
Phase 4   微信 MVP + 浏览器扩展        [新增浏览器扩展]
Phase 5   付费系统
Phase 6   融合检索
Phase 7-9 (已有)

Phase 10  Translation                  [并行 CC-B, ADR-018]
  - oprim.translate
  - oskill.knowledge.translate_substrate
  - derivative.translation

Phase 11  Agent + Scheduled Jobs + 外挂集成   [新增]
  - omodul.knowledge.agents (§14)
  - omodul.knowledge.scheduler (§15)
  - oprim.external.* (whisper / TTS / SD / searxng)
  - derivative: audio_narration / illustration

Phase 12  hevi + screenpipe 集成        [新增]
  - oprim.external.hevi_client
  - oprim.input.screenpipe
  - medium: screen_event

Phase 13  Views (§16)                   [新增]
  - omodul.knowledge.views
  - search 接口 view_id 支持
```

### 依赖图修订

```
Phase 1 → Phase 1.5 → Phase 2 (CC-A) + Phase 10 (CC-B) [并行]
Phase 2 + Phase 10 → Phase 4 (微信+扩展) → Phase 5 (付费)
Phase 5 → Phase 6 (融合检索)
Phase 6 → Phase 11 (Agent + 外挂)
Phase 11 → Phase 12 (hevi/screenpipe)
Phase 12 → Phase 13 (Views)
```

---

## P11 §21 未决问题修订 (原 §18)

### 新增未决问题

- **Q9**: Agent v1.0 是否允许用户自定义? 当前规范 v1.0 只预定义, 用户编辑配置但不能新增。v2.0 评估。
- **Q10**: Scheduled Jobs 推送通道优先级? 浏览器 vs 邮件 vs 微信。Phase 11 启动前实证。
- **Q11**: Views 数量上限? 当前规范无限制, 是否需要分层 (Free 3 个 / Plus 10 个 / Pro 无限)?
- **Q12**: 外挂能力健康检查统一规范? 当前 ExternalToolClient.health_check() 返回 dict 但格式未定。Phase 11 启动前确定。
- **Q13**: pinned substrate 数量上限? 太多会让 boost 失效。考虑 max 50。

---

## P12 4O 清单 v0.2 → v0.3 同步修订

### 新增 sub-packages

```
oprim 层 (Phase 10+):
+ oprim.translate                    [Phase 10, ADR-018]
+ oprim.external.mcp_client          [Phase 11]
+ oprim.external.whisper_client      [Phase 11]
+ oprim.external.tts_client          [Phase 11]
+ oprim.external.sd_client           [Phase 11]
+ oprim.external.searxng_client      [Phase 11]
+ oprim.external.hevi_client         [Phase 12]
+ oprim.input.screenpipe             [Phase 12]
+ oprim.llm.vision                   [Phase 11, multi-modal]
+ oprim.storage.gdrive               [Phase 2, ADR-009 撤销国内网盘]
+ oprim.storage.local                [Phase 2]
+ oprim.changefeed                   [Phase 2]
+ oprim.push                         [Phase 11, Scheduled Jobs 推送]

oskill 层:
+ oskill.knowledge.translate_substrate          [Phase 10]
+ oskill.knowledge.generate_audio_narration     [Phase 11]
+ oskill.knowledge.generate_illustration        [Phase 11]
+ oskill.knowledge.web_search_augmented         [Phase 11]
+ oskill.knowledge.transcribe_audio_substrate   [Phase 11]
+ oskill.sync.flush_outbox                      [Phase 2]
+ oskill.sync.apply_remote_events               [Phase 2]
+ oskill.sync.snapshot_backup                   [Phase 2]
+ oskill.sync.restore_from_snapshot             [Phase 2]

omodul 层:
+ omodul.knowledge.agents.*          [Phase 11, §14]
+ omodul.knowledge.scheduler         [Phase 11, §15]
+ omodul.knowledge.views             [Phase 13, §16]
+ omodul.knowledge.browser_extension [Phase 4, §17.4]
+ omodul.sync.bg_sync                [Phase 2]
```

### 修订现有 sub-packages

```
oskill.knowledge.hybrid_search:
  - 加 mode 参数 (strict / augmented)
  - 加 view_id 参数
  - 加 pinned_boost
  - 输出强制含 citation

oskill.knowledge.ingest_substrate:
  - 支持 is_pinned 初始值

oprim.meta_db:
  - schema 加 substrate.is_pinned / substrate.pinned_at
  - 新表: scheduled_jobs / scheduled_job_runs / agent_runs / views
```

---

## P13 应用此 patch 的步骤

按顺序:

1. **复制 v0.5 → v0.6 工作副本**
2. **应用 P1**: 全局章节编号右移 (§14-§18 → §17-§21)
3. **应用 P2-P5**: 修订 §3.2 / §10.1 / §10.2 / §11 / §13
4. **应用 P6-P8**: 插入新章节 §14 / §15 / §16 (在原 §13 后)
5. **应用 P9**: §17.4 浏览器扩展追加
6. **应用 P10**: 重写 §19 实施路线
7. **应用 P11**: §21 未决问题追加
8. **应用 P12**: 同步更新 4O 清单 v0.3

预计完整 v0.6 文档体量: 1700-1900 行 (v0.5 1214 + 500-700 新增)。

---

**End of v0.6 PATCH 文档**
