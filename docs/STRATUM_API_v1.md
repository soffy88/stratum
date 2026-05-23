# STRATUM API v1.0

> **版本**: v1.0 (Phase 1–13 + 11B)
> **受众**: Helios 前端架构组 + 任何 Stratum 客户端开发者
> **数据契约**: 严格 snake_case (ADR_STRATUM_SNAKE_CASE 双签)
> **生成日期**: 2026-05-23

---

## §1 数据模型

Stratum v1.0 使用 DuckDB 作为元数据存储 (`~/.stratum/meta.duckdb`)，LanceDB 作为向量索引 (`~/.stratum/index/lance/`)。

本节定义 13 个实体的完整 schema。每个实体包含：
- **DuckDB DDL** — 真实表结构
- **Python dataclass** — 代码中的类型定义
- **TypeScript interface** — 供 Helios 前端使用 (附录 A 完整版)
- **真实示例** — 来自 Phase 1–13 实际运行数据

**命名规则**: Python 字段名 = TypeScript 字段名 = JSON key = DuckDB 列名，1:1 snake_case。

**ID 策略**:
- substrate / derivative: ULID (26 字符, 时间有序, e.g. `01KS2MD25C3FAAAD7B9KTF9ZM9`)
- agent_runs / note / push_subscriptions / browser_ext_url_index: UUID v4
- changefeed_events / changefeed_local: BIGINT 自增序列
- scheduled_jobs / scheduled_job_runs: UUID v4


### §1.1 substrate

原始素材记录。不可变层 — 一旦 ingest 完成，substrate 行只允许更新 `is_pinned` / `pinned_at` / `updated_at`。

**DuckDB DDL**:

```sql
CREATE TABLE substrate (
    id              VARCHAR NOT NULL PRIMARY KEY,  -- ULID
    ulid            VARCHAR NOT NULL,              -- 冗余, = id
    title           VARCHAR,
    mime            VARCHAR,
    source_path     VARCHAR,
    file_hash       VARCHAR,                       -- SHA-256
    byte_size       INTEGER,
    page_count      INTEGER,
    parser          VARCHAR,
    language        VARCHAR,
    has_cjk         BOOLEAN DEFAULT FALSE,
    is_scanned      BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_json       VARCHAR DEFAULT '{}',          -- JSON: {medium, source_type, source, domain, ...}
    is_pinned       BOOLEAN DEFAULT FALSE,
    pinned_at       TIMESTAMP
);
```

**Python dataclass** (oskill/knowledge/ingest_substrate.py 产出):

```python
@dataclass
class IngestResult:
    substrate_id: str
    medium: str
    derivatives: list[str] = field(default_factory=list)
    duplicate_of: str | None = None
    elapsed_seconds: float = 0.0
    cost_usd: float = 0.0
```

**TypeScript interface**:

```typescript
interface Substrate {
  id: string;                // ULID
  ulid: string;
  title: string | null;
  mime: string | null;
  source_path: string | null;
  file_hash: string | null;
  byte_size: number | null;
  page_count: number | null;
  parser: string | null;
  language: string | null;
  has_cjk: boolean;
  is_scanned: boolean;
  created_at: string;        // ISO 8601
  updated_at: string;
  meta_json: SubstrateMeta;
  is_pinned: boolean;
  pinned_at: string | null;
}

interface SubstrateMeta {
  medium: string;            // "webpage" | "markdown_note" | "paper" | "book" | "other" | ...
  source_type: string;       // "browser_extension" | "inbox_local" | "gdrive_sync"
  source: Record<string, unknown>;
  domain?: string;
}
```

**真实示例**:

```json
{
  "id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "ulid": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "title": "attention_is_all_you_need_9bks08iy",
  "mime": "",
  "source_path": null,
  "file_hash": null,
  "byte_size": null,
  "page_count": null,
  "parser": null,
  "language": null,
  "has_cjk": false,
  "is_scanned": false,
  "created_at": "2026-05-20T18:15:16.954104",
  "updated_at": "2026-05-20T18:15:16.954104",
  "meta_json": {
    "medium": "webpage",
    "source_type": "browser_extension",
    "source": {
      "type": "browser_extension",
      "url": "https://arxiv.org/abs/1706.03762",
      "title": "Attention Is All You Need",
      "tags": ["transformer", "nlp"]
    }
  },
  "is_pinned": false,
  "pinned_at": null
}
```

---

### §1.2 fragment

> ⚠️ **v1.0 无独立 fragment 表**。Fragment 是 chunk-level 的逻辑概念，通过 `{substrate_id}#{chunk_idx}` 字符串锚点表示。

**v1.0 实现方式**:
- 向量索引 ID 格式: `01KS2MD25C3FAAAD7B9KTF9ZM9#0` (ULID + `#` + chunk 序号)
- citation 中的 `fragment_id` 字段使用此格式
- `anchor` 对象: `{"section": null, "char_start": 0, "char_end": 0}` — v1.0 仅 chunk-level，char_start/char_end 始终为 0

**TypeScript interface**:

```typescript
/** 逻辑概念, 非独立表. 用于 citation 引用. */
interface FragmentRef {
  fragment_id: string;       // "{substrate_id}#{chunk_idx}"
  anchor: {
    section: string | null;
    char_start: number;      // v1.0 始终 0
    char_end: number;        // v1.0 始终 0
  };
}
```

**v1.0 限制**: 无 char-level 定位，仅 chunk-level。v2.0 评估独立 fragment 表 + char-level anchor。


### §1.3 derivative

substrate 的派生产物。一个 substrate 可有多个 derivative (markdown 解析、plaintext 提取、翻译等)。

**DuckDB DDL**:

```sql
CREATE TABLE derivative (
    id              VARCHAR NOT NULL PRIMARY KEY,  -- ULID
    substrate_id    VARCHAR NOT NULL,              -- FK → substrate.id
    kind            VARCHAR NOT NULL,              -- "markdown" | "plaintext" | "translation_zh-CN" | ...
    seq             INTEGER DEFAULT 0,             -- 同 kind 多版本时的序号
    content         VARCHAR,                       -- 派生内容全文
    embedding_id    VARCHAR,                       -- 关联向量 ID (v1.0 未使用此列, 向量在 LanceDB)
    embedding_dim   INTEGER,
    meta_json       VARCHAR DEFAULT '{}',          -- JSON: kind-specific metadata
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Python dataclass** (oskill/knowledge/translate_substrate.py):

```python
@dataclass
class TranslateResult:
    derivative_id: str
    substrate_id: str
    target_lang: str
    provider: str          # "deepseek" | "claude" | "qwen3"
    chunks_translated: int
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    cost_usd: float = 0.0
    embedding_ids: list[str] = field(default_factory=list)
```

**TypeScript interface**:

```typescript
interface Derivative {
  id: string;              // ULID
  substrate_id: string;
  kind: DerivativeKind;
  seq: number;
  content: string | null;
  embedding_id: string | null;
  embedding_dim: number | null;
  meta_json: Record<string, unknown>;
  created_at: string;
}

type DerivativeKind = "markdown" | "plaintext" | `translation_${string}`;
```

**真实示例**:

```json
{
  "id": "01KS2MQHTQN7D0G6H3A8ZYWQHA",
  "substrate_id": "01KRX5S8ZM3EF5F89YASCDHSEW",
  "kind": "translation_zh-CN",
  "seq": 0,
  "content": null,
  "embedding_id": null,
  "embedding_dim": null,
  "meta_json": {
    "source_lang": "auto",
    "target_lang": "zh-CN",
    "provider": "deepseek",
    "chunks": 1,
    "cost_usd": 0.0
  },
  "created_at": "2026-05-20T12:05:11"
}
```

---

### §1.4 note

用户笔记，可关联 substrate。支持 wikilink 引用。

**DuckDB DDL**:

```sql
CREATE TABLE note (
    id              VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    title           VARCHAR,
    content         VARCHAR,
    wikilinks       VARCHAR DEFAULT '[]',          -- JSON array of wikilink strings
    substrate_id    VARCHAR,                       -- FK → substrate.id (可选)
    meta_json       VARCHAR DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**TypeScript interface**:

```typescript
interface Note {
  id: string;              // UUID v4
  title: string | null;
  content: string | null;
  wikilinks: string[];     // e.g. ["[[Attention Is All You Need]]"]
  substrate_id: string | null;
  meta_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
```

**真实示例**:

```json
{
  "id": "3bc57993-049a-49a6-bca7-1fa661f65648",
  "title": "Selected Passage Test",
  "content": "Key result: BLEU score benchmark",
  "wikilinks": [],
  "substrate_id": "01KS2E3Y6D4Z3XPGX8RJHYK138",
  "meta_json": {},
  "created_at": "2026-05-20T18:15:23",
  "updated_at": "2026-05-20T18:15:23"
}
```

---

### §1.5 concept

概念图谱节点。v1.0 schema 就绪，弱关联 (通过 `source_ids` JSON 数组引用 substrate)。

**DuckDB DDL**:

```sql
CREATE TABLE concept (
    id              VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    name            VARCHAR NOT NULL,
    aliases         VARCHAR,                       -- JSON array or comma-separated
    description     VARCHAR,
    wikilink        VARCHAR,                       -- canonical wikilink form
    source_ids      VARCHAR DEFAULT '[]',          -- JSON array of substrate_id
    meta_json       VARCHAR DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**TypeScript interface**:

```typescript
interface Concept {
  id: string;
  name: string;
  aliases: string | null;
  description: string | null;
  wikilink: string | null;
  source_ids: string[];      // substrate_id[]
  meta_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
```

**v1.0 状态**: schema 就绪，暂无生产数据 (0 行)。concept 提取流水线在 Phase 14+ 实施。


### §1.6 view

搜索视图 (Phase 13)。每个 view 定义一组默认过滤条件 + LLM 配置，用户可切换 default view 改变 hybrid_search 行为。

**DuckDB DDL**:

```sql
CREATE TABLE views (
    id                      VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    user_id                 VARCHAR NOT NULL,
    name                    VARCHAR NOT NULL,
    description             VARCHAR,
    default_filter          VARCHAR,          -- JSON: {medium: [...], domain: [...], time_range: "..."}
    default_llm             VARCHAR,          -- JSON: {provider: "...", model: "...", temperature: 0.2}
    default_system_prompt   VARCHAR,
    icon                    VARCHAR,
    is_default              BOOLEAN DEFAULT FALSE,
    is_builtin              BOOLEAN DEFAULT FALSE,
    created_at              TIMESTAMP NOT NULL,
    updated_at              TIMESTAMP NOT NULL
);
```

**TypeScript interface**:

```typescript
interface View {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  default_filter: ViewFilter;
  default_llm: ViewLLM;
  default_system_prompt: string | null;
  icon: string | null;
  is_default: boolean;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

interface ViewFilter {
  medium?: string[];       // e.g. ["paper", "book"]
  domain?: string[];       // e.g. ["quant", "finance"]
  time_range?: string;     // "last_7d" | "last_30d" | "last_90d"
}

interface ViewLLM {
  provider?: string;       // "qwen3_dashscope" | "claude" | "deepseek"
  model?: string;
  temperature?: number;
}
```

**v1.0 状态**: schema 就绪，暂无生产数据 (0 行)。5 个预置 view yaml 定义在 `omodul/knowledge/views/presets/`，通过 `preset_loader` 安装。

---

### §1.7 agent_run

Agent 执行记录。每次 agent 调用产生一行，含完整 trace (工具调用链) 和 citations。

**DuckDB DDL**:

```sql
CREATE TABLE agent_runs (
    id                  VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    user_id             VARCHAR NOT NULL,
    agent_name          VARCHAR NOT NULL,              -- "knowledge_curator" | "translation_worker" | ...
    params              VARCHAR NOT NULL,              -- JSON: agent 入参
    status              VARCHAR NOT NULL,              -- "running" | "completed" | "failed" | "timeout"
    trace               VARCHAR,                       -- JSON: AgentStep[]
    citations           VARCHAR,                       -- JSON: Citation[]
    output              VARCHAR,                       -- JSON: agent 输出
    total_input_tokens  INTEGER DEFAULT 0,
    total_output_tokens INTEGER DEFAULT 0,
    cost_usd            FLOAT DEFAULT 0.0,
    started_at          TIMESTAMP NOT NULL,
    completed_at        TIMESTAMP,
    error_message       VARCHAR
);
```

**Python dataclass** (omodul/knowledge/agents/base.py):

```python
@dataclass
class AgentResult:
    success: bool
    output: dict
    trace: list[AgentStep]
    citations: list[Citation]
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    elapsed_seconds: float = 0.0
    cost_usd: float = 0.0
    error: str | None = None

@dataclass
class AgentStep:
    step_num: int
    tool_name: str
    tool_input: dict = field(default_factory=dict)
    tool_output: dict | None = None
    duration_ms: int = 0
    error: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class Citation:
    substrate_id: str
    title: str = ""
    fragment_id: str | None = None
    anchor: dict | None = None
    deep_link: str | None = None
```

**TypeScript interface**:

```typescript
interface AgentRun {
  id: string;
  user_id: string;
  agent_name: AgentName;
  params: Record<string, unknown>;
  status: "running" | "completed" | "failed" | "timeout";
  trace: AgentStep[];
  citations: Citation[];
  output: Record<string, unknown> | null;
  total_input_tokens: number;
  total_output_tokens: number;
  cost_usd: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

type AgentName = "knowledge_curator" | "translation_worker" | "daily_digest"
  | "reading_companion" | "lint_bot" | "audio_generator";

interface AgentStep {
  step_num: number;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_output: Record<string, unknown> | null;
  duration_ms: number;
  error: string | null;
  timestamp: string;
}

interface Citation {
  substrate_id: string;
  title: string;
  fragment_id: string | null;
  anchor: { section: string | null; char_start: number; char_end: number } | null;
  deep_link: string | null;
}
```

**真实示例**:

```json
{
  "id": "748c306e-8ac0-4c30-98c5-6a4b962ee54f",
  "user_id": "demo_user",
  "agent_name": "knowledge_curator",
  "params": "{}",
  "status": "completed",
  "trace": [
    {
      "step_num": 1,
      "tool_name": "ingest_substrate",
      "tool_input": {"file": "/home/soffy/.stratum/inbox/test_rag_paper.md"},
      "tool_output": {"substrate_id": "01KS2MD25C3FAAAD7B9KTF9ZM9", "medium": "other"},
      "duration_ms": 311,
      "error": null,
      "timestamp": "2026-05-20T12:05:11.146744"
    }
  ],
  "citations": [],
  "output": {"files_found": 1, "ingested": 1, "skipped": 0, "failed": 0},
  "total_input_tokens": 0,
  "total_output_tokens": 0,
  "cost_usd": 0.0,
  "started_at": "2026-05-20T12:05:10.750309",
  "completed_at": "2026-05-20T12:05:11.146788",
  "error_message": null
}
```


### §1.8 scheduled_job

定时任务定义。每个 job 绑定一个 agent，按 cron 表达式触发。

**DuckDB DDL**:

```sql
CREATE TABLE scheduled_jobs (
    id                      VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    user_id                 VARCHAR NOT NULL,
    name                    VARCHAR NOT NULL,              -- unique per user
    agent_name              VARCHAR NOT NULL,
    agent_params            VARCHAR NOT NULL DEFAULT '{}', -- JSON
    cron_expression         VARCHAR NOT NULL,              -- 5-field cron
    timezone                VARCHAR NOT NULL DEFAULT 'Asia/Shanghai',
    enabled                 BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_completion    BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_failure       BOOLEAN NOT NULL DEFAULT TRUE,
    max_runtime_seconds     INTEGER NOT NULL DEFAULT 1800,
    created_at              TIMESTAMP NOT NULL,
    updated_at              TIMESTAMP NOT NULL
);
```

**TypeScript interface**:

```typescript
interface ScheduledJob {
  id: string;
  user_id: string;
  name: string;
  agent_name: AgentName;
  agent_params: Record<string, unknown>;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  notify_on_completion: boolean;
  notify_on_failure: boolean;
  max_runtime_seconds: number;
  created_at: string;
  updated_at: string;
}
```

**5 个 builtin jobs** (通过 `install_builtin_jobs` 安装):

| name | agent_name | cron | default enabled |
|------|-----------|------|-----------------|
| daily_inbox_process | knowledge_curator | `0 6 * * *` | true |
| daily_digest | daily_digest | `0 8 * * *` | true |
| weekly_lint | lint_bot | `0 7 * * 1` | true |
| nightly_translation | translation_worker | `0 2 * * *` | false |
| nightly_audio_gen | audio_generator | `0 3 * * *` | false (TTS v1.0 unavailable) |

**v1.0 状态**: schema 就绪，暂无生产数据 (0 行)。builtin jobs 在首次 `install_builtin_jobs(user_id)` 调用时写入。

**注意**: `next_run_at` / `last_run_at` 字段不存在于表中。前端需用 cron-parser 库自行计算下次执行时间。

---

### §1.9 scheduled_job_run

定时任务执行记录。每次 cron 触发产生一行，关联到 agent_runs。

**DuckDB DDL**:

```sql
CREATE TABLE scheduled_job_runs (
    id              VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    job_id          VARCHAR NOT NULL,              -- FK → scheduled_jobs.id
    agent_run_id    VARCHAR,                       -- FK → agent_runs.id (成功时填入)
    status          VARCHAR NOT NULL,              -- "running" | "completed" | "failed" | "timeout"
    started_at      TIMESTAMP NOT NULL,
    completed_at    TIMESTAMP,
    error_message   VARCHAR
);
```

**TypeScript interface**:

```typescript
interface ScheduledJobRun {
  id: string;
  job_id: string;
  agent_run_id: string | null;
  status: "running" | "completed" | "failed" | "timeout";
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}
```

**v1.0 状态**: schema 就绪，暂无生产数据 (0 行)。


### §1.10 push_subscriptions

用户推送订阅。每个用户可注册多个 channel (web VAPID / email / wechat placeholder / system)。

**DuckDB DDL**:

```sql
CREATE TABLE push_subscriptions (
    id              VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    user_id         VARCHAR NOT NULL,
    channel         VARCHAR NOT NULL,              -- "web" | "email" | "wechat" | "system"
    recipient       VARCHAR NOT NULL,              -- channel-specific: JSON subscription (web) / email addr / openid
    keys_json       VARCHAR DEFAULT '{}',          -- channel-specific keys (e.g. VAPID p256dh/auth)
    enabled         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**TypeScript interface**:

```typescript
interface PushSubscription {
  id: string;
  user_id: string;
  channel: "web" | "email" | "wechat" | "system";
  recipient: string;
  keys_json: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
}
```

**v1.0 状态**: schema 就绪，暂无生产数据 (0 行)。Push 模块代码在 `feat/phase-10-translation` 分支，v1.0 完工前合并 main。

---

### §1.11 changefeed_events

远端同步事件 (Phase 2 GDrive sync)。per-user 序列号，append-only。

**DuckDB DDL**:

```sql
CREATE TABLE changefeed_events (
    id              BIGINT NOT NULL PRIMARY KEY DEFAULT nextval('changefeed_event_id_seq'),
    device_id       VARCHAR NOT NULL,
    user_id         VARCHAR NOT NULL,
    event_type      VARCHAR NOT NULL,              -- "substrate_created" | "derivative_created" | ...
    aggregate_id    VARCHAR,                       -- 关联实体 ID
    payload         VARCHAR NOT NULL,              -- JSON event body
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    seq             BIGINT NOT NULL                -- per-user monotonic sequence
);
```

**TypeScript interface**:

```typescript
interface ChangefeedEvent {
  id: number;              // BIGINT auto-increment
  device_id: string;
  user_id: string;
  event_type: string;
  aggregate_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  seq: number;
}
```

**v1.0 状态**: schema 就绪，暂无生产数据 (0 行)。Phase 2 GDrive sync 9 项集成测试通过但未产生远端事件。

---

### §1.12 changefeed_local

本地变更日志。每次 substrate/derivative 写入时 append 一条，用于增量同步。

**DuckDB DDL**:

```sql
CREATE TABLE changefeed_local (
    seq             BIGINT NOT NULL PRIMARY KEY,   -- nextval('changefeed_seq')
    table_name      VARCHAR NOT NULL,              -- "substrate" | "derivative" | ...
    row_id          VARCHAR NOT NULL,              -- 变更行的 ID
    op              VARCHAR NOT NULL,              -- "insert" | "update" | "delete"
    payload         VARCHAR,                       -- JSON: 变更摘要
    ts              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**TypeScript interface**:

```typescript
interface ChangefeedLocal {
  seq: number;
  table_name: string;
  row_id: string;
  op: "insert" | "update" | "delete";
  payload: Record<string, unknown> | null;
  ts: string;
}
```

**真实示例**:

```json
{
  "seq": 1,
  "table_name": "substrate",
  "row_id": "01KRX5S8ZM3EF5F89YASCDHSEW",
  "op": "insert",
  "payload": {"substrate_id": "01KRX5S8ZM3EF5F89YASCDHSEW"},
  "ts": "2026-05-18T17:13:30.563263"
}
```

---

### §1.13 browser_ext_url_index

浏览器扩展 URL 去重索引。每次通过扩展 ingest 网页时写入，用于快速判断 URL 是否已保存。

**DuckDB DDL**:

```sql
CREATE TABLE browser_ext_url_index (
    id              VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    url             VARCHAR NOT NULL,              -- 原始 URL
    normalized_url  VARCHAR NOT NULL,              -- normalize_url() 处理后
    substrate_id    VARCHAR NOT NULL,              -- FK → substrate.id
    ingested_at     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**TypeScript interface**:

```typescript
interface BrowserExtUrlIndex {
  id: string;
  url: string;
  normalized_url: string;
  substrate_id: string;
  ingested_at: string;
}
```

**真实示例**:

```json
{
  "id": "415ba8d8-ae4a-4f9a-b8ae-4f5587c20aa0",
  "url": "https://arxiv.org/abs/1706.03762",
  "normalized_url": "https://arxiv.org/abs/1706.03762",
  "substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "ingested_at": "2026-05-20T18:15:17.006967"
}
```

---

### §1.14 changefeed_snapshots

同步快照记录 (Phase 2)。记录每次 snapshot_backup 的元数据。

**DuckDB DDL**:

```sql
CREATE TABLE changefeed_snapshots (
    id              VARCHAR NOT NULL PRIMARY KEY,  -- UUID v4
    user_id         VARCHAR NOT NULL,
    device_id       VARCHAR NOT NULL,
    seq_at          BIGINT NOT NULL,               -- snapshot 时的 changefeed_local.seq
    file_id         VARCHAR,                       -- 远端存储 file ID (GDrive)
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**TypeScript interface**:

```typescript
interface ChangefeedSnapshot {
  id: string;
  user_id: string;
  device_id: string;
  seq_at: number;
  file_id: string | null;
  created_at: string;
}
```

**v1.0 状态**: schema 就绪，暂无生产数据 (0 行)。


---

## §2 MCP Server

Stratum 通过 MCP (Model Context Protocol) 暴露 8 个 tool，供 Claude Desktop / Hermes / 任何 MCP 客户端调用。

### §2.1 启动方式

**服务端入口**: `omodul/knowledge/start_mcp_server.py`

```python
from omodul.knowledge.start_mcp_server import start_mcp_server
start_mcp_server(host="0.0.0.0", port=8765)
```

**Claude Desktop 配置** (`~/.config/claude/mcp.json`):

```json
{
  "mcpServers": {
    "stratum": {
      "command": "python",
      "args": ["-m", "omodul.knowledge.start_mcp_server"],
      "env": {
        "STRATUM_USER_ID": "wiki"
      }
    }
  }
}
```

**Hermes 配置** (`~/.config/hermes/mcp.json`):

```json
{
  "stratum": {
    "command": "python",
    "args": ["-m", "omodul.knowledge.start_mcp_server"],
    "env": {
      "STRATUM_USER_ID": "wiki"
    }
  }
}
```

**Server metadata**:
- Name: `stratum`
- Version: `0.1.6`
- Protocol: MCP (FastMCP)
- Tools: 8
- Auth: 默认无鉴权，通过 `STRATUM_USER_ID` 环境变量标识用户


### §2.2 Tool 定义

---

#### Tool 1: `stratum.search`

Hybrid BM25 + dense vector 搜索，RRF 融合排序。

**Input JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "query": {"type": "string", "description": "搜索查询文本"},
    "top_k": {"type": "integer", "default": 20, "description": "返回结果数上限"},
    "medium_filter": {
      "type": "array", "items": {"type": "string"},
      "description": "按 medium 过滤, e.g. [\"paper\", \"webpage\"]"
    }
  },
  "required": ["query"]
}
```

**Output JSON Schema**:

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "id": {"type": "string"},
      "type": {"type": "string", "enum": ["substrate", "llm_augmented"]},
      "title": {"type": "string"},
      "score": {"type": "number"},
      "highlight": {"type": "string", "nullable": true},
      "metadata": {
        "type": "object",
        "properties": {
          "medium": {"type": "string", "nullable": true},
          "source_type": {"type": "string", "nullable": true},
          "domain": {"type": "string", "nullable": true},
          "created_at": {"type": "string", "nullable": true}
        }
      }
    }
  }
}
```

**真实调用示例**:

```json
// Input
{"query": "attention mechanism transformer", "top_k": 5}

// Output
[
  {
    "id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
    "type": "substrate",
    "title": "attention_is_all_you_need_9bks08iy",
    "score": 0.032786885245901636,
    "highlight": null,
    "metadata": {
      "medium": "webpage",
      "source_type": "browser_extension",
      "domain": null,
      "created_at": "2026-05-20 18:15:16.954104"
    }
  }
]
```

---

#### Tool 2: `stratum.fetch_substrate`

按 ID 获取单个 substrate 记录。

**Input JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "substrate_id": {"type": "string", "description": "substrate ULID"}
  },
  "required": ["substrate_id"]
}
```

**Output JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "id": {"type": "string"},
    "ulid": {"type": "string"},
    "title": {"type": "string", "nullable": true},
    "mime": {"type": "string", "nullable": true},
    "source_path": {"type": "string", "nullable": true},
    "file_hash": {"type": "string", "nullable": true},
    "byte_size": {"type": "integer", "nullable": true},
    "medium": {"type": "string", "nullable": true},
    "created_at": {"type": "string"}
  }
}
```

**真实调用示例**:

```json
// Input
{"substrate_id": "01KS2MD25C3FAAAD7B9KTF9ZM9"}

// Output
{
  "id": "01KS2MD25C3FAAAD7B9KTF9ZM9",
  "ulid": "01KS2MD25C3FAAAD7B9KTF9ZM9",
  "title": "test_rag_paper",
  "mime": "",
  "source_path": null,
  "file_hash": null,
  "byte_size": null,
  "medium": "other",
  "created_at": "2026-05-20 12:05:11.146788"
}
```

**错误响应** (substrate 不存在):

```json
{"error": "substrate '01NONEXISTENT' not found"}
```

---

#### Tool 3: `stratum.list_notes`

列出最近的笔记 (按 created_at DESC)。

**Input JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "limit": {"type": "integer", "default": 20, "description": "返回数量上限"}
  }
}
```

**Output JSON Schema**:

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "id": {"type": "string"},
      "title": {"type": "string", "nullable": true},
      "content_preview": {"type": "string", "description": "前 200 字符"},
      "wikilinks": {"type": "string"},
      "substrate_id": {"type": "string", "nullable": true},
      "created_at": {"type": "string"}
    }
  }
}
```

**真实调用示例**:

```json
// Input
{"limit": 5}

// Output
[
  {
    "id": "3bc57993-049a-49a6-bca7-1fa661f65648",
    "title": "Selected Passage Test",
    "content_preview": "Key result: BLEU score benchmark",
    "wikilinks": "[]",
    "substrate_id": "01KS2E3Y6D4Z3XPGX8RJHYK138",
    "created_at": "2026-05-20 18:15:23.685501"
  }
]
```

---

#### Tool 4: `stratum.recent_changes`

列出最近的本地变更事件 (changefeed_local, 按 seq DESC)。

**Input JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "limit": {"type": "integer", "default": 20, "description": "返回数量上限"}
  }
}
```

**Output JSON Schema**:

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "seq": {"type": "integer"},
      "table_name": {"type": "string"},
      "row_id": {"type": "string"},
      "op": {"type": "string", "enum": ["insert", "update", "delete"]},
      "payload": {"type": "string", "nullable": true},
      "ts": {"type": "string"}
    }
  }
}
```

**真实调用示例**:

```json
// Input
{"limit": 3}

// Output
[
  {"seq": 6, "table_name": "derivative", "row_id": "01KS2MQHTQN7D0G6H3A8ZYWQHA", "op": "insert", "payload": "{\"substrate_id\": \"01KRX5S8ZM3EF5F89YASCDHSEW\", \"kind\": \"translation_zh-CN\"}", "ts": "2026-05-20 18:15:30.123456"},
  {"seq": 5, "table_name": "substrate", "row_id": "01KS2MD25C3FAAAD7B9KTF9ZM9", "op": "insert", "payload": "{\"substrate_id\": \"01KS2MD25C3FAAAD7B9KTF9ZM9\"}", "ts": "2026-05-20 12:05:11.146788"},
  {"seq": 4, "table_name": "substrate", "row_id": "01KS2E3Y6D4Z3XPGX8RJHYK138", "op": "insert", "payload": "{\"substrate_id\": \"01KS2E3Y6D4Z3XPGX8RJHYK138\"}", "ts": "2026-05-20 18:15:23.685501"}
]
```


---

#### Tool 5: `stratum.pin_substrate`

Pin 一个 substrate，使其在搜索中获得 boost (默认 1.5x)。

**Input JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "substrate_id": {"type": "string", "description": "要 pin 的 substrate ULID"}
  },
  "required": ["substrate_id"]
}
```

**Output JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "substrate_id": {"type": "string"},
    "is_pinned": {"type": "boolean"},
    "updated_at": {"type": "string"}
  }
}
```

**真实调用示例**:

```json
// Input
{"substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9"}

// Output
{
  "substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "is_pinned": true,
  "updated_at": "2026-05-23T01:30:00.000000"
}
```

**错误响应**:

```json
{"error": "substrate '01NONEXISTENT' not found"}
```

---

#### Tool 6: `stratum.unpin_substrate`

Unpin 一个 substrate，恢复正常搜索权重。

**Input JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "substrate_id": {"type": "string", "description": "要 unpin 的 substrate ULID"}
  },
  "required": ["substrate_id"]
}
```

**Output JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "substrate_id": {"type": "string"},
    "is_pinned": {"type": "boolean"},
    "updated_at": {"type": "string"}
  }
}
```

**真实调用示例**:

```json
// Input
{"substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9"}

// Output
{
  "substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "is_pinned": false,
  "updated_at": "2026-05-23T01:31:00.000000"
}
```

---

#### Tool 7: `stratum.list_views`

列出用户的所有 view。

**Input JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "user_id": {"type": "string", "description": "用户 ID"}
  },
  "required": ["user_id"]
}
```

**Output JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "views": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "string"},
          "user_id": {"type": "string"},
          "name": {"type": "string"},
          "description": {"type": "string", "nullable": true},
          "default_filter": {"type": "object"},
          "default_llm": {"type": "object"},
          "default_system_prompt": {"type": "string", "nullable": true},
          "icon": {"type": "string", "nullable": true},
          "is_default": {"type": "boolean"},
          "is_builtin": {"type": "boolean"},
          "created_at": {"type": "string"},
          "updated_at": {"type": "string"}
        }
      }
    }
  }
}
```

**调用示例** (views 表为空时):

```json
// Input
{"user_id": "wiki"}

// Output
{"views": []}
```

**v1.0 说明**: 5 个预置 view 通过 `preset_loader.install_presets(user_id)` 安装后才会出现。

---

#### Tool 8: `stratum.set_default_view`

设置用户的默认 view (单一默认约束: 同一用户只有一个 is_default=true)。

**Input JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "user_id": {"type": "string", "description": "用户 ID"},
    "view_id": {"type": "string", "description": "要设为默认的 view ID"}
  },
  "required": ["user_id", "view_id"]
}
```

**Output JSON Schema**:

```json
{
  "type": "object",
  "properties": {
    "success": {"type": "boolean"},
    "view_id": {"type": "string"},
    "name": {"type": "string"}
  }
}
```

**调用示例**:

```json
// Input
{"user_id": "wiki", "view_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"}

// Output
{"success": true, "view_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890", "name": "Research"}
```

**错误响应**:

```json
{"error": "view 'nonexistent-id' not found"}
```


---

### §2.3 错误处理与鉴权

#### 错误响应格式

所有 MCP tool 在出错时返回包含 `error` 字段的 JSON 对象 (非 MCP protocol error):

```json
{"error": "<human-readable error message>"}
```

常见错误:

| 场景 | error 内容 |
|------|-----------|
| meta_db 文件不存在 | `"meta_db not found"` |
| substrate 不存在 | `"substrate '{id}' not found"` |
| view 不存在 | `"view '{id}' not found"` |
| DuckDB 查询异常 | `"<exception message>"` |

#### 鉴权

**v1.0 默认无鉴权**。MCP server 运行在本地 (localhost)，通过环境变量标识用户:

```bash
export STRATUM_USER_ID=wiki
```

- `STRATUM_USER_ID` 用于 `list_views` / `set_default_view` 等需要 user_id 的 tool
- 不传时 tool 仍可调用，但 view 相关操作需要显式传入 `user_id` 参数
- v1.1+ 评估 token-based auth (与浏览器扩展 `X-Stratum-Token` 统一)

#### Tool 汇总表

| # | tool name | 读/写 | Phase | 说明 |
|---|-----------|-------|-------|------|
| 1 | stratum.search | 读 | 1 | Hybrid BM25+vector 搜索 |
| 2 | stratum.fetch_substrate | 读 | 1 | 按 ID 获取 substrate |
| 3 | stratum.list_notes | 读 | 1 | 列出笔记 |
| 4 | stratum.recent_changes | 读 | 1 | 列出变更事件 |
| 5 | stratum.pin_substrate | 写 | 1.5 | Pin substrate |
| 6 | stratum.unpin_substrate | 写 | 1.5 | Unpin substrate |
| 7 | stratum.list_views | 读 | 13 | 列出用户 views |
| 8 | stratum.set_default_view | 写 | 13 | 设置默认 view |


---

## §3 HTTP REST API (浏览器扩展)

Stratum 通过 FastAPI 提供 HTTP REST API，专供浏览器扩展 (Chrome/Firefox/Edge) 调用。

### §3.1 服务启动

**入口**: `omodul/knowledge/browser_extension/server.py`

```bash
# 直接启动
python -m omodul.knowledge.browser_extension --host 127.0.0.1 --port 14567

# 或通过 uvicorn
uvicorn omodul.knowledge.browser_extension.server:app --host 127.0.0.1 --port 14567
```

**默认配置**:
- Host: `127.0.0.1` (仅本地)
- Port: `14567`
- Workers: 1 (单进程，DuckDB 不支持多写)

---

### §3.2 端点定义

---

#### POST `/api/v1/browser-extension/ingest`

一键保存网页 / 选中文本到 Stratum。

**Request**:

| Header | 值 | 必填 |
|--------|---|------|
| Content-Type | application/json | ✓ |
| X-Stratum-Token | `<token>` | ✓ |

```json
{
  "url": "https://arxiv.org/abs/1706.03762",
  "title": "Attention Is All You Need",
  "html": "<html>...</html>",
  "selection_text": null,
  "tags": ["transformer", "nlp"],
  "create_note": false,
  "note_content": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✓ | 页面 URL |
| title | string | ✓ | 页面标题 |
| html | string \| null | △ | 页面 HTML (与 selection_text 二选一) |
| selection_text | string \| null | △ | 选中文本 (优先于 html) |
| tags | string[] | — | 用户标签 |
| create_note | boolean | — | 是否同时创建笔记 |
| note_content | string \| null | — | 笔记内容 (create_note=true 时) |

**Response** (200):

```json
{
  "substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "note_id": null,
  "deduplicated": false,
  "message": "Saved to Stratum"
}
```

**Response** (200, URL 已存在 — 去重):

```json
{
  "substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "note_id": null,
  "deduplicated": true,
  "message": "Already saved (substrate 01KS2E3QK3KVN1WBVYSEEFAYT9)"
}
```

**错误码**:

| HTTP | 场景 |
|------|------|
| 400 | html 和 selection_text 都为空 |
| 401 | X-Stratum-Token 无效 |
| 500 | ingest 流水线内部错误 |

---

#### POST `/api/v1/browser-extension/sidebar-search`

侧边栏搜索 — 根据当前页面上下文搜索 Stratum 知识库。

**Request**:

| Header | 值 | 必填 |
|--------|---|------|
| Content-Type | application/json | ✓ |
| X-Stratum-Token | `<token>` | ✓ |

```json
{
  "url": "https://arxiv.org/abs/1706.03762",
  "page_title": "Attention Is All You Need",
  "selected_text": "multi-head attention"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| url | string | ✓ | 当前页面 URL |
| page_title | string | ✓ | 页面标题 (作为搜索 query 基础) |
| selected_text | string \| null | — | 选中文本 (追加到 query) |

**Response** (200):

```json
{
  "results": [
    {
      "id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
      "type": "substrate",
      "title": "attention_is_all_you_need_9bks08iy",
      "score": 0.032786885245901636,
      "highlight": null
    }
  ]
}
```

**搜索逻辑**: `query = page_title + " " + selected_text`，调用 `hybrid_search(query, top_k=10, mode="strict")`。

**错误码**:

| HTTP | 场景 |
|------|------|
| 401 | X-Stratum-Token 无效 |
| 500 | 搜索内部错误 |

---

#### GET `/api/v1/browser-extension/health`

健康检查，无需鉴权。

**Response** (200):

```json
{"status": "ok", "version": "0.1.0"}
```


---

### §3.3 CORS 与 Token 鉴权

#### CORS 配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "chrome-extension://*",
        "moz-extension://*",
        "ms-browser-extension://*",
    ],
    allow_origin_regex=r"(chrome-extension|moz-extension|ms-browser-extension)://.*",
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-Stratum-Token", "Content-Type"],
)
```

- 仅允许浏览器扩展 origin (chrome-extension / moz-extension / ms-browser-extension)
- 不允许 `http://localhost` 等 web origin (v1.1+ Web API 使用独立端口)
- OPTIONS preflight 自动处理

#### Token 鉴权

所有 POST 端点要求 `X-Stratum-Token` header。

**Token 生成**: 用户在首次配置扩展时生成，存储在 `~/.stratum/config.yaml`:

```yaml
browser_extension:
  token: "stratum_ext_<random_32_hex>"
```

**验证逻辑** (`auth.py`):
1. 从 header 提取 token
2. 与 config.yaml 中的 token 比对
3. 不匹配 → 401 `{"detail": "Invalid or missing token"}`

**GET /health 无需 token** — 用于扩展连接检测。

---

### §3.4 v1.1+ Web API 预留

v1.0 仅提供浏览器扩展 API (port 14567)。v1.1+ 计划:

| 版本 | 端口 | namespace | 说明 |
|------|------|-----------|------|
| v1.0 | 14567 | `/api/v1/browser-extension/*` | 浏览器扩展专用 |
| v1.1+ | 14568 | `/api/v1/web/*` | Helios Web 前端 API |

v1.1 Web API 预期端点 (v1.0 未实施):
- `GET /api/v1/web/substrates` — list_substrates (分页)
- `GET /api/v1/web/substrates/:id` — fetch_substrate
- `POST /api/v1/web/search` — hybrid_search (完整参数)
- `GET /api/v1/web/views` — list_views
- `POST /api/v1/web/views/:id/set-default` — set_default_view
- `GET /api/v1/web/agent-runs` — list_agent_runs (分页)


---

## §4 Agent 系统

### §4.1 调用契约

Agent 通过 `AgentRunner.run()` 执行，完整生命周期:

```
AgentRunner.run(agent, user_id, params)
  → tracer.create_run(run_id, status="running")
  → asyncio.wait_for(agent.run(params, context), timeout=agent.timeout_seconds)
  → tracer.complete_run(run_id, result)  // or fail_run on exception/timeout
  → return AgentResult
```

**Python 签名**:

```python
class AgentRunner:
    def __init__(self, tracer: AgentTracer) -> None: ...

    async def run(self, agent: Agent, user_id: str, params: dict) -> AgentResult:
        """Execute agent with timeout, persist trace to agent_runs table."""
```

**调用方式** (应用层):

```python
from omodul.knowledge.agents.registry import get_registry
from omodul.knowledge.agents.runner import AgentRunner
from omodul.knowledge.agents.tracer import AgentTracer

registry = get_registry()
agent_cls = registry.get("knowledge_curator")
agent = agent_cls()
runner = AgentRunner(tracer=AgentTracer())
result = await runner.run(agent, user_id="wiki", params={"inbox_dir": "~/.stratum/inbox"})
```

**超时处理**: `asyncio.wait_for` 超时 → status="timeout", error_message 记录。

---

### §4.2 Builtin Agents

v1.0 提供 5 个 builtin agent (+1 disabled):

---

#### 4.2.1 knowledge_curator

**用途**: 处理 inbox 文件 — ingest (classify + dedup + embed + index)。

| 属性 | 值 |
|------|---|
| name | `knowledge_curator` |
| allowed_tools | `oskill.knowledge.ingest_substrate` |
| timeout_seconds | 1800 |

**params schema**:

```json
{"inbox_dir": "~/.stratum/inbox"}
```

**output schema**:

```json
{"files_found": 1, "ingested": 1, "skipped": 0, "failed": 0}
```

**真实示例**: 见 §1.7 agent_run 示例 (id `748c306e`)。

---

#### 4.2.2 daily_digest

**用途**: 汇总过去 24h 新增 substrate，生成摘要并推送。

| 属性 | 值 |
|------|---|
| name | `daily_digest` |
| allowed_tools | `oskill.knowledge.hybrid_search`, `oprim.llm.llm_call`, `oprim.push.dispatcher` |
| timeout_seconds | 1800 |

**params schema**:

```json
{}
```

**output schema**:

```json
{"new_substrates": 3, "digest_sent": true, "summary": "..."}
```

---

#### 4.2.3 translation_worker

**用途**: 批量翻译缺少中文翻译的英文 substrate。

| 属性 | 值 |
|------|---|
| name | `translation_worker` |
| allowed_tools | `oskill.knowledge.translate_substrate` |
| timeout_seconds | 3600 |

**params schema**:

```json
{"max_substrates": 5, "target_lang": "zh-CN"}
```

**output schema**:

```json
{"translated": 0, "candidates": 0}
```

**真实示例** (agent_run `a597d9f4`):

```json
{
  "trace": [{"step_num": 1, "tool_name": "list_substrates_without_translation", "tool_input": {"max": 1, "target_lang": "zh-CN"}, "tool_output": {"candidates": 0}, "duration_ms": 20}],
  "output": {"translated": 0, "candidates": 0}
}
```

---

#### 4.2.4 reading_companion

**用途**: 基于用户知识库的问答 (hybrid search + LLM grounded answer)。

| 属性 | 值 |
|------|---|
| name | `reading_companion` |
| allowed_tools | `oskill.knowledge.hybrid_search`, `oprim.llm.llm_call` |
| timeout_seconds | 1800 |

**params schema**:

```json
{"question": "What is the key innovation of the Transformer architecture?"}
```

**output schema**:

```json
{"answer": "...", "sources_used": 3}
```

---

#### 4.2.5 lint_bot

**用途**: 周度健康检查 — 孤立 substrate、断裂引用、缺失 embedding。

| 属性 | 值 |
|------|---|
| name | `lint_bot` |
| allowed_tools | `oskill.knowledge.lint`, `oprim.push.dispatcher` |
| timeout_seconds | 1800 |

**params schema**:

```json
{}
```

**output schema**:

```json
{"issues_found": 2, "categories": {"orphan_substrate": 1, "missing_embedding": 1}}
```

---

#### 4.2.6 audio_generator (disabled)

**用途**: 为 substrate 生成音频朗读 (F5-TTS)。

| 属性 | 值 |
|------|---|
| name | `audio_generator` |
| allowed_tools | `oskill.knowledge.generate_audio_narration` |
| timeout_seconds | 1800 |
| **status** | **v1.0 不可用** — upstream image broken |

**params schema**:

```json
{"max_substrates": 3, "voice": "default", "speed": 1.0}
```

调用 `run()` 立即 raise `NotImplementedError("TTS unavailable v1.0")`。


---

### §4.3 AgentResult 详细 Schema

`AgentResult` 是所有 agent 的统一返回类型，持久化到 `agent_runs` 表:

```python
@dataclass
class AgentResult:
    success: bool              # True = completed, False = failed
    output: dict               # agent-specific output (见 §4.2 各 agent output schema)
    trace: list[AgentStep]     # 工具调用链 (平铺 array, 按 step_num 排序)
    citations: list[Citation]  # 引用的 substrate (可为空)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    elapsed_seconds: float = 0.0   # runner 填入 (wall clock)
    cost_usd: float = 0.0
    error: str | None = None       # 失败时的错误信息
```

**持久化映射** (AgentResult → agent_runs 表):

| AgentResult 字段 | agent_runs 列 | 存储格式 |
|-----------------|---------------|---------|
| success | status | `"completed"` if success else `"failed"` |
| output | output | JSON string |
| trace | trace | JSON string (AgentStep[] 序列化) |
| citations | citations | JSON string (Citation[] 序列化) |
| total_input_tokens | total_input_tokens | int |
| total_output_tokens | total_output_tokens | int |
| cost_usd | cost_usd | float |
| error | error_message | string \| null |
| elapsed_seconds | completed_at - started_at | 计算得出 |

**AgentStep 序列化格式**:

```json
{
  "step_num": 1,
  "tool_name": "ingest_substrate",
  "tool_input": {"file": "/path/to/file.md"},
  "tool_output": {"substrate_id": "01KS2MD25C3FAAAD7B9KTF9ZM9", "medium": "other"},
  "duration_ms": 311,
  "error": null,
  "timestamp": "2026-05-20T12:05:11.146744"
}
```

**Citation 序列化格式**:

```json
{
  "substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "fragment_id": "01KS2E3QK3KVN1WBVYSEEFAYT9#0",
  "anchor": {"section": null, "char_start": 0, "char_end": 0},
  "deep_link": "stratum://substrate/01KS2E3QK3KVN1WBVYSEEFAYT9/#01KS2E3QK3KVN1WBVYSEEFAYT9#0"
}
```

---

### §4.4 AgentTracer

`AgentTracer` 负责将 agent 执行记录持久化到 DuckDB `agent_runs` 表。

**API**:

```python
class AgentTracer:
    def __init__(self, db: MetaDB | None = None) -> None: ...

    def create_run(self, run_id: str, user_id: str, agent_name: str,
                   params: dict, started_at: datetime) -> None:
        """INSERT INTO agent_runs (status='running')."""

    def complete_run(self, run_id: str, result: AgentResult) -> None:
        """UPDATE agent_runs SET status='completed', trace=..., output=..., completed_at=now()."""

    def fail_run(self, run_id: str, error: str) -> None:
        """UPDATE agent_runs SET status='failed', error_message=..., completed_at=now()."""

    def list_runs(self, user_id: str, limit: int = 50) -> list[dict]:
        """SELECT (精简列) FROM agent_runs WHERE user_id=? ORDER BY started_at DESC."""
```

**list_runs 返回列**: `id`, `agent_name`, `status`, `started_at`, `completed_at`, `cost_usd`。不含 trace/output (大字段按需 fetch)。

---

### §4.5 Registry

`AgentRegistry` 管理 agent 注册与查找。

**API**:

```python
class AgentRegistry:
    def register(self, agent_cls: Type[Agent]) -> None: ...
    def get(self, name: str) -> Type[Agent]: ...       # raises AgentNotFoundError
    def list_agents(self) -> list[dict]: ...            # [{name, description, allowed_tools, timeout_seconds}]
    def __contains__(self, name: str) -> bool: ...

# 全局单例
_global_registry = AgentRegistry()
def get_registry() -> AgentRegistry: ...

# 装饰器注册
@register_agent
class MyAgent(Agent): ...
```

**v1.0 限制**: 不开放用户自定义 agent。仅 builtin 6 个 (含 disabled audio_generator)。v1.1+ 评估 plugin 机制。


---

## §5 Scheduler

### §5.1 Cron Engine

基于 APScheduler 3.x 的异步 cron 调度器，配合 Redis 分布式锁防止重复执行。

**架构**:

```
CronEngine
├── APScheduler (AsyncIOScheduler)
├── JobStore (DuckDB CRUD)
├── RunLock (Redis SETNX, key="stratum:job_lock:{job_id}")
├── ScheduledJobRunner → AgentRunner → Agent.run()
└── Notifier → PushDispatcher
```

**CronEngine API**:

```python
class CronEngine:
    def __init__(self, job_store: JobStore, run_lock: RunLock, runner: ScheduledJobRunner) -> None: ...

    async def start(self) -> None:
        """Load enabled jobs from DB, register cron triggers, start scheduler."""

    async def stop(self) -> None:
        """Graceful shutdown (wait for running jobs)."""
```

**执行流程**:

1. `CronEngine.start()` → 从 `scheduled_jobs` 表加载 `enabled=True` 的 job
2. 为每个 job 注册 `CronTrigger.from_crontab(cron_expression, timezone=timezone)`
3. 触发时 → `RunLock.acquire(job_id)` (Redis SETNX, TTL=max_runtime_seconds)
4. 获锁成功 → `ScheduledJobRunner.run(job_id)`
5. Runner 从 registry 获取 agent → `AgentRunner.run(agent, user_id, params)`
6. 完成/失败 → `JobStore.update_run()` + `Notifier.notify()`
7. 释放锁

**时区**: 默认 `Asia/Shanghai`，per-job 可配置。

---

### §5.2 Job CRUD API

`JobStore` 提供 scheduled_jobs + scheduled_job_runs 的完整 CRUD:

```python
class JobStore:
    def create(self, spec: dict) -> dict: ...
    def get(self, job_id: str) -> dict: ...                    # raises JobNotFoundError
    def find_by_name(self, user_id: str, name: str) -> dict | None: ...
    def list_jobs(self, user_id: str) -> list[dict]: ...
    def list_enabled_jobs(self) -> list[dict]: ...
    def update(self, job_id: str, updates: dict) -> dict: ...
    def delete(self, job_id: str) -> None: ...                 # cascades to runs

    # Run history
    def create_run(self, run_id: str, job_id: str, status: str, started_at: datetime) -> None: ...
    def update_run(self, run_id: str, status: str, agent_run_id: str | None = None,
                   error_message: str | None = None, completed_at: datetime | None = None) -> None: ...
    def list_runs(self, job_id: str, limit: int = 50) -> list[dict]: ...
```

**create spec 字段**:

```json
{
  "user_id": "wiki",
  "name": "daily_inbox_process",
  "agent_name": "knowledge_curator",
  "agent_params": {"inbox_dir": "~/.stratum/inbox"},
  "cron_expression": "0 6 * * *",
  "timezone": "Asia/Shanghai",
  "enabled": true,
  "notify_on_completion": true,
  "notify_on_failure": true,
  "max_runtime_seconds": 1800
}
```

**update 允许字段**: `enabled`, `cron_expression`, `timezone`, `agent_params`, `notify_on_completion`, `notify_on_failure`, `max_runtime_seconds`。

**便捷方法**:

```python
def install_builtin_jobs(user_id: str, job_store: JobStore) -> list[dict]:
    """Idempotent — create builtin jobs if not already present (by name)."""
```


---

### §5.3 Builtin Jobs

通过 `install_builtin_jobs(user_id, job_store)` 安装，幂等 (按 name 去重):

| # | name | agent | cron | 说明 | enabled |
|---|------|-------|------|------|---------|
| 1 | daily_inbox_process | knowledge_curator | `0 6 * * *` | 每天 6:00 处理 inbox | ✓ |
| 2 | daily_digest | daily_digest | `0 8 * * *` | 每天 8:00 生成摘要推送 | ✓ |
| 3 | weekly_lint | lint_bot | `0 7 * * 1` | 每周一 7:00 健康检查 | ✓ |
| 4 | nightly_translation | translation_worker | `0 2 * * *` | 每天 2:00 批量翻译 | ✗ (用户手动启用) |
| 5 | nightly_audio_gen | audio_generator | `0 3 * * *` | 每天 3:00 生成音频 | ✗ (v1.0 unavailable, upstream image broken) |

**agent_params 默认值**:

```json
// daily_inbox_process
{"inbox_dir": "~/.stratum/inbox"}

// nightly_translation
{"max_substrates": 5}

// nightly_audio_gen
{"max_substrates": 3, "voice": "default", "speed": 1.0}
```

---

### §5.4 通知

Job 完成/失败时通过 `Notifier` → `PushDispatcher` 推送:

```python
class Notifier:
    def __init__(self, dispatcher: PushDispatcher) -> None: ...

    async def notify_completion(self, job: dict, result: AgentResult) -> None:
        """If job.notify_on_completion: push success summary."""

    async def notify_failure(self, job: dict, error: str) -> None:
        """If job.notify_on_failure: push error alert."""
```

**通知内容**:
- 标题: `"[Stratum] {job_name} completed"` / `"[Stratum] {job_name} failed"`
- body: 摘要 (output 前 200 字符) 或 error_message
- deep_link: `stratum://agent_run/{agent_run_id}`
- channels_preference: `["web", "email"]` (默认)

**v1.0 状态**: Notifier 代码就绪，但 push_subscriptions 表为空 (无注册订阅)，实际不会发送。

---

### §5.5 缺失字段说明

以下字段**不存在于** `scheduled_jobs` 表:

| 字段 | 说明 | 前端处理方式 |
|------|------|-------------|
| `next_run_at` | 下次执行时间 | 前端用 cron-parser 库 + timezone 自行计算 |
| `last_run_at` | 上次执行时间 | 查 `scheduled_job_runs` 表最新一条的 `started_at` |
| `last_status` | 上次执行状态 | 查 `scheduled_job_runs` 表最新一条的 `status` |

**推荐前端库**: `cron-parser` (npm) 或 `cronstrue` (人类可读描述)。


---

## §6 Push

> **代码位置**: `oprim/push/` (分支 `feat/phase-10-translation`，v1.0 完工前合并 main)

### §6.1 PushDispatcher

```python
class PushDispatcher:
    def __init__(self, channels: dict[str, PushChannel], db: MetaDB | None = None) -> None: ...

    async def push(
        self,
        user_id: str,
        title: str,
        body: str,
        channels_preference: list[str] | None = None,  # default: ["web", "email"]
        deep_link: str | None = None,
        metadata: dict | None = None,
    ) -> list[PushResult]: ...
```

**行为**:
1. 按 `channels_preference` 顺序尝试
2. 从 `push_subscriptions` 表查找 user 的 recipient
3. 调用 channel.send()
4. **第一个成功即停止** (不重复发送)
5. 返回所有尝试的 PushResult (含失败的)

**PushResult**:

```python
@dataclass
class PushResult:
    channel: str           # "web" | "email" | "wechat" | "system"
    success: bool
    recipient: str         # 截断到 50 字符 (隐私)
    error_message: str | None = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
```

---

### §6.2 四个 Channel

| channel | 实现 | 依赖 | v1.0 状态 |
|---------|------|------|-----------|
| `web` | WebPushChannel (VAPID RFC 8030/8292) | pywebpush | 代码就绪，无订阅 |
| `email` | EmailPushChannel (SMTP) | smtplib | 代码就绪，无订阅 |
| `wechat` | — | — | placeholder，v1.0 未实施 |
| `system` | — | — | placeholder，v1.0 未实施 |

**WebPushChannel 配置**:

```python
WebPushChannel(
    vapid_private_key="<base64 EC private key>",
    vapid_claims={"sub": "mailto:admin@stratum.local"},
)
```

**recipient 格式** (web channel):

```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/...",
  "keys": {
    "p256dh": "<base64>",
    "auth": "<base64>"
  }
}
```

---

### §6.3 用户订阅 (push_subscriptions 表)

见 §1.10。前端注册订阅流程:

1. 浏览器 `Notification.requestPermission()` + `serviceWorkerRegistration.pushManager.subscribe()`
2. 获得 subscription JSON → POST 到 Stratum API (v1.1+ Web API)
3. 写入 `push_subscriptions` 表

**v1.0 状态**: 表存在但 0 行。无前端注册流程 (v1.1+ 实施)。

---

### §6.4 Deep Link 格式

Push 通知中的 `deep_link` 字段，供前端路由:

| 类型 | 格式 | 示例 |
|------|------|------|
| substrate | `stratum://substrate/{id}` | `stratum://substrate/01KS2MD25C3FAAAD7B9KTF9ZM9` |
| substrate_fragment | `stratum://substrate/{id}/#{fragment_id}` | `stratum://substrate/01KS2MD25C3FAAAD7B9KTF9ZM9/#01KS2MD25C3FAAAD7B9KTF9ZM9#0` |
| agent_run | `stratum://agent_run/{id}` | `stratum://agent_run/748c306e-8ac0-4c30-98c5-6a4b962ee54f` |
| digest | `stratum://digest/{date}` | `stratum://digest/2026-05-23` |

**metadata 已知 key** (push 调用时可附加):

| key | 类型 | 说明 |
|-----|------|------|
| `agent_name` | string | 触发推送的 agent |
| `job_name` | string | 触发推送的 scheduled job |
| `substrate_count` | number | digest 中包含的 substrate 数 |


---

## §7 hybrid_search

> **代码位置**: `oskill/knowledge/hybrid_search.py`

### §7.1 Python API 签名

```python
async def hybrid_search(
    query: str,
    top_k: int = 20,
    medium_filter: list[str] | None = None,
    domain_filter: list[str] | None = None,
    type_filter: list[str] | None = None,
    mode: Literal["strict", "augmented"] = "augmented",
    view_id: str | None = None,
    user_id: str | None = None,
    pinned_boost: float = 1.5,
    return_citations: bool = True,
    time_range: str | None = None,
) -> list[SearchResult]:
```

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| query | str | — | 搜索文本 |
| top_k | int | 20 | 返回上限 |
| medium_filter | list[str] \| None | None | 按 medium 过滤 |
| domain_filter | list[str] \| None | None | 按 domain 过滤 |
| type_filter | list[str] \| None | None | 按 result type 过滤 |
| mode | "strict" \| "augmented" | "augmented" | 搜索模式 |
| view_id | str \| None | None | 应用指定 view 的 default_filter |
| user_id | str \| None | None | 无 view_id 时自动应用用户 default view |
| pinned_boost | float | 1.5 | pinned substrate 分数乘数 |
| return_citations | bool | True | 是否填充 citation 字段 |
| time_range | str \| None | None | "last_24h" \| "last_7d" \| "last_30d" \| "last_90d" |

---

### §7.2 mode: strict vs augmented

| mode | 行为 |
|------|------|
| `strict` | 仅返回 substrate 命中，无 LLM 兜底 |
| `augmented` | substrate 命中为空时，调用 `oprim.llm.llm_call` 生成通用回答 (type="llm_augmented") |

**v1.0 实际行为**: `augmented` 模式已实施 LLM 兜底 (通过 `_llm_augmented()`)，但仅在 **零命中** 时触发。非零命中时 augmented = strict。

---

### §7.3 排序: RRF + pinned_boost

**执行流水线**:

```
query → [BM25 (tantivy)] → ranked list A (top_k*2)
      → [Dense (LanceDB)] → ranked list B (top_k*2)
      → RRF fusion (k=60) → fused list
      → pinned_boost (×1.5 for is_pinned=true, re-sort)
      → enrich (fetch metadata from DuckDB)
      → apply filters (medium, domain, type, time_range)
      → return top_k
```

**RRF 公式**: `score(d) = Σ 1/(k + rank_i(d))`, k=60

**pinned_boost**: 查 `substrate` 表 `is_pinned=true` 的 ID，将其 RRF score × boost 因子，然后重新排序。

---

### §7.4 跨语种搜索

翻译 derivative 被 embed 到同一个 `vectors_text` LanceDB 表:

```
substrate (en) → embed → vectors_text: "01KRX5S8ZM3EF5F89YASCDHSEW#0"
derivative (zh-CN translation) → embed → vectors_text: "01KS2MQHTQN7D0G6H3A8ZYWQHA#0"
```

**效果**: 中文 query 可命中英文 substrate 的中文翻译 derivative，dense search 返回 `derivative_id#chunk_idx`，enrich 阶段通过 `derivative.substrate_id` 回溯到原始 substrate。

**matched_language**: v1.0 未在 SearchResult 中暴露 matched_language 字段。前端无法区分是原文命中还是翻译命中。v1.1+ 评估添加。

---

### §7.5 Embedding Provider

**v1.0 硬编码**: `qwen3_dashscope` (text-embedding-v3, dim=1024)

```python
vecs = embed_text([query], provider="qwen3_dashscope", dim=1024)
```

- 模型: DashScope `text-embedding-v3`
- 维度: 1024
- 批次上限: 10 texts/call
- 重试: 3 次 (指数退避)
- 成本: ~$0.0007/1K tokens

**v1.0 限制**: 无 fallback provider。DashScope 不可用时 dense search 返回空，仅 BM25 生效。v1.1+ 加 bge_m3 本地 fallback。


---

## §8 浏览器扩展 (Phase 4)

> **代码位置**: `omodul/knowledge/browser_extension/`

### §8.1 安装步骤

1. **启动后端**: `python -m omodul.knowledge.browser_extension --port 14567`
2. **配置 token**: 在 `~/.stratum/config.yaml` 设置 `browser_extension.token`
3. **加载扩展**: Chrome → `chrome://extensions` → 开发者模式 → 加载已解压扩展
4. **扩展配置**: 填入 `http://127.0.0.1:14567` + token

---

### §8.2 三个使用场景

#### 场景 1: 一键保存整页

用户点击扩展图标 → 扩展抓取当前页面 HTML → POST `/ingest`:

```json
{
  "url": "https://arxiv.org/abs/1706.03762",
  "title": "Attention Is All You Need",
  "html": "<html>...(full page)...</html>",
  "tags": ["transformer"]
}
```

后端流程: `extract_main_content(html)` → 写临时 .html → `ingest_substrate()` → 返回 substrate_id。

#### 场景 2: 选中文本保存

用户选中文本 → 右键菜单 "Save to Stratum" → POST `/ingest`:

```json
{
  "url": "https://example.com/paper",
  "title": "Selected Passage Test",
  "selection_text": "Key result: BLEU score benchmark...",
  "create_note": true,
  "note_content": "Key result: BLEU score benchmark"
}
```

后端流程: selection_text 优先于 html → ingest → 可选创建 note。

#### 场景 3: 侧边栏搜索

用户打开侧边栏 → 自动以当前页面标题搜索 → POST `/sidebar-search`:

```json
{
  "url": "https://arxiv.org/abs/1706.03762",
  "page_title": "Attention Is All You Need",
  "selected_text": null
}
```

返回知识库中相关 substrate 列表 (top 10, mode=strict)。

---

### §8.3 URL 去重

**模块**: `browser_extension/url_dedup.py`

**流程**:
1. `normalize_url(url)` — 去除 trailing slash、fragment、排序 query params
2. 查 `browser_ext_url_index` 表: `SELECT substrate_id WHERE normalized_url = ?`
3. 已存在 → 返回 `IngestResponse(deduplicated=true, substrate_id=existing_id)`
4. 不存在 → 正常 ingest → `mark_url_ingested(url, substrate_id)` 写入索引

**normalize_url 规则**:
- 移除 fragment (`#...`)
- 移除 trailing `/`
- query params 按 key 排序
- scheme + host 小写

---

### §8.4 网页 substrate 存储

浏览器扩展 ingest 的网页 substrate 特点:

**meta_json.source 结构** (平铺，无嵌套):

```json
{
  "medium": "webpage",
  "source_type": "browser_extension",
  "source": {
    "type": "browser_extension",
    "url": "https://arxiv.org/abs/1706.03762",
    "title": "Attention Is All You Need",
    "tags": ["transformer", "nlp"]
  }
}
```

**存储流程**:
1. 内容写入临时 `.html` 文件 (prefix=slugified title)
2. `ingest_substrate(path=tmp_html, source={...})` — 走标准 ingest 流水线
3. 临时文件在 ingest 完成后删除
4. substrate 行的 `source_path` 为 null (临时文件已删)
5. 内容保留在 `derivative` 表 (kind="markdown" + kind="plaintext")


---

## §9 Sync (Phase 2)

> **代码位置**: `oskill/sync/` (4 skills) + `omodul/sync/bg_sync.py` (daemon)

### §9.1 ChangeFeed

本地变更通过 `changefeed_local` 表记录 (append-only)，远端同步通过 `changefeed_events` 表交换。

**本地写入** (自动，在 ingest/translate 等操作中):

```sql
INSERT INTO changefeed_local (seq, table_name, row_id, op, payload)
VALUES (nextval('changefeed_seq'), 'substrate', ?, 'insert', ?);
```

**远端事件** (从 GDrive 拉取后写入):

```sql
INSERT INTO changefeed_events (device_id, user_id, event_type, aggregate_id, payload, seq)
VALUES (?, ?, 'substrate_created', ?, ?, ?);
```

**per-user seq**: 每个用户维护独立的单调递增序列号，用于增量同步。

---

### §9.2 Google Drive 存储适配

**OAuth**: Google OAuth 2.0 (Desktop app flow)，token 存储在 `~/.stratum/gdrive_token.json`。

**WSL2 适配**: OAuth redirect 通过 `localhost` loopback，WSL2 环境需确保端口转发或使用 `--no-browser` 模式。

**存储结构** (GDrive):

```
Stratum Sync/
├── events/
│   ├── {user_id}_{device_id}_{seq_start}_{seq_end}.jsonl
│   └── ...
└── snapshots/
    ├── {snapshot_id}.tar.gz
    └── ...
```

**Phase 2 集成测试**: 9 项测试通过 (flush + apply + snapshot + restore + conflict)。

---

### §9.3 四个 Sync Skill

#### flush_outbox

上传本地 changefeed_local 事件到远端存储。

```python
@dataclass
class FlushResult:
    flushed_count: int
    failed_count: int
    last_flushed_seq: int
    uploaded_files: list[str] = field(default_factory=list)
```

#### apply_remote_events

从远端拉取事件并应用到本地 DB。

```python
@dataclass
class ApplyResult:
    applied_count: int
    skipped_count: int
    conflict_count: int
    last_applied_seq: int
    errors: list[str] = field(default_factory=list)
```

#### snapshot_backup

创建全量快照并上传到远端。

```python
async def snapshot_backup(user_id, device_id, db, storage_adapter) -> dict:
    # Returns: {snapshot_id, seq_at, file_id, substrate_count, concept_count, note_count}
```

#### restore_from_snapshot

从远端下载快照并恢复本地 DB。

```python
async def restore_from_snapshot(snapshot_file_id, db, storage_adapter) -> dict:
    # WARNING: truncates local tables before restore
    # Returns: {seq_at, snapshot_id, substrate_count, concept_count, note_count}
```

---

### §9.4 BackgroundSyncDaemon

后台同步守护进程，周期性执行 flush + pull + snapshot:

```python
class BackgroundSyncDaemon:
    def __init__(
        self,
        user_id: str,
        device_id: str,
        db: MetaDB,
        storage: Any,
        *,
        flush_interval_sec: int = 30,      # 每 30s flush 一次
        pull_interval_sec: int = 60,       # 每 60s pull 一次
        snapshot_interval_hours: int = 24, # 每 24h snapshot 一次
    ) -> None: ...

    async def run(self) -> None:
        """Blocks until shutdown(). Runs 3 concurrent loops."""

    async def shutdown(self) -> None:
        """Graceful stop."""
```

**并发模型**: 3 个 asyncio task 并发运行 (flush loop / pull loop / snapshot loop)。

---

### §9.5 LWW 冲突解决

**策略**: Last-Writer-Wins (LWW)，基于事件 `created_at` 时间戳。

**冲突场景**: 两个设备同时修改同一 substrate 的 `is_pinned`:
1. Device A: pin at T1
2. Device B: unpin at T2 (T2 > T1)
3. apply_remote_events 时比较 timestamp → T2 wins → is_pinned=false

**conflict_count**: `ApplyResult.conflict_count` 记录本次 apply 中发生的冲突数 (信息性，不阻塞)。

**v1.0 限制**: 仅 LWW，无 CRDT。对于 content 字段冲突 (如 note.content 同时编辑)，后写覆盖前写，无合并。v2.0 评估 OT/CRDT。


---

## §10 View (Phase 13)

> **代码位置**: `omodul/knowledge/views/`

### §10.1 CRUD API

```python
# omodul/knowledge/views/crud.py
def create_view(user_id: str, spec: dict) -> dict: ...
def get_view(view_id: str) -> dict | None: ...
def list_views(user_id: str) -> list[dict]: ...
def update_view(view_id: str, updates: dict) -> dict | None: ...
def delete_view(view_id: str) -> None: ...
def set_default(user_id: str, view_id: str) -> None: ...
def get_default_view(user_id: str) -> dict | None: ...
```

**create spec**:

```json
{
  "name": "Research",
  "description": "Papers and books only",
  "default_filter": {"medium": ["paper", "book"], "time_range": "last_90d"},
  "default_llm": {"provider": "qwen3_dashscope", "model": "qwen-max", "temperature": 0.2},
  "default_system_prompt": "You are a research assistant...",
  "icon": "📚",
  "is_default": false,
  "is_builtin": true
}
```

**update 允许字段**: `name`, `description`, `default_filter`, `default_llm`, `default_system_prompt`, `icon`。

**单一默认约束**: `set_default(user_id, view_id)` 先将该用户所有 view 的 `is_default=false`，再设目标为 `true`。

### §10.2 View 生效机制

`hybrid_search` 中 view 的应用 (oskill 层直接读 views 表，不反向 import omodul):

```python
# hybrid_search 内部
if view_id or user_id:
    vf = _load_view_filter(view_id, user_id)  # 直接 SQL 查 views 表
    # 将 vf 中的 medium/domain/time_range 作为默认 filter
```

**优先级**: 显式传入的 `medium_filter` > view 的 `default_filter.medium`。

### §10.3 预置 View

5 个预置 view 通过 `preset_loader.install_presets(user_id)` 安装 (幂等):

| name | medium filter | domain filter | time_range | icon |
|------|--------------|---------------|------------|------|
| All | — | — | — | 🌐 |
| Research | paper, book | — | — | 📚 |
| Web Clips | webpage | — | last_30d | 🔖 |
| Notes | markdown_note | — | — | 📝 |
| Recent | — | — | last_7d | ⏰ |

---

## §11 Pin (Phase 1.5)

### §11.1 Pin/Unpin API

**MCP tools**: `stratum.pin_substrate` / `stratum.unpin_substrate` (见 §2.2)

**Python 层** (MCP handler 内部):

```python
def _set_pinned(substrate_id: str, pinned: bool) -> dict:
    """UPDATE substrate SET is_pinned=?, pinned_at=?, updated_at=? WHERE id=?"""
```

- pin: `is_pinned=True`, `pinned_at=now()`
- unpin: `is_pinned=False`, `pinned_at=None`

### §11.2 pinned_boost 搜索效果

pinned substrate 在 hybrid_search 中获得 1.5x 分数加成:

```python
# hybrid_search 内部
if pinned_boost != 1.0:
    fused = _boost_pinned(fused, pinned_boost)  # score × 1.5, re-sort
```

**效果**: pinned substrate 在搜索结果中排名提升，但不保证置顶 (取决于原始 RRF score)。

### §11.3 list_pinned

v1.0 无独立 `list_pinned` API。前端获取 pinned 列表方式:

```sql
SELECT id, title, pinned_at FROM substrate WHERE is_pinned = TRUE ORDER BY pinned_at DESC;
```

通过 MCP `stratum.search` 无法直接过滤 pinned-only。v1.1+ 评估添加 `pinned_only` 参数。

---

## §12 Translation (Phase 10)

> **代码位置**: `oskill/knowledge/translate_substrate.py`

### §12.1 translate_substrate Skill

```python
async def translate_substrate(
    substrate_id: str,
    target_lang: str,
    source_lang: str = "auto",
    provider: str = "deepseek",
    *,
    model: str | None = None,
    domain: str | None = None,
    max_chars: int = 2000,
    checkpoint_dir: Path | None = None,
    glossary: TerminologyGlossary | None = None,
    overwrite: bool = False,
    embed_translation: bool = True,
) -> TranslateResult:
```

### §12.2 三个 Provider

| provider | 模型 | 用途 | 成本 |
|----------|------|------|------|
| `deepseek` | deepseek-chat | 默认，性价比高 | ~$0.001/1K tokens |
| `claude` | claude-3-haiku | 高质量学术翻译 | ~$0.003/1K tokens |
| `qwen3` | qwen-max (dashscope) | 中文优化 | ~$0.002/1K tokens |

### §12.3 异步实施

- 分块翻译: 按 `max_chars=2000` 切分
- checkpoint: 可选 `checkpoint_dir`，每 chunk 完成后写 checkpoint JSON，支持断点续传
- glossary: `TerminologyGlossary` 对象，domain-specific 术语表

### §12.4 翻译 Derivative 与跨语种 Embed

翻译完成后:
1. 写入 `derivative` 表: `kind="translation_{target_lang}"`, `meta_json` 含 provider/cost/chunks
2. 若 `embed_translation=True` (默认): 将翻译文本分块 embed 到 `vectors_text` LanceDB
3. 向量 ID 格式: `{derivative_id}#{chunk_idx}`

**效果**: 中文 query → dense search 命中翻译 derivative → 通过 `derivative.substrate_id` 回溯原始英文 substrate。


---

## §13 错误处理

### §13.1 StratumError 类树

```
StratumError (oprim/errors.py)
├── ConfigError
├── PDFParseError
├── UnsupportedFileTypeError
├── UnsupportedImageError
├── EmbeddingError
│   └── QuotaExceededError
├── VectorDBError
├── FulltextError
├── MetaDBError
├── LLMError
│   └── LLMRateLimitError
├── IngestError
│   └── DuplicateSubstrateError
└── AgentError (omodul/knowledge/agents/errors.py)
    ├── AgentToolNotAllowedError
    ├── AgentTimeoutError
    └── AgentNotFoundError

PushError (oprim/push/errors.py)
├── PushConfigError
├── PushDeliveryError
└── PushRateLimitError

SchedulerError (omodul/knowledge/scheduler/errors.py)
├── JobNotFoundError
└── (其他 scheduler 错误)

SyncError (oskill/sync/errors.py)
├── FlushError
├── ApplyError
└── SnapshotError
```

### §13.2 HTTP 错误码映射 (浏览器扩展 API)

| 异常 | HTTP | response body |
|------|------|---------------|
| `AuthError` | 401 | `{"detail": "Invalid or missing token"}` |
| `StratumError` | 500 | `{"detail": "<error message>"}` |
| `HTTPException(400)` | 400 | `{"detail": "Either html or selection_text is required"}` |
| `HTTPException(422)` | 422 | Pydantic validation error (FastAPI 自动) |
| 未捕获异常 | 500 | `{"detail": "Internal Server Error"}` |

**FastAPI exception handlers** (server.py):

```python
@app.exception_handler(AuthError)
async def _auth_error_handler(request, exc):
    return JSONResponse(status_code=401, content={"detail": str(exc)})

@app.exception_handler(StratumError)
async def _stratum_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
```

### §13.3 MCP 错误响应

MCP tool 不使用 MCP protocol-level error。错误通过返回值中的 `error` 字段传递:

```json
{"error": "substrate '01NONEXISTENT' not found"}
```

| 场景 | error 内容 |
|------|-----------|
| meta_db 不存在 | `"meta_db not found"` |
| substrate 不存在 | `"substrate '{id}' not found"` |
| view 不存在 | `"view '{id}' not found"` |
| DB 异常 | `"<exception str>"` |

**前端处理**: 检查返回对象是否含 `error` key，有则展示错误 UI。

### §13.4 Agent 错误

Agent 执行中的错误记录在 `agent_runs.error_message`:

| 场景 | status | error_message |
|------|--------|---------------|
| 正常完成 | `completed` | null |
| agent.run() 抛异常 | `failed` | exception message |
| asyncio.TimeoutError | `timeout` | `"Agent exceeded timeout of {n}s"` |
| tool 不在 allow-list | `failed` | `"'{agent}' attempted to call disallowed tool: '{tool}'"` |


---

## §14 部署

### §14.1 单机拓扑

**环境**: Win11 + WSL2 Ubuntu 24.04, 单台物理机 (RTX 4090 24G VRAM, 64G RAM)。

```
┌─────────────────────────────────────────────────────────────┐
│  WSL2 Ubuntu 24.04                                          │
│                                                             │
│  ┌─── Layer A (核心服务, systemd) ───────────────────────┐  │
│  │  PostgreSQL (5432)  Redis (6379)  RabbitMQ (5672)     │  │
│  │  Ollama (11434)     Caddy (443/80)                    │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─── Layer B (GPU 外挂, docker compose) ────────────────┐  │
│  │  F5-TTS (9301) [STOPPED]   ComfyUI/SD (9302)         │  │
│  │  whisper.cpp (9303)         SearXNG (9304)            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─── Stratum 应用层 (Python, 直接运行) ─────────────────┐  │
│  │  MCP Server (stdio)                                   │  │
│  │  Browser Extension API (14567)                        │  │
│  │  BackgroundSyncDaemon                                 │  │
│  │  CronEngine (APScheduler)                             │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### §14.2 端口清单

| 端口 | 服务 | 层 | 绑定 |
|------|------|---|------|
| 5432 | PostgreSQL | A | 127.0.0.1 |
| 6379 | Redis | A | 127.0.0.1 |
| 5672 | RabbitMQ | A | 127.0.0.1 |
| 11434 | Ollama | A | 127.0.0.1 |
| 443/80 | Caddy (reverse proxy) | A | 0.0.0.0 |
| 9301 | F5-TTS | B | 127.0.0.1 (STOPPED) |
| 9302 | ComfyUI/SD 1.5 | B | 127.0.0.1 |
| 9303 | whisper.cpp | B | 127.0.0.1 |
| 9304 | SearXNG | B | 127.0.0.1 |
| 14567 | Browser Extension API | App | 127.0.0.1 |
| 8765 | MCP Server | App | stdio (非 TCP) |

### §14.3 用户配置

**主配置**: `~/.stratum/config.yaml`

```yaml
user_id: wiki
device_id: wsl2-desktop

storage:
  meta_db: ~/.stratum/meta.duckdb
  lance_index: ~/.stratum/index/lance
  tantivy_index: ~/.stratum/index/tantivy
  inbox: ~/.stratum/inbox

browser_extension:
  port: 14567
  token: "stratum_ext_<random_32_hex>"

sync:
  enabled: true
  provider: gdrive
  flush_interval_sec: 30
  pull_interval_sec: 60

embedding:
  provider: qwen3_dashscope
  dim: 1024

translation:
  default_provider: deepseek
  default_target_lang: zh-CN

scheduler:
  timezone: Asia/Shanghai
```

**密钥**: `~/.config/keys/.env` (不入 git):

```bash
DASHSCOPE_API_KEY=sk-...
DEEPSEEK_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-...
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
```

### §14.4 Docker Compose (Layer B)

文件: `docker-compose.layer-b.yml`

```bash
# 启动
docker compose -f docker-compose.layer-b.yml up -d

# 停止单个服务 (保留 container)
docker compose -f docker-compose.layer-b.yml stop stratum-tts

# 查看状态
docker compose -f docker-compose.layer-b.yml ps
```

**GPU 并发约束** (ADR-021):
- whisper large-v3 (~4-5G) + F5-TTS (~6-8G) = 不可并发
- SD (~4-6G) 可与 whisper 共存
- Ollama (~8-10G) 运行时不启动 F5/SD
- 通过 Redis `GpuLock` 互斥 (oprim 层)


---

## §15 已知限制与路线图

### §15.1 v1.0 已知限制

| # | 限制 | 影响 | 计划 |
|---|------|------|------|
| 1 | mode=augmented 仅零命中时触发 LLM 兜底 | 非零命中时 augmented = strict | Phase 11+ 修 |
| 2 | 单用户场景 | 无多租户隔离 | Phase 14+ |
| 3 | 无 wechat push | channel placeholder | v1.1+ |
| 4 | 无 vision LLM 本地 | 走 Claude API，Aegis 接管 ollama 后切回本地 | Aegis Q4 |
| 5 | TTS / audio_generator 不可用 | upstream image (ghcr.io/swivid/f5-tts:main) torch/torchvision 冲突 | v1.1 |
| 6 | 无 char-level fragment | 仅 chunk-level (ULID#chunk_idx) | v2.0 |
| 7 | 全非流式 | 所有 API 同步返回完整结果 | v1.1+ SSE |
| 8 | list_substrates 仅 Python SDK + MCP | 无 REST 端点 | v1.1 |
| 9 | dashscope embedding 硬编码 | 无 fallback，DashScope 不可用时 dense search 失效 | v1.1 bge_m3 |
| 10 | next_run_at / last_run_at 不在 DB | 前端需 cron-parser 自算 | 评估中 |
| 11 | push_subscriptions 0 行 | 通知实际不发送 | v1.1 前端注册流程 |
| 12 | concept 表 0 行 | 概念提取流水线未实施 | Phase 14+ |
| 13 | matched_language 未暴露 | 前端无法区分原文/翻译命中 | v1.1 |
| 14 | Push 模块在 feat 分支 | 未合入 main | v1.0 完工前合并 |

---

### §15.2 v1.1 计划

| 项目 | 说明 |
|------|------|
| TTS 自写 wrapper 或换 image | 解决 torch/torchvision 冲突 |
| audio_generator Agent 启用 | 依赖 TTS 修复 |
| web_search_augmented 增强 | SearXNG 集成到 augmented mode |
| SSE 流式 | Agent 执行 + search 支持 Server-Sent Events |
| mode=augmented 真实施 LLM 兜底 | 非零命中时也可追加 LLM 补充 |
| list_substrates REST 端点 | port 14568 Web API |
| bge_m3 本地 fallback | DashScope 不可用时切本地 embedding |
| matched_language 字段 | SearchResult 中标注命中语言 |
| push 前端注册流程 | Web Push subscription UI |

---

### §15.3 v2.0 (商业化期)

| 项目 | 说明 |
|------|------|
| 多用户 / 多租户 | user_id 隔离 + RBAC |
| 付费层 | 免费 / Pro / Enterprise |
| 微信小程序集成 | wechat push channel 实施 |
| char-level fragment 表 | 独立 fragment 表 + char_start/char_end |
| CRDT 同步 | 替代 LWW，支持 content 合并 |
| 联邦搜索 | 跨 Stratum 实例搜索 |

---

### §15.4 跨项目治理 (Aegis)

Aegis 接管路线已确认:
- **2026-Q4 MVP**: Aegis 统一 GPU 调度 + 模型管理
- **当前**: Stratum 内部 `GpuLock` (Redis SETNX) 自治
- **过渡**: Aegis MVP 后 Stratum 的 GpuLock 迁移到 Aegis 调度 API
- **不写时间表**: 具体日期由 Aegis 团队确定


---

## 附录 A: TypeScript 接口定义

供 Helios 前端使用。严格 snake_case，与 Python 字段名 1:1。

```typescript
// ═══════════════════════════════════════════════════════════════
// Stratum API v1.0 TypeScript Interfaces
// Generated from: oprim v2.8.0 / oskill v2.9.0 / omodul v1.8.0
// ═══════════════════════════════════════════════════════════════

// ── Core Entities ────────────────────────────────────────────

interface Substrate {
  id: string;
  ulid: string;
  title: string | null;
  mime: string | null;
  source_path: string | null;
  file_hash: string | null;
  byte_size: number | null;
  page_count: number | null;
  parser: string | null;
  language: string | null;
  has_cjk: boolean;
  is_scanned: boolean;
  created_at: string;
  updated_at: string;
  meta_json: SubstrateMeta;
  is_pinned: boolean;
  pinned_at: string | null;
}

interface SubstrateMeta {
  medium: Medium;
  source_type: SourceType;
  source: Record<string, unknown>;
  domain?: string;
}

interface Derivative {
  id: string;
  substrate_id: string;
  kind: DerivativeKind;
  seq: number;
  content: string | null;
  embedding_id: string | null;
  embedding_dim: number | null;
  meta_json: Record<string, unknown>;
  created_at: string;
}

interface Note {
  id: string;
  title: string | null;
  content: string | null;
  wikilinks: string[];
  substrate_id: string | null;
  meta_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

interface Concept {
  id: string;
  name: string;
  aliases: string | null;
  description: string | null;
  wikilink: string | null;
  source_ids: string[];
  meta_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

// ── View ─────────────────────────────────────────────────────

interface View {
  id: string;
  user_id: string;
  name: string;
  description: string | null;
  default_filter: ViewFilter;
  default_llm: ViewLLM;
  default_system_prompt: string | null;
  icon: string | null;
  is_default: boolean;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

interface ViewFilter {
  medium?: Medium[];
  domain?: string[];
  time_range?: TimeRange;
}

interface ViewLLM {
  provider?: string;
  model?: string;
  temperature?: number;
}

// ── Agent ────────────────────────────────────────────────────

interface AgentRun {
  id: string;
  user_id: string;
  agent_name: AgentName;
  params: Record<string, unknown>;
  status: AgentStatus;
  trace: AgentStep[];
  citations: Citation[];
  output: Record<string, unknown> | null;
  total_input_tokens: number;
  total_output_tokens: number;
  cost_usd: number;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

interface AgentStep {
  step_num: number;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_output: Record<string, unknown> | null;
  duration_ms: number;
  error: string | null;
  timestamp: string;
}

interface Citation {
  substrate_id: string;
  title?: string;
  fragment_id: string | null;
  anchor: FragmentAnchor | null;
  deep_link: string | null;
}

interface FragmentAnchor {
  section: string | null;
  char_start: number;  // v1.0: always 0
  char_end: number;    // v1.0: always 0
}

// ── Scheduler ────────────────────────────────────────────────

interface ScheduledJob {
  id: string;
  user_id: string;
  name: string;
  agent_name: AgentName;
  agent_params: Record<string, unknown>;
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  notify_on_completion: boolean;
  notify_on_failure: boolean;
  max_runtime_seconds: number;
  created_at: string;
  updated_at: string;
}

interface ScheduledJobRun {
  id: string;
  job_id: string;
  agent_run_id: string | null;
  status: AgentStatus;
  started_at: string;
  completed_at: string | null;
  error_message: string | null;
}

// ── Push ─────────────────────────────────────────────────────

interface PushSubscription {
  id: string;
  user_id: string;
  channel: PushChannel;
  recipient: string;
  keys_json: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
}

// ── Sync ─────────────────────────────────────────────────────

interface ChangefeedEvent {
  id: number;
  device_id: string;
  user_id: string;
  event_type: string;
  aggregate_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  seq: number;
}

interface ChangefeedLocal {
  seq: number;
  table_name: string;
  row_id: string;
  op: "insert" | "update" | "delete";
  payload: Record<string, unknown> | null;
  ts: string;
}

// ── Search ───────────────────────────────────────────────────

interface SearchResult {
  id: string;
  type: "substrate" | "llm_augmented";
  title: string;
  score: number;
  highlight: string | null;
  metadata: SearchMetadata;
  citation: SearchCitation | null;
}

interface SearchMetadata {
  medium: string | null;
  source_type: string | null;
  domain: string | null;
  created_at: string | null;
}

interface SearchCitation {
  substrate_id: string;
  fragment_id: string;
  anchor: FragmentAnchor;
  deep_link: string;
}

// ── Browser Extension ────────────────────────────────────────

interface BrowserExtIngestRequest {
  url: string;
  title: string;
  html?: string | null;
  selection_text?: string | null;
  tags?: string[];
  create_note?: boolean;
  note_content?: string | null;
}

interface BrowserExtIngestResponse {
  substrate_id: string;
  note_id: string | null;
  deduplicated: boolean;
  message: string;
}

// ── Enums / Unions ───────────────────────────────────────────

type Medium = "webpage" | "paper" | "book" | "markdown_note" | "transcript" | "chat" | "other";
type SourceType = "browser_extension" | "inbox_local" | "gdrive_sync";
type DerivativeKind = "markdown" | "plaintext" | `translation_${string}`;
type AgentName = "knowledge_curator" | "translation_worker" | "daily_digest"
  | "reading_companion" | "lint_bot" | "audio_generator";
type AgentStatus = "running" | "completed" | "failed" | "timeout";
type PushChannel = "web" | "email" | "wechat" | "system";
type TimeRange = "last_24h" | "last_7d" | "last_30d" | "last_90d";

// ── Utility Types ────────────────────────────────────────────

/** Wrap any response type with citations array */
type WithCitations<T> = T & { citations: Citation[] };
```


---

## 附录 B: 真实示例数据

所有数据来自 Phase 1–13 实际运行，非编造。

### B.1 Substrate

```json
{
  "id": "01KS2MD25C3FAAAD7B9KTF9ZM9",
  "title": "test_rag_paper",
  "meta_json": {"medium": "other", "source_type": "inbox_local", "source": {"user_id": "demo_user"}},
  "is_pinned": false,
  "created_at": "2026-05-20T12:05:11"
}
```

### B.2 Derivative (翻译)

```json
{
  "id": "01KS2MQHTQN7D0G6H3A8ZYWQHA",
  "substrate_id": "01KRX5S8ZM3EF5F89YASCDHSEW",
  "kind": "translation_zh-CN",
  "seq": 0,
  "meta_json": {"source_lang": "auto", "target_lang": "zh-CN", "provider": "deepseek", "chunks": 1, "cost_usd": 0.0}
}
```

### B.3 Agent Run (knowledge_curator, completed)

```json
{
  "id": "748c306e-8ac0-4c30-98c5-6a4b962ee54f",
  "agent_name": "knowledge_curator",
  "status": "completed",
  "trace": [
    {"step_num": 1, "tool_name": "ingest_substrate", "tool_input": {"file": "/home/soffy/.stratum/inbox/test_rag_paper.md"}, "tool_output": {"substrate_id": "01KS2MD25C3FAAAD7B9KTF9ZM9", "medium": "other"}, "duration_ms": 311, "error": null, "timestamp": "2026-05-20T12:05:11.146744"}
  ],
  "output": {"files_found": 1, "ingested": 1, "skipped": 0, "failed": 0},
  "started_at": "2026-05-20T12:05:10.750309",
  "completed_at": "2026-05-20T12:05:11.146788"
}
```

### B.4 Agent Run (translation_worker, completed, 0 candidates)

```json
{
  "id": "a597d9f4-d1b9-4a7a-b041-8c0fa2ad2151",
  "agent_name": "translation_worker",
  "status": "completed",
  "trace": [
    {"step_num": 1, "tool_name": "list_substrates_without_translation", "tool_input": {"max": 1, "target_lang": "zh-CN"}, "tool_output": {"candidates": 0}, "duration_ms": 20, "error": null}
  ],
  "output": {"translated": 0, "candidates": 0}
}
```

### B.5 LanceDB Vector Records

```json
[
  {"id": "01KRX5S8ZM3EF5F89YASCDHSEW#0", "embedding": "[1024-dim float32]", "metadata": {"substrate_id": "01KRX5S8ZM3EF5F89YASCDHSEW", "chunk_idx": 0}},
  {"id": "01KS2MQHTQN7D0G6H3A8ZYWQHA#0", "embedding": "[1024-dim float32]", "metadata": {"derivative_id": "01KS2MQHTQN7D0G6H3A8ZYWQHA", "chunk_idx": 0}}
]
```

### B.6 Browser Extension URL Index

```json
[
  {"id": "415ba8d8-ae4a-4f9a-b8ae-4f5587c20aa0", "url": "https://arxiv.org/abs/1706.03762", "normalized_url": "https://arxiv.org/abs/1706.03762", "substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9", "ingested_at": "2026-05-20T18:15:17.006967"},
  {"id": "6e40e623-3e61-4315-a252-c25e0c1ff207", "url": "https://example.com/zh/attention-survey", "normalized_url": "https://example.com/zh/attention-survey", "substrate_id": "01KS2E3TW4XXY4JWQJYA90AX1D", "ingested_at": "2026-05-20T18:15:20.463523"}
]
```

### B.7 Changefeed Local

```json
{"seq": 1, "table_name": "substrate", "row_id": "01KRX5S8ZM3EF5F89YASCDHSEW", "op": "insert", "payload": "{\"substrate_id\": \"01KRX5S8ZM3EF5F89YASCDHSEW\"}", "ts": "2026-05-18T17:13:30.563263"}
```


---

## 附录 C: Cron 表达式参考

Stratum 使用标准 5 字段 cron (APScheduler `CronTrigger.from_crontab`):

```
┌───────────── minute (0-59)
│ ┌───────────── hour (0-23)
│ │ ┌───────────── day of month (1-31)
│ │ │ ┌───────────── month (1-12)
│ │ │ │ ┌───────────── day of week (0-6, 0=Monday)
│ │ │ │ │
* * * * *
```

**常用模式**:

| 表达式 | 含义 | 用于 |
|--------|------|------|
| `0 6 * * *` | 每天 06:00 | daily_inbox_process |
| `0 8 * * *` | 每天 08:00 | daily_digest |
| `0 2 * * *` | 每天 02:00 | nightly_translation |
| `0 3 * * *` | 每天 03:00 | nightly_audio_gen |
| `0 7 * * 1` | 每周一 07:00 | weekly_lint |
| `*/30 * * * *` | 每 30 分钟 | (自定义) |
| `0 */4 * * *` | 每 4 小时 | (自定义) |
| `0 0 1 * *` | 每月 1 日 00:00 | (自定义) |

**时区**: per-job 配置，默认 `Asia/Shanghai`。APScheduler 内部使用 `pytz` / `zoneinfo`。

**前端推荐库**:
- `cron-parser` (npm): 计算 next/prev 执行时间
- `cronstrue` (npm): 将 cron 表达式转为人类可读描述

---

## 附录 D: Enum 枚举值

从 Phase 1–13 实际数据 (`SELECT DISTINCT`) + 代码定义汇总。

### D.1 medium (substrate.meta_json.medium)

| 值 | 说明 | 来源 |
|----|------|------|
| `webpage` | 网页 (浏览器扩展保存) | Phase 4 实际数据 |
| `markdown_note` | Markdown 笔记 | Phase 1 实际数据 |
| `paper` | 学术论文 (PDF) | schema 定义，v1.0 未产生 |
| `book` | 书籍 (PDF/EPUB) | schema 定义，v1.0 未产生 |
| `transcript` | 音视频字幕 | schema 定义，v1.0 未产生 |
| `chat` | 对话存档 | schema 定义，v1.0 未产生 |
| `other` | 未分类 | Phase 1 实际数据 |

### D.2 source_type (substrate.meta_json.source_type)

| 值 | 说明 |
|----|------|
| `browser_extension` | 浏览器扩展 ingest |
| `inbox_local` | 本地 inbox 目录 ingest |
| `gdrive_sync` | GDrive 同步拉取 (v1.0 未产生) |

### D.3 derivative.kind

| 值 | 说明 |
|----|------|
| `markdown` | Markdown 解析结果 |
| `plaintext` | 纯文本提取 |
| `translation_{lang}` | 翻译 (e.g. `translation_zh-CN`) |
| `summary` | 摘要 (v1.0 未产生) |
| `note` | 笔记型 derivative (v1.0 未产生) |
| `tag` | 标签提取 (v1.0 未产生) |

### D.4 agent_runs.status

| 值 | 说明 |
|----|------|
| `running` | 执行中 |
| `completed` | 成功完成 |
| `failed` | 执行失败 (异常) |
| `timeout` | 超时 (超过 timeout_seconds) |

### D.5 agent_name

| 值 | 说明 | v1.0 实际运行 |
|----|------|---------------|
| `knowledge_curator` | inbox 处理 | ✓ |
| `daily_digest` | 每日摘要 | ✓ |
| `translation_worker` | 批量翻译 | ✓ |
| `reading_companion` | 问答 | ✓ |
| `lint_bot` | 健康检查 | ✗ (未触发) |
| `audio_generator` | 音频生成 | ✗ (disabled) |

### D.6 push channel

| 值 | 说明 | v1.0 状态 |
|----|------|-----------|
| `web` | Web Push (VAPID) | 代码就绪 |
| `email` | SMTP 邮件 | 代码就绪 |
| `wechat` | 微信推送 | placeholder |
| `system` | 系统通知 | placeholder |

### D.7 time_range (hybrid_search / view filter)

| 值 | 天数 |
|----|------|
| `last_24h` | 1 |
| `last_7d` | 7 |
| `last_30d` | 30 |
| `last_90d` | 90 |

---

**End of STRATUM_API_v1.md**

