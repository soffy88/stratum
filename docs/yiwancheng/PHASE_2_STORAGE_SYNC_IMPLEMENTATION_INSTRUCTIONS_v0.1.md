# PHASE_2_STORAGE_SYNC_IMPLEMENTATION_INSTRUCTIONS_v0.1.md

**任务**: 实施 Stratum Phase 2 网盘 + 多端同步
**执行者**: CC-A (跟 CC-B Phase 10 并行)
**执行模式**: Claude Code FULL AUTO
**SPEC 依据**:
- STRATUM_SPEC v0.5 §7 网盘适配层 + §12 多端同步
- 4O 扩充清单 v0.3 PATCH §B (Phase 2)
- ADR-006 (用户网盘 + 本地)
- ADR-009 (修订: Google Drive 替代阿里云盘, Wiki 拍板)

**预期产物**:
- platform/oprim 新增 sub-packages: storage.gdrive / storage.local / changefeed / push
- platform/oprim version: v2.2.0 → v2.3.0
- platform/oskill 新增 sub-package: sync (4 个 skills)
- platform/oskill version: v2.3.0 → v2.4.0
- platform/omodul 新增 sub-package: sync.bg_sync
- platform/omodul version: v1.2.0 → v1.3.0
- 端到端 demo: 设备 A 创建 substrate → GDrive → 设备 B 拉取 → 能搜
- 单元 + 集成测试全部通过

**前置**:
- ✅ Phase 1 完工 (v2.2.0 / v2.3.0 / v1.2.0 已 tag)
- ⏳ Wiki 申请的 Google Drive OAuth client_id + client_secret (Wiki 提供, 写入 ~/.stratum/secrets/gdrive_oauth.json)

**并行协调** (跟 CC-B Phase 10 共仓库):
- 同 branch (main), 不分叉
- 模块隔离: CC-A 只动 `oprim/storage/` / `oprim/changefeed/` / `oprim/push/` / `oskill/sync/` / `omodul/sync/`, **绝不动** `oprim/translate/` / `oskill/knowledge/translate_substrate.py`
- pyproject.toml 修改时 deps 加新行不删既有, 跟 CC-B 协调避免冲突
- 每完成一个 Wave 立即 commit + push
- CC-A 跟 CC-B 用各自 PR, 不互相 review (Wiki 集中验收)

---

## §0 FULL AUTO 头部规则 (必读)

### 0.1 红线 (绝对不允许)

**R-1: 失败不静默**

任何场景下禁止:
- `except Exception: return <default>` 不 emit 日志
- 同步失败时无声跳过 (必须 emit 事件)
- 上传失败时假装成功 (返回假 file_id)
- token 过期时静默不刷新 (必须报告 + 重试)
- 网络中断时直接 swallow (必须区分临时 vs 永久错误)
- 冲突解决时悄悄丢数据 (必须 log + 触发用户警告)

降级三条件 (跟 Phase 1 / 10 同标准):
1. 调用方显式参数控制
2. obase.logging emit 显式 error/warning
3. 调用方可区分成功 vs 降级成功

**R-2: SPEC 是真理源**

冲突时**停止报告**, 不自行解决。具体禁止:

- 不按 ADR-009 修订选 GDrive 作主 (例: 改默认到 onedrive / aliyundrive)
- 不按 4O v0.3 §B.2 changefeed schema (例: 改 event_type 命名 / 字段)
- 不按 SPEC v0.5 §12 多端同步策略 (例: 改 last-write-wins 为别的)
- 不按 ADR-016 本地部署 (例: 强制走远程后端 sync server)
- 不按 ADR-017 不做 E2EE (例: 顺手加 E2E 加密)

**R-4: 禁止扩大范围**

Phase 2 范围严格如下:

✅ 允许:
- oprim.storage.gdrive (Google Drive OAuth + API)
- oprim.storage.local (本地文件系统)
- oprim.changefeed (event log + reader + compactor + snapshot)
- oprim.push (web push + email)
- oskill.sync.* (flush_outbox / apply_remote_events / snapshot_backup / restore_from_snapshot)
- omodul.sync.bg_sync (守护进程)
- 端到端: 设备 A → GDrive → 设备 B

❌ 禁止 (留给后续 Phase):
- onedrive / dropbox provider (P1/P2, 不在 Phase 2 起步)
- aliyundrive (DEFER, 凭证未解决)
- 微信小程序推送 wechat_mp (DEFER, Phase 4)
- 跨用户协作 / 多用户权限 (v2.x)
- E2E 加密 (ADR-017 禁)
- substrate.is_pinned 字段 (Phase 1.5 干, 不归你)
- hybrid_search mode 参数 (Phase 1.5, 不归你)
- 翻译 / TTS / Agent (Phase 10/11, 不归你)
- 浏览器扩展 (Phase 4)
- Gemini / 任何其他外挂 (Phase 11+)

如发现超范围, **立即停止报告**, 不要"顺手做了"。

**R-5: namespace 隔离 (跟 CC-B 协调)**

绝不动 (CC-B 负责):
- `oprim/translate/` (CC-B 新建)
- `oskill/knowledge/translate_substrate.py` (CC-B 新建)

只动:
- `oprim/storage/` (扩展, 已有基础)
- `oprim/changefeed/` (新建整个目录)
- `oprim/push/` (新建整个目录)
- `oskill/sync/` (新建整个目录)
- `omodul/sync/` (新建整个目录)
- `oprim/pyproject.toml` (加 deps, 改 version, **小心 merge conflict**)
- `oskill/pyproject.toml` (同上)
- `omodul/pyproject.toml` (同上)

如发现需要改隔离区文件, **立即停止报告**让 Wiki 协调跨 CC 修改。

### 0.2 工作流程

```
Wave 0: 准入检查 + GDrive OAuth 验证
  ↓
Wave 1: oprim.storage.gdrive + storage.local 实施
  ↓ verify
Wave 2: oprim.changefeed 实施 (event log + reader + compactor + snapshot)
  ↓ verify
Wave 3: oprim.push 实施 (web push + email)
  ↓ verify
Wave 4: oskill.sync.* 实施 (4 个 skill)
  ↓ verify
Wave 5: omodul.sync.bg_sync 守护进程
  ↓ verify
Wave 6: 测试 + 端到端 demo (两设备模拟) + Gate 验收
  ↓
报告完工
```

每个 Wave 完成立即 commit, 内部 self-verify 通过才进下一 Wave。

### 0.3 输出要求 (跟 Phase 10 同标准)

- 每个 Wave 完工报告: 完工内容 + 测试结果 + commit hash
- 测试覆盖率 ≥ 80%
- 不打太极, 失败就报告失败
- Wave 中间不问 Wiki 问题, 攒到末尾或停止报告

---

## §1 Wave 0 — 准入检查

### 1.1 仓库状态

```bash
cd ~/projects/platform/oprim
git status   # clean 或仅 CC-B translate/ 进行中
git pull
git log --oneline -5

cd ~/projects/platform/oskill
git status
git pull

cd ~/projects/platform/omodul
git status
git pull
```

### 1.2 验证 Phase 1 状态

```bash
cd ~/projects/platform/oprim
python -c "import oprim; print(oprim.__version__)"   # 期待 2.2.0+
python -c "from oprim import classifier, parser, embedding, vector_db, fulltext, meta_db, llm, mcp; print('OK')"

cd ~/projects/platform/oskill
python -c "import oskill; print(oskill.__version__)"   # 期待 2.3.0+
python -c "from oskill.knowledge import (
    classify_inbox_file, detect_duplicate_substrate, generate_derivative,
    hybrid_search, ingest_substrate, lint
); print('OK')"

cd ~/projects/platform/omodul
python -c "import omodul; print(omodul.__version__)"   # 期待 1.2.0+
```

如失败, **停止报告**。

### 1.3 GDrive OAuth 验证

```bash
# 验证 secrets 文件存在
ls -la ~/.stratum/secrets/gdrive_oauth.json
# 期待: {"client_id": "...", "client_secret": "...", "redirect_uri": "..."}

# 验证 google-api-python-client 可装
pip install google-api-python-client google-auth-oauthlib google-auth-httplib2 --break-system-packages --quiet
python -c "
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
print('Google libs OK')
"

# 验证 OAuth flow 可运行 (但不实际授权, 只验证 client_id 格式)
python -c "
import json
with open('$HOME/.stratum/secrets/gdrive_oauth.json') as f:
    cfg = json.load(f)
assert 'client_id' in cfg
assert 'client_secret' in cfg
assert cfg['client_id'].endswith('.apps.googleusercontent.com'), 'client_id format invalid'
print('OAuth config OK:', cfg['client_id'][:30])
"
```

如 secrets 文件不存在或格式不对, **立即停止报告等 Wiki 处理**。

### 1.4 Wave 0 完成报告

```
=== Wave 0 完成 ===
- Phase 1 baseline OK
- GDrive OAuth config OK (client_id 前缀: <xxx>)
- google libs install OK
- CC-B 当前 branch 状态: <pull 后 log>
- 进入 Wave 1
```

---

## §2 Wave 1 — oprim.storage.gdrive + storage.local

### 2.1 目录结构

```
platform/oprim/oprim/storage/
├── __init__.py
├── protocol.py            # StorageAdapter Protocol
├── errors.py              # 异常类
├── _oauth.py              # OAuth flow 共享
├── providers/
│   ├── __init__.py
│   ├── gdrive.py          # Google Drive 实施
│   └── local.py           # 本地文件系统实施
└── tests/
    └── ...
```

### 2.2 protocol.py 实施

```python
# oprim/storage/protocol.py
from typing import Protocol, AsyncIterator, BinaryIO
from dataclasses import dataclass
from datetime import datetime

@dataclass
class StorageFile:
    file_id: str           # provider 内部 ID (gdrive file_id / local path)
    name: str
    size: int
    mime_type: str
    created_at: datetime
    modified_at: datetime
    md5: str | None
    metadata: dict         # provider-specific


@dataclass
class StorageQuota:
    used_bytes: int
    total_bytes: int
    available_bytes: int


@dataclass
class UploadResult:
    file_id: str
    size: int
    md5: str


class StorageAdapter(Protocol):
    """统一存储 provider 接口"""

    name: str
    supports_changes_api: bool   # 增量同步能力
    max_file_size: int            # 单文件上限

    async def authenticate(self) -> bool:
        """OAuth 流程, 首次使用"""

    async def upload(
        self,
        local_path: str,
        remote_path: str,
        mime_type: str | None = None,
        on_progress: callable | None = None,
    ) -> UploadResult: ...

    async def download(
        self,
        file_id: str,
        local_path: str,
        on_progress: callable | None = None,
    ) -> None: ...

    async def delete(self, file_id: str) -> None: ...

    async def list_files(
        self,
        folder: str = "/Stratum",
        recursive: bool = False,
        page_size: int = 100,
    ) -> AsyncIterator[StorageFile]: ...

    async def get_file_metadata(self, file_id: str) -> StorageFile: ...

    async def get_quota(self) -> StorageQuota: ...

    async def list_changes_since(
        self,
        page_token: str | None,
    ) -> tuple[list[dict], str]:
        """
        增量变更 (用于 changefeed pull):
        Returns: (list of change events, next_page_token)
        """

    async def health_check(self) -> bool: ...
```

### 2.3 errors.py

```python
# oprim/storage/errors.py
from obase.errors import OBaseError

class StorageError(OBaseError): pass
class AuthenticationError(StorageError): pass
class QuotaExceededError(StorageError): pass
class FileNotFoundError(StorageError): pass
class RateLimitError(StorageError): pass
class NetworkError(StorageError): pass
class ConflictError(StorageError): pass    # 文件已存在 / md5 不匹配
class TokenExpiredError(StorageError): pass
```

### 2.4 providers/gdrive.py

```python
# oprim/storage/providers/gdrive.py
import os, json, asyncio
from pathlib import Path
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError
from obase.logging import get_logger

from ..protocol import StorageAdapter, StorageFile, StorageQuota, UploadResult
from ..errors import (
    StorageError, AuthenticationError, QuotaExceededError,
    FileNotFoundError, RateLimitError, NetworkError, TokenExpiredError,
)

logger = get_logger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.file']
# drive.file: 只能访问 app 创建的文件, 隐私最佳
# drive: 完整权限 (避免)

class GoogleDriveAdapter:
    name = "gdrive"
    supports_changes_api = True
    max_file_size = 5 * 1024**4  # 5 TB per file

    def __init__(
        self,
        credentials_dir: Path = Path.home() / ".stratum" / "credentials",
        oauth_config_path: Path = Path.home() / ".stratum" / "secrets" / "gdrive_oauth.json",
    ):
        self.credentials_dir = credentials_dir
        self.credentials_dir.mkdir(parents=True, exist_ok=True)
        self.oauth_config_path = oauth_config_path
        self.token_path = credentials_dir / "gdrive_token.json"
        self._service = None
        self._creds: Credentials | None = None

    async def authenticate(self) -> bool:
        """OAuth flow. 首次需要浏览器授权, 后续自动 refresh token。"""
        # 1. 尝试加载已存 token
        if self.token_path.exists():
            self._creds = Credentials.from_authorized_user_file(str(self.token_path), SCOPES)

        # 2. 如果没有 token 或 expired, 跑 OAuth flow
        if not self._creds or not self._creds.valid:
            if self._creds and self._creds.expired and self._creds.refresh_token:
                try:
                    self._creds.refresh(...)
                except Exception as e:
                    logger.error("gdrive_token_refresh_failed", error=str(e))
                    raise TokenExpiredError(f"Refresh failed: {e}") from e
            else:
                if not self.oauth_config_path.exists():
                    raise AuthenticationError(f"OAuth config not found: {self.oauth_config_path}")
                flow = InstalledAppFlow.from_client_secrets_file(str(self.oauth_config_path), SCOPES)
                # 本地浏览器授权 (Wiki 看到并点击)
                self._creds = flow.run_local_server(port=0)

            # 3. 持久化 token
            self.token_path.write_text(self._creds.to_json())
            os.chmod(self.token_path, 0o600)

        # 4. 构建 service
        self._service = build('drive', 'v3', credentials=self._creds, cache_discovery=False)
        return True

    def _ensure_authenticated(self):
        if self._service is None:
            raise AuthenticationError("Not authenticated. Call authenticate() first.")

    async def _ensure_folder(self, folder_path: str = "/Stratum") -> str:
        """确保 /Stratum 文件夹存在, 返回 folder_id"""
        # 顶层 Stratum 文件夹查询
        # 如不存在则创建
        ...

    async def upload(
        self,
        local_path: str,
        remote_path: str,
        mime_type: str | None = None,
        on_progress: callable | None = None,
    ) -> UploadResult:
        self._ensure_authenticated()

        # resolve folder
        folder_path = "/Stratum/" + "/".join(remote_path.split("/")[:-1]) if "/" in remote_path else "/Stratum"
        folder_id = await self._ensure_folder(folder_path)
        file_name = remote_path.split("/")[-1]

        media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
        metadata = {"name": file_name, "parents": [folder_id]}

        try:
            # 在 thread pool 执行同步 API (Google client 不是 async)
            file = await asyncio.to_thread(
                self._service.files().create(body=metadata, media_body=media, fields="id,size,md5Checksum").execute
            )
            return UploadResult(
                file_id=file["id"],
                size=int(file.get("size", 0)),
                md5=file.get("md5Checksum", ""),
            )
        except HttpError as e:
            self._handle_http_error(e, context=f"upload {remote_path}")

    async def download(self, file_id: str, local_path: str, on_progress=None):
        self._ensure_authenticated()
        try:
            request = self._service.files().get_media(fileId=file_id)
            with open(local_path, "wb") as fh:
                downloader = MediaIoBaseDownload(fh, request, chunksize=10 * 1024 * 1024)
                done = False
                while not done:
                    status, done = await asyncio.to_thread(downloader.next_chunk)
                    if on_progress:
                        on_progress(status.progress() if status else 1.0)
        except HttpError as e:
            self._handle_http_error(e, context=f"download {file_id}")

    async def delete(self, file_id: str):
        self._ensure_authenticated()
        try:
            await asyncio.to_thread(self._service.files().delete(fileId=file_id).execute)
        except HttpError as e:
            self._handle_http_error(e, context=f"delete {file_id}")

    async def list_files(self, folder="/Stratum", recursive=False, page_size=100):
        self._ensure_authenticated()
        folder_id = await self._ensure_folder(folder)
        page_token = None
        while True:
            try:
                resp = await asyncio.to_thread(
                    self._service.files().list(
                        q=f"'{folder_id}' in parents and trashed=false",
                        pageSize=page_size,
                        pageToken=page_token,
                        fields="nextPageToken, files(id,name,size,mimeType,createdTime,modifiedTime,md5Checksum)",
                    ).execute
                )
                for f in resp.get("files", []):
                    yield StorageFile(
                        file_id=f["id"], name=f["name"],
                        size=int(f.get("size", 0)),
                        mime_type=f.get("mimeType", ""),
                        created_at=datetime.fromisoformat(f["createdTime"].rstrip("Z")),
                        modified_at=datetime.fromisoformat(f["modifiedTime"].rstrip("Z")),
                        md5=f.get("md5Checksum"),
                        metadata={},
                    )
                page_token = resp.get("nextPageToken")
                if not page_token:
                    break
            except HttpError as e:
                self._handle_http_error(e, context=f"list_files {folder}")

    async def get_quota(self) -> StorageQuota:
        self._ensure_authenticated()
        try:
            about = await asyncio.to_thread(
                self._service.about().get(fields="storageQuota").execute
            )
            q = about["storageQuota"]
            used = int(q.get("usage", 0))
            total = int(q.get("limit", 0))
            return StorageQuota(used_bytes=used, total_bytes=total, available_bytes=total - used)
        except HttpError as e:
            self._handle_http_error(e, context="get_quota")

    async def list_changes_since(self, page_token: str | None) -> tuple[list, str]:
        """GDrive Changes API - 增量同步"""
        self._ensure_authenticated()
        if page_token is None:
            # 第一次, 获取起始 token
            resp = await asyncio.to_thread(
                self._service.changes().getStartPageToken().execute
            )
            return ([], resp["startPageToken"])

        try:
            resp = await asyncio.to_thread(
                self._service.changes().list(
                    pageToken=page_token,
                    fields="nextPageToken, newStartPageToken, changes(fileId, removed, file(id,name,modifiedTime,md5Checksum))",
                ).execute
            )
            changes = resp.get("changes", [])
            next_token = resp.get("nextPageToken") or resp.get("newStartPageToken")
            return (changes, next_token)
        except HttpError as e:
            self._handle_http_error(e, context="list_changes")

    async def health_check(self) -> bool:
        try:
            self._ensure_authenticated()
            await asyncio.to_thread(self._service.about().get(fields="user").execute)
            return True
        except Exception as e:
            logger.warning("gdrive_health_check_failed", error=str(e))
            return False

    def _handle_http_error(self, e: HttpError, context: str):
        """统一 HTTP error 处理"""
        status = e.resp.status
        if status == 401:
            logger.error("gdrive_auth_failed", context=context)
            raise TokenExpiredError(f"Auth failed at {context}") from e
        elif status == 403:
            # 区分 quota / rate limit / permission
            reason = e.error_details[0].get("reason") if e.error_details else ""
            if "quotaExceeded" in reason or "storageQuotaExceeded" in reason:
                raise QuotaExceededError(f"Quota exceeded at {context}") from e
            elif "rateLimitExceeded" in reason or "userRateLimitExceeded" in reason:
                raise RateLimitError(f"Rate limit at {context}") from e
            else:
                raise StorageError(f"Forbidden at {context}: {reason}") from e
        elif status == 404:
            raise FileNotFoundError(f"Not found at {context}") from e
        elif status >= 500:
            raise NetworkError(f"Server error at {context}: {status}") from e
        else:
            raise StorageError(f"HTTP {status} at {context}: {e}") from e
```

### 2.5 providers/local.py

```python
# oprim/storage/providers/local.py
import hashlib, shutil, asyncio
from pathlib import Path
from datetime import datetime
from ..protocol import StorageAdapter, StorageFile, StorageQuota, UploadResult
from ..errors import StorageError, FileNotFoundError
from obase.logging import get_logger

logger = get_logger(__name__)

class LocalStorageAdapter:
    """本地文件系统 (用于隐私敏感场景或测试)"""
    name = "local"
    supports_changes_api = False
    max_file_size = 100 * 1024**3  # 100 GB

    def __init__(self, root_dir: Path = Path.home() / ".stratum" / "storage_local"):
        self.root = root_dir
        self.root.mkdir(parents=True, exist_ok=True)

    async def authenticate(self) -> bool:
        return self.root.exists() and self.root.is_dir()

    async def upload(self, local_path, remote_path, mime_type=None, on_progress=None) -> UploadResult:
        dest = self.root / remote_path.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, local_path, dest)

        # md5
        h = hashlib.md5()
        with open(dest, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return UploadResult(file_id=str(dest), size=dest.stat().st_size, md5=h.hexdigest())

    async def download(self, file_id, local_path, on_progress=None):
        src = Path(file_id)
        if not src.exists():
            raise FileNotFoundError(f"File not found: {file_id}")
        await asyncio.to_thread(shutil.copy2, src, local_path)

    async def delete(self, file_id):
        p = Path(file_id)
        if p.exists():
            p.unlink()

    async def list_files(self, folder="/Stratum", recursive=False, page_size=100):
        base = self.root / folder.lstrip("/")
        if not base.exists():
            return
        pattern = "**/*" if recursive else "*"
        for p in base.glob(pattern):
            if p.is_file():
                st = p.stat()
                yield StorageFile(
                    file_id=str(p), name=p.name,
                    size=st.st_size, mime_type="application/octet-stream",
                    created_at=datetime.fromtimestamp(st.st_ctime),
                    modified_at=datetime.fromtimestamp(st.st_mtime),
                    md5=None, metadata={},
                )

    async def get_quota(self) -> StorageQuota:
        st = shutil.disk_usage(self.root)
        return StorageQuota(used_bytes=st.used, total_bytes=st.total, available_bytes=st.free)

    async def list_changes_since(self, page_token):
        raise NotImplementedError("Local storage doesn't support changes API. Use polling instead.")

    async def health_check(self) -> bool:
        return self.root.exists() and self.root.is_dir()
```

### 2.6 Wave 1 测试

```bash
cd ~/projects/platform/oprim
pip install google-api-python-client google-auth-oauthlib --break-system-packages

# 单元测试
pytest oprim/tests/storage/test_protocol.py -v
pytest oprim/tests/storage/test_local.py -v

# gdrive 集成测试 (实际 OAuth, Wiki 配合手动授权一次, 后续自动 refresh)
pytest oprim/tests/storage/test_gdrive_integration.py -v --runintegration
```

测试要求:
- LocalStorageAdapter: 完整 CRUD 单元测试
- GoogleDriveAdapter: OAuth flow + 上传 (小文件) + 下载 + 删除 + list + 配额
- 错误处理: 401 / 403 / 404 / 5xx 各情况
- changes API: 起始 token + 增量 changes

### 2.7 Wave 1 完成报告

```
=== Wave 1 完成 ===
- oprim/storage/ 模块结构 OK
- protocol.py: StorageAdapter Protocol + 4 dataclass
- errors.py: 8 异常类
- providers/local.py: 完整实施
- providers/gdrive.py: 完整实施 (OAuth + CRUD + changes API + quota)
- 单元测试 (LocalStorageAdapter): 通过 <数>
- 集成测试 (GoogleDriveAdapter): <数> (Wiki 一次性授权后)
- commit hash: <xxx>
```

---

## §3 Wave 2 — oprim.changefeed

### 3.1 目录结构

```
platform/oprim/oprim/changefeed/
├── __init__.py
├── schema.py              # event 类型定义
├── writer.py              # append-only log writer
├── reader.py              # cursor-based reader
├── compactor.py           # 历史压缩
├── snapshot.py            # 周期性 snapshot
└── tests/
```

### 3.2 schema.py

```python
# oprim/changefeed/schema.py
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

class EventType(str, Enum):
    SUBSTRATE_CREATED = "substrate.created"
    SUBSTRATE_UPDATED = "substrate.updated"
    SUBSTRATE_DELETED = "substrate.deleted"
    SUBSTRATE_PINNED = "substrate.pinned"          # Phase 1.5
    SUBSTRATE_UNPINNED = "substrate.unpinned"      # Phase 1.5
    DERIVATIVE_CREATED = "derivative.created"
    DERIVATIVE_DELETED = "derivative.deleted"
    NOTE_CREATED = "note.created"
    NOTE_UPDATED = "note.updated"
    NOTE_DELETED = "note.deleted"
    CONCEPT_CREATED = "concept.created"
    CONCEPT_LINKED = "concept.linked"
    CONCEPT_UNLINKED = "concept.unlinked"


@dataclass
class ChangefeedEvent:
    id: int                    # auto increment
    device_id: str             # 来源设备
    user_id: str               # UUID
    event_type: EventType
    aggregate_id: str | None   # ULID
    payload: dict
    created_at: datetime
    seq: int                   # 全序序号 per user
```

### 3.3 writer.py 实施 (PostgreSQL 后端)

```python
# oprim/changefeed/writer.py
import json, uuid
from datetime import datetime
from oprim.meta_db import get_db_pool
from obase.logging import get_logger
from .schema import EventType, ChangefeedEvent

logger = get_logger(__name__)

class ChangefeedWriter:
    """Append-only log writer"""

    def __init__(self, user_id: str, device_id: str):
        self.user_id = user_id
        self.device_id = device_id

    async def append(
        self,
        event_type: EventType,
        aggregate_id: str | None,
        payload: dict,
    ) -> ChangefeedEvent:
        """
        幂等性: 同 (user_id, aggregate_id, event_type, payload md5) 重复写入不重
        seq 自增 per user
        """
        async with get_db_pool().acquire() as conn:
            async with conn.transaction():
                # 1. 获取下个 seq (per user 锁)
                next_seq = await conn.fetchval(
                    "SELECT COALESCE(MAX(seq), 0) + 1 FROM changefeed_events WHERE user_id = $1 FOR UPDATE",
                    self.user_id,
                )
                # 2. 插入
                row = await conn.fetchrow(
                    """
                    INSERT INTO changefeed_events
                        (device_id, user_id, event_type, aggregate_id, payload, created_at, seq)
                    VALUES ($1, $2, $3, $4, $5::jsonb, NOW(), $6)
                    ON CONFLICT (user_id, seq) DO NOTHING
                    RETURNING id, created_at
                    """,
                    self.device_id, self.user_id, event_type.value,
                    aggregate_id, json.dumps(payload), next_seq,
                )
                if not row:
                    raise StorageError("Conflict on (user_id, seq)")

                event = ChangefeedEvent(
                    id=row["id"], device_id=self.device_id, user_id=self.user_id,
                    event_type=event_type, aggregate_id=aggregate_id,
                    payload=payload, created_at=row["created_at"], seq=next_seq,
                )
                logger.info("changefeed_event_written", event_type=event_type.value, seq=next_seq)
                return event
```

### 3.4 reader.py 实施

```python
# oprim/changefeed/reader.py
class ChangefeedReader:
    def __init__(self, user_id: str):
        self.user_id = user_id

    async def read_since(
        self,
        since_seq: int,
        batch_size: int = 100,
        event_types: list[EventType] | None = None,
    ) -> list[ChangefeedEvent]:
        """读 seq > since_seq 的 events, 按 seq 升序"""
        async with get_db_pool().acquire() as conn:
            query = """
                SELECT id, device_id, user_id, event_type, aggregate_id, payload, created_at, seq
                FROM changefeed_events
                WHERE user_id = $1 AND seq > $2
            """
            args = [self.user_id, since_seq]
            if event_types:
                query += " AND event_type = ANY($3)"
                args.append([et.value for et in event_types])
            query += " ORDER BY seq ASC LIMIT $%d" % (len(args) + 1)
            args.append(batch_size)

            rows = await conn.fetch(query, *args)
            return [self._row_to_event(r) for r in rows]

    async def get_latest_seq(self) -> int:
        async with get_db_pool().acquire() as conn:
            return await conn.fetchval(
                "SELECT COALESCE(MAX(seq), 0) FROM changefeed_events WHERE user_id = $1",
                self.user_id,
            )
```

### 3.5 compactor.py 实施

```python
# oprim/changefeed/compactor.py
class ChangefeedCompactor:
    """
    压缩规则:
    - SUBSTRATE_DELETED + 之前的 SUBSTRATE_CREATED/UPDATED → 全删 (墓碑)
    - 连续 SUBSTRATE_UPDATED → 保留最新一个
    - 跨 snapshot 边界的 events 不压缩
    """

    async def compact_user_events(
        self,
        user_id: str,
        before_seq: int,
        dry_run: bool = False,
    ) -> dict:
        """压缩 seq < before_seq 的 events"""
        ...
```

### 3.6 snapshot.py 实施

```python
# oprim/changefeed/snapshot.py
class ChangefeedSnapshot:
    """
    周期性快照:
    - 把当前 DB 状态序列化成 snapshot.json (含 substrate / concept / note / pinned 等)
    - 上传到 storage.gdrive
    - 标记 snapshot_at_seq (新设备 cold start 用)
    """

    async def create_snapshot(
        self,
        user_id: str,
        storage_adapter,
    ) -> dict:
        ...

    async def restore_from_snapshot(
        self,
        snapshot_file_id: str,
        storage_adapter,
    ) -> dict:
        ...
```

### 3.7 数据库 migration

```sql
-- migrations/v2_3_001_changefeed.sql
CREATE TABLE IF NOT EXISTS changefeed_events (
    id BIGSERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    user_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    aggregate_id TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    seq BIGINT NOT NULL,
    UNIQUE (user_id, seq)
);

CREATE INDEX IF NOT EXISTS idx_changefeed_user_seq
    ON changefeed_events(user_id, seq);
CREATE INDEX IF NOT EXISTS idx_changefeed_user_created
    ON changefeed_events(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_changefeed_aggregate
    ON changefeed_events(user_id, aggregate_id) WHERE aggregate_id IS NOT NULL;
```

### 3.8 Wave 2 测试

- writer 幂等性
- reader cursor 正确性 (since_seq 严格大于)
- compactor 不丢 event
- snapshot create + restore 等价 full replay
- 并发 writer (两 device 同时写, seq 不冲突)

### 3.9 Wave 2 完成报告

(略, 同 Wave 1 格式)

---

## §4 Wave 3 — oprim.push

### 4.1 目录结构

```
platform/oprim/oprim/push/
├── __init__.py
├── protocol.py            # PushChannel Protocol
├── channels/
│   ├── web.py             # Web Push (VAPID)
│   └── email.py           # Email (SMTP / SendGrid)
├── dispatcher.py          # 多通道路由
└── tests/
```

### 4.2 protocol.py

```python
# oprim/push/protocol.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class PushResult:
    channel: str          # "web" | "email"
    success: bool
    recipient: str
    error_message: str | None = None
    sent_at: datetime = None


class PushChannel(Protocol):
    name: str

    async def send(
        self,
        recipient: str,
        title: str,
        body: str,
        deep_link: str | None = None,
        metadata: dict | None = None,
    ) -> PushResult: ...

    async def health_check(self) -> bool: ...
```

### 4.3 channels/web.py + email.py

(略, 具体实施跟 protocol 对齐, web 用 pywebpush, email 用 smtplib + Jinja2)

### 4.4 dispatcher.py

```python
# oprim/push/dispatcher.py
class PushDispatcher:
    def __init__(self, channels: dict[str, PushChannel]):
        self.channels = channels

    async def push(
        self,
        user_id: str,
        title: str,
        body: str,
        channels_preference: list[str] = ["web", "email"],
        deep_link: str | None = None,
    ) -> list[PushResult]:
        """按优先级尝试, 第一个成功就停"""
        results = []
        for ch_name in channels_preference:
            if ch_name not in self.channels:
                continue
            ch = self.channels[ch_name]
            recipient = await self._get_recipient(user_id, ch_name)
            if not recipient:
                continue
            result = await ch.send(recipient, title, body, deep_link)
            results.append(result)
            if result.success:
                break
        return results
```

### 4.5 数据库 migration

```sql
-- migrations/v2_3_002_push.sql
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id ULID PRIMARY KEY,
    user_id UUID NOT NULL,
    channel TEXT NOT NULL,        -- web | email | wechat_mp
    recipient TEXT NOT NULL,       -- endpoint / email / openid
    keys JSONB,                    -- web push p256dh + auth
    enabled BOOL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 4.6 Wave 3 测试

- web push: 浏览器无连接时记录排队
- email: 模板渲染 + 发送 (mock SMTP)
- dispatcher: 优先级回退
- 失败重试

---

## §5 Wave 4 — oskill.sync.*

### 5.1 目录结构

```
platform/oskill/oskill/sync/
├── __init__.py
├── errors.py
├── flush_outbox.py
├── apply_remote_events.py
├── snapshot_backup.py
├── restore_from_snapshot.py
└── tests/
```

### 5.2 flush_outbox.py

```python
# oskill/sync/flush_outbox.py
"""
1. 读 ~/.stratum/outbox/ 中所有 pending events
2. 按 batch 上传到 storage:/Stratum/changefeed/events_{date}.jsonl
3. 上传成功后从 outbox 删除 + 写入本地 last_flushed_seq
4. 处理冲突 (server seq 大于 local) → 触发 apply_remote_events
"""

async def flush_outbox(
    user_id: str,
    device_id: str,
    storage: StorageAdapter,
    outbox_dir: Path = Path.home() / ".stratum" / "outbox",
    batch_size: int = 50,
) -> FlushResult:
    ...
```

### 5.3 apply_remote_events.py

```python
# oskill/sync/apply_remote_events.py
"""
1. 从 storage 读 changefeed/events_*.jsonl 中 seq > since_seq 的 events
2. 按 event_type 路由到 handler
3. apply 到本地 meta DB
4. 更新 last_applied_seq
5. 触发索引重建
"""

EVENT_HANDLERS = {
    EventType.SUBSTRATE_CREATED: _handle_substrate_created,
    EventType.SUBSTRATE_UPDATED: _handle_substrate_updated,
    EventType.SUBSTRATE_DELETED: _handle_substrate_deleted,
    EventType.SUBSTRATE_PINNED: _handle_substrate_pinned,    # Phase 1.5
    ...
}

async def apply_remote_events(
    user_id: str,
    device_id: str,
    storage: StorageAdapter,
    since_seq: int,
) -> ApplyResult:
    ...
```

### 5.4 snapshot_backup.py + restore_from_snapshot.py

(略, 具体见 4O v0.3 §B.4)

### 5.5 Wave 4 测试

- 端到端 (单机模拟): 模拟设备 A 操作 → flush → 模拟设备 B apply → 状态一致
- 冲突: 同 substrate 两 device 同时改 → last-write-wins (按 created_at)
- 离线: 断网时操作进 outbox, 联网 flush
- snapshot/restore 等价 replay

---

## §6 Wave 5 — omodul.sync.bg_sync

### 6.1 实施

```python
# omodul/sync/bg_sync.py
import asyncio, signal
from oskill.sync import flush_outbox, apply_remote_events, snapshot_backup

class BackgroundSyncDaemon:
    def __init__(
        self,
        user_id: str,
        device_id: str,
        storage,
        flush_interval_sec: int = 30,
        pull_interval_sec: int = 60,
        snapshot_interval_hours: int = 24,
    ):
        self.user_id = user_id
        self.device_id = device_id
        self.storage = storage
        self.flush_interval = flush_interval_sec
        self.pull_interval = pull_interval_sec
        self.snapshot_interval = snapshot_interval_hours * 3600
        self._stop = asyncio.Event()
        self._last_snapshot_at = None

    async def run(self):
        signal.signal(signal.SIGTERM, lambda *_: asyncio.create_task(self.shutdown()))
        await self.storage.authenticate()

        # 启动并发 task
        tasks = [
            asyncio.create_task(self._flush_loop()),
            asyncio.create_task(self._pull_loop()),
            asyncio.create_task(self._snapshot_loop()),
        ]
        await self._stop.wait()
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _flush_loop(self):
        while not self._stop.is_set():
            try:
                await flush_outbox(self.user_id, self.device_id, self.storage)
            except Exception as e:
                logger.error("flush_loop_error", error=str(e))
                await asyncio.sleep(60)  # 退避
                continue
            await asyncio.sleep(self.flush_interval)

    async def _pull_loop(self):
        ...

    async def _snapshot_loop(self):
        ...

    async def shutdown(self):
        self._stop.set()

    def status(self) -> dict:
        return {
            "last_flush_at": ...,
            "last_pull_at": ...,
            "last_snapshot_at": self._last_snapshot_at,
            "outbox_pending_count": ...,
            "last_applied_seq": ...,
        }
```

### 6.2 启动入口

```bash
python -m omodul.sync.bg_sync --user-id=<uuid> --device-id=<device>
```

---

## §7 Wave 6 — 测试 + 端到端 demo + Gate 验收

### 7.1 端到端 demo (单机模拟两 device)

```bash
# Setup
stratum init --device-id=device_A
stratum init --device-id=device_B --home=$HOME/.stratum_B

# Device A: 创建 substrate
cp /tmp/paper.md ~/.stratum/inbox/
python -m omodul.knowledge.process_inbox
# 拿到 substrate_id

# Device A: 启动 bg_sync, flush 到 GDrive
python -m omodul.sync.bg_sync --user-id=$USER_ID --device-id=device_A &
sleep 60  # 等 flush

# Device B: 启动 bg_sync, pull 从 GDrive
HOME=$HOME/.stratum_B python -m omodul.sync.bg_sync --user-id=$USER_ID --device-id=device_B &
sleep 60  # 等 pull

# Device B: 搜该 substrate
HOME=$HOME/.stratum_B python -c "
from oskill.knowledge import hybrid_search
import asyncio
results = asyncio.run(hybrid_search(query='<关键词>'))
assert len(results) > 0
print('Sync OK:', results[0].title)
"
```

### 7.2 Gate 验收

| 验收项 | 通过标准 |
|---|---|
| storage.gdrive 实施 | OAuth + CRUD + changes + quota 全 OK |
| storage.local 实施 | 完整 CRUD |
| changefeed 4 模块 | writer + reader + compactor + snapshot |
| push 实施 | web + email 至少各一通道 + dispatcher |
| sync 4 个 skill | flush_outbox + apply_remote + snapshot + restore |
| bg_sync 守护 | 启动 / 停止 / 状态查询 |
| 端到端 demo | 两 device 同步成功 |
| 离线 → 联网 flush | 不丢 event |
| 冲突解决 | last-write-wins 工作 |
| 单元测试覆盖 ≥ 80% | sync 各模块 |
| 集成测试 | 真实 GDrive OAuth + 完整流程 |
| CC-B namespace 隔离 | 未动 translate/ |
| version bump | oprim 2.3.0 / oskill 2.4.0 / omodul 1.3.0 |
| tag | v2.3.0-storage-sync / v2.4.0-sync / v1.3.0-sync |

### 7.3 完工报告

(略, 同 Phase 1 / Phase 10 格式)

---

## §8 异常处理 + 报告规范

立即停止 + 报告:
- GDrive OAuth 失败 (refresh / re-auth 失败)
- changefeed seq 冲突无法恢复
- 端到端 demo 两设备状态不一致
- 同步过程数据丢失 (event 顺序错乱)
- CC-B namespace 冲突

非阻塞 (log + 继续):
- 单次 push 失败 (retry 后给出)
- 临时网络问题 (退避后继续)
- snapshot 失败 (下次再试, 不阻塞当前 sync)

---

**预估工程量**: 6 周 FULL AUTO

Wave 1 (storage): 1 周
Wave 2 (changefeed): 1.5 周
Wave 3 (push): 0.5 周
Wave 4 (sync skills): 1.5 周
Wave 5 (bg_sync): 0.5 周
Wave 6 (test + verify): 1 周

---

**End of PHASE_2_STORAGE_SYNC_IMPLEMENTATION_INSTRUCTIONS_v0.1.md**
