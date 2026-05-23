# Wave 0: Ground Truth Data

Collected 2026-05-23. Source: `~/.stratum/meta.duckdb` + `~/.stratum/index/lance/` + `~/projects/platform/{oprim,oskill,omodul}`.

---

## 1. DuckDB Tables (13 total, excl. _migrations)

### 1.1 substrate

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | ulid | VARCHAR | T | — | |
| 2 | title | VARCHAR | F | — | |
| 3 | mime | VARCHAR | F | — | |
| 4 | source_path | VARCHAR | F | — | |
| 5 | file_hash | VARCHAR | F | — | |
| 6 | byte_size | INTEGER | F | — | |
| 7 | page_count | INTEGER | F | — | |
| 8 | parser | VARCHAR | F | — | |
| 9 | language | VARCHAR | F | — | |
| 10 | has_cjk | BOOLEAN | F | false | |
| 11 | is_scanned | BOOLEAN | F | false | |
| 12 | created_at | TIMESTAMP | F | CURRENT_TIMESTAMP | |
| 13 | updated_at | TIMESTAMP | F | CURRENT_TIMESTAMP | |
| 14 | meta_json | VARCHAR | F | '{}' | |
| 15 | is_pinned | BOOLEAN | F | false | |
| 16 | pinned_at | TIMESTAMP | F | — | |

### 1.2 derivative

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | substrate_id | VARCHAR | T | — | |
| 2 | kind | VARCHAR | T | — | |
| 3 | seq | INTEGER | F | 0 | |
| 4 | content | VARCHAR | F | — | |
| 5 | embedding_id | VARCHAR | F | — | |
| 6 | embedding_dim | INTEGER | F | — | |
| 7 | meta_json | VARCHAR | F | '{}' | |
| 8 | created_at | TIMESTAMP | F | CURRENT_TIMESTAMP | |

### 1.3 agent_runs

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | user_id | VARCHAR | T | — | |
| 2 | agent_name | VARCHAR | T | — | |
| 3 | params | VARCHAR | T | — | |
| 4 | status | VARCHAR | T | — | |
| 5 | trace | VARCHAR | F | — | |
| 6 | citations | VARCHAR | F | — | |
| 7 | output | VARCHAR | F | — | |
| 8 | total_input_tokens | INTEGER | F | 0 | |
| 9 | total_output_tokens | INTEGER | F | 0 | |
| 10 | cost_usd | FLOAT | F | 0.0 | |
| 11 | started_at | TIMESTAMP | T | — | |
| 12 | completed_at | TIMESTAMP | F | — | |
| 13 | error_message | VARCHAR | F | — | |

### 1.4 scheduled_jobs

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | user_id | VARCHAR | T | — | |
| 2 | name | VARCHAR | T | — | |
| 3 | agent_name | VARCHAR | T | — | |
| 4 | agent_params | VARCHAR | T | '{}' | |
| 5 | cron_expression | VARCHAR | T | — | |
| 6 | timezone | VARCHAR | T | 'Asia/Shanghai' | |
| 7 | enabled | BOOLEAN | T | true | |
| 8 | notify_on_completion | BOOLEAN | T | true | |
| 9 | notify_on_failure | BOOLEAN | T | true | |
| 10 | max_runtime_seconds | INTEGER | T | 1800 | |
| 11 | created_at | TIMESTAMP | T | — | |
| 12 | updated_at | TIMESTAMP | T | — | |

### 1.5 scheduled_job_runs

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | job_id | VARCHAR | T | — | |
| 2 | agent_run_id | VARCHAR | F | — | |
| 3 | status | VARCHAR | T | — | |
| 4 | started_at | TIMESTAMP | T | — | |
| 5 | completed_at | TIMESTAMP | F | — | |
| 6 | error_message | VARCHAR | F | — | |

### 1.6 views

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | user_id | VARCHAR | T | — | |
| 2 | name | VARCHAR | T | — | |
| 3 | description | VARCHAR | F | — | |
| 4 | default_filter | VARCHAR | F | — | |
| 5 | default_llm | VARCHAR | F | — | |
| 6 | default_system_prompt | VARCHAR | F | — | |
| 7 | icon | VARCHAR | F | — | |
| 8 | is_default | BOOLEAN | F | false | |
| 9 | is_builtin | BOOLEAN | F | false | |
| 10 | created_at | TIMESTAMP | T | — | |
| 11 | updated_at | TIMESTAMP | T | — | |

### 1.7 browser_ext_url_index

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | url | VARCHAR | T | — | |
| 2 | normalized_url | VARCHAR | T | — | |
| 3 | substrate_id | VARCHAR | T | — | |
| 4 | ingested_at | TIMESTAMP | T | CURRENT_TIMESTAMP | |

### 1.8 note

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | title | VARCHAR | F | — | |
| 2 | content | VARCHAR | F | — | |
| 3 | wikilinks | VARCHAR | F | '[]' | |
| 4 | substrate_id | VARCHAR | F | — | |
| 5 | meta_json | VARCHAR | F | '{}' | |
| 6 | created_at | TIMESTAMP | F | CURRENT_TIMESTAMP | |
| 7 | updated_at | TIMESTAMP | F | CURRENT_TIMESTAMP | |

### 1.9 concept

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | name | VARCHAR | T | — | |
| 2 | aliases | VARCHAR | F | — | |
| 3 | description | VARCHAR | F | — | |
| 4 | wikilink | VARCHAR | F | — | |
| 5 | source_ids | VARCHAR | F | '[]' | |
| 6 | meta_json | VARCHAR | F | '{}' | |
| 7 | created_at | TIMESTAMP | F | CURRENT_TIMESTAMP | |
| 8 | updated_at | TIMESTAMP | F | CURRENT_TIMESTAMP | |

### 1.10 push_subscriptions

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | user_id | VARCHAR | T | — | |
| 2 | channel | VARCHAR | T | — | |
| 3 | recipient | VARCHAR | T | — | |
| 4 | keys_json | VARCHAR | F | '{}' | |
| 5 | enabled | BOOLEAN | F | true | |
| 6 | created_at | TIMESTAMP | T | CURRENT_TIMESTAMP | |

### 1.11 changefeed_events

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | BIGINT | T | nextval('changefeed_event_id_seq') | PK |
| 1 | device_id | VARCHAR | T | — | |
| 2 | user_id | VARCHAR | T | — | |
| 3 | event_type | VARCHAR | T | — | |
| 4 | aggregate_id | VARCHAR | F | — | |
| 5 | payload | VARCHAR | T | — | |
| 6 | created_at | TIMESTAMP | T | CURRENT_TIMESTAMP | |
| 7 | seq | BIGINT | T | — | |

### 1.12 changefeed_local

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | seq | BIGINT | T | — | PK |
| 1 | table_name | VARCHAR | T | — | |
| 2 | row_id | VARCHAR | T | — | |
| 3 | op | VARCHAR | T | — | |
| 4 | payload | VARCHAR | F | — | |
| 5 | ts | TIMESTAMP | F | CURRENT_TIMESTAMP | |

### 1.13 changefeed_snapshots

| # | column | type | not_null | default | pk |
|---|--------|------|----------|---------|-----|
| 0 | id | VARCHAR | T | — | PK |
| 1 | user_id | VARCHAR | T | — | |
| 2 | device_id | VARCHAR | T | — | |
| 3 | seq_at | BIGINT | T | — | |
| 4 | file_id | VARCHAR | F | — | |
| 5 | created_at | TIMESTAMP | T | CURRENT_TIMESTAMP | |

---

## 2. LanceDB vectors_text

- **Path**: `~/.stratum/index/lance/vectors_text.lance/`
- **Row count**: 2
- **Schema**:
  - `id`: string — format `{ULID}#{chunk_idx}` (e.g. `01KRX5S8ZM3EF5F89YASCDHSEW#0`)
  - `embedding`: fixed_size_list<float>[1024] — Qwen3 dashscope text-embedding-v3
  - `metadata`: string (JSON) — `{"substrate_id": "...", "chunk_idx": 0}` or `{"derivative_id": "...", "chunk_idx": 0}`

**Sample records**:
```json
{"id": "01KRX5S8ZM3EF5F89YASCDHSEW#0", "metadata": {"substrate_id": "01KRX5S8ZM3EF5F89YASCDHSEW", "chunk_idx": 0}}
{"id": "01KS2MQHTQN7D0G6H3A8ZYWQHA#0", "metadata": {"derivative_id": "01KS2MQHTQN7D0G6H3A8ZYWQHA", "chunk_idx": 0}}
```

---

## 3. Python Dataclass / Pydantic Models

### 3.1 oprim/errors.py — Error Hierarchy

```
StratumError
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
└── (from omodul) AgentError
    ├── AgentToolNotAllowedError
    ├── AgentTimeoutError
    └── AgentNotFoundError
```

### 3.2 oprim/embedding — TextEmbedder Protocol

```python
class TextEmbedder(Protocol):
    def embed(self, texts: Sequence[str], dim: int = 1024) -> list[list[float]]: ...
    @property
    def model_name(self) -> str: ...
    @property
    def native_dim(self) -> int: ...

class Qwen3DashscopeEmbedder:
    model_name = "text-embedding-v3"
    native_dim = 1024
    # DashScope API, retry x3, batch max 10
```

### 3.3 oprim/push — PushDispatcher + PushChannel

```python
@dataclass
class PushResult:
    channel: str
    success: bool
    recipient: str
    error_message: str | None = None
    sent_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))

class PushChannel(Protocol):
    name: str
    async def send(self, recipient, title, body, deep_link=None, metadata=None) -> PushResult: ...
    async def health_check(self) -> bool: ...

class PushDispatcher:
    async def push(self, user_id, title, body, channels_preference=None, deep_link=None, metadata=None) -> list[PushResult]: ...
    # channels_preference default: ["web", "email"]
    # Tries in order, stops after first success
```

### 3.4 oskill/knowledge/hybrid_search.py — SearchResult

```python
@dataclass
class SearchResult:
    type: str          # "substrate" | "llm_augmented"
    id: str            # substrate_id or "llm-augmented-0"
    title: str
    score: float
    highlight: str | None
    metadata: dict     # {medium, source_type, domain, created_at}
    citation: dict | None  # {substrate_id, fragment_id, anchor, deep_link}

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
    time_range: str | None = None,  # "last_24h" | "last_7d" | "last_30d" | "last_90d"
) -> list[SearchResult]: ...
```

### 3.5 oskill/knowledge/ingest_substrate.py — IngestResult

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

### 3.6 oskill/knowledge/translate_substrate.py — TranslateResult

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
    chunk_results: list[TranslationResult] = field(default_factory=list)
```

### 3.7 omodul/knowledge/agents/base.py — Agent System

```python
@dataclass
class Citation:
    substrate_id: str
    title: str = ""
    fragment_id: str | None = None
    anchor: dict | None = None
    deep_link: str | None = None

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
class AgentContext:
    user_id: str
    agent_run_id: str
    invoked_at: datetime
    metadata: dict = field(default_factory=dict)

class Agent(ABC):
    name: str = ""
    description: str = ""
    allowed_tools: list[str] = []
    llm_provider: str = "qwen3_dashscope"
    llm_model: str = "qwen-max"
    temperature: float = 0.2
    timeout_seconds: int = 1800
    @abstractmethod
    async def run(self, params: dict, context: AgentContext) -> AgentResult: ...
```

### 3.8 omodul/knowledge/browser_extension/server.py — Pydantic Models

```python
class IngestRequest(BaseModel):
    url: str
    title: str
    html: Optional[str] = None
    selection_text: Optional[str] = None
    tags: list[str] = []
    create_note: bool = False
    note_content: Optional[str] = None

class IngestResponse(BaseModel):
    substrate_id: str
    note_id: Optional[str] = None
    deduplicated: bool
    message: str = ""

class SidebarSearchRequest(BaseModel):
    url: str
    page_title: str
    selected_text: Optional[str] = None
```

### 3.9 omodul/knowledge/scheduler/builtin_jobs.py — BUILTIN_JOB_SPECS

| name | agent_name | cron | enabled |
|------|-----------|------|---------|
| daily_inbox_process | knowledge_curator | 0 6 * * * | True |
| daily_digest | daily_digest | 0 8 * * * | True |
| weekly_lint | lint_bot | 0 7 * * 1 | True |
| nightly_translation | translation_worker | 0 2 * * * | False |
| nightly_audio_gen | audio_generator | 0 3 * * * | False |

### 3.10 omodul/knowledge/start_mcp_server.py — 8 MCP Tools

| tool | handler | phase |
|------|---------|-------|
| stratum.search | hybrid_search | 1 |
| stratum.fetch_substrate | DuckDB lookup | 1 |
| stratum.list_notes | DuckDB query | 1 |
| stratum.recent_changes | changefeed_local query | 1 |
| stratum.pin_substrate | UPDATE is_pinned=true | 1.5 |
| stratum.unpin_substrate | UPDATE is_pinned=false | 1.5 |
| stratum.list_views | views CRUD | 13 |
| stratum.set_default_view | views set_default | 13 |

---

## 4. Real Demo Data

### 4.1 Row Counts

| table | count |
|-------|-------|
| substrate | 5 |
| derivative | 9 |
| agent_runs | 13 |
| browser_ext_url_index | 3 |
| changefeed_events | 0 |
| changefeed_local | 6 |
| changefeed_snapshots | 0 |
| concept | 0 |
| note | 1 |
| push_subscriptions | 0 |
| scheduled_jobs | 0 |
| scheduled_job_runs | 0 |
| views | 0 |

### 4.2 Key Substrate Records

```json
{
  "id": "01KS2MD25C3FAAAD7B9KTF9ZM9",
  "title": "test_rag_paper",
  "meta_json": {"medium": "other", "source_type": "inbox_local", "source": {"user_id": "demo_user"}}
}
```
```json
{
  "id": "01KS2E3QK3KVN1WBVYSEEFAYT9",
  "title": "attention_is_all_you_need_9bks08iy",
  "meta_json": {"medium": "webpage", "source_type": "browser_extension", "source": {"type": "browser_extension", "url": "https://arxiv.org/abs/1706.03762", "title": "Attention Is All You Need", "tags": ["transformer", "nlp"]}}
}
```
```json
{
  "id": "01KRX5S8ZM3EF5F89YASCDHSEW",
  "title": "demo_note",
  "meta_json": {"medium": "markdown_note", "source_type": "inbox_local", "source": {"type": "inbox_local", "filename": "demo_note.md"}}
}
```

### 4.3 Key Derivative Records

```json
{"id": "01KS2MQHTQN7D0G6H3A8ZYWQHA", "substrate_id": "01KRX5S8ZM3EF5F89YASCDHSEW", "kind": "translation_zh-CN", "meta_json": {"source_lang": "auto", "target_lang": "zh-CN", "provider": "deepseek", "chunks": 1, "cost_usd": 0.0}}
```

Derivative kinds observed: `markdown`, `plaintext`, `translation_zh-CN`

### 4.4 Agent Run (completed)

```json
{
  "id": "748c306e-8ac0-4c30-98c5-6a4b962ee54f",
  "agent_name": "knowledge_curator",
  "status": "completed",
  "trace": [{"step_num": 1, "tool_name": "ingest_substrate", "tool_input": {"file": "/home/soffy/.stratum/inbox/test_rag_paper.md"}, "tool_output": {"substrate_id": "01KS2MD25C3FAAAD7B9KTF9ZM9", "medium": "other"}, "duration_ms": 311, "error": null, "timestamp": "2026-05-20T12:05:11.146744"}],
  "citations": [],
  "output": {"files_found": 1, "ingested": 1, "skipped": 0, "failed": 0},
  "total_input_tokens": 0,
  "total_output_tokens": 0,
  "cost_usd": 0.0,
  "started_at": "2026-05-20T12:05:10.750309",
  "completed_at": "2026-05-20T12:05:11.146788"
}
```

### 4.5 Browser Extension URL Index

```json
[
  {"id": "415ba8d8-ae4a-4f9a-b8ae-4f5587c20aa0", "url": "https://arxiv.org/abs/1706.03762", "normalized_url": "https://arxiv.org/abs/1706.03762", "substrate_id": "01KS2E3QK3KVN1WBVYSEEFAYT9"},
  {"id": "6e40e623-3e61-4315-a252-c25e0c1ff207", "url": "https://example.com/zh/attention-survey", "substrate_id": "01KS2E3TW4XXY4JWQJYA90AX1D"},
  {"id": "0efb031a-5fa7-4853-9ed6-0a2d88f9fdb7", "url": "https://example.com/paper/selected", "substrate_id": "01KS2E3Y6D4Z3XPGX8RJHYK138"}
]
```

### 4.6 Note

```json
{"id": "3bc57993-049a-49a6-bca7-1fa661f65648", "title": "Selected Passage Test", "content": "Key result: BLEU score benchmark", "wikilinks": "[]", "substrate_id": "01KS2E3Y6D4Z3XPGX8RJHYK138"}
```

### 4.7 Changefeed Local (sample)

```json
[
  {"seq": 1, "table_name": "substrate", "row_id": "01KRX5S8ZM3EF5F89YASCDHSEW", "op": "insert", "payload": "{\"substrate_id\": \"01KRX5S8ZM3EF5F89YASCDHSEW\"}", "ts": "2026-05-18T17:13:30.563263"},
  {"seq": 2, "table_name": "substrate", "row_id": "01KS2E3QK3KVN1WBVYSEEFAYT9", "op": "insert", "ts": "2026-05-20T18:15:16.954104"},
  {"seq": 3, "table_name": "substrate", "row_id": "01KS2E3TW4XXY4JWQJYA90AX1D", "op": "insert", "ts": "2026-05-20T18:15:20.404304"}
]
```

---

## 5. HTTP REST API (Browser Extension)

- **Port**: 14567 (default)
- **Base path**: `/api/v1/browser-extension/`
- **Auth**: `X-Stratum-Token` header
- **CORS**: `chrome-extension://*`, `moz-extension://*`, `ms-browser-extension://*`

| method | path | request | response |
|--------|------|---------|----------|
| GET | /health | — | `{"status": "ok", "version": "0.1.0"}` |
| POST | /ingest | IngestRequest | IngestResponse |
| POST | /sidebar-search | SidebarSearchRequest | `{"results": [...]}` |

---

## 6. Key Constants

- Embedding dim: **1024** (Qwen3 dashscope text-embedding-v3)
- Vector table: `vectors_text`
- RRF k: 60
- Pinned boost default: 1.5x
- Agent timeout default: 1800s
- Scheduler timezone default: `Asia/Shanghai`
- Max runtime default: 1800s
- MCP server version: 0.1.6
- Browser extension API version: 0.1.0

---

**End of Wave 0 ground truth.**
