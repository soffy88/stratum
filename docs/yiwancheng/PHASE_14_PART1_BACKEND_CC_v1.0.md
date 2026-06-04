# PHASE 14 PART 1 — 后端 CC 执行指令书 (Wave 0-5)

**CC FULL AUTO 实施指令书**

**项目**: stratum-web 准产品 alpha — 后端补
**Phase**: 14 Part 1 (3 段中第 1 段)
**前置**: Step 11 RFC v0.1 核准 (Wiki + 3O 经理人)
**执行**: CC FULL AUTO, Wave 0-5
**预算**: 2.6-3.8 月

---

## §0 范围声明 (R-4 严格)

✅ 允许:
- Stratum repo 服务层新增 (src/stratum/auth / src/stratum/dao 内新文件)
- Stratum repo migrations 新增 (012+ 编号)
- Stratum repo mcp_server / http_api 新增 routes
- 部署脚本 / docker-compose / 环境配置
- 后端测试 (Stratum repo tests/)

❌ 禁止 (Phase 11D 才动):
- **不修改 ~/projects/platform/omodul/omodul/knowledge/** 内任何 .py 文件
- **不修改 ~/projects/platform/oskill/** 内任何 .py 文件
- **不修改 ~/projects/platform/oprim/** 内任何 .py 文件
- 不修改 obase

如发现必须改 omodul/knowledge/* 才能完成某 Wave → **立即停止报告 advisor**, 不擅自改。

---

## §1 FULL AUTO 规则 (R-1 ~ R-6)

### R-1 失败不静默
任何 skill / 实施 / 测试 / CI / 部署失败 → 明确报告, 不假装成功。

### R-2 SPEC 是真理源
本文 + Step 11 RFC v0.1 是真理。不脑补不在范围内的元素。

### R-3 真实示例强制
每个 API endpoint 必须有真实可跑的 curl / httpx 调用示例 + 单元测试 + 集成测试。

### R-4 严格范围
见 §0。Wave 1-5 全部在 Stratum repo 内, 不动 platform/* 任何文件。

### R-5 namespace 隔离

只动 + 新建:

| 路径 | 操作 |
|---|---|
| ~/projects/stratum/src/stratum/auth/ | 新建目录 + 子文件 |
| ~/projects/stratum/src/stratum/dao/users.py | 新建 |
| ~/projects/stratum/src/stratum/dao/sessions.py | 新建 |
| ~/projects/stratum/src/stratum/dao/share_tokens.py | 新建 |
| ~/projects/stratum/src/stratum/dao/profile.py | 新建 |
| ~/projects/stratum/src/stratum/http_api/ | 新建目录 (FastAPI app) |
| ~/projects/stratum/src/stratum/middleware/ | 新建目录 (corpus 隔离 / rate limit / abuse detect) |
| ~/projects/stratum/src/stratum/db/migrations/012_users.sql ~ 016_*.sql | 新建 5 migration |
| ~/projects/stratum/deploy/ | 新建目录 (docker-compose.yml / Cloudflare Tunnel config / Nginx) |
| ~/projects/stratum/tests/ | 新建 / 扩展测试 |
| ~/projects/stratum/CHANGELOG.md | 新增 v1.2.0 段 |

### R-6 破坏性操作 Wiki sign-off

不允许 CC 自行:
- DROP TABLE / DELETE FROM (含 migration 中)
- 删现有 dao / route 文件
- 改 omodul/knowledge/* 任何文件 (上方 §0 强制)
- 部署到公网前不报告 Wiki (Wave 3 强制 sign-off)

本指令书 sign-off 范围:
- ✅ 新建 src/stratum/auth/ 等新目录
- ✅ 新建 5 个 migration (012-016)
- ✅ 新建 dao / route 文件
- ✅ docker-compose 修订 (加 nginx / certbot)
- ❌ Cloudflare Tunnel 真公网发布 (Wave 3 末等 Wiki 显式 sign-off)

---

## §2 Wave 0 — 准入 (0.5 天)

### 2.1 baseline 验证

```bash
# Stratum 后端运行状态
docker ps --format "table {{.Names}}\t{{.Status}}"
# 期待: stratum-sd / stratum-searxng / stratum-whisper healthy
# stratum-tts Exited (v1.0 暂缓, Phase 11B Wave 6 真补已完成)

# Python / 包版本
python3 --version  # 期待 3.14
cd ~/projects/stratum && pip list | grep -E "fastapi|sqlalchemy|duckdb|tantivy|lancedb"

# 主 omodul / oskill / oprim 版本
python3 -c "import omodul, oskill, oprim; print(omodul.__version__, oskill.__version__, oprim.__version__)"
# 期待: 1.11.0 / 3.0.0 / 2.11.0 (Phase 11C 后)

# DuckDB schema 状态
cd ~/projects/stratum
python3 -c "
import duckdb
conn = duckdb.connect('~/.stratum/stratum.duckdb')
tables = conn.execute('SHOW TABLES').fetchall()
print(f'当前 DuckDB tables: {len(tables)}')
for t in tables: print(f'  {t[0]}')
"
# 期待: 15 张表 (Phase 11C 后)

# migration 最新版本
ls ~/projects/stratum/src/stratum/db/migrations/ | sort | tail -3
# 期待: 010_tasks.sql / 011_templates.sql 是最新

# API keys
cat ~/.config/keys/.env | grep -E "DASHSCOPE|DEEPSEEK|ANTHROPIC|JWT_SECRET|COOKIE_SECRET" | wc -l
# 期待: 3 keys 齐 + 2 个新的 (JWT_SECRET / COOKIE_SECRET 后面 Wave 1 加)
```

### 2.2 备份 (R-6 安全垫)

```bash
# DuckDB 备份 (Wave 1 开始动 schema 前)
cp ~/.stratum/stratum.duckdb ~/.stratum/stratum.duckdb.pre-phase14-backup
ls -lh ~/.stratum/stratum.duckdb.pre-phase14-backup

# 当前 commit hash 记录
cd ~/projects/stratum && git log -1 --oneline
```

### 2.3 Phase 14 分支创建

```bash
cd ~/projects/stratum
git checkout -b phase14/backend-saas
```

### 2.4 Wave 0 完工报告

```
Wave 0 ✅
- baseline: stratum 后端正常
- omodul 1.11.0 / oskill 3.0.0 / oprim 2.11.0
- DuckDB 15 tables, migration 最新 011_templates.sql
- DuckDB 备份: <path>
- 当前 commit: <hash>
- 分支: phase14/backend-saas
进 Wave 1
```

---

## §3 Wave 1 — 用户系统 (0.5-1 月)

### 3.1 数据库 migration 012-013

#### migration 012 — users 表

```sql
-- src/stratum/db/migrations/012_users.sql

CREATE TABLE IF NOT EXISTS users (
    id              VARCHAR PRIMARY KEY,                    -- ULID
    email           VARCHAR UNIQUE NOT NULL,
    username        VARCHAR UNIQUE NOT NULL,                -- 公开 (用于 share 链接)
    password_hash   VARCHAR NOT NULL,                       -- argon2id
    corpus_id       VARCHAR UNIQUE NOT NULL,                -- 跟 user 一对一, 内部用于 oskill 隔离
    email_verified  BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    is_suspended    BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at   TIMESTAMP,
    meta_json       VARCHAR DEFAULT '{}'
);

CREATE UNIQUE INDEX idx_users_email ON users(email);
CREATE UNIQUE INDEX idx_users_username ON users(username);
CREATE UNIQUE INDEX idx_users_corpus_id ON users(corpus_id);
CREATE INDEX idx_users_created ON users(created_at);
```

#### migration 013 — sessions 表

```sql
-- src/stratum/db/migrations/013_sessions.sql

CREATE TABLE IF NOT EXISTS sessions (
    id              VARCHAR PRIMARY KEY,                    -- ULID
    user_id         VARCHAR NOT NULL,                       -- FK users.id
    refresh_token_hash VARCHAR UNIQUE NOT NULL,             -- SHA-256 of refresh token
    user_agent      VARCHAR,
    ip_address      VARCHAR,
    expires_at      TIMESTAMP NOT NULL,                     -- 30 天
    revoked_at      TIMESTAMP,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sessions_user ON sessions(user_id);
CREATE UNIQUE INDEX idx_sessions_refresh_hash ON sessions(refresh_token_hash);
CREATE INDEX idx_sessions_expires ON sessions(expires_at);
```

### 3.2 auth/ 包结构

```
src/stratum/auth/
├── __init__.py
├── password.py             # argon2id hash / verify
├── jwt_handler.py          # JWT encode / decode (access token, 15 min)
├── refresh_handler.py      # refresh token (30 天, httpOnly cookie)
├── exceptions.py           # AuthError / InvalidCredentials / TokenExpired / etc
└── dependencies.py         # FastAPI dependency: get_current_user
```

#### auth/password.py 要求

- argon2-cffi 库 (Python 标准)
- `hash_password(password: str) -> str` (返回 argon2id 串)
- `verify_password(password: str, hash: str) -> bool`
- 强制 password 最小 10 chars / 含数字 + 字母 + 特殊字符 (Pydantic validator)

#### auth/jwt_handler.py 要求

- pyjwt 库
- HS256 算法
- 密钥读 `~/.config/keys/.env` 的 `JWT_SECRET` (Wiki 提前生成 256 bit 随机)
- access token 含 claims: `{sub: user_id, corpus_id, exp, iat}`
- TTL 15 分钟
- `encode_access(user_id, corpus_id) -> str`
- `decode_access(token) -> dict | raise TokenExpired/InvalidToken`

#### auth/refresh_handler.py 要求

- refresh token = ULID + 64 字节随机 secret, hash 后存 sessions 表
- TTL 30 天
- httpOnly + Secure + SameSite=Lax cookie 设置
- `create_refresh(user_id, user_agent, ip) -> (token_str, session_id)`
- `validate_refresh(token_str) -> user_id | raise`
- `revoke_refresh(session_id)`

#### auth/dependencies.py 要求

```python
async def get_current_user(
    request: Request,
    authorization: str | None = Header(None),
) -> User:
    """FastAPI dependency, 从 Authorization header (Bearer JWT) 解出 user.
    
    raise HTTPException(401) if token missing/invalid/expired.
    """
```

### 3.3 dao/users.py / sessions.py 要求

#### dao/users.py

```python
# 接口规约
def create_user(*, email: str, username: str, password: str) -> User: ...
def get_user_by_id(user_id: str) -> User | None: ...
def get_user_by_email(email: str) -> User | None: ...
def get_user_by_username(username: str) -> User | None: ...
def update_user(user_id: str, **fields) -> User: ...
def verify_email(user_id: str) -> None: ...
def suspend_user(user_id: str, reason: str) -> None: ...
def update_last_login(user_id: str) -> None: ...

# 创建时自动生成 corpus_id = f"user_{user_id}" (ULID 内部 derive, 不暴露生成逻辑给上层)
```

#### dao/sessions.py

```python
def create_session(*, user_id: str, refresh_token_hash: str, user_agent: str | None, ip: str | None, ttl_days: int = 30) -> Session: ...
def get_session_by_refresh_hash(refresh_token_hash: str) -> Session | None: ...
def list_user_sessions(user_id: str, active_only: bool = True) -> list[Session]: ...
def revoke_session(session_id: str) -> None: ...
def revoke_all_user_sessions(user_id: str, except_session: str | None = None) -> int: ...
def cleanup_expired() -> int: ...     # 后台 daemon 调
```

### 3.4 http_api/ FastAPI app

```
src/stratum/http_api/
├── __init__.py
├── app.py                  # FastAPI app instance (含 CORS / 中间件)
├── routes/
│   ├── __init__.py
│   ├── auth.py             # /api/auth/* (register / login / logout / refresh / verify / reset)
│   ├── users.py            # /api/users/me + PATCH
│   ├── substrates.py       # Wave 5 加
│   ├── notes.py            # Wave 5 加
│   ├── search.py           # Wave 5 加
│   └── share.py            # Wave 4 加
├── schemas/
│   ├── __init__.py
│   ├── auth.py             # Pydantic: RegisterRequest / LoginRequest / TokenResponse / etc
│   └── user.py             # Pydantic: UserPublic / UserProfile
└── deps.py                 # common FastAPI deps (db / current_user / etc)
```

### 3.5 auth routes 接口契约

```python
# POST /api/auth/register
class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=32, pattern=r'^[a-zA-Z0-9_]+$')
    password: str = Field(..., min_length=10)
    
class RegisterResponse(BaseModel):
    user_id: str
    email: str
    username: str
    # 不返回 corpus_id (内部细节)
    verify_email_sent: bool


# POST /api/auth/login
class LoginRequest(BaseModel):
    email_or_username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str       # JWT (15 min)
    expires_in: int         # 900
    user: UserPublic
    # refresh_token 走 httpOnly cookie, 不在 response body


# POST /api/auth/refresh
# 无 body, refresh_token 从 cookie 取
class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int


# POST /api/auth/logout
# 无 body, 撤销当前 session


# GET /api/users/me
class UserPublic(BaseModel):
    user_id: str
    email: str
    username: str
    email_verified: bool
    created_at: datetime
    # avatar_url / display_name Wave 4 加


# PATCH /api/users/me
class UpdateUserRequest(BaseModel):
    username: str | None = None
    # 改 username 需要确认不冲突
```

### 3.6 邮件验证 (基础版)

Wave 1 alpha 期: 暂不发真邮件, `verify_email_sent` 返回 false, 用户手动从日志拿验证链接 (Wiki 自决何时接 SMTP)。

Phase 14 后续 Wave 可加 Resend / Mailgun 等。

### 3.7 测试要求 (5 红线 §14.2 对齐)

```
tests/auth/test_password.py            (≥5 tests)
tests/auth/test_jwt_handler.py         (≥8 tests)
tests/auth/test_refresh_handler.py     (≥8 tests)
tests/auth/test_dependencies.py        (≥5 tests, mock JWT)
tests/dao/test_users.py                (≥10 tests, 含 CRUD + 唯一性 + corpus_id 生成)
tests/dao/test_sessions.py             (≥8 tests, 含 expires / revoke / cleanup)
tests/http_api/test_auth_routes.py     (≥15 tests, integration: register → login → me → refresh → logout 全链)
```

总: ≥59 新测试。

红线:
- 覆盖率 src/stratum/auth/ ≥90% / src/stratum/dao/users.py + sessions.py ≥90% / http_api/routes/auth.py ≥85%
- mypy --strict 通过
- ruff check 通过

### 3.8 Wave 1 Gate

```bash
cd ~/projects/stratum
# 跑 migration
python3 src/stratum/db/run_migrations.py
# 测试
pytest tests/auth/ tests/dao/test_users.py tests/dao/test_sessions.py tests/http_api/test_auth_routes.py -v --cov

# 启动 FastAPI dev (Wave 1 单独测)
uvicorn stratum.http_api.app:app --reload --port 9302 &
sleep 2

# 端到端 curl 验证
curl -X POST http://localhost:9302/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"wiki@test.com","username":"wiki","password":"Test123456!"}'
# 期待 200, 返回 user_id

curl -X POST http://localhost:9302/api/auth/login \
  -H "Content-Type: application/json" \
  -c /tmp/cookies.txt \
  -d '{"email_or_username":"wiki@test.com","password":"Test123456!"}'
# 期待 200, 返回 access_token + cookie

ACCESS_TOKEN=$(... extract)
curl http://localhost:9302/api/users/me -H "Authorization: Bearer $ACCESS_TOKEN"
# 期待 200, 返回 user 信息

# 关闭 dev
pkill -f "uvicorn stratum.http_api"

git add -A && git commit -m "Phase 14 Wave 1: 用户系统 (users + sessions + auth routes + JWT + refresh)"
```

报告:
```
Wave 1 ✅ (用户系统)
- migration 012 users / 013 sessions 创建成功
- auth 包: password / jwt_handler / refresh_handler / dependencies / exceptions
- dao users / sessions
- http_api/routes/auth: 5 endpoint (register/login/logout/refresh/me)
- 测试: <N> 个 (>= 59), 覆盖率达标
- 端到端 register → login → me → refresh → logout 全链验证
- commit: <hash>
进 Wave 2
```

---

## §4 Wave 2 — 多 corpus 隔离 (1-1.5 月)

### 4.1 数据库 schema 全面加 corpus_id

#### migration 014 — substrate / note / tag / concept / view / task / template / scheduled_job 全部加 corpus_id

⚠️ 这是 Wave 2 最核心修改, 触及现有 15 表中 ~12 张, 是 BREAKING migration。

```sql
-- src/stratum/db/migrations/014_corpus_isolation.sql

-- 1. substrate 表加 corpus_id (替代 user_id 概念)
ALTER TABLE substrate ADD COLUMN corpus_id VARCHAR;
UPDATE substrate SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
ALTER TABLE substrate ALTER COLUMN corpus_id SET NOT NULL;
CREATE INDEX idx_substrate_corpus ON substrate(corpus_id);

-- 2. derivative 表 (跟 substrate 一对多, derivative 通过 substrate_id 间接 corpus_id, 但加冗余字段加速查询)
ALTER TABLE derivative ADD COLUMN corpus_id VARCHAR;
UPDATE derivative d SET corpus_id = (SELECT s.corpus_id FROM substrate s WHERE s.id = d.substrate_id);
ALTER TABLE derivative ALTER COLUMN corpus_id SET NOT NULL;
CREATE INDEX idx_derivative_corpus ON derivative(corpus_id);

-- 3. note 表
ALTER TABLE note ADD COLUMN corpus_id VARCHAR;
UPDATE note SET corpus_id = 'corpus_default' WHERE corpus_id IS NULL;
ALTER TABLE note ALTER COLUMN corpus_id SET NOT NULL;
CREATE INDEX idx_note_corpus ON note(corpus_id);

-- 4. 其余 (tag / concept / view / task / note_template / scheduled_job / agent_run / push_subscription)
-- ... 各表相同模式

-- 全表完成后, 老 user_id 字段保留 (向后兼容 Phase 11C MCP routes), 但所有新查询走 corpus_id
```

#### migration 015 — 数据迁移 (历史 user_id → corpus_id 映射)

```sql
-- src/stratum/db/migrations/015_migrate_default_user.sql

-- 当前 Stratum 单用户, user_id 多为 'wiki' / 'demo_user' / 'default'
-- 1. 创建一个默认 user (wiki 自己), corpus_id 跟旧数据匹配
INSERT INTO users (id, email, username, password_hash, corpus_id, email_verified, is_active)
VALUES (
    'wiki_default_user_ulid',                 -- 固定 ULID, Wiki 手动改密码 + email
    'wiki@stratum.local',
    'wiki',
    'argon2_placeholder_to_be_reset',         -- Wave 1 后 Wiki 调 /api/auth/reset 改
    'corpus_default',
    TRUE,
    TRUE
);

-- 2. 验证: 所有 substrate / note / etc 的 corpus_id 都指向 'corpus_default'
SELECT COUNT(*) FROM substrate WHERE corpus_id != 'corpus_default';
-- 期待 0
```

### 4.2 dao 层全部加 corpus_id 强制过滤

⚠️ 这是 Wave 2 第二核心修改, 触及 ~12 个 dao 文件。

要求: 所有 dao 函数签名加 `corpus_id: str` 必填参数, 所有 SQL query 加 `WHERE corpus_id = ?` 过滤。

例: dao/substrate.py

```python
# 修订前 (Phase 11C 之前):
def list_substrates(user_id: str, medium: str | None = None, limit: int = 50) -> list[Substrate]: ...

# 修订后:
def list_substrates(*, corpus_id: str, medium: str | None = None, limit: int = 50) -> list[Substrate]:
    """所有 substrate 列表查询. corpus_id 必填, 强制 corpus 隔离."""
    sql = "SELECT * FROM substrate WHERE corpus_id = ?"
    params = [corpus_id]
    if medium:
        sql += " AND medium = ?"
        params.append(medium)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    return ...

def get_substrate(*, substrate_id: str, corpus_id: str) -> Substrate | None:
    """get 也强制 corpus_id 校验, 避免猜测 ID 越权."""
    return ... "WHERE id = ? AND corpus_id = ?"
```

所有 dao 函数:
- `list_*` 加 corpus_id 过滤
- `get_*` 加 corpus_id 校验 (返回 None 如不匹配)
- `create_*` 入参强制 corpus_id, 写入时同写
- `update_*` 校验 corpus_id 后才允许 update
- `delete_*` 同 update

dao 文件清单 (需修订):
```
src/stratum/dao/substrate.py
src/stratum/dao/derivative.py
src/stratum/dao/note.py
src/stratum/dao/tag.py
src/stratum/dao/concept.py
src/stratum/dao/view.py
src/stratum/dao/task.py             (Phase 11C 已加, 改 user_id 字段 → corpus_id)
src/stratum/dao/template.py         (Phase 11C 已加, 同)
src/stratum/dao/scheduled_job.py    (如有, Phase 11D 历史)
src/stratum/dao/agent_run.py        (如有)
src/stratum/dao/push_subscription.py (如有)
```

### 4.3 中间件: corpus 隔离 middleware

```python
# src/stratum/middleware/corpus_isolation.py

from fastapi import Request, HTTPException
from stratum.auth.dependencies import get_current_user_from_request

async def corpus_isolation_middleware(request: Request, call_next):
    """所有 /api/* 路由强制注入 corpus_id 到 request.state.
    
    /api/auth/* 例外 (无需 user).
    /share/* 例外 (public read).
    """
    if request.url.path.startswith("/api/auth/") or request.url.path.startswith("/share/"):
        return await call_next(request)
    
    if request.url.path.startswith("/api/"):
        user = await get_current_user_from_request(request)  # raise 401 if no auth
        request.state.user_id = user.id
        request.state.corpus_id = user.corpus_id
    
    return await call_next(request)
```

各 routes 通过 `request.state.corpus_id` 取值, 不允许从 query/body 接受 corpus_id。

### 4.4 hybrid_search caller 修订 (Phase 11C 已迁的服务层映射验证)

```python
# src/stratum/service/search.py

from oskill import hybrid_search    # Phase 11C v3.0, 接受 corpus_id

def stratum_search(*, query: str, user_id: str, ...) -> list[SearchResult]:
    """服务层包装 oskill.hybrid_search, 做 user_id → corpus_id 映射."""
    user = dao.users.get_user_by_id(user_id)
    if not user:
        raise ValueError(f"user {user_id} not found")
    
    return hybrid_search(
        query=query,
        corpus_id=user.corpus_id,
        ...
    )
```

### 4.5 BM25 / 向量索引按 corpus 分区

⚠️ 这块需要详细查 oskill.hybrid_search 实施细节, 因为 BM25 / 向量索引可能是全局共享的 (Phase 11C 设计意图: corpus_id 是过滤参数, 不是物理分区)。

CC 任务: 验证 oskill.hybrid_search 是否真的按 corpus_id 隔离, 不是只是参数透传:

```bash
# 创建 user A 写若干 substrate, user B 写若干 substrate
# 调 hybrid_search(corpus_id="corpus_A") 看是否能搜到 B 的内容
# 不能 → 隔离 OK
# 能 → ⚠️ 立即报告 advisor (oskill 层未隔离, Wave 2 必须修, 但因 R-4 不许动 oskill, 等 Phase 11D)

如果 oskill 层未隔离 → 临时方案: Stratum 服务层做 post-filter (拿到 result 后用 corpus_id 过滤掉不属于当前 corpus 的 fragment_id / substrate_id), 性能差但合规. 详见 R-1 不静默原则.
```

### 4.6 测试要求 (corpus 隔离 = 安全关键)

```
tests/dao/test_substrate_corpus_isolation.py    (≥15 tests)
tests/dao/test_note_corpus_isolation.py         (≥10 tests)
tests/dao/test_<其他每个表>_corpus_isolation.py  (≥5-10 tests/表)
tests/middleware/test_corpus_isolation.py       (≥10 tests)
tests/service/test_search_isolation.py          (≥15 tests: A/B 用户互不可见)
tests/integration/test_cross_corpus_block.py   (≥20 tests: 渗透测试)
```

**关键红线测试** (任何一条 fail = Wave 2 block):

```python
def test_user_A_cannot_read_user_B_substrate_via_get():
    """直接 get(substrate_id=B's id, corpus_id=A's corpus) → None."""

def test_user_A_cannot_search_user_B_content():
    """hybrid_search(corpus_id=A's corpus) 结果中无 B's content."""

def test_user_A_cannot_update_user_B_note_even_with_known_id():
    """update_note(note_id=B's id, corpus_id=A's corpus) → raise / no-op."""

def test_corpus_id_injection_attack_blocked():
    """攻击者在 query body 传 corpus_id="B's corpus" → middleware 拒绝, 走 request.state.corpus_id."""

def test_no_api_route_accepts_corpus_id_from_input():
    """grep src/stratum/http_api/routes/ 确保没有任何 endpoint 接受 corpus_id query/body 参数."""
```

任一 fail → 立即停, 不许 Wave 2 完工。

### 4.7 Wave 2 Gate

```bash
cd ~/projects/stratum
python3 src/stratum/db/run_migrations.py   # 014 + 015
pytest tests/dao/ tests/middleware/ tests/service/ tests/integration/ -v --cov

# 渗透测试单独跑, 必须 100% pass
pytest tests/integration/test_cross_corpus_block.py -v

# 全量回归测试 (现有所有 Stratum 测试)
pytest tests/ -v

git add -A && git commit -m "Phase 14 Wave 2: 多 corpus 隔离 (migration 014/015 + dao 全表 + middleware + 渗透测试)"
```

报告:
```
Wave 2 ✅ (多 corpus 隔离)
- migration 014 corpus_isolation / 015 migrate_default_user 创建成功
- dao 12 文件全部加 corpus_id 强制过滤
- middleware corpus_isolation 实施
- BM25/向量索引隔离验证: <OK / 需 post-filter>
- 渗透测试: <N> 项全过 (任一 fail block)
- 全量回归 0 regression
- commit: <hash>
进 Wave 3
```

---

## §5 Wave 3 — 公网部署 (0.5 月)

### 5.1 部署架构

```
公网 (Cloudflare)
    │
    ↓ HTTPS (TLS 1.3)
Cloudflare Tunnel
    │
    ↓ (Tailscale 内网)
WSL2 (Win11)
    │
    ├── nginx (8443 → routing)
    │       ├── /api/* → FastAPI (9302)
    │       ├── /share/* → FastAPI (9302)
    │       ├── /* → stratum-web Next.js (3000, Wave 6 后)
    │       └── 静态资源缓存
    │
    └── FastAPI (uvicorn) on 9302
            └── Stratum services
```

### 5.2 docker-compose 修订

```yaml
# ~/projects/stratum/deploy/docker-compose.yml

version: '3.9'

services:
  stratum-api:
    build:
      context: ..
      dockerfile: deploy/Dockerfile.api
    container_name: stratum-api
    restart: unless-stopped
    ports:
      - "127.0.0.1:9302:9302"    # 仅 localhost, 走 nginx
    volumes:
      - ~/.stratum:/data/stratum
      - ~/.config/keys:/keys:ro
    environment:
      - STRATUM_ENV=production
      - DATABASE_PATH=/data/stratum/stratum.duckdb
      - JWT_SECRET_FILE=/keys/.env
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9302/health"]
      interval: 30s
      timeout: 5s
      retries: 3
  
  stratum-nginx:
    image: nginx:1.27-alpine
    container_name: stratum-nginx
    restart: unless-stopped
    ports:
      - "127.0.0.1:8443:8443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./logs:/var/log/nginx
    depends_on:
      - stratum-api
  
  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: stratum-cloudflared
    restart: unless-stopped
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN_FILE=/secrets/tunnel-token
    volumes:
      - ~/.config/keys/cloudflared:/secrets:ro

networks:
  default:
    name: stratum-net
    external: true
```

### 5.3 nginx 配置

```nginx
# deploy/nginx.conf

worker_processes auto;
events { worker_connections 1024; }

http {
    include /etc/nginx/mime.types;
    sendfile on;
    keepalive_timeout 65;
    
    # rate limit
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=2r/s;
    
    upstream stratum_api {
        server stratum-api:9302;
    }
    
    server {
        listen 8443 ssl http2;
        server_name stratum.<wiki-domain>;
        
        # SSL 由 Cloudflare 终结, nginx 内部用 self-signed (TLS 间内网)
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        
        # API
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://stratum_api/api/;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Real-IP $remote_addr;
        }
        
        # auth 加严 rate limit
        location /api/auth/ {
            limit_req zone=auth burst=5 nodelay;
            proxy_pass http://stratum_api/api/auth/;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        }
        
        # share public
        location /share/ {
            proxy_pass http://stratum_api/share/;
            add_header Cache-Control "public, max-age=300";
        }
        
        # Next.js (Wave 6 后)
        # location / { proxy_pass http://stratum-web:3000; }
        
        # 错误页
        error_page 502 503 504 /50x.html;
    }
}
```

### 5.4 Cloudflare Tunnel 配置

Wiki 提前在 Cloudflare dashboard:
1. 创建 Tunnel (cloudflared)
2. 路由 stratum.<wiki-domain> → http://stratum-nginx:8443
3. 把 tunnel token 存到 ~/.config/keys/cloudflared/tunnel-token

CC 任务: 写好 docker-compose / nginx 配置, **不真公网发布**, 等 Wave 3 末 Wiki 显式 sign-off。

### 5.5 rate limit 服务层

除 nginx 层 rate limit, 服务层加细粒度 (per user):

```python
# src/stratum/middleware/rate_limit.py

# 用 Redis (现有依赖) 实施滑动窗口
# 限制:
#   /api/auth/register: 3/hour per IP
#   /api/auth/login: 10/hour per IP
#   /api/auth/refresh: 30/hour per user
#   其他 /api/*: 60/min per user
# 超限 → 429 Too Many Requests
```

### 5.6 abuse detection (基础)

```python
# src/stratum/middleware/abuse_detection.py

# 检测:
#   同 IP 5 分钟内 10+ register → 暂封 1 小时
#   同 IP 5 分钟内 20+ failed login → 暂封 4 小时
#   单 user 1 小时内 100+ /api/* → 警告 + 限速降级
# 暂封记到 DuckDB blocked_ips 表 (新加 migration 016)
```

#### migration 016 — abuse 跟踪

```sql
-- src/stratum/db/migrations/016_abuse_tracking.sql

CREATE TABLE IF NOT EXISTS blocked_ips (
    ip_address      VARCHAR PRIMARY KEY,
    reason          VARCHAR NOT NULL,
    blocked_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP NOT NULL,
    blocked_count   INTEGER DEFAULT 1
);

CREATE INDEX idx_blocked_ips_expires ON blocked_ips(expires_at);

CREATE TABLE IF NOT EXISTS auth_events (
    id              VARCHAR PRIMARY KEY,        -- ULID
    event_type      VARCHAR NOT NULL,           -- 'register' | 'login_success' | 'login_failed' | etc
    ip_address      VARCHAR NOT NULL,
    user_id         VARCHAR,                    -- nullable for failed login
    user_agent      VARCHAR,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    meta_json       VARCHAR DEFAULT '{}'
);

CREATE INDEX idx_auth_events_ip ON auth_events(ip_address, created_at);
CREATE INDEX idx_auth_events_user ON auth_events(user_id, created_at);
```

### 5.7 测试

```
tests/middleware/test_rate_limit.py             (≥10)
tests/middleware/test_abuse_detection.py        (≥10)
tests/deploy/test_nginx_config.py               (≥5, 静态 nginx -t 验证)
```

### 5.8 Wave 3 内测 (本地内网)

⚠️ 不真公网, 仅 localhost + 内网 tailscale 测试:

```bash
cd ~/projects/stratum/deploy
docker compose up -d

# 等启动
sleep 10

# health
curl -k https://localhost:8443/health    # 期待 200
docker compose logs stratum-api --tail 20

# 完整链路: nginx → api
curl -k -X POST https://localhost:8443/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test2@local","username":"test2","password":"Test123456!"}'
# 期待 200

# rate limit 测试
for i in {1..30}; do
  curl -k -s -o /dev/null -w "%{http_code}\n" https://localhost:8443/api/auth/login \
    -X POST -H "Content-Type: application/json" \
    -d '{"email_or_username":"none","password":"none"}'
done
# 期待: 前 5-10 个 401 (账号不对), 后续 429 (rate limited)
```

### 5.9 Wave 3 Gate

```bash
pytest tests/middleware/test_rate_limit.py tests/middleware/test_abuse_detection.py tests/deploy/ -v
git add -A && git commit -m "Phase 14 Wave 3: 公网部署基础设施 (docker-compose + nginx + tunnel + rate limit + abuse)"
```

报告 + ⚠️ **等 Wiki 显式 sign-off** 才真公网发布:
```
Wave 3 ✅ (公网部署基础设施)
- docker-compose 4 服务 (api / nginx / cloudflared / + 现有 stratum-sd/searxng/whisper)
- migration 016 abuse_tracking 创建
- rate limit (nginx 层 + 服务层 per-user)
- abuse detection
- 本地 + 内网 tailscale 验证全通
- 测试: <N> 个全过
- commit: <hash>

⚠️ Cloudflare Tunnel 真公网发布 = R-6 操作, 等 Wiki sign-off:
- 配置已就绪
- 待 Wiki 拍 "公网开" 后, CC 跑: docker compose --profile public up -d cloudflared
- domain stratum.<wiki> 需 Wiki 在 Cloudflare 配 DNS A 记录指向 tunnel

进 Wave 4 (share 机制) — 内网继续, 不需等公网 sign-off
```

---

## §6 Wave 4 — share 机制 + profile (0.5 月)

### 6.1 migration 017 — share_tokens 表

```sql
-- src/stratum/db/migrations/017_share_tokens.sql

CREATE TABLE IF NOT EXISTS share_tokens (
    token           VARCHAR PRIMARY KEY,          -- nanoid (短 URL friendly, 16 chars)
    resource_type   VARCHAR NOT NULL,             -- 'note' | 'substrate' | 'view' | 'report' (Phase 14 仅 note)
    resource_id     VARCHAR NOT NULL,
    corpus_id       VARCHAR NOT NULL,             -- 创建者的 corpus
    created_by      VARCHAR NOT NULL,             -- user_id
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at      TIMESTAMP,                    -- NULL = 永久
    revoked_at      TIMESTAMP,
    access_count    INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    allow_anonymous BOOLEAN DEFAULT TRUE,         -- false = 需登录
    meta_json       VARCHAR DEFAULT '{}'          -- 含 share 时的 snapshot config
);

CREATE INDEX idx_share_tokens_resource ON share_tokens(resource_type, resource_id);
CREATE INDEX idx_share_tokens_created_by ON share_tokens(created_by, created_at);
```

### 6.2 dao/share_tokens.py

```python
def create_share_token(*, resource_type: str, resource_id: str, corpus_id: str, created_by: str, expires_at: datetime | None = None, allow_anonymous: bool = True) -> ShareToken: ...
def get_share_token(token: str) -> ShareToken | None: ...
def list_user_shares(user_id: str, resource_type: str | None = None) -> list[ShareToken]: ...
def revoke_share(token: str, user_id: str) -> bool: ...                # 校验 user_id == created_by
def increment_access(token: str) -> None: ...                          # 每次 /share/:token 调用时
def cleanup_expired() -> int: ...
```

### 6.3 http_api/routes/share.py

```python
# POST /api/share/note/:note_id
# 权限: 必须 corpus_id 匹配 (user 拥有该 note)
class CreateShareRequest(BaseModel):
    expires_in_days: int | None = None      # None = 永久
    allow_anonymous: bool = True

class CreateShareResponse(BaseModel):
    token: str
    share_url: str                          # https://stratum.<domain>/share/:token
    expires_at: datetime | None


# GET /share/:token (public, no auth)
class PublicNoteResponse(BaseModel):
    note: NotePublic                        # 不含 user_id / corpus_id
    shared_by_username: str                 # 公开用户名
    shared_at: datetime
    # citation / fragments 含 (chunk-level)


# DELETE /api/share/:token
# 权限: 校验 user_id == created_by


# GET /api/shares (list current user's shares)
class ListSharesResponse(BaseModel):
    items: list[ShareTokenPublic]
    total: int
```

### 6.4 public-read 数据脱敏

`GET /share/:token` 返回的 PublicNoteResponse:
- ✅ 含: note 内容 / title / 创建时间 / shared_by_username
- ❌ 不含: user_id / corpus_id / email / 私人 tag (前缀 `_private_`) / 关联的私 note (backlinks 过滤)

```python
def to_public_note(note: Note, sharer: User) -> NotePublic:
    """脱敏: 移除任何 corpus 内部标识."""
    return NotePublic(
        title=note.title,
        content=_strip_private_refs(note.content),    # 移除 [[...]] 指向私 note 的反链
        created_at=note.created_at,
        shared_by_username=sharer.username,
        ...
    )
```

### 6.5 profile dao + avatar

#### migration 018 — profile 表 (拆 users 表, 解耦认证 vs profile)

```sql
-- src/stratum/db/migrations/018_user_profiles.sql

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id         VARCHAR PRIMARY KEY,          -- FK users.id
    display_name    VARCHAR,                      -- 可改, 跟 username 不同
    avatar_url      VARCHAR,                      -- /api/avatars/:user_id.png
    bio             VARCHAR,                      -- max 280 chars
    location        VARCHAR,                      -- 选填
    website         VARCHAR,                      -- 选填
    timezone        VARCHAR DEFAULT 'Asia/Shanghai',
    locale          VARCHAR DEFAULT 'zh-CN',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### avatar 上传

```python
# POST /api/users/me/avatar
# multipart/form-data, image/png|jpeg, max 2 MB, server resize 到 256x256
# 存到 ~/.stratum/avatars/<user_id>.png

# GET /api/avatars/:user_id.png (public, no auth)
# CDN-friendly, Cache-Control: 1 day
```

### 6.6 测试

```
tests/dao/test_share_tokens.py                  (≥10)
tests/dao/test_user_profile.py                  (≥8)
tests/http_api/test_share_routes.py             (≥15, 含 cross-corpus block 测试: A 的 share token, B 不能 revoke)
tests/http_api/test_profile_routes.py           (≥10)
tests/integration/test_share_public_access.py   (≥10, public read 不需 auth)
tests/integration/test_share_data_leak.py       (≥15, 关键: public response 不含 corpus_id / user_id / email / private tag)
```

**红线测试**:

```python
def test_public_share_response_no_user_id():
    """GET /share/:token 返回 JSON 不含 'user_id' / 'corpus_id' / 'email' 字段."""

def test_public_share_strips_private_backlinks():
    """note 内容含 [[private_note_title]] 反链, public response 中替换为 [私有引用]."""

def test_user_A_cannot_revoke_user_B_share():
    """DELETE /api/share/:token (token 属于 B), A 调用 → 403."""

def test_share_token_expires():
    """expired share 返回 410 Gone, 不返回内容."""
```

### 6.7 Wave 4 Gate

```bash
cd ~/projects/stratum
python3 src/stratum/db/run_migrations.py   # 017 + 018
pytest tests/dao/test_share_tokens.py tests/dao/test_user_profile.py tests/http_api/test_share_routes.py tests/http_api/test_profile_routes.py tests/integration/test_share_*.py -v --cov

# 端到端
ACCESS_TOKEN=$(...)
NOTE_ID=$(...)

# 创建 share
SHARE=$(curl -X POST http://localhost:9302/api/share/note/$NOTE_ID \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"allow_anonymous":true}')
TOKEN=$(echo $SHARE | jq -r .token)

# 匿名访问
curl http://localhost:9302/share/$TOKEN | jq
# 期待: 含 note / shared_by_username, 不含 user_id

git add -A && git commit -m "Phase 14 Wave 4: share 机制 + user profile + avatar"
```

报告:
```
Wave 4 ✅ (share + profile)
- migration 017 share_tokens / 018 user_profiles
- dao share_tokens / user_profile
- routes: POST/GET/DELETE /api/share + GET /share/:token (public) + profile + avatar
- 数据脱敏: public response 不含 user_id/corpus_id/email/private refs
- 红线测试: <N> 个全过
- 端到端 share + 匿名访问验证
- commit: <hash>
进 Wave 5
```

---

## §7 Wave 5 — REST API 补全 (0.3 月)

### 7.1 缺失的 REST endpoint (跟 Helios 9 Block 数据契约对齐)

| Block | 需要的 REST | 状态 |
|---|---|---|
| OSemanticSearch | POST /api/search | ⚠️ 新增 |
| OAIQAPanel | POST /api/agents/reading_companion/run | ⚠️ 新增 |
| OAISummaryCard | GET /api/agents/daily_digest/latest, GET /api/agents/runs?agent=daily_digest | ⚠️ 新增 |
| OScheduledJobsManager | GET/POST/PUT/DELETE /api/scheduled_jobs, GET /api/scheduled_jobs/:id/runs | ⚠️ 新增 |
| ODocumentTree | GET /api/substrates | ⚠️ 新增 (Helios 标的 v1.0 限制) |
| ODocumentReader | GET /api/substrates/:id, GET /api/substrates/:id/derivatives | ⚠️ 新增 |
| OAnnotationLayer | GET /api/fragments?substrate_id=X | ⚠️ 新增 (chunk-level) |
| OBacklinkPanel | GET /api/notes/:id/backlinks | ⚠️ 新增 |
| OCitationCard | (复用现有 citation 数据, 跟 search/agent 一起返回) | ✅ |

### 7.2 routes 实施 (按 Block 顺序)

#### POST /api/search

```python
class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    mode: Literal["strict", "augmented"] = "augmented"
    rerank: bool = False
    expand: bool = False
    view_id: str | None = None
    filter_medium: list[str] | None = None
    filter_tags: list[str] | None = None

class SearchResponse(BaseModel):
    results: list[SearchResult]      # Helios 已 typed
    metadata: SearchMetadata
    query_used: str
    expanded_queries: list[str] | None
```

实施: 调 `stratum_search()` 服务层包装, 服务层做 user_id → corpus_id 映射 + 注入 LLM provider (DeepSeek/DashScope) + 注入 rerank/expand caller (基于 request flag)。

#### POST /api/agents/:agent_name/run

```python
class RunAgentRequest(BaseModel):
    params: dict                     # agent-specific
    on_step_sse: bool = False        # v1.0 不支持 SSE, 强制 false

class RunAgentResponse(BaseModel):
    agent_run: AgentRun              # 跟 Phase 11C 后端 schema 一致
    citations: list[Citation]
```

实施: 调主 omodul/knowledge/agents/registry.py 的 Agent.run() (不修改 platform, 只在 Stratum 服务层调)。

#### GET /api/scheduled_jobs

```python
class ListScheduledJobsResponse(BaseModel):
    items: list[ScheduledJob]
    total: int

# POST /api/scheduled_jobs (create)
# PUT /api/scheduled_jobs/:id (update, e.g. enable/disable)
# DELETE /api/scheduled_jobs/:id
# GET /api/scheduled_jobs/:id/runs (list runs, with pagination)
```

实施: 调主 omodul/knowledge/scheduler/job_store.py (只读) + Stratum 服务层 dao 包装。

#### GET /api/substrates

```python
class ListSubstratesRequest(BaseModel):
    medium: list[str] | None = None
    tags: list[str] | None = None
    created_after: datetime | None = None
    cursor: str | None = None        # pagination
    limit: int = 50

class ListSubstratesResponse(BaseModel):
    items: list[Substrate]
    next_cursor: str | None
    total: int | None                 # nullable for large corpus
```

实施: dao/substrate.list_substrates 包装, 服务层加 cursor 编码 (base64 of last_id + last_created_at)。

#### GET /api/substrates/:id + /api/substrates/:id/derivatives

#### GET /api/fragments?substrate_id=X

#### GET /api/notes/:id/backlinks

详细 schema 见 STRATUM_API_v1.md (Helios 已 typed, 后端补 REST 即可, 不重新设计 schema)。

### 7.3 测试

```
tests/http_api/test_search_routes.py            (≥15)
tests/http_api/test_agent_routes.py             (≥10)
tests/http_api/test_scheduled_jobs_routes.py    (≥15)
tests/http_api/test_substrate_routes.py         (≥15)
tests/http_api/test_fragment_routes.py          (≥10)
tests/http_api/test_backlink_routes.py          (≥10)
tests/integration/test_corpus_isolation_in_routes.py (≥20, 关键: 所有新 routes 都 corpus 隔离)
```

### 7.4 Wave 5 Gate

```bash
cd ~/projects/stratum
pytest tests/http_api/ tests/integration/test_corpus_isolation_in_routes.py -v --cov

# OpenAPI 验证
curl http://localhost:9302/openapi.json | jq .paths | keys
# 期待: /api/auth/* + /api/users/me + /api/search + /api/agents/* + /api/scheduled_jobs + /api/substrates + /api/fragments + /api/notes/:id/backlinks + /api/share + /share/:token

# 全量回归测试
pytest tests/ -v

git add -A && git commit -m "Phase 14 Wave 5: REST API 补全 (search + agents + scheduled_jobs + substrates + fragments + backlinks)"
```

报告:
```
Wave 5 ✅ (REST API 补全)
- 8 endpoint 新增 (search / agents / scheduled_jobs / substrates / fragments / backlinks)
- 所有 routes 走 corpus_isolation middleware
- 渗透测试: 20+ 项全过
- OpenAPI 完整
- 测试: <N> 个全过, 全量回归 0 regression
- commit: <hash>
进 Part 2 (前端 Wave 6-9)
```

---

## §8 Part 1 完工 + 跨 Wave 整合

### 8.1 后端完工 SELF_CHECK

CC 完工时附 `SELF_CHECK_PHASE14_PART1.md`:
- Wave 0-5 全部 Gate 通过
- 5 红线 (覆盖率 / 测试数 / 接口规约 / 静态检查 / 文档)
- 渗透测试 (cross-corpus + data leak) 全部清单 + 通过证据
- 跟 Helios 9 Block 数据契约对齐表
- 现有功能 0 regression
- 端到端 demo: register → login → ingest → search → share → 匿名访问 全链路

### 8.2 Part 1 PR

```bash
git push origin phase14/backend-saas
# 创建 PR: Phase 14 Part 1 - 后端 SaaS 准产品基础设施
# Reviewer: Wiki (跨大量服务层, 不需 3O 经理人, 因为不动 omodul/knowledge/*)
```

### 8.3 公网发布 sign-off (R-6)

Wave 3 配置就绪, Wave 5 完工后 Wiki sign-off → CC 跑:

```bash
cd ~/projects/stratum/deploy
docker compose --profile public up -d cloudflared
# 验证: 公网 curl https://stratum.<wiki>/health → 200
```

报告公网 IP / 健康 / 测试用户访问。

---

## §9 异常处理 (R-1)

立即停 + 报告 advisor:
- migration 失败 (014 corpus_isolation 是 BREAKING, 数据迁移失败时回滚 backup)
- 渗透测试任一项 fail (corpus 隔离不能含糊)
- oskill.hybrid_search 实际没按 corpus 隔离 (Wave 2 §4.5, 临时 post-filter)
- 需要改 platform/omodul/oskill/oprim 才能完成 (R-4 禁止, 等 Phase 11D)
- 部署到公网前 (R-6 等 Wiki sign-off)

非阻塞继续:
- 邮件验证暂不接 SMTP (Wave 1 已注明)
- avatar 上传暂用本地存储 (后续 CDN)
- 实时通信不做 (v1.0 全非流式)

---

## §10 时间预算总览

| Wave | 工作 | 月 |
|---|---|---|
| 0 | 准入 | 0.02 |
| 1 | 用户系统 | 0.5-1 |
| 2 | corpus 隔离 | 1-1.5 |
| 3 | 公网部署 + rate limit + abuse | 0.5 |
| 4 | share 机制 + profile + avatar | 0.5 |
| 5 | REST API 补全 (8 endpoints) | 0.3 |
| **Part 1 总** | | **2.8-3.8 月** |

跟 Step 11 RFC §2.1 后端小计 (2.6-3.8 月) 接近, 略上浮因 abuse 模块加细。

---

**End Part 1**

— Stratum 经理人 Claude
2026-05-24
