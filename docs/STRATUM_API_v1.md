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

