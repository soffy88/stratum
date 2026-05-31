# STRATUM_SPEC v0.3

**版本**: v0.3
**日期**: 2026-05-17
**作者**: Wiki (chief), Claude (chief advisor)
**前置**: 批 2 实证 #1-#5 五份报告

---

## §1 设计约束

本节列举对工程实施有约束力的设计原则。每条都能翻译成具体的"必须 / 不能"。

### 1.1 数据归用户

**约束**: 用户原始文件 (substrate) 必须存在用户自己的网盘或本地, **不能存我们的服务器**。

**含义**:
- 后端 API 不能持久化 substrate 原始 bytes
- 临时处理 (e.g. embedding 计算时下载 substrate) 完成后 30 分钟内必须删除
- 用户卸载我们的服务后, **用户在自己网盘里的数据完整可用** (不能依赖我们的 SaaS 还原)

**例外**: changefeed 日志 + 用户配置 (token, 偏好) 可以存我们服务器 — 这部分是"产品状态", 不是"用户内容"。

### 1.2 多设备是默认状态

**约束**: 所有数据结构 + 接口设计必须**预设多设备使用场景**, 单设备是退化情况。

**含义**:
- 任何 substrate ID / concept ID / note ID 必须设备无关 (ULID 已满足)
- 任何写操作必须**生成 changefeed event**, 不能"只更新本地"
- 任何读操作必须**显式处理"未同步状态"**, 不能假设本地数据是最新的

### 1.3 ID 不可变 + 内容可变

**约束**:
- ULID 一旦分配, 永久不变 (即使用户重命名 / 移动文件)
- substrate 文件内容**可变** (e.g. 用户重新扫描同一本书, 替换 PDF), 但 ULID 保持
- 内容变化记录在 derivative.yaml 的 `revisions[]` 字段

**含义**:
- 文件移动 / 重命名通过 changefeed 同步, 不影响搜索
- 新设备初始化时可通过 ULID 重建索引

### 1.4 失败不静默

**约束**: 所有自动处理失败必须有用户可见的状态, **不能藏在隐藏目录里**。

**含义**:
- 解析失败的 PDF: 用户在 UI 里看到"待处理"状态 + 失败原因 + 重试按钮
- 网盘 quota 满: 用户看到"网盘已满"提示 + 解决路径 (升级 / 换网盘 / 删除)
- 同步冲突: 用户看到"两个版本", 必须选一个 (不自动决定)

### 1.5 离线可用

**约束**: 任何"已同步"内容必须在离线状态下可搜索 + 可读。

**含义**:
- 本地缓存必须包含**完整索引** (meta + fulltext + vector)
- 本地缓存必须包含**用户最近访问的 substrate** (LRU, 默认上限 5 GB)
- 离线状态下的写操作进入 outbox, 联网后自动同步

### 1.6 操作可审计

**约束**: 任何对用户数据的修改必须有 audit log。

**含义**:
- changefeed 记录所有 ingest / update / delete / move 操作
- 删除是软删除 (标记 `deleted_at`), 30 天内可恢复, 之后才物理删除
- 用户可导出完整 audit log

---

## §2 用户可见的接口约束

本节列举用户可见的功能, **仅为约束接口设计**, 不写产品营销描述。

### 2.1 用户视角的核心动作

| 用户动作 | 触发的内部操作 |
|---|---|
| 在微信小程序里"分享文件给 Stratum" | POST /api/v1/inbox/submit (含 file_url + source=wechat_mp) |
| 在桌面 app 里"拖文件到窗口" | POST /api/v1/inbox/submit (含 file_path + source=desktop_drag) |
| 拍照入库 | POST /api/v1/inbox/submit (含 multipart image + source=mobile_camera) |
| 浏览器扩展 "保存当前页" | POST /api/v1/inbox/submit (含 url + html + source=browser_ext) |
| 搜索 "项羽" | POST /api/v1/search (返回 substrate + concept + note 混合结果) |
| 打开一个 substrate | GET /api/v1/substrate/{ulid} (含网盘临时 download URL) |
| 写笔记关联到 substrate | POST /api/v1/notes (含 substrate_refs) |

### 2.2 用户不可见的内部概念

下述概念**仅内部使用**, 不暴露给最终用户:

- "substrate" / "concept" / "note" 三层分类 — UI 上统一叫"资料"
- "medium" 的 18 类 — UI 上用图标 + 简单标签 (例: 📚 / 🎙️ / 📝)
- "derivative" / "fragment" — 完全不暴露
- ULID — 不暴露 (URL 里可能含但不强调)

### 2.3 用户可配置项

| 配置项 | 默认 | 范围 |
|---|---|---|
| 主网盘 | 引导用户首次选择 | OneDrive / 阿里云盘 / Dropbox / Google Drive / WPS 云空间 / 本地 |
| 本地缓存上限 | 5 GB | 1 GB - 50 GB |
| embedding 计算位置 | "自动" (服务器调 Qwen3 API) | 自动 / 本地 / 必须服务器 |
| 同步频率 | 实时 | 实时 / 每 5 分钟 / 仅 WiFi / 手动 |
| 失败重试策略 | 自动 3 次 | 自动 N 次 / 手动 |

---

## §3 18 medium / 12 derivative / 11 concept

(对工程实施有用: 这些是 schema 定义, 决定数据库表 + 接口字段)

### 3.1 18 medium

每个 substrate 必须分类到 18 个 medium 之一:

**文本类** (6):
- `book` — 书籍 (epub / mobi / azw / 纸质书扫描 PDF)
- `paper` — 学术论文 (有 abstract + references 结构)
- `webpage` — 网页 (HTML / 截图 / 印刷 PDF)
- `markdown_note` — 用户自己写的 markdown 笔记 (区别于 omodul.notes)
- `chat` — 聊天导出 (WhatsApp / Slack / 微信 / Claude / ChatGPT)
- `thread` — 论坛 / 社交媒体长贴 (X 串 / Reddit / V2EX)

**音频类** (4):
- `podcast` — 播客 (有 episode 结构)
- `lecture` — 讲座录音 (单一讲者 + 讲稿)
- `audiobook` — 有声书
- `music` — 音乐

**视频类** (3):
- `video_lecture` — 视频课程 / YouTube 知识视频
- `interview` — 访谈 (多人对谈)
- `documentary` — 纪录片

**视觉类** (3):
- `artwork` — 艺术作品 (绘画 / 雕塑照片)
- `photograph` — 照片 (有 EXIF 相机信息)
- `diagram` — 图表 (截图 / 手绘 / 图示)

**结构化** (2):
- `dataset` — 表格 / CSV / JSON / parquet
- `code` — 源代码文件

### 3.2 medium 检测策略

按实证 #1 (inbox 分类器) 三层架构:

**Layer 1** (扩展名 + MIME + 文件名前缀, 覆盖 60-70%):
```python
".epub" / ".mobi" → book
".md" → markdown_note
".csv" / ".tsv" / ".parquet" → dataset
".py" / ".js" / ".ts" / ... → code
mime: audio/* → 候选: podcast / lecture / audiobook / music
mime: image/* + EXIF.Make → photograph
filename prefix "podcast--xxx" → podcast (99% 置信)
filename prefix "book--xxx" → book
```

**Layer 2** (文件特征启发式, 覆盖 15-25%):
- PDF 启发式: page_count + 首页关键词 (Abstract/arXiv/DOI → paper, Chapter/ISBN/Contents → book)
- 图像启发式: EXIF.Make 存在 → photograph
- audio 启发式: 时长 < 10min → 短音频 (可能 podcast 片段), > 1h → audiobook/lecture

**Layer 3** (LLM 兜底, 10-25%):
- 调用 Qwen3 / Haiku 看内容采样
- 返回 medium + 置信度
- 置信度 < 0.5 → 进 "待用户确认" 队列

### 3.3 12 derivative 类型

每个 substrate 自动生成 1-N 个 derivative:

| derivative | 适用 medium | 内容 |
|---|---|---|
| `markdown` | text 类全部 | 转 markdown |
| `plaintext` | text 类全部 | 纯文本 |
| `transcript` | audio / video 类 | 转写文本 |
| `summary` | 全部 | LLM 摘要 (200/500/1500 字三档) |
| `key_quotes` | text / transcript | 提取 5-20 个金句 |
| `chapters` | book / video_lecture / podcast | 章节切分 |
| `outline` | text 类 | 大纲 |
| `entities` | 全部 | 命名实体 (人名 / 地名 / 组织 / 概念) |
| `tags` | 全部 | 自动 tag (5-15 个) |
| `embedding_chunks` | 全部 | 切片 + embedding (用于向量检索) |
| `ocr_text` | image (含截图 PDF) | OCR 文本 |
| `thumbnail` | image / video / pdf | 缩略图 |

### 3.4 11 concept 类型

concept 是从 substrate 抽取的实体, 不是 substrate 本身:

| concept type | 例子 |
|---|---|
| `person` | 项羽 / Linus Torvalds |
| `event` | 鸿门宴 / 2008 金融危机 |
| `place` | 长安 / 旧金山 |
| `organization` | 阿里巴巴 / Anthropic |
| `concept_idea` | "技术债" / "复利效应" |
| `work` | 《项羽本纪》 / 《思考快与慢》 |
| `time_period` | 楚汉时期 / 2010s |
| `theory_framework` | 凯恩斯主义 / 系统思考 |
| `quote` | 某段经典引语 |
| `term_definition` | 术语 + 定义 |
| `relation` | 概念之间的关系 |

---

## §4 三层数据架构

### 4.1 数据分层

```
用户原始数据 (用户网盘):
├── substrate/                # 原始文件, 用户拥有
├── derivative/               # 自动生成衍生物
├── concepts/                 # 概念 JSON
├── notes/                    # 用户写的 markdown
└── _hub_backup/              # 索引压缩备份 (供新设备初始化)
    └── snapshot-{date}.zip

用户本地缓存 (各设备各一份):
└── ~/.stratum/               # 或 Windows %APPDATA%/Stratum
    ├── cache/
    │   ├── meta.duckdb       # 元数据
    │   ├── fulltext.tantivy/ # 全文索引
    │   ├── vectors-text.lance/
    │   ├── vectors-image.lance/
    │   └── substrate_lru/    # 最近访问的原始文件缓存 (LRU)
    ├── config.yaml           # 用户配置
    ├── outbox/               # 待同步操作 (离线时入)
    └── tokens.encrypted      # 加密的网盘 OAuth token

我们服务器:
└── /api/
    ├── user_meta/{user_id}/
    │   ├── account.json      # 邮箱 / plan / 创建时间
    │   ├── storage_config.json  # 用户网盘选择 + 引用
    │   └── changefeed.log    # 所有事件流, 用于多端同步
    └── (无用户原始内容存储)
```

### 4.2 三层各自的角色

| 层 | 存什么 | 不存什么 | 谁能访问 |
|---|---|---|---|
| **用户网盘** | substrate + derivative + concepts + notes + 索引备份 | (无) | 用户 (通过我们的 app 间接) |
| **用户本地** | 完整索引 + LRU 缓存 + OAuth token + outbox | (无) | 仅本设备 + 用户 |
| **我们服务器** | account info + changefeed + storage_config | substrate / derivative / 索引 / token 明文 | 用户 + 我们后端 |

### 4.3 关键约束

1. **我们服务器永不持有 substrate 原始 bytes** — 即使临时下载也必须 30 分钟内清理
2. **用户 OAuth token 明文不存我们服务器** — 必须用用户主密钥加密 (主密钥可派生自用户密码)
3. **本地索引可丢失** — 任何时候都可从用户网盘的 snapshot.zip 恢复
4. **用户网盘可丢失** (用户删了我们的目录) — 我们服务器的 changefeed 可让用户重新决定如何恢复 (从其他设备的本地索引重建)

---

## §5 网盘适配层 (oprim.storage)

### 5.1 适配器优先级

按实证 #5 结论:

| Provider | 优先级 | 状态 |
|---|---|---|
| OneDrive (via Microsoft Graph) | **P0** | 必须支持, 国内可用 |
| 阿里云盘 (开放平台 API) | **P1** | 必须支持, 需先确认拿到开放平台凭证 |
| Dropbox | **P1** | 国际用户主选 |
| Google Drive | **P1** | 国际用户备选, 国内需 VPN |
| WPS 云空间 | **P2** | 学生用户多 |
| 本地文件夹 (无网盘) | **P0** | 隐私敏感 / 离线场景 |
| 百度网盘 | **不支持** | 合规接入路径不通 |
| 微信文件传输助手 | **不支持** | 微信个人号无官方 API |

### 5.2 storage_adapter 接口

```python
class StorageAdapter(Protocol):
    """所有网盘适配器必须实现"""

    async def authenticate(self, oauth_code: str) -> StorageCredentials:
        """OAuth 流程, 返回加密后存储的凭证"""

    async def upload(self, local_path: Path, remote_path: str) -> RemoteFileRef:
        """上传文件, 返回远程引用 (含 ID + URL + size)"""

    async def download(self, remote_ref: RemoteFileRef, local_path: Path) -> None:
        """下载到本地路径"""

    async def list(self, remote_path: str, recursive: bool = False) -> list[RemoteFileRef]:
        """列目录"""

    async def delete(self, remote_ref: RemoteFileRef) -> None:
        """删除文件"""

    async def get_download_url(self, remote_ref: RemoteFileRef, ttl: int = 3600) -> str:
        """获取临时下载 URL (用于客户端直连下载, 不经过我们服务器)"""

    async def get_quota(self) -> StorageQuota:
        """剩余空间"""

    async def watch(self, remote_path: str, callback: Callable) -> WatchHandle:
        """监听远程变更 (用于"网盘里被外部修改"的同步)"""
```

### 5.3 各 adapter 关键差异

**OneDrive (msgraph-sdk)**:
- OAuth: Microsoft identity platform v2.0
- 上传: 小文件 PUT, 大文件 (> 4 MB) 用 createUploadSession
- 下载: GET 临时 URL, 有效 1 小时
- watch: Microsoft Graph subscriptions, push 到我们的 webhook URL
- quota: GET /me/drive

**阿里云盘 (开放平台 API)**:
- OAuth: aliyun OAuth 2.0
- 上传: 三步 (create / proof / complete), 大文件分片
- 下载: 获取 download_url, 有效 4 小时
- watch: 无 push, 必须 polling (或本地变更触发 changefeed)
- quota: /v1.0/user/getDriveInfo
- **重要**: 不付费"三方应用权益包"用户限速 + 限并发, adapter 必须处理 rate limit

**Dropbox**:
- OAuth: Dropbox OAuth 2.0
- 上传: files/upload (4 MB 内) / upload_session (大文件)
- 下载: files/get_temporary_link
- watch: Dropbox webhook
- quota: users/get_space_usage

**Google Drive**:
- OAuth: Google OAuth 2.0
- 上传: drive.files.create + media upload
- 下载: drive.files.get?alt=media
- watch: drive.changes.watch
- quota: drive.about.get

**WPS 云空间**:
- (待 SDK 文档具体确认, P2 阶段处理)

**本地文件夹**:
- 跳过 OAuth, 用户选目录
- 所有操作直接 fs
- watch: inotify (Linux) / FSEvents (Mac) / ReadDirectoryChangesW (Windows)

### 5.4 多 adapter 并存

用户可以同时连接多个网盘:

```yaml
# ~/.stratum/config.yaml 片段
storage:
  primary: onedrive_a
  secondaries:
    - aliyundrive_b   # 用作国内访问加速
    - local_c         # 用作离线场景

adapters:
  onedrive_a:
    type: onedrive
    credentials_ref: tokens.encrypted/onedrive_a
    base_path: /Stratum
  aliyundrive_b:
    type: aliyundrive
    credentials_ref: tokens.encrypted/aliyundrive_b
    base_path: /Stratum
  local_c:
    type: local
    base_path: /Users/wiki/Documents/Stratum
```

**多 adapter 协调规则**:
- 入库时写入 primary, secondaries 异步备份
- 读取时优先 primary, primary 不可达时 fallback secondaries
- 主从切换: 用户手动 (不自动, 避免数据分裂)

---

## §6 索引架构

### 6.1 索引存储位置

按实证 #5 推荐的方案 C:

| 索引 | 主存储 | 备份 | 同步机制 |
|---|---|---|---|
| meta.duckdb | 用户本地 | 用户网盘 _hub_backup (每日 snapshot) | changefeed 增量 |
| fulltext.tantivy/ | 用户本地 | 同上 | changefeed 增量 |
| vectors-text.lance | 用户本地 | 同上 | changefeed 增量 |
| vectors-image.lance | 用户本地 | 同上 | changefeed 增量 |

### 6.2 各索引技术选型

按实证 #2 结论:

- **元数据**: DuckDB (本地, 支持 SQL 复杂查询)
- **全文索引**: Tantivy (Rust 写, Python bindings, 速度快)
- **向量库**: **LanceDB** (主推, 实证 #2 证明 upsert 性能优秀)

(qdrant 内嵌模式被否决, 见实证 #2)

### 6.3 vectors-audio.lance 不在 v1.0 范围

按实证 #3 结论, audio 检索走 transcript 文本路径 (transcript → 走 vectors-text), v1.0 不建独立 audio embedding。

### 6.4 embedding 模型选择

按实证 #3 结论:

| 用途 | 主推 | 备选 | 维度 |
|---|---|---|---|
| 文本 embedding | **Qwen3-Embedding (DashScope API)** | BGE-M3 (local self-host) | 1024 |
| 图像 embedding | **SigLIP-2** | DINOv2 (v1.x) | 768 |
| 音频 embedding | (v1.0 不实施) | CLAP (v1.x) | - |

### 6.5 索引 schema

**meta.duckdb 主要表**:

```sql
CREATE TABLE substrate (
    id TEXT PRIMARY KEY,        -- ULID
    medium TEXT NOT NULL,        -- 18 个之一
    title TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP,        -- 软删除
    source_type TEXT,            -- inbox_wechat / inbox_mobile / etc.
    source_meta JSONB,           -- 入库元数据
    storage_adapter TEXT,        -- 哪个网盘
    storage_path TEXT,           -- 网盘内路径
    storage_ref JSONB,           -- adapter-specific (e.g. file_id)
    file_hash TEXT,              -- sha256, 用于去重
    file_size BIGINT,
    mime_type TEXT,
    language TEXT
);

CREATE TABLE derivative (
    id TEXT PRIMARY KEY,
    substrate_id TEXT NOT NULL,
    type TEXT NOT NULL,           -- 12 个之一
    storage_path TEXT,
    content_hash TEXT,
    generated_at TIMESTAMP,
    generator_version TEXT        -- 用于检测过时
);

CREATE TABLE concept (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,           -- 11 个之一
    label TEXT NOT NULL,
    label_aliases TEXT[],
    description TEXT,
    related_substrate_ids TEXT[]
);

CREATE TABLE note (
    id TEXT PRIMARY KEY,
    title TEXT,
    content_markdown TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    substrate_refs TEXT[],
    concept_refs TEXT[]
);

CREATE TABLE changefeed_local (
    -- 本地 outbox, 等待同步到我们服务器
    seq BIGINT PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,
    payload JSONB,
    created_at TIMESTAMP,
    synced_at TIMESTAMP NULL
);
```

**fulltext.tantivy 索引字段**:
- substrate: title + ocr_text + transcript + content_markdown
- derivative.summary / derivative.key_quotes
- note.title + note.content_markdown
- concept.label + concept.description

**vectors-text.lance schema**:
```python
{
    "id": "substrate_id#chunk_idx",       # composite
    "substrate_id": str,
    "chunk_idx": int,
    "chunk_text": str,                    # 200-500 token 切片
    "embedding": list[float],             # 1024 dim
    "medium": str,
    "language": str,
    "created_at": int,                    # epoch
}
```

### 6.6 索引 snapshot 备份策略

- 每日凌晨自动 snapshot (用户网盘里), 保留 7 天
- 每次大量入库后 (新增 > 100 substrate) trigger snapshot
- snapshot 是 zip (含 meta.duckdb + tantivy + lance 文件)
- 新设备初始化时优先从最新 snapshot 拉, 失败 fallback 完整重建

---

## §7 抗腐烂规则 (lint)

### 7.1 schema 一致性

- 任何 substrate 必须有 medium 字段 (18 个之一)
- 任何 derivative 必须 reference 一个 substrate
- 任何 concept 关联的 substrate_ids 必须真实存在
- ULID 必须符合 ULID 规范 (26 字符 Crockford base32)

### 7.2 命名约定

- ULID 不可有空格 / 引号 / 路径分隔符
- 文件名 (网盘内) 命名规则: `{ulid}--{slug_title}.{ext}`, e.g. `01HY8KXYZ...--xiang-yu-ben-ji.pdf`
- slug_title 是 ASCII 化的标题, 最多 50 字符 (UTF-8 安全)

### 7.3 引用完整性

- substrate 删除 → 关联 derivative 必须同时删 (软删除)
- concept 删除前必须解绑所有 substrate_refs
- note 引用的 substrate_refs / concept_refs 必须存在, 否则 lint 报警

### 7.4 derivative 时效性

- derivative 含 `generator_version` 字段
- 当 `generator_version < current_pipeline_version` 时, 标记为 "过时"
- 用户可触发 "重新生成所有过时 derivative"

### 7.5 lint 工具

- CLI: `stratum lint` (查所有, 报告)
- 自动: 每次 ingest 后跑当前 substrate 相关 lint
- CI: 用户网盘 _hub_backup snapshot 跑全量 lint, 异常推送通知

---

## §8 检索接口

### 8.1 search 接口

```
POST /api/v1/search
Request:
{
    "query": "项羽 鸿门宴",
    "modalities": ["text", "audio_transcript", "image_ocr"],  # 可选
    "medium_filter": ["book", "paper"],                        # 可选
    "language_filter": ["zh", "en"],                           # 可选
    "date_range": {"from": "2020-01-01", "to": null},          # 可选
    "top_k": 20,
    "include_concepts": true,
    "include_notes": true
}

Response:
{
    "results": [
        {
            "type": "substrate",
            "id": "01HY...",
            "title": "史记·项羽本纪",
            "medium": "book",
            "score": 0.92,
            "highlight": "项羽闻沛公已破咸阳, 大怒...",
            "fragment_id": "01HY...#chunk_47"
        },
        {
            "type": "concept",
            "id": "01HZ...",
            "label": "鸿门宴",
            "concept_type": "event",
            "score": 0.88,
            "related_substrate_count": 5
        },
        ...
    ],
    "sync_status": {
        "is_fully_synced": true,
        "pending_substrate_count": 0,
        "last_sync_at": "2026-05-17T14:30:00Z"
    },
    "search_time_ms": 145
}
```

**关键点**:
- `sync_status` 字段必填, 让客户端能展示"还在同步 X 条"
- `modalities` 默认全部 (text + audio_transcript + image_ocr)
- score 是 hybrid score (BM25 + 向量相似度, 用 RRF 融合)

### 8.2 fetch_substrate

```
GET /api/v1/substrate/{ulid}?include=metadata,derivatives,download_url

Response:
{
    "id": "01HY...",
    "metadata": { ... },
    "derivatives": [
        {"type": "summary", "content": "..."},
        {"type": "transcript", "content": "..."},
        ...
    ],
    "download_url": "https://onedrive.live.com/...",  # 临时直连, 1h ttl
    "fragment_index": [
        {"fragment_id": "...#chunk_0", "char_start": 0, "char_end": 500, "preview": "..."},
        ...
    ]
}
```

### 8.3 list_notes / recent_changes / fetch_concept

(略, 跟 v0.2 §9.3 类似, 这里不重复)

### 8.4 MCP tool 暴露

按实证 #4 结论, 用 `mcp.server.fastmcp.FastMCP` (官方内置高阶 API)。

暴露的 tools (供外部 LLM / agent 调用):

- `stratum.search` (同 8.1)
- `stratum.fetch_substrate` (同 8.2)
- `stratum.fetch_fragment` (fragment 级精确读取)
- `stratum.fetch_concept`
- `stratum.list_notes`
- `stratum.search_concepts`
- `stratum.recent_changes`

### 8.5 离线降级

客户端检测离线时:
- 优先返回本地索引命中结果
- response 加 `sync_status.is_offline: true`
- 用户搜索不在本地缓存的内容时, 返回 "已有 X 条本地结果, 联网后可能更多"

---

## §9 流水线

### 9.1 入库流水线 (ingest)

```
触发: 用户在任一入口提交文件
↓
Step 1: 上传到我们服务器临时区 (≤30 min TTL)
↓
Step 2: 计算 file_hash (sha256), 查重
    - 若已存在 (同 hash + 同用户) → 返回现有 ULID, 流水线结束
↓
Step 3: 三层分类器 (medium 识别, 见 §3.2)
    - 高置信度 → 自动入库
    - 中置信度 → 加 "needs_review" 标志, 仍入库
    - 低置信度 → 推送给用户确认 (UI 提示)
↓
Step 4: 上传 substrate 到用户主网盘 (路径: /Stratum/substrate/{medium}/{ulid}--{slug}.{ext})
↓
Step 5: 生成 derivative (并行):
    - parse → markdown / plaintext / transcript / ocr_text
    - summarize → summary
    - extract → entities / key_quotes / tags
    - chunk → embedding_chunks
    - upload derivative 到用户网盘 /Stratum/derivative/{substrate_id}/
↓
Step 6: 计算 vector embeddings (调 Qwen3 DashScope)
    - 写入本地 vectors-text.lance
    - 写入网盘 _hub_backup 的下一个 snapshot
↓
Step 7: 提取 concept 候选 (LLM 调用)
    - 跟现有 concept 去重 (label + 别名)
    - 新增 concept 写入 concepts/
↓
Step 8: 删除服务器临时文件
↓
Step 9: 发 changefeed event: {type: "ingest", substrate_id: "01HY...", user_id: "..."}
↓
Step 10: 其他设备收到 push notification, 拉新 substrate (按 §10)
```

### 9.2 三层分类器

按实证 (inbox 设计 v0.1):

```python
def classify_inbox_file(file: UploadedFile) -> ClassifyResult:
    # Layer 1: 扩展名 + MIME + 文件名前缀
    layer1 = classify_by_extension(file)
    if layer1.confidence >= 0.85:
        return layer1

    # Layer 2: 文件特征启发式
    layer2 = classify_by_heuristic(file, layer1)
    if layer2.confidence >= 0.65:
        return layer2

    # Layer 3: LLM 兜底
    layer3 = classify_by_llm(file, layer2.candidates)
    return layer3
```

详细规则见 §3.2。

### 9.3 derivative 生成流水线 (含 PDF 解析)

按实证 #1 结论:

```python
def parse_pdf(pdf_path: Path, hint: dict | None) -> ParsedContent:
    # 决定 provider
    if hint and hint.get("language") == "zh" and detect_cjk(pdf_path):
        provider = "mineru"          # 中文场景 P0
    elif detect_if_scanned(pdf_path):
        provider = "marker"          # 扫描件用 OCR
    else:
        provider = "pymupdf4llm"     # 默认快速

    return providers[provider].parse(pdf_path)
```

### 9.4 同步 outbox flush

客户端定期 (实时 / 每 5 分钟) flush 本地 outbox:

```python
async def flush_outbox():
    pending = await get_pending_changefeed_local()
    for event in pending:
        try:
            await api.changefeed_post(event)
            await mark_synced(event.seq)
        except NetworkError:
            return  # 下次重试
```

### 9.5 删除流水线

```
用户点 "删除"
↓
Step 1: 标记本地 deleted_at = now()
↓
Step 2: 写 changefeed event: {type: "delete", substrate_id, soft: true}
↓
Step 3: 30 天宽限期 (本地 + 网盘 + 其他设备都保留)
↓
Step 4: 30 天后, 物理删除:
    - 删用户网盘的 substrate + derivative
    - 删本地索引条目
    - changefeed: {type: "physical_delete"}
↓
用户可在 30 天内 "恢复"
```

---

## §10 多端同步

### 10.1 changefeed 协议

每个事件:

```json
{
    "seq": 12345,
    "user_id": "user_abc",
    "device_id": "device_xyz",
    "timestamp": "2026-05-17T14:30:00Z",
    "event_type": "ingest",
    "payload": {
        "substrate_id": "01HY...",
        "medium": "book",
        "storage_adapter": "onedrive_a",
        "storage_ref": {"file_id": "..."},
        "metadata_hash": "abc...",
        ...
    }
}
```

### 10.2 event 类型

| event_type | 触发场景 |
|---|---|
| `ingest` | 新 substrate 入库 |
| `derivative_added` | 新 derivative 生成 |
| `update_metadata` | substrate 元数据修改 |
| `move` | 文件在网盘内移动 |
| `delete` | 软删除 |
| `physical_delete` | 30 天后物理删除 |
| `note_create` / `note_update` / `note_delete` | 笔记操作 |
| `concept_create` / `concept_merge` / `concept_split` | 概念操作 |
| `storage_added` / `storage_removed` | 用户切网盘 |
| `snapshot_created` | 网盘备份完成 |

### 10.3 多端同步流程

```
设备 A: 完成 ingest 流水线 (§9.1)
↓
设备 A: POST changefeed event 到我们服务器
↓
服务器: 持久化 event, 触发 push notification 给该用户的其他设备
↓
设备 B: 收到 push, 调 GET /api/v1/changefeed?after_seq={local_max_seq}
↓
设备 B: 按 event 类型分发处理:
    - ingest event → 从 payload 取 storage_ref, 调用 storage adapter 下载到本地 LRU
    - 计算 embedding (本地 or 调服务器 API, 按用户配置)
    - 写本地 meta.duckdb + tantivy + lance
↓
设备 B: 通知用户 UI 刷新 (新增 X 条资料)
```

### 10.4 push 通知机制

| 平台 | 机制 |
|---|---|
| iOS app | APNs |
| Android app | FCM (Google) + 国内备选 (小米推送 / 华为推送) |
| Web | Web Push API + Service Worker |
| 桌面 (Electron / Tauri) | 长连接 WebSocket |
| 微信小程序 | 微信"订阅消息" |

降级: push 失败时, 客户端定期 polling (默认 5 分钟一次)。

### 10.5 冲突处理

**正常情况下不应有冲突** (changefeed 单调递增 seq + ULID 唯一)。

但存在冲突的场景:

| 冲突类型 | 处理 |
|---|---|
| 同一 substrate 两个设备同时更新元数据 | last-write-wins (按 timestamp), changefeed 记录两个 event |
| 同一 substrate 一个设备删除另一个设备更新 | "已删除" 优先, 但 UI 提示用户 |
| 同一文件被外部 (用户在网盘里直接改了) 修改 | watch 触发 reindex |
| 两个设备在离线模式下都新增了同一文件 (同 hash) | 服务端合并: 只创建一个 substrate, 关联两个 source 记录 |

---

## §11 安全与隐私

### 11.1 用户身份

- 邮箱 + 密码登录 (主要)
- 微信小程序登录 (可选, 仅 prefer 微信生态用户)
- OAuth 第三方 (Google / Apple / 微信开放平台) 可选
- 密码用 Argon2id, salt + 迭代

### 11.2 OAuth token 管理

**用户网盘 OAuth token 加密存储**:

- 主密钥派生自用户密码 (PBKDF2 / Argon2)
- 服务器只存密文 + salt (不存主密钥)
- 用户每次登录时, 客户端用密码派生主密钥, 解密 token, 调用网盘 API
- 用户改密码 → token 必须重新加密

**例外**: 服务器需要后台调用网盘 API 时 (例: 推送 push 后, 服务器替设备 B 检查 storage_ref 仍存在), 使用临时 access token (短 TTL, 30 分钟内有效), 不留持久 token。

### 11.3 服务器后端的数据访问

- 服务器不持久化 substrate 原始 bytes (§1.1 约束)
- 服务器可临时下载 substrate 用于:
  - embedding 计算 (用户选 "服务器计算" 时)
  - LLM 调用 (summarize / extract concept)
- 临时文件加密 (用户独立 key) + 30 min TTL 强制清理
- 所有临时下载有 audit log, 用户可查

### 11.4 端到端加密 (E2EE) 选项

**v1.0 不实施**, v1.x 评估。

如做 E2EE:
- 用户文件加密上传 (客户端用主密钥加密 → 上传到网盘)
- 服务器无法做服务器端处理 (embedding / summary 全部本地)
- trade-off: 隐私强但性能差 (本地 GPU 需求)

### 11.5 用户卸载场景

用户卸载我们服务时:

1. 注销账号 → 删除我们服务器的 account + changefeed (30 天宽限)
2. 用户网盘里的 `/Stratum/` 目录 + 索引 snapshot 保留
3. 用户可手动删除 `/Stratum/` 或保留 (作为只读归档)
4. 重新注册后, 可选择 "从网盘 snapshot 恢复"

### 11.6 监管合规

- 所有用户内容**不存我们服务器** → 大幅降低内容审核责任
- 涉及 LLM 调用的中间内容 (临时下载): 接合规 LLM (Qwen3 / 文心 / DeepSeek 已备案)
- 中国大陆部署: ICP 备案 + 微信小程序合规审核

---

## §12 微信集成

### 12.1 微信优先 = 微信小程序 + 公众号, 不是个人号

按实证 #5 结论, **个人微信号无任何官方 API, 第三方接入封号率 > 80%, 商业化不可用**。

合规路径只有:
- ✅ **微信小程序**: 用户主入口 (capture + 搜索 + 通知)
- ✅ **微信公众号**: 辅助入口 (用户绑定后可推送通知 / 发文件)
- ✅ **企业微信 API**: 团队功能 (v1.x 评估)
- ❌ **个人微信 API / Hook / WeChaty 等**: 严禁使用

### 12.2 微信小程序功能范围

**输入** (capture):
- `wx.chooseMessageFile` — 用户从聊天里选文件
- `wx.chooseImage` / `wx.chooseMedia` — 选图片 / 视频
- `wx.startRecord` — 录音
- `wx.scanCode` — 扫码 (用于网盘授权 / 邀请)
- 网页分享 → 小程序 (微信内置浏览器分享菜单)

**输出** (search / view):
- 搜索 UI
- substrate 预览 (PDF / 图像 / 音频 — 微信小程序原生支持)
- 跳转外部 (`wx.openDocument` 用第三方 app 打开)
- 分享给好友 / 转发到群

**通知**:
- 微信"订阅消息" (新入库 / 同步完成 / 失败提示)

### 12.3 微信公众号功能范围

- 用户绑定: 关注公众号 + 扫码绑定账号
- 推送: 重要通知 (容量满 / 系统更新 / 月度总结)
- 发文件: 用户给公众号发文件 → 触发 ingest (兜底入口, 适合不爱开小程序的用户)
- 简单查询: 用户发文字 "找昨天的 PDF" → 返回结果链接 (跳小程序)

### 12.4 文件大小限制

- 微信小程序单文件上传上限 **100 MB** (用 `wx.uploadFile` HTTPS 上传)
- 大文件 (视频 / 大 PDF) → 引导用户用桌面 / 移动 app
- 公众号发文件上限 **20 MB** (用 wx.media API)

### 12.5 微信小程序的 capture 流程

```
用户在聊天里收到 PDF
↓
长按 PDF → "更多" → "分享到 Stratum 小程序"
↓
小程序接收文件 (用 wx.chooseMessageFile / onShareAppMessage)
↓
小程序调用我们的 API: POST /api/v1/inbox/submit
    - source: "wechat_mp"
    - file: multipart upload
↓
服务器走入库流水线 (§9.1)
    - substrate 上传到用户已授权的主网盘 (非微信)
↓
小程序展示: "已入库, 类型: 书籍, 标题: XXX"
↓
用户可立即在小程序内搜索
```

---

## §13 实施路线 (依赖关系, 不写时间)

按依赖关系而非时间排列。每一步必须完成才能进入下一步。

### Phase 1: 基础设施

**前置**: 无
**产出**: 4O 库 (obase / oprim / oskill / omodul) 可用

- obase 实施 (CC + hevi advisor review)
- oprim 实施 (按 4O 扩充清单 v0.2)
- oskill / omodul 框架

### Phase 2: 单机版 Stratum (核心数据 + 检索)

**前置**: Phase 1 完成
**产出**: 命令行可用的单设备 Stratum

- §3 schema 实施 (DuckDB / Tantivy / LanceDB)
- §4 三层架构 (本地版, 不含网盘 / changefeed)
- §6 索引架构 (本地索引)
- §8 检索接口 (单机版, 无 sync_status)
- §9 入库流水线 (无三层分类器 LLM, 仅 Layer 1+2)
- §7 抗腐烂 lint

### Phase 3: 网盘适配层

**前置**: Phase 2 完成
**产出**: substrate 可存到网盘

- §5 OneDrive adapter (P0)
- §5 本地文件夹 adapter (P0)
- §5 storage_adapter 抽象接口
- §11 用户 OAuth + token 加密

### Phase 4: 多端同步

**前置**: Phase 3 完成
**产出**: 多设备同步可用

- 我们服务器端 changefeed API
- §10 push 通知 (至少 1 个平台先跑通, e.g. WebSocket for desktop)
- §10 本地 outbox + flush
- §6 网盘索引 snapshot 备份

### Phase 5: 微信集成

**前置**: Phase 4 完成
**产出**: 微信小程序 + 公众号上线

- §12 微信小程序 (capture + 搜索)
- §12 微信公众号 (通知 + 兜底)
- 微信登录 + 账号体系

### Phase 6: 第二批网盘适配

**前置**: Phase 5 完成
**产出**: 用户网盘选择多样化

- 阿里云盘 adapter (P1, 前置: 拿到开放平台凭证)
- Dropbox adapter (P1)
- Google Drive adapter (P1)
- WPS 云空间 adapter (P2)

### Phase 7: LLM 增强

**前置**: Phase 6 完成
**产出**: 三层分类器 + 高级 derivative

- §9.2 三层分类器 Layer 3 (LLM 兜底)
- derivative.summary / key_quotes / entities 完整化
- concept 抽取流水线

### Phase 8: 移动端

**前置**: Phase 5 + Phase 7 完成
**产出**: iOS / Android app

- iOS app (Swift + share extension)
- Android app (Kotlin + share intent)
- 复用后端 + 微信小程序业务逻辑

### Phase 9: 桌面端 + 浏览器扩展

**前置**: Phase 8 完成
**产出**: 全平台 capture 入口

- 桌面 app (Tauri 优先, Electron 备选)
- 浏览器扩展 (Chrome / Safari / Firefox)

---

## §14 关键技术决策来源

(本节简短引用批 2 实证, 不重述细节)

| 决策 | 来源 |
|---|---|
| MCP 框架 = `mcp.server.fastmcp.FastMCP` | 实证 #4 |
| PDF 解析 = pymupdf4llm + Marker + MinerU 分层 | 实证 #1 |
| 向量库 = LanceDB | 实证 #2 |
| Embedding = Qwen3-Embedding (DashScope) | 实证 #3 |
| 数据存用户网盘 + 本地 + 服务器 changefeed | 实证 #5 |
| OneDrive P0 / 阿里云盘 P1 / 弃百度 | 实证 #5 |
| 微信小程序 + 公众号, 不碰个人号 | 实证 #5 |

完整实证报告:
- /mnt/user-data/outputs/batch2-experiment-04/REPORT.md
- /mnt/user-data/outputs/batch2-experiment-01/REPORT.md
- /mnt/user-data/outputs/batch2-experiment-02/REPORT.md
- /mnt/user-data/outputs/batch2-experiment-03/REPORT.md
- /mnt/user-data/outputs/batch2-experiment-05/REPORT.md

---

## §15 未决问题

写作过程中发现的需 Wiki 后续决定的问题:

### Q1: 阿里云盘开放平台凭证可行性

**问题**: 实证 #5 提到阿里云盘开放平台 client_id + client_secret 需内测申请, 个人/初创可能拿不到。

**影响**: 如果拿不到, 国内用户主要靠 OneDrive (国内慢) + WPS (用户少), 国内体验大打折扣。

**决定时机**: Phase 6 启动前必须先确认。

### Q2: 服务器部署区域

**问题**: 用户主要在国内 vs 国际, 服务器部署区域不同。

**影响**:
- 国内: 阿里云 / 腾讯云 + ICP 备案
- 国际: AWS / Cloudflare Workers + GDPR 合规
- 双区: 工程复杂度 x 2

**决定时机**: Phase 4 (changefeed 服务) 启动前。

### Q3: embedding 计算位置默认值

**问题**: §6.4 用 Qwen3 DashScope API, 但用户可选 "本地计算"。默认应该是哪个?

**影响**:
- 默认 DashScope: 体验好, 但用户内容片段会传 DashScope (虽然 Qwen3 不留存)
- 默认本地: 隐私好, 但低端设备性能差 (Qwen3-0.6B 在 8GB RAM 手机上慢)

**决定时机**: Phase 7 启动前。

### Q4: 移动端跨平台还是原生

**问题**: iOS + Android 用 React Native / Flutter (跨平台) 还是 Swift + Kotlin (原生)?

**影响**:
- 跨平台: 工程量减半, 性能 80%, 平台特性受限
- 原生: 工程量 x 2, 性能 100%, 平台特性完整

**决定时机**: Phase 8 启动前。

### Q5: E2EE 是否纳入 v1.0

**问题**: §11.4 说 E2EE v1.0 不实施, 是否真不要?

**影响**:
- 不做: 服务器后台可访问临时下载内容, 部分用户拒绝
- 做: 工程量大幅增加, embedding / LLM 必须本地, 性能差

**决定时机**: Phase 2 启动前 (影响数据架构基础)。

### Q6: 公开 API 开放范围

**问题**: §8.4 MCP tool 是否对外部第三方开发者开放 (类似 OpenAI API)?

**影响**:
- 开放: Stratum 成为生态平台 (e.g. 第三方 agent 用 stratum.search)
- 不开放: 仅自家产品用

**决定时机**: Phase 7 启动前。

---

**End of STRATUM_SPEC v0.3**
