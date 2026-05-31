# Stratum API v1 — Reference Specification

**Version**: 1.2.0  
**Last updated**: 2026-05-27  
**Scope**: Phase 11C (users/sessions/feedback/share) + Phase 14 (all endpoints, @helios/blocks 1.5.0 contracts)  
**OpenAPI supplement**: [`STRATUM_API_v1.openapi.json`](./STRATUM_API_v1.openapi.json)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Authentication Model](#2-authentication-model)
3. [Corpus Isolation Middleware](#3-corpus-isolation-middleware)
4. [Common Conventions](#4-common-conventions)
5. [Auth Endpoints](#5-auth-endpoints)
6. [Notes Endpoints](#6-notes-endpoints)
7. [Substrates Endpoints](#7-substrates-endpoints)
8. [Search Endpoints](#8-search-endpoints)
9. [Agents Endpoints](#9-agents-endpoints)
10. [Scheduled Jobs Endpoints](#10-scheduled-jobs-endpoints)
11. [Share Endpoints](#11-share-endpoints)
12. [Users Endpoints](#12-users-endpoints)
13. [Feedback Endpoints](#13-feedback-endpoints)
14. [Admin Endpoints](#14-admin-endpoints)
15. [Health Endpoint](#15-health-endpoint)
16. [Helios Block Data Contracts](#16-helios-block-data-contracts)
17. [Error Reference](#17-error-reference)
18. [Environment Variables](#18-environment-variables)
19. [Changelog](#19-changelog)

---

## 1. Architecture Overview

```
Browser / CLI
    │
    ▼
Next.js (port 3000)
    │  /api/* → rewrites → Stratum API  (STRATUM_API_PORT, default 9302)
    │  /share/[token] → Server Component (STRATUM_API_INTERNAL_URL, default http://localhost:9305)
    ▼
Stratum FastAPI  (port 9302 prod / 9305 dev / 9311 e2e)
    │  JWT Bearer auth on all /api/* except auth + public share + admin
    │  Corpus isolation middleware injects user_id + corpus_id per request
    ▼
DuckDB  (~/.stratum/meta.duckdb)
```

**Framework**: FastAPI 1.2.0  
**Database**: DuckDB (single-writer; all routes access via per-request connection)  
**ID format**: ULID strings for all entity IDs (sortable, URL-safe)  
**Time format**: ISO 8601 UTC throughout (`2026-05-27T12:00:00Z`)

---

## 2. Authentication Model

### 2.1 Token Types

| Token | Storage | TTL | Purpose |
|-------|---------|-----|---------|
| `access_token` | In-memory (JS) | 15 min | API authorization header |
| `refresh_token` | HTTP-only cookie | 30 days | Obtain new access token |

### 2.2 JWT Structure

```json
{
  "sub": "<user_id>",
  "corpus_id": "<corpus_id>",
  "exp": 1748347200,
  "iat": 1748346300
}
```

**Algorithm**: HS256  
**Secret**: `JWT_SECRET` env var (see §18)  
**`corpus_id`** = `"user_{user_id}"` — every user has exactly one corpus in v1.0

### 2.3 Access Token Usage

```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2.4 Token Lifecycle

```
POST /api/auth/login
  → access_token (15 min) + refresh_token cookie (30 days)

GET /api/auth/me  (with expired access token)
  → 401

POST /api/auth/refresh  (automatic, using cookie)
  → new access_token (15 min); refresh_token cookie unchanged

POST /api/auth/logout
  → refresh_token cookie deleted; session row revoked in DB
```

The frontend API client (`stratum-web/src/lib/api-client.ts`) automatically calls `/api/auth/refresh` on any 401 response and retries the original request once.

---

## 3. Corpus Isolation Middleware

**File**: `src/stratum/middleware/corpus_isolation.py`

All `/api/*` routes (except the exempt list below) pass through this middleware. It:
1. Reads the `Authorization: Bearer <token>` header
2. Verifies and decodes the JWT
3. Injects `request.state.user_id` and `request.state.corpus_id` into the request context
4. Passes the request through; each route handler reads these state values to scope DB queries

Routes that bypass corpus isolation:

| Pattern | Reason |
|---------|--------|
| `/api/auth/*` | Public — login/register/refresh |
| `/share/*` | Public share read (anonymous access) |
| `/api/users/by-username/*` | Public profile lookup |
| `/api/admin/*` | Uses X-Admin-Secret header instead |
| `/health` | Infrastructure probe |
| `/openapi.json`, `/docs`, `/redoc` | FastAPI dev tools |

---

## 4. Common Conventions

### 4.1 Request Format

- Content-Type: `application/json` for all POST/PUT bodies
- All fields are camelCase on the Next.js frontend; snake_case in the Python API
- The adapter layer (`stratum-web/src/lib/adapters/`) handles the translation

### 4.2 Pagination

List endpoints follow a consistent envelope:

```json
{
  "items": [...],
  "total": 42
}
```

No cursor/offset pagination in v1.0 — all lists return up to their default `limit`.

### 4.3 Empty vs. Null

- Missing optional fields: `null` (not omitted) in responses
- Empty lists: `[]` (not null)
- Empty objects: `{}` (not null)

### 4.4 ID Formats

| Entity | Format | Example |
|--------|--------|---------|
| `user_id` | ULID string | `01JSMKRQ9P7Q95YQGF1QJ934XV` |
| `corpus_id` | `"user_{user_id}"` | `user_01JSMKRQ9P7Q95YQGF1QJ934XV` |
| `note_id` | UUID v4 | `b3e2a1d0-...` |
| `substrate_id` | ULID | `01JSMKRQ9P7Q95YQGF1QZABCDE` |
| `session_id` | ULID | `01JSMKRQ9P7Q95YQGF1QJ934YZ` |
| `share_token` | Random base62 (16 chars) | `xUnNe7WeCTo42Wl0` |

---

## 5. Auth Endpoints

**Prefix**: `/api/auth`  
**Auth**: None (all public)

---

### POST `/api/auth/register`

Register a new user account.

**Request body**:

```json
{
  "email": "user@example.com",
  "username": "myusername",
  "password": "s3cure-passphrase"
}
```

| Field | Type | Constraints |
|-------|------|-------------|
| `email` | string | Valid email format; must be unique |
| `username` | string | 3–32 chars; alphanumeric + underscore; must be unique |
| `password` | string | Minimum 10 characters |

**Response 200**:

```json
{
  "user_id": "01JSMKRQ9P7Q95YQGF1QJ934XV",
  "email": "user@example.com",
  "username": "myusername",
  "verify_email_sent": false
}
```

**Errors**:

| Status | Condition |
|--------|-----------|
| 400 | Email already registered |
| 400 | Username already taken |
| 400 | Password too short (<10 chars) |
| 422 | Invalid email format |

**Notes**: `verify_email_sent` is always `false` in v1.0 (email verification not yet implemented).

---

### POST `/api/auth/login`

Authenticate with email/username + password.

**Request body**:

```json
{
  "email_or_username": "user@example.com",
  "password": "s3cure-passphrase"
}
```

**Response 200**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900,
  "user": {
    "user_id": "01JSMKRQ9P7Q95YQGF1QJ934XV",
    "email": "user@example.com",
    "username": "myusername",
    "email_verified": false,
    "created_at": "2026-05-27T10:00:00Z"
  }
}
```

**Side effect**: Sets `refresh_token` as an HTTP-only, `SameSite=Lax`, `Secure` cookie with 30-day expiry. A new session row is created in the DB.

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | Invalid credentials |

---

### POST `/api/auth/refresh`

Exchange the `refresh_token` cookie for a new `access_token`.

**Request**: No body. Reads `refresh_token` cookie automatically.

**Response 200**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900
}
```

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | Cookie missing, token invalid, token expired, or session revoked |

---

### POST `/api/auth/logout`

Revoke the current session.

**Request**: No body. Reads `refresh_token` cookie.

**Response 200**:

```json
{ "status": "ok" }
```

**Side effects**:
- Deletes `refresh_token` cookie (sets it to empty with immediate expiry)
- Marks the matching session row as revoked in DB

No error is returned if the cookie is absent — logout is always idempotent.

---

### GET `/api/auth/me`

Get the currently authenticated user's profile.

**Auth**: Bearer JWT required

**Response 200**:

```json
{
  "user_id": "01JSMKRQ9P7Q95YQGF1QJ934XV",
  "email": "user@example.com",
  "username": "myusername",
  "email_verified": false,
  "created_at": "2026-05-27T10:00:00Z"
}
```

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 404 | User record deleted (edge case) |

---

## 6. Notes Endpoints

**Prefix**: `/api`  
**Auth**: Bearer JWT (corpus-isolated)

Notes are Markdown documents stored in the user's corpus. They are created via the CLI (`stratum add`) and read via the API. Write/delete via API is not supported in v1.0.

---

### GET `/api/notes/{note_id}`

Fetch a note by ID.

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `note_id` | string | UUID v4 of the note |

**Response 200**:

```json
{
  "id": "b3e2a1d0-4f5a-4e6b-8c9d-0a1b2c3d4e5f",
  "title": "Attention Is All You Need",
  "content": "# Attention Is All You Need\n\nThe dominant sequence...",
  "wikilinks": ["[[Transformer]]", "[[BERT]]"],
  "substrate_id": "01JSMKRQ9P7Q95YQGF1QZABCDE",
  "meta_json": {},
  "created_at": "2026-05-01T08:00:00Z",
  "updated_at": "2026-05-20T14:30:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | UUID v4 |
| `title` | string \| null | Extracted from first `# heading` |
| `content` | string \| null | Full raw Markdown |
| `wikilinks` | string[] | All `[[wikilink]]` references found in content |
| `substrate_id` | string \| null | ID of the source substrate (if note was derived from a document) |
| `meta_json` | object | Arbitrary note metadata |
| `created_at` | string | ISO 8601 UTC |
| `updated_at` | string | ISO 8601 UTC |

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 404 | Note not found, or note belongs to another user's corpus |

**Used by**: `ODocumentReader` (note view), `OBacklinkPanel` (via `/backlinks`)

---

### GET `/api/notes/{note_id}/backlinks`

Get all notes that contain a wikilink pointing to the given note.

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `note_id` | string | UUID v4 of the target note |

**Response 200**:

```json
{
  "items": [
    {
      "id": "a1b2c3d4-...",
      "title": "My Reading Notes",
      "snippet": "See also [[Attention Is All You Need]] for the original..."
    }
  ],
  "total": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items[].id` | string | UUID v4 of the referencing note |
| `items[].title` | string | Title of the referencing note |
| `items[].snippet` | string \| null | First 100 chars of the referencing note's content |
| `total` | integer | Total count (equal to `items.length` in v1.0) |

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 404 | Note not found |

**Used by**: `OBacklinkPanel`

---

## 7. Substrates Endpoints

**Prefix**: `/api`  
**Auth**: Bearer JWT (corpus-isolated)

Substrates are source documents imported via the CLI (PDFs, webpages, Markdown files, etc.). Each substrate can have multiple derivatives (parsed text, summaries, translations).

---

### GET `/api/substrates`

List all substrates in the user's corpus.

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `medium` | string \| null | — | Filter by medium (`paper`, `webpage`, `markdown_note`, etc.) |
| `limit` | integer | 50 | Maximum items to return |

**Response 200**:

```json
{
  "items": [
    {
      "id": "01JSMKRQ9P7Q95YQGF1QZABCDE",
      "title": "Attention Is All You Need",
      "mime": "application/pdf",
      "language": "en",
      "page_count": 15,
      "created_at": "2026-05-01T08:00:00Z"
    }
  ],
  "total": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items[].id` | string | ULID |
| `items[].title` | string \| null | Document title |
| `items[].mime` | string \| null | MIME type (`application/pdf`, `text/markdown`, `text/html`, …) |
| `items[].language` | string \| null | ISO 639-1 language code |
| `items[].page_count` | integer \| null | Page count (PDFs only) |
| `items[].created_at` | string \| null | ISO 8601 UTC |
| `total` | integer | Total in corpus (may exceed `items.length` if limit applied) |

**Used by**: `ODocumentTree`

---

### GET `/api/substrates/{substrate_id}`

Fetch a single substrate by ID.

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `substrate_id` | string | ULID |

**Response 200**: Single substrate object (same shape as `items[]` above, not wrapped).

```json
{
  "id": "01JSMKRQ9P7Q95YQGF1QZABCDE",
  "title": "Attention Is All You Need",
  "mime": "application/pdf",
  "language": "en",
  "page_count": 15,
  "created_at": "2026-05-01T08:00:00Z"
}
```

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 404 | Substrate not found or belongs to another corpus |

**Used by**: `ODocumentReader` (document view)

---

### GET `/api/substrates/{substrate_id}/derivatives`

Get all derivatives for a substrate (parsed text, summaries, translations).

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `substrate_id` | string | ULID |

**Response 200**:

```json
{
  "items": [
    {
      "id": "01JSMKRQ9P7Q95YQGF1QABCDEF",
      "kind": "markdown",
      "seq": 0,
      "content": "# Attention Is All You Need\n\n..."
    },
    {
      "id": "01JSMKRQ9P7Q95YQGF1QABCDEG",
      "kind": "summary",
      "seq": 0,
      "content": "This paper introduces the Transformer architecture..."
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items[].id` | string | ULID |
| `items[].kind` | string | Derivative type (see below) |
| `items[].seq` | integer | Version sequence (0 = first; higher = newer) |
| `items[].content` | string \| null | Text content |

**Derivative kinds**:

| Kind | Description |
|------|-------------|
| `markdown` | Parsed Markdown from source document |
| `plaintext` | Plain text extraction |
| `summary` | LLM-generated summary |
| `note` | Handwritten annotation note |
| `tag` | Comma-separated tags |
| `translation_{lang}` | Translation to target language (e.g. `translation_zh-CN`) |

**Used by**: `ODocumentReader` (document view — renders `markdown` derivative in bilingual mode)

---

## 8. Search Endpoints

**Prefix**: `/api`  
**Auth**: Bearer JWT (corpus-isolated)

---

### POST `/api/search`

Run semantic + keyword search over the user's corpus.

**Request body**:

```json
{
  "query": "attention mechanism transformer",
  "top_k": 10,
  "mode": "augmented",
  "rerank": false,
  "expand": false,
  "view_id": null,
  "filter_medium": null
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query text |
| `top_k` | integer | 10 | Max results to return |
| `mode` | `"strict"` \| `"augmented"` | `"augmented"` | Strict = keyword only; augmented = semantic + keyword |
| `rerank` | boolean | false | Apply cross-encoder reranking (slower but more accurate) |
| `expand` | boolean | false | Query expansion via LLM |
| `view_id` | string \| null | null | Filter to a named view (future feature) |
| `filter_medium` | string[] \| null | null | Restrict to specific mediums |

**Response 200**:

```json
{
  "results": [
    {
      "id": "01JSMKRQ9P7Q95YQGF1QZABCDE",
      "type": "substrate",
      "title": "Attention Is All You Need",
      "score": 0.92,
      "highlight": "...the dominant sequence transduction models..."
    }
  ],
  "query_used": "attention mechanism transformer"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `results[].id` | string | ULID of the matching substrate |
| `results[].type` | string | `"substrate"` \| `"llm_augmented"` |
| `results[].title` | string | Document title |
| `results[].score` | float | Relevance score (0–1) |
| `results[].highlight` | string \| null | Matching passage excerpt |
| `query_used` | string | Actual query sent to search engine (may differ from input if expanded) |

**Used by**: `OSemanticSearch`

---

## 9. Agents Endpoints

**Prefix**: `/api`  
**Auth**: Bearer JWT (corpus-isolated)

Agents are named async tasks that run over the corpus. In v1.0 the backend returns a stub response immediately; production would dispatch to an agent worker.

**Available agent names**:

| Name | Description |
|------|-------------|
| `reading_companion` | Q&A over selected documents |
| `daily_digest` | Daily summary digest |
| `knowledge_curator` | Auto-tagging + linking |
| `translation_worker` | Document translation |
| `lint_bot` | Note quality linter |
| `audio_generator` | TTS (unavailable in v1.0 — TTS torch conflict) |

---

### POST `/api/agents/{agent_name}/run`

Trigger an agent run.

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `agent_name` | string | Agent identifier (see table above) |

**Request body**:

```json
{
  "params": {
    "query": "What are the key contributions of this paper?"
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `params` | object | `{}` | Agent-specific parameters |

**`reading_companion` params**:

| Param | Type | Description |
|-------|------|-------------|
| `query` | string | The question to ask |

**Response 200**:

```json
{
  "agent_run": {
    "id": "01JSMKRQ9P7Q95YQGF1QRUN001",
    "agent_name": "reading_companion",
    "status": "pending",
    "output": null,
    "started_at": null,
    "completed_at": null,
    "error_message": null
  },
  "message": "Agent execution is not available in this environment"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `agent_run.id` | string | ULID of the run record |
| `agent_run.agent_name` | string | Agent name |
| `agent_run.status` | string | `"pending"` \| `"running"` \| `"completed"` \| `"failed"` |
| `agent_run.output` | string \| null | Agent output text |
| `agent_run.started_at` | string \| null | ISO 8601 UTC |
| `agent_run.completed_at` | string \| null | ISO 8601 UTC |
| `agent_run.error_message` | string \| null | Error description if `status == "failed"` |
| `message` | string | Human-readable status message |

**Used by**: `OAIQAPanel` (calls `reading_companion`), `OScheduledJobsManager` (run-now for any agent)

---

### GET `/api/agents/runs`

List agent run history.

**Query parameters**:

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `agent` | string \| null | — | Filter by agent name |
| `limit` | integer | 20 | Max items to return |

**Response 200**:

```json
{
  "items": [
    {
      "id": "01JSMKRQ9P7Q95YQGF1QRUN001",
      "agent_name": "daily_digest",
      "status": "completed",
      "output": "今日摘要：您的语料库新增了 3 篇文档...",
      "started_at": "2026-05-27T06:00:00Z",
      "completed_at": "2026-05-27T06:02:30Z",
      "error_message": null
    }
  ],
  "total": 1
}
```

**Used by**: `OAISummaryCard` (fetches `?agent=daily_digest` runs)

---

## 10. Scheduled Jobs Endpoints

**Prefix**: `/api`  
**Auth**: Bearer JWT (corpus-isolated)

---

### GET `/api/scheduled_jobs`

List all scheduled jobs for the user.

**Response 200**:

```json
{
  "items": [
    {
      "id": "01JSMKRQ9P7Q95YQGF1QJOB001",
      "name": "Daily Digest",
      "agent_name": "daily_digest",
      "cron_expression": "0 6 * * *",
      "timezone": "Asia/Shanghai",
      "enabled": true,
      "created_at": "2026-05-01T10:00:00Z"
    }
  ],
  "total": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items[].id` | string | ULID |
| `items[].name` | string | Human-readable job name |
| `items[].agent_name` | string | Agent to invoke |
| `items[].cron_expression` | string | Standard 5-field cron (e.g. `"0 6 * * *"`) |
| `items[].timezone` | string | IANA timezone (default `"Asia/Shanghai"`) |
| `items[].enabled` | boolean | Whether the job is active |
| `items[].created_at` | string \| null | ISO 8601 UTC |
| `total` | integer | Total count |

**Used by**: `OScheduledJobsManager`

---

### POST `/api/scheduled_jobs`

Create a new scheduled job.

**Request body**:

```json
{
  "name": "Evening Digest",
  "agent_name": "daily_digest",
  "agent_params": {},
  "cron_expression": "0 20 * * *",
  "timezone": "Asia/Shanghai",
  "enabled": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | string | required | Job name |
| `agent_name` | string | required | Agent to invoke |
| `agent_params` | object | `{}` | Params passed to the agent on each run |
| `cron_expression` | string | required | 5-field cron expression |
| `timezone` | string | `"Asia/Shanghai"` | IANA timezone |
| `enabled` | boolean | `true` | Start enabled |

**Response 200**: The created job object (same shape as `GET` items).

**DB defaults set on creation**:
- `notify_on_completion`: `false`
- `notify_on_failure`: `false`
- `max_runtime_seconds`: `300`

---

### PUT `/api/scheduled_jobs/{job_id}`

Update a scheduled job (partial update).

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `job_id` | string | ULID of the job |

**Request body** (all fields optional):

```json
{
  "enabled": false,
  "cron_expression": "0 8 * * 1-5",
  "name": "Weekday Digest"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `enabled` | boolean \| null | Toggle job on/off |
| `cron_expression` | string \| null | New cron schedule |
| `name` | string \| null | New display name |

**Response 200**: Updated job object.

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 404 | Job not found or belongs to another user |

**Used by**: `OScheduledJobsManager` (toggle enabled)

---

### DELETE `/api/scheduled_jobs/{job_id}`

Delete a scheduled job.

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `job_id` | string | ULID of the job |

**Response 200**:

```json
{ "status": "deleted" }
```

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 404 | Job not found or belongs to another user |

**Note**: Builtin jobs (`daily_digest`, `reading_companion`) are marked `is_builtin: true` by the frontend adapter and cannot be deleted via the UI (adapter guard). The API does not enforce this restriction — the guard is frontend-only.

**Used by**: `OScheduledJobsManager`

---

## 11. Share Endpoints

**Prefix**: none (full path in each route)  
**Auth**: Mixed — authenticated for create/list/revoke; public for read

---

### POST `/api/share/note/{note_id}`

Create a public share link for a note.

**Auth**: Bearer JWT required

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `note_id` | string | UUID v4 of the note to share |

**Request body**:

```json
{
  "expires_in_days": 30,
  "allow_anonymous": true
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `expires_in_days` | integer \| null | null | Days until expiry; null = never expires |
| `allow_anonymous` | boolean | `true` | Currently always true (enforced by backend) |

**Response 200**:

```json
{
  "token": "xUnNe7WeCTo42Wl0",
  "share_url": "/share/xUnNe7WeCTo42Wl0",
  "expires_at": "2026-06-26T10:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `token` | string | 16-char random base62 token |
| `share_url` | string | Relative URL path for the share page |
| `expires_at` | string \| null | ISO 8601 UTC; null if no expiry |

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 404 | Note not found or belongs to another user |

---

### GET `/api/shares`

List all active share tokens owned by the authenticated user.

**Auth**: Bearer JWT required

**Response 200**:

```json
{
  "items": [
    {
      "token": "xUnNe7WeCTo42Wl0",
      "resource_type": "note",
      "resource_id": "b3e2a1d0-...",
      "created_at": "2026-05-27T10:00:00Z",
      "expires_at": "2026-06-26T10:00:00Z",
      "access_count": 7
    }
  ],
  "total": 1
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items[].token` | string | Share token |
| `items[].resource_type` | string | `"note"` (only type in v1.0) |
| `items[].resource_id` | string | UUID v4 of the shared note |
| `items[].created_at` | string | ISO 8601 UTC |
| `items[].expires_at` | string \| null | ISO 8601 UTC; null if no expiry |
| `items[].access_count` | integer | Number of times the share page was accessed |
| `total` | integer | Total count |

---

### DELETE `/api/share/{token}`

Revoke a share token.

**Auth**: Bearer JWT required

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `token` | string | The share token to revoke |

**Response 200**:

```json
{ "status": "revoked" }
```

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 403 | Token exists but belongs to another user |

---

### GET `/share/{token}`

Fetch a publicly shared note. **No authentication required.**

This endpoint is served by the FastAPI backend and consumed by the Next.js `share/[token]` Server Component via a server-side fetch (not proxied through `/api/*`).

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `token` | string | The share token |

**Response 200**:

```json
{
  "title": "Attention Is All You Need",
  "content": "# Attention Is All You Need\n\nThe dominant sequence...",
  "shared_by_username": "myusername",
  "shared_at": "2026-05-27T10:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Note title |
| `content` | string | Note content — private wikilinks (`[[_private...]]`) are replaced with `[私有引用]` |
| `shared_by_username` | string | Username of the note owner |
| `shared_at` | string | ISO 8601 UTC when share was created |

**Privacy guarantee**: The response never includes `user_id`, `corpus_id`, or `email`. Wikilinks starting with `_` (private namespace convention) are redacted.

**Side effect**: Increments `access_count` on the share token row.

**Errors**:

| Status | Condition |
|--------|-----------|
| 404 | Token not found, resource not found, or unsupported resource type |
| 410 | Share token revoked or expired |

---

## 12. Users Endpoints

**Prefix**: `/api/users`  
**Auth**: Mixed (see per-endpoint notes)

---

### GET `/api/users/by-username/{username}`

Look up a user's public profile by username. **No authentication required.**

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `username` | string | The username to look up |

**Response 200**:

```json
{
  "username": "myusername",
  "display_name": null,
  "bio": null,
  "avatar_url": null,
  "created_at": "2026-05-01T10:00:00Z"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `username` | string | Username |
| `display_name` | string \| null | Optional display name (v1.0: always null) |
| `bio` | string \| null | Short bio (v1.0: always null) |
| `avatar_url` | string \| null | Avatar URL (v1.0: always null) |
| `created_at` | string | ISO 8601 UTC |

**Errors**:

| Status | Condition |
|--------|-----------|
| 404 | User not found, not active, or suspended |

---

### GET `/api/users/me/sessions`

List all active sessions for the authenticated user.

**Auth**: Bearer JWT required

**Response 200**:

```json
{
  "items": [
    {
      "id": "01JSMKRQ9P7Q95YQGF1QSESSION",
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
      "ip_address": "192.168.1.x",
      "created_at": "2026-05-27T10:00:00Z",
      "last_used_at": "2026-05-27T11:30:00Z",
      "is_current": true
    }
  ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `items[].id` | string | ULID of the session |
| `items[].user_agent` | string \| null | Browser User-Agent string |
| `items[].ip_address` | string \| null | Truncated to max 16 chars for privacy |
| `items[].created_at` | string | ISO 8601 UTC — when session was created |
| `items[].last_used_at` | string | ISO 8601 UTC — last refresh token use |
| `items[].is_current` | boolean | Whether this session matches the current `refresh_token` cookie |

**Used by**: Settings page → Sessions tab

---

### DELETE `/api/users/me/sessions/{session_id}`

Revoke a specific session (remote logout).

**Auth**: Bearer JWT required

**Path parameters**:

| Param | Type | Description |
|-------|------|-------------|
| `session_id` | string | ULID of the session to revoke |

**Response 200**:

```json
{ "status": "revoked" }
```

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 404 | Session not found or does not belong to this user |

---

## 13. Feedback Endpoints

**Prefix**: `/api`  
**Auth**: Bearer JWT required

---

### POST `/api/feedback`

Submit in-app feedback during the alpha period.

**Request body**:

```json
{
  "content": "The search results are very relevant. Would love PDF export.",
  "page_url": "/search"
}
```

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `content` | string | 1–2000 chars | Feedback text |
| `page_url` | string \| null | — | The page the user was on when submitting |

**Response 200**:

```json
{ "status": "received" }
```

**Errors**:

| Status | Condition |
|--------|-----------|
| 401 | JWT missing or invalid |
| 422 | `content` empty or exceeds 2000 chars |

---

## 14. Admin Endpoints

**Prefix**: `/api`  
**Auth**: `X-Admin-Secret` header (HMAC comparison — see §18)

Admin endpoints are not served to browsers. They require a secret header verified via constant-time HMAC comparison to prevent timing attacks.

---

### GET `/api/admin/stats`

Get aggregate platform statistics.

**Required header**:

```http
X-Admin-Secret: <secret>
```

**Response 200**:

```json
{
  "users": 142,
  "substrates": 3891,
  "active_sessions": 38,
  "feedback_submissions": 27,
  "share_links": 94
}
```

| Field | Type | Description |
|-------|------|-------------|
| `users` | integer | Total registered users |
| `substrates` | integer | Total documents across all corpora |
| `active_sessions` | integer | Non-revoked, non-expired session rows |
| `feedback_submissions` | integer | Total feedback items received |
| `share_links` | integer | Total share tokens created (including revoked) |

**Errors**:

| Status | Condition |
|--------|-----------|
| 403 | `X-Admin-Secret` missing or does not match `ADMIN_SECRET` env var |
| 503 | `ADMIN_SECRET` env var is not configured |

---

## 15. Health Endpoint

---

### GET `/health`

Health probe. Returns immediately without touching the database.

**Auth**: None  
**Middleware**: Bypasses corpus isolation

**Response 200**:

```json
{ "status": "healthy" }
```

Used by: docker-compose healthcheck, load balancers, monitoring systems.

---

## 16. Helios Block Data Contracts

This section documents the exact data shapes that `@helios/blocks` 1.5.0 components expect, and how Stratum's API responses are adapted to meet those contracts. All adapters live in `stratum-web/src/lib/adapters/`.

### 16.1 Core Type Definitions

These types are shared across multiple blocks.

#### `Note`

```typescript
interface Note {
  id: string;            // UUID v4
  title: string | null;
  content: string | null; // Raw Markdown
  wikilinks: string[];   // e.g. ["[[Attention Is All You Need]]"]
  substrate_id: string | null;
  meta_json: Record<string, unknown>;
  created_at: string;    // ISO 8601
  updated_at: string;
}
```

**API source**: `GET /api/notes/{id}`

#### `Substrate`

```typescript
interface Substrate {
  id: string;            // ULID
  ulid: string;          // = id (redundant field required by Helios 1.5)
  title: string | null;
  mime: string | null;
  source_path: string | null;
  file_hash: string | null;  // SHA-256
  byte_size: number | null;
  page_count: number | null;
  parser: string | null;
  language: string | null;
  has_cjk: boolean;
  is_scanned: boolean;
  created_at: string;    // ISO 8601
  updated_at: string;
  is_pinned: boolean;
  pinned_at: string | null;
  meta_json: {
    medium: Medium;
    source_type: SourceType;
    source: Record<string, unknown>;
  };
}

type Medium =
  | 'webpage' | 'paper' | 'book' | 'markdown_note'
  | 'transcript' | 'chat' | 'other';

type SourceType =
  | 'browser_extension' | 'inbox_local' | 'gdrive_sync';
```

**API source**: `GET /api/substrates/{id}` (document) or synthesized from `Note` (note view)  
**Adapter gap-fills**: `source_path`, `file_hash`, `byte_size`, `parser` → `null`; `has_cjk`, `is_scanned`, `is_pinned` → `false`

#### `Derivative`

```typescript
interface Derivative {
  id: string;             // ULID
  substrate_id: string;   // FK → Substrate.id
  kind: DerivativeKind;
  seq: number;            // Version sequence; 0 = first
  content: string | null;
  embedding_id: string | null;   // unused in v1.0
  embedding_dim: number | null;
  meta_json: Record<string, unknown>;
  created_at: string;     // ISO 8601
}

type DerivativeKind =
  | 'markdown' | 'plaintext' | 'summary' | 'note' | 'tag'
  | `translation_${string}`;
```

**API source**: `GET /api/substrates/{id}/derivatives`  
**Adapter gap-fills**: `embedding_id` → `null`, `embedding_dim` → `null`, `created_at` → `new Date().toISOString()`

#### `Citation` / `AgentCitation`

```typescript
interface Citation {
  substrate_id: string;
  title?: string;
  fragment_id: string | null;  // "{substrate_id}#{chunk_idx}"
  anchor: FragmentAnchor | null;
  deep_link: string | null;    // "stratum://substrate/{id}/#{fragment_id}"
}

interface AgentCitation extends Citation {}
// Same shape; separate type for agent-sourced citations
```

---

### 16.2 OSemanticSearch

**Adapter**: `stratum-web/src/lib/adapters/search.ts`  
**Hook**: `useStratumSearch()`

```typescript
// Block props
interface OSemanticSearchProps {
  onSearch: (query: string) => Promise<SearchResult[]>; // REQUIRED
  onResultClick?: (result: SearchResult) => void;
  placeholder?: string;
  defaultQuery?: string;
  query?: string;            // controlled
  onQueryChange?: (q: string) => void;
  showScore?: boolean;       // default: true
  showHighlight?: boolean;   // default: true
}

// Helios SearchResult shape (what the block receives)
interface SearchResult {
  id: string;
  type: 'substrate' | 'llm_augmented';
  title: string;
  score: number;
  highlight: string | null;
  metadata: {
    medium: string | null;
    source_type: string | null;
    domain: string | null;
    created_at: string | null;
  };
  citation: Citation | null;
}
```

**API call**: `POST /api/search`

**Adaptation** (backend `SearchResultItem` → Helios `SearchResult`):

```typescript
// Backend shape
interface SearchResultItem {
  id: string;
  type: string;
  title: string;
  score: number;
  highlight?: string | null;
}

// Adapter adds missing Helios fields with defaults
function adapt(item: SearchResultItem): SearchResult {
  return {
    ...item,
    highlight: item.highlight ?? null,
    metadata: { medium: null, source_type: null, domain: null, created_at: null },
    citation: null,
  };
}
```

---

### 16.3 OAIQAPanel

**Adapter**: `stratum-web/src/lib/adapters/agents.ts`  
**Hook**: `useAgentQA()`

```typescript
// Block props
interface OAIQAPanelProps {
  onAsk: (question: string) => Promise<QAResponse>; // REQUIRED
  history?: QATurn[];
  onTurnComplete?: (turn: QATurn) => void;
  placeholder?: string;
  maxHistory?: number; // default: 5
}

interface QAResponse {
  answer: string;
  citations: Array<Citation | AgentCitation>;
  sources_used?: number;
}

interface QATurn {
  question: string;
  answer: string;
  citations: Array<Citation | AgentCitation>;
}
```

**API call**: `POST /api/agents/reading_companion/run` with `{ params: { query } }`

**Adaptation** (`RunAgentResponse` → `QAResponse`):

```typescript
function adapt(res: RunAgentResponse): QAResponse {
  return {
    answer: res.agent_run.output ?? res.message,
    citations: [],
    sources_used: undefined,
  };
}
```

---

### 16.4 OAISummaryCard

**Adapter**: `stratum-web/src/lib/adapters/agents.ts`  
**Hook**: `useAgentSummaries()`

```typescript
// Block props
interface OAISummaryCardProps {
  title?: string;        // default: "每日摘要"
  date?: string;         // ISO 8601
  summary: string;       // REQUIRED
  newSubstrates?: number;
  digestSent?: boolean;
  citations?: Array<Citation | AgentCitation>;
  onCitationClick?: (c: Citation | AgentCitation) => void;
}
```

**API call**: `GET /api/agents/runs?agent=daily_digest&limit=5`

**Adaptation** (`AgentRun` → `OAISummaryCardProps`):

```typescript
function adapt(run: AgentRun) {
  return {
    summary: run.output ?? "摘要生成中...",
    date: run.started_at ?? undefined,
    digestSent: run.status === "completed",
    citations: [],
  };
}
```

---

### 16.5 OScheduledJobsManager

**Adapter**: `stratum-web/src/lib/adapters/jobs.ts`  
**Hook**: `useScheduledJobs()`

```typescript
// Block props
interface OScheduledJobsManagerProps {
  jobs: ScheduledJobWithStatus[];  // REQUIRED
  onToggleEnabled?: (job: ScheduledJobWithStatus, newEnabled: boolean) => void;
  onEditCron?: (job: ScheduledJobWithStatus) => void;  // ⚠️ not implemented
  onDelete?: (job: ScheduledJobWithStatus) => void;
  onRunNow?: (job: ScheduledJobWithStatus) => void;
}

// Helios ScheduledJobWithStatus (superset of backend ScheduledJob)
interface ScheduledJobWithStatus {
  id: string;
  user_id: string;       // adapter sets ""
  name: string;
  agent_name: AgentName;
  agent_params: string;  // JSON string — adapter sets "{}"
  cron_expression: string;
  timezone: string;
  enabled: boolean;
  notify_on_completion: boolean;  // adapter sets false
  notify_on_failure: boolean;     // adapter sets false
  max_runtime_seconds: number;    // adapter sets 300
  created_at: string;
  updated_at: string;
  is_builtin?: boolean;           // true for daily_digest, reading_companion
  next_run_at?: string | null;    // computed by frontend (cron-parser)
  last_run_at?: string | null;    // not available from backend in v1.0
  last_status?: 'running' | 'completed' | 'failed' | 'timeout' | null;
}

type AgentName =
  | 'knowledge_curator' | 'reading_companion' | 'daily_digest'
  | 'translation_worker' | 'lint_bot' | 'audio_generator';
```

**API calls**:
- `GET /api/scheduled_jobs` — list
- `PUT /api/scheduled_jobs/{id}` with `{ enabled: boolean }` — toggle
- `DELETE /api/scheduled_jobs/{id}` — delete
- `POST /api/scheduled_jobs` with `{ name, agent_name, cron_expression }` — create
- `POST /api/agents/{agent_name}/run` — run-now

**Known gap**: `onEditCron` is passed to the block but no UI is wired to it. `next_run_at` and `last_run_at` are not populated from the backend (Phase 15 work).

---

### 16.6 ODocumentTree

**Adapter**: `stratum-web/src/lib/adapters/documents.ts`  
**Hook**: `useDocumentTree()`

```typescript
// Block props
interface ODocumentTreeProps {
  substrates: Substrate[];  // REQUIRED
  selectedId?: string;
  onSelect?: (substrate: Substrate) => void;
  defaultExpandedMediums?: Medium[];
  emptyText?: string;       // default: "暂无文档，请通过 CLI 导入文件"
}
```

**API call**: `GET /api/substrates?limit=200`

**Adaptation** (`SubstrateItem` → `Substrate`):

```typescript
function adaptSubstrate(item: SubstrateItem): Substrate {
  return {
    id: item.id,
    ulid: item.id,
    title: item.title ?? null,
    mime: item.mime ?? null,
    source_path: null,
    file_hash: null,
    byte_size: null,
    page_count: item.page_count ?? null,
    parser: null,
    language: item.language ?? null,
    has_cjk: false,
    is_scanned: false,
    created_at: item.created_at ?? new Date().toISOString(),
    updated_at: item.created_at ?? new Date().toISOString(),
    is_pinned: false,
    pinned_at: null,
    meta_json: {
      medium: inferMedium(item.mime),  // maps MIME → Medium
      source_type: "inbox_local",
      source: {},
    },
  };
}

// MIME → Medium mapping
function inferMedium(mime: string | null | undefined): Medium {
  if (!mime) return "other";
  if (mime === "application/pdf") return "paper";
  if (mime === "text/markdown") return "markdown_note";
  if (mime.startsWith("text/html")) return "webpage";
  return "other";
}
```

---

### 16.7 ODocumentReader — Document View

**Adapter**: `stratum-web/src/lib/adapters/documents.ts`  
**Hook**: `useDocumentReader(substrateId)`

```typescript
// Block props
interface ODocumentReaderProps {
  substrate: Substrate;      // REQUIRED
  derivatives: Derivative[]; // REQUIRED
  defaultMode?: ReaderMode;  // default: "original"
  onTogglePin?: (substrate: Substrate, newPinned: boolean) => void;
}

type ReaderMode = 'original' | 'bilingual' | 'translation';
```

**API calls**:
- `GET /api/substrates/{id}` → `SubstrateItem` → adapted to `Substrate`
- `GET /api/substrates/{id}/derivatives` → `DerivativeItem[]` → adapted to `Derivative[]`

**Adaptation** (`DerivativeItem` → `Derivative`):

```typescript
function adaptDerivative(item: DerivativeItem, substrateId: string): Derivative {
  return {
    id: item.id,
    substrate_id: substrateId,
    kind: item.kind as Derivative["kind"],
    seq: item.seq,
    content: item.content ?? null,
    embedding_id: null,
    embedding_dim: null,
    meta_json: {},
    created_at: new Date().toISOString(),
  };
}
```

---

### 16.8 ODocumentReader — Note View

**Adapter**: `stratum-web/src/lib/adapters/notes.ts`  
**Usage**: `notes/[id]/page.tsx`

Notes are rendered in `ODocumentReader` by synthesizing a `Substrate` + `Derivative[]` from the `Note` object. This allows the same bilingual reader UI to handle both documents and notes.

**API call**: `GET /api/notes/{id}` → `NoteDetail` → synthesized `Substrate` + `Derivative[]`

**Synthesis logic**:

```typescript
function noteToReaderProps(note: Note): { substrate: Substrate; derivatives: Derivative[] } {
  const substrate: Substrate = {
    id: note.id,
    ulid: note.id,
    title: note.title,
    mime: "text/markdown",
    source_path: null,
    file_hash: null,
    byte_size: null,
    page_count: null,
    parser: null,
    language: null,
    has_cjk: false,
    is_scanned: false,
    created_at: note.created_at,
    updated_at: note.updated_at,
    is_pinned: false,
    pinned_at: null,
    meta_json: { medium: "markdown_note", source_type: "inbox_local", source: {} },
  };

  const derivatives: Derivative[] = note.content
    ? [{
        id: `${note.id}#0`,
        substrate_id: note.id,
        kind: "translation_zh-zh",  // bilingual rendering of same-language note
        seq: 0,
        content: note.content,
        embedding_id: null,
        embedding_dim: null,
        meta_json: {},
        created_at: note.created_at,
      }]
    : [];

  return { substrate, derivatives };
}
```

**Display behavior**: When no source document is attached (`substrate_id == null`), `ODocumentReader` shows "无原文内容" in the original pane. The note's content renders in the bilingual pane via the `translation_zh-zh` derivative.

---

### 16.9 OBacklinkPanel

**Adapter**: `stratum-web/src/lib/adapters/notes.ts`  
**Hook**: `useBacklinks(noteId)`

```typescript
// Block props
interface OBacklinkPanelProps {
  backlinks: BacklinkItem[];  // REQUIRED
  targetTitle?: string;
  onSelect?: (item: BacklinkItem) => void;
  emptyText?: string;         // default: "暂无反链"
}

// Helios BacklinkItem
interface BacklinkItem {
  note: Note;           // the referencing note (minimal — content/wikilinks empty)
  excerpt?: string;     // the [[wikilink]] context snippet
  link_text?: string;   // text inside the [[...]]
}
```

**API call**: `GET /api/notes/{id}/backlinks`

**Adaptation** (backend `BacklinkItem` → Helios `BacklinkItem`):

```typescript
function adaptBacklink(item: { id: string; title: string; snippet?: string | null }): BacklinkItem {
  return {
    note: {
      id: item.id,
      title: item.title,
      content: null,     // not populated from backlink row
      wikilinks: [],
      substrate_id: null,
      meta_json: {},
      created_at: "",
      updated_at: "",
    },
    excerpt: item.snippet ?? undefined,
    link_text: undefined,
  };
}
```

---

### 16.10 Block-to-Endpoint Matrix

| Block | Primary Endpoint | Secondary Endpoints |
|-------|-----------------|---------------------|
| `OSemanticSearch` | `POST /api/search` | — |
| `OAIQAPanel` | `POST /api/agents/reading_companion/run` | — |
| `OAISummaryCard` | `GET /api/agents/runs?agent=daily_digest` | — |
| `OScheduledJobsManager` | `GET /api/scheduled_jobs` | `PUT /api/scheduled_jobs/{id}`, `DELETE /api/scheduled_jobs/{id}`, `POST /api/scheduled_jobs`, `POST /api/agents/{name}/run` |
| `ODocumentTree` | `GET /api/substrates` | — |
| `ODocumentReader` (doc) | `GET /api/substrates/{id}` | `GET /api/substrates/{id}/derivatives` |
| `ODocumentReader` (note) | `GET /api/notes/{id}` | — |
| `OBacklinkPanel` | `GET /api/notes/{id}/backlinks` | — |
| `OAnnotationLayer` | *(none — display-only in v1.0)* | `/api/annotations` planned Phase 15 |

---

## 17. Error Reference

### 17.1 Standard Error Envelope

FastAPI returns errors in this format:

```json
{
  "detail": "Error description"
}
```

For validation errors (422):

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "password"],
      "msg": "String should have at least 10 characters",
      "input": "short",
      "ctx": { "min_length": 10 }
    }
  ]
}
```

### 17.2 HTTP Status Code Reference

| Status | Meaning in Stratum |
|--------|--------------------|
| 200 | Success |
| 400 | Business rule violation (duplicate email, weak password) |
| 401 | JWT missing, invalid, or expired |
| 403 | Authenticated but not authorized (wrong user's resource, admin secret mismatch) |
| 404 | Resource not found, or found but outside user's corpus |
| 410 | Share token revoked or expired |
| 422 | Request body failed Pydantic validation |
| 503 | Server misconfiguration (e.g. `ADMIN_SECRET` not set) |

### 17.3 Auth Error Details

| `detail` string | Cause |
|-----------------|-------|
| `"Not authenticated"` | `Authorization` header missing |
| `"Invalid token"` | JWT signature invalid or malformed |
| `"Token expired"` | JWT `exp` claim in the past |
| `"Session revoked"` | Refresh token was revoked by logout or admin |
| `"Admin secret not configured"` | `ADMIN_SECRET` env var missing (503) |
| `"Forbidden"` | Admin secret present but does not match |

---

## 18. Environment Variables

### Stratum API (Python)

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET` | `"super-secret-key-change-this-in-prod"` | HS256 signing secret — **must be changed in production** |
| `DATABASE_PATH` | `~/.stratum/meta.duckdb` | DuckDB file path |
| `ADMIN_SECRET` | *(unset)* | Required to use `/api/admin/stats`; if unset, endpoint returns 503 |
| `SENTRY_DSN` | *(unset)* | Sentry error tracking DSN; telemetry disabled if unset |
| `SENTRY_TRACES_SAMPLE_RATE` | `"0.1"` | Sentry trace sampling rate (0–1) |
| `STRATUM_ENV` | *(unset)* | Set to `"production"` in docker-compose |

### Next.js Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `STRATUM_API_PORT` | `9302` | Port for browser-facing `/api/*` rewrite proxy |
| `STRATUM_API_INTERNAL_URL` | `http://localhost:9305` | Full URL for server-side fetch in `share/[token]` Server Component. Set to `http://stratum-api:9302` when containerised. |

### E2E Test Override

The Playwright browser config (`playwright.browser.config.ts`) sets:
```
STRATUM_API_PORT=9311
STRATUM_API_INTERNAL_URL=http://localhost:9311
```

This points both the browser-facing proxy and the server-side fetch to the isolated test backend.

---

## 19. Changelog

### v1.2.0 — 2026-05-27 (Phase 14, Wave 12)

- **Added**: `GET /api/notes/{note_id}` — full note detail with content, wikilinks, meta_json
- **Added**: `GET /api/notes/{note_id}/backlinks` — backlink graph traversal
- **Changed**: `share/[token]` Server Component now uses `STRATUM_API_INTERNAL_URL` env var instead of hardcoded port (B-1 fix)
- **Added**: `@helios/blocks` 1.5.0 integration — 9 blocks wired, 5 adapter files, data contracts documented in §16
- **Added**: This document

### v1.1.0 — 2026-05-20 (Phase 11C, Wave 10-11)

- **Added**: `GET /api/users/me/sessions` — list active sessions
- **Added**: `DELETE /api/users/me/sessions/{id}` — remote session revocation
- **Added**: `GET /api/users/by-username/{username}` — public profile lookup
- **Added**: `POST /api/feedback` — alpha feedback collection
- **Added**: `GET /api/admin/stats` — admin dashboard with HMAC auth
- **Security**: Constant-time comparison for admin secret (timing-attack fix)

### v1.0.0 — 2026-05-01 (Phase 1-10)

- Initial API: auth, search, substrates, agents, scheduled_jobs, share
