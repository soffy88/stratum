# STRATUM_SPEC v0.5

**版本**: v0.5
**日期**: 2026-05-17
**作者**: Wiki (chief), Claude (chief advisor)
**前置**: 批 2 实证 #1-#5, hevi 作为内容生产引擎

---

## §1 产品本质

Stratum 是**内容平台 + 工具混合体**:

- **平台侧**: 分发 hevi 出品的独有内容 (投资 / 金融 / 量化垂直领域), 用户付费订阅
- **工具侧**: 用户管理自己资料 (substrate / concept / note 三层架构), 数据存用户自有网盘
- **核心差异化**: 平台内容 ↔ 用户自有数据**深度融合检索** (得到 / 喜马拉雅做不到)

---

## §2 设计约束

### 2.1 数据所有权分层

| 数据类型 | 所有权 | 存储位置 |
|---|---|---|
| **平台内容** (hevi 出品的文章 / 概念百科 / 音频) | 平台拥有版权 | 我们服务器 + CDN |
| **用户自有内容** (用户上传的 substrate / derivative / concept / note) | 用户拥有 | 用户网盘 + 本地缓存 |
| **用户跟内容的交互** (笔记 / 高亮 / 标注 / 关联) | 用户拥有 | 用户网盘 + 本地缓存 |
| **用户元数据** (账号 / 订阅 / 偏好) | 平台拥有 | 我们服务器 |

**关键约束**:
- 平台内容**不下载到用户网盘** (流式访问, 防盗版)
- 用户自有内容**不上传到我们服务器** (隐私)
- 用户对平台内容的笔记/高亮 → 存用户网盘 (用户拥有自己的思考)
- 用户取消订阅后, 平台内容不再可访问, 但用户的笔记/高亮保留

### 2.2 ID 不可变 + 内容可变

- ULID 一旦分配永久不变 (substrate / concept / note)
- 平台内容用独立 ID 命名空间: `stratum-content-{ulid}` 区别于用户 substrate
- 平台内容版本化 (hevi 更新文章 → v2, 老版本可访问)

### 2.3 多设备是默认状态

- 任何操作必须生成 changefeed event
- 读操作必须暴露 sync_status
- 离线状态下平台内容**已下载到本地缓存的部分**仍可读

### 2.4 内容跟用户数据融合是核心约束

任何"展示平台内容"的页面必须**同时检查**:
1. 用户自有资料里有无相关内容 (substrate)
2. 用户笔记里有无相关思考 (note)
3. 概念图谱里有无关联 (concept)

不允许"只展示平台内容不关联用户数据"的页面 (违反产品核心差异化)。

### 2.5 失败不静默

- 解析失败 / 同步失败 / 支付失败 必须用户可见
- 不允许隐藏目录 (`_failed/` 等)

### 2.6 操作可审计

- changefeed 记录所有用户操作
- 平台内容访问记录 (用于推荐 + 防盗版)
- 删除是软删除 + 30 天宽限

---

## §3 用户可见接口

### 3.1 用户动作 → 内部 API

| 用户动作 | 内部操作 |
|---|---|
| 浏览发现页 | GET /api/v1/content/feed (返回 hevi 出品内容列表) |
| 打开一篇平台文章 | GET /api/v1/content/{content_id} (含内容 + 相关用户资料) |
| 收藏平台内容 | POST /api/v1/user/bookmarks |
| 给平台内容写笔记 | POST /api/v1/notes (含 content_ref 而非 substrate_ref) |
| 高亮平台内容 | POST /api/v1/highlights (位置 + 文本) |
| 上传自己资料 | POST /api/v1/inbox/submit (走 substrate 流水线) |
| 跨内容搜索 | POST /api/v1/search (同时查 content + substrate + note + concept) |
| 查看概念图谱 | GET /api/v1/graph/concept/{concept_id} |
| 订阅 / 付费 | POST /api/v1/billing/subscribe (走微信支付) |

### 3.2 用户不可见的内部概念

- "substrate" / "concept" / "note" 三层分类 — UI 统一叫"资料"或"卡片"
- "medium" 18 类 — UI 用图标 + 简单标签
- "derivative" / "fragment" — 不暴露
- ULID — URL 里可能有但不强调

### 3.3 用户可配置项

| 配置项 | 默认 | 范围 |
|---|---|---|
| 主网盘 | 首次引导选择 | OneDrive / 阿里云盘 / Dropbox / Google Drive / WPS / 本地 |
| 本地缓存上限 (用户自有 + 平台内容) | 5 GB | 1-50 GB |
| 平台内容缓存策略 | 已订阅 + 最近 30 天访问 | 配置可调 |
| embedding 计算位置 | 自动 (服务器 Qwen3 API) | 自动 / 本地 / 必须服务器 |
| 同步频率 | 实时 | 实时 / 每 5 分钟 / 仅 WiFi / 手动 |
| 通知开关 | hevi 新内容 + 同步状态 | 细粒度可调 |

---

## §4 内容体系

### 4.1 平台内容三种形态

| 形态 | 描述 | 生产频次 | 用户消费 |
|---|---|---|---|
| **深度文章** | hevi 出品的长文 (3000-8000 字), 含图表 / 数据 / 案例 | 每周 1-2 篇 | 阅读 |
| **概念百科** | 结构化概念条目, 含 Wiki 实战观点 | 持续积累 | 检索 / 关联 |
| **音频解读** | 深度文章的 TTS 版本 | 跟文章 1:1 | 通勤听 |

### 4.2 平台内容 schema

```sql
CREATE TABLE platform_content (
    id TEXT PRIMARY KEY,              -- "stratum-content-{ulid}"
    type TEXT NOT NULL,                -- 'article' / 'concept_entry' / 'audio'
    title TEXT NOT NULL,
    author TEXT,                       -- 默认 'hevi'
    body_markdown TEXT,                -- 文章正文 (Markdown)
    body_html TEXT,                    -- 渲染后 (含图表 / 公式)
    audio_url TEXT,                    -- 音频 CDN URL (有则)
    duration_seconds INT,              -- 音频时长
    published_at TIMESTAMP,
    updated_at TIMESTAMP,
    version INT DEFAULT 1,
    domain TEXT[],                     -- ['investing', 'quant', 'macro', ...]
    tags TEXT[],
    related_content_ids TEXT[],        -- 平台内部内容关联
    related_concepts TEXT[],           -- 关联的 concept (用于跟用户数据融合)
    access_tier TEXT NOT NULL,         -- 'free' / 'plus' / 'pro'
    deleted_at TIMESTAMP NULL
);

CREATE TABLE platform_content_chunk (
    -- 用于 embedding + 检索
    id TEXT PRIMARY KEY,               -- "{content_id}#chunk_{idx}"
    content_id TEXT NOT NULL,
    chunk_idx INT NOT NULL,
    text TEXT NOT NULL,
    embedding VECTOR(1024),            -- pgvector / qdrant 服务端
    chunk_meta JSONB                   -- 章节 / 段落定位
);

CREATE TABLE user_content_interaction (
    -- 用户跟平台内容的交互
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    interaction_type TEXT,             -- 'view' / 'bookmark' / 'highlight' / 'completed'
    payload JSONB,                     -- e.g. highlight position
    created_at TIMESTAMP
);
```

### 4.3 平台内容跟 hevi 的对接

hevi 是独立项目, 但 Stratum 通过明确接口从 hevi 拉内容:

```
hevi 产出新内容 (markdown + meta.yaml)
  ↓ hevi 内部
git push hevi-content-repo
  ↓
hevi-content-repo (内容仓库, 私有)
  ↓ Stratum 服务端定时拉
content_ingest_pipeline (Stratum 内):
  - parse markdown + meta
  - 生成 chunks + embeddings (Qwen3)
  - 自动生成 TTS 音频 (Phase 2)
  - 提取概念 + 关联到 concept 库
  - 写入 platform_content + platform_content_chunk
  ↓
对用户可见
```

**关键**: hevi-content-repo 是**两个项目的桥接点**, 协议必须稳定:
- 文件结构: `{year}/{month}/{slug}.md` + `{slug}.meta.yaml`
- meta.yaml 字段: title / author / domain / tags / access_tier / related_concepts
- 内容更新通过 git commit 触发, Stratum 拉取并 reindex

### 4.4 概念百科的特殊地位

**概念百科**是 Stratum 跟得到 / 喜马拉雅的核心差异:

- 不是简单的"术语解释" (那是百度百科 / 维基百科的事)
- 是**带 hevi 实战观点的结构化条目**:
  - 标准定义
  - hevi 的解读 / 实战案例
  - 关联概念图
  - 用户视角的"已学/未学"标记 (跟用户数据融合)

例: "凯利公式" 条目结构:
```
1. 定义 (公式 + 推导)
2. hevi 解读:
   - 何时适用
   - 何时失效 (例: 高波动品种 / 不可重复博弈)
   - Wiki 实战经验
3. 关联概念: 资金管理 / 风险控制 / 期望值 / 复利
4. 推荐顺序: 期望值 → 凯利公式 → 部分凯利
5. 你的笔记区 (跟用户自有数据融合)
```

---

## §5 用户自有数据架构 (沿用 v0.3 大部分)

### 5.1 18 medium 分类

(同 v0.3 §3.1, 不重复)

### 5.2 12 derivative 类型

(同 v0.3 §3.3, 不重复)

### 5.3 11 concept 类型

(同 v0.3 §3.4, 不重复)

**关键扩展**: concept 是**用户和平台共享命名空间**

- hevi 出的概念百科条目 → 创建 platform-owned concept
- 用户笔记里抽取的概念 → 创建 user-owned concept
- 检索时, 同一 label (例 "凯利公式") 优先返回 platform-owned, 再返回 user-owned
- 用户可以"订阅"某个 platform concept (新版本时通知)

### 5.4 三层分类器

(同 v0.3 §3.2, 不重复)

---

## §6 三层数据架构

```
平台层 (我们服务器 + CDN):
├── platform_content/          # hevi 出品内容
├── platform_content_chunk/    # 内容切片 + embedding (服务端向量库)
├── platform_concept/          # 平台拥有的概念百科
└── audio_cdn/                 # 音频文件 CDN

用户网盘层 (用户拥有):
└── /Stratum/
    ├── substrate/             # 用户上传的原始文件
    ├── derivative/            # 衍生物
    ├── concepts/              # 用户私有 concept
    ├── notes/                 # 用户笔记 (含给平台内容的笔记)
    ├── highlights/            # 用户高亮 (按 content_id / substrate_id 索引)
    └── _hub_backup/           # 索引备份
        └── snapshot-{date}.zip

用户本地层 (各设备):
└── ~/.stratum/
    ├── cache/
    │   ├── meta.duckdb        # 用户元数据
    │   ├── fulltext.tantivy/  # 用户内容全文索引
    │   ├── vectors-text.lance/
    │   ├── platform_cache/    # 平台内容本地缓存 (已订阅 + 最近访问)
    │   │   ├── articles/      # markdown
    │   │   ├── audio/         # 音频 (按需缓存)
    │   │   └── chunks.lance   # 平台内容 embedding 缓存
    │   └── substrate_lru/     # 用户原始文件 LRU
    ├── config.yaml
    ├── outbox/                # 待同步操作
    └── tokens.encrypted       # 网盘 OAuth token

服务器协调层:
└── /api/
    ├── user_meta/{user_id}/
    │   ├── account.json
    │   ├── subscription.json  # 订阅状态
    │   ├── storage_config.json
    │   └── changefeed.log
    └── platform_content_meta/ # 内容元数据 (不含 body, body 走 CDN)
```

### 6.1 三层的不变量

1. 我们服务器**不持有用户 substrate 原始 bytes**
2. 用户网盘**不持有平台内容 body** (只持有用户对平台内容的笔记 / 高亮)
3. 本地 platform_cache 是**只读副本**, 跟服务器同步, 不写回
4. 用户取消订阅 → 本地 platform_cache 在下次同步时清空 (用户笔记保留)

---

## §7 网盘适配层 (oprim.storage)

### 7.1 适配器优先级

| Provider | 优先级 | 状态 |
|---|---|---|
| OneDrive (Microsoft Graph) | **P0** | 国内可用 |
| 阿里云盘 (开放平台) | **P1** | 需开放平台凭证 |
| Dropbox | **P1** | 国际用户主选 |
| Google Drive | **P1** | 国际用户备选 |
| WPS 云空间 | **P2** | 学生用户广 |
| 本地文件夹 | **P0** | 隐私敏感 / 离线 |
| 百度网盘 | **不支持** | 合规接入路径不通 |
| 微信文件传输助手 | **不支持** | 个人号无官方 API |

### 7.2 storage_adapter 接口

```python
class StorageAdapter(Protocol):
    async def authenticate(self, oauth_code: str) -> StorageCredentials: ...
    async def upload(self, local_path: Path, remote_path: str) -> RemoteFileRef: ...
    async def download(self, remote_ref: RemoteFileRef, local_path: Path) -> None: ...
    async def list(self, remote_path: str, recursive: bool = False) -> list[RemoteFileRef]: ...
    async def delete(self, remote_ref: RemoteFileRef) -> None: ...
    async def get_download_url(self, remote_ref: RemoteFileRef, ttl: int = 3600) -> str: ...
    async def get_quota(self) -> StorageQuota: ...
    async def watch(self, remote_path: str, callback: Callable) -> WatchHandle: ...
```

### 7.3 各 adapter 差异

(同 v0.3 §5.3 关键差异点)

- OneDrive: msgraph-sdk, OAuth v2.0, subscriptions push
- 阿里云盘: 开放平台 OAuth, 三步上传, 4 小时 download URL, 无 push (用 polling)
- Dropbox: 块级同步优势, files/get_temporary_link
- Google Drive: drive.changes.watch
- 本地: inotify / FSEvents / ReadDirectoryChangesW

### 7.4 多 adapter 并存

(同 v0.3 §5.4)

---

## §8 索引架构

### 8.1 双索引

**平台索引** (服务器端):
- platform_content + platform_content_chunk → pgvector (PostgreSQL 扩展)
- 服务器端搜索, 用户查询走 API
- 不分发给用户本地 (除已订阅 + 缓存的部分)

**用户索引** (本地 + 网盘备份):
- 用户 substrate / derivative / note / concept → 本地 LanceDB
- 本地为主, 网盘备份 snapshot

**融合检索**: 用户查询同时打两个索引, 结果按 RRF 融合 (见 §10)

### 8.2 技术选型

按批 2 实证:

| 索引 | 平台侧 (服务器) | 用户侧 (本地) |
|---|---|---|
| 元数据 | PostgreSQL | DuckDB |
| 全文 | PostgreSQL FTS / Elasticsearch | Tantivy |
| 向量 | pgvector / Qdrant Server | LanceDB |
| Embedding | Qwen3 (DashScope) | Qwen3 (DashScope) 或本地 |

**关键决策**: 平台侧用 PostgreSQL + pgvector (运维简单, 单一数据库). 用户本地按实证 #2 用 LanceDB (嵌入式 + 性能优秀).

### 8.3 平台索引 schema

```sql
-- platform_content_chunk 已在 §4.2
-- 平台 fulltext 用 PostgreSQL tsvector:

ALTER TABLE platform_content ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (
    to_tsvector('chinese_zh_jieba_ext',
        coalesce(title, '') || ' ' || coalesce(body_markdown, '')
    )
) STORED;

CREATE INDEX idx_platform_content_search ON platform_content USING GIN(search_vector);
```

### 8.4 用户索引 schema

(同 v0.3 §6.5, 不重复)

### 8.5 平台内容本地缓存

为了离线访问 + 性能, 已订阅用户的最近 30 天访问内容缓存到本地:

```python
class PlatformContentCache:
    base_path = "~/.stratum/cache/platform_cache/"

    def cache_content(content_id: str, body_markdown: str, chunks: list, audio_url: str | None):
        # 写本地 articles/{content_id}.md
        # 写本地 chunks 到 chunks.lance
        # audio 按需下载
        pass

    def evict_old(): ...      # LRU 淘汰
    def clear_on_unsubscribe(): ...  # 取消订阅时清空
```

### 8.6 平台内容索引备份

用户网盘**不存平台内容 body**, 但存:
- 用户的笔记 → /Stratum/notes/{note_id}.md (笔记里引用 content_id)
- 用户的高亮 → /Stratum/highlights/{content_id}/highlights.json

含义: 用户卸载我们的服务 → 平台内容拿不到了, 但**用户自己的笔记 / 高亮永久属于用户**, 在网盘里可读。

---

## §9 抗腐烂规则 (lint)

### 9.1 schema 一致性

- 任何 substrate 必须有 medium 字段
- 任何 derivative 必须 reference 一个 substrate
- 任何 concept 关联的 substrate_ids 必须真实存在
- 任何 user_content_interaction 必须 reference 真实 content_id 或 substrate_id (不能两个都空)
- 任何 highlight 必须 reference 真实 content_id 或 substrate_id
- ULID 必须符合规范

### 9.2 命名约定

- 用户 substrate ULID: `01HY...` (26 字符)
- 平台 content ULID: `stratum-content-{26字符}`
- 用户 concept: `01HZ...`
- 平台 concept: `stratum-concept-{26字符}`
- 文件名 (网盘内): `{ulid}--{slug_title}.{ext}`

### 9.3 引用完整性

- substrate 删除 → 关联 derivative 软删除
- concept 删除前必须解绑所有 substrate_refs
- 笔记引用的 substrate_refs / concept_refs / content_refs 必须存在
- 用户取消订阅 → 用户对平台内容的笔记保留, 但平台 content 引用变为 "已失效订阅" 状态

### 9.4 平台内容版本一致性

- platform_content 更新 (hevi push 新版) → version 自增
- 用户已有的高亮 / 笔记跟 version 绑定
- 新版本发布后:
  - 用户在旧版本的高亮 → 标记 "可能位置变化, 请确认"
  - 笔记中的引文如有变化 → 提示用户

### 9.5 lint 工具

- CLI: `stratum lint` (本地用户数据)
- 服务端 cron: 平台内容 lint (每日)
- CI: 用户网盘 snapshot lint (异常推送)

---

## §10 检索接口 (融合)

### 10.1 search 接口 (核心融合点)

```
POST /api/v1/search
Request:
{
    "query": "凯利公式",
    "scope": ["platform_content", "user_substrate", "user_notes", "concept"],
    "modalities": ["text", "audio_transcript", "image_ocr"],
    "medium_filter": ["book", "paper", "article"],
    "domain_filter": ["investing", "quant"],
    "language_filter": ["zh", "en"],
    "date_range": {"from": null, "to": null},
    "top_k": 20
}

Response:
{
    "results": [
        {
            "type": "platform_content",
            "id": "stratum-content-01HY...",
            "title": "凯利公式在 BTC 投资的实战检验",
            "author": "hevi",
            "score": 0.95,
            "highlight": "凯利公式假设...",
            "access_tier": "plus",
            "user_has_access": true
        },
        {
            "type": "platform_concept",
            "id": "stratum-concept-01HY...",
            "label": "凯利公式",
            "summary": "...",
            "score": 0.92,
            "related_count": {"platform_content": 5, "user_substrate": 2, "user_notes": 1}
        },
        {
            "type": "user_substrate",
            "id": "01HZ...",
            "title": "随机漫步的傻瓜 (Nassim Taleb)",
            "medium": "book",
            "score": 0.78,
            "highlight": "第 7 章提到凯利的赌博理论...",
            "fragment_id": "01HZ...#chunk_47"
        },
        {
            "type": "user_note",
            "id": "01HW...",
            "title": "凯利公式不适合 BTC 高波动品种",
            "score": 0.71,
            "preview": "实测发现连续亏损时..."
        }
    ],
    "sync_status": {
        "is_fully_synced": true,
        "pending_substrate_count": 0,
        "last_sync_at": "..."
    },
    "search_time_ms": 145
}
```

**关键**:
- `scope` 决定查哪几层 (默认全部)
- 结果**跨层混合排序**, 不是分组
- `user_has_access` 字段告诉客户端用户是否能访问该平台内容 (未订阅时引导付费)

### 10.2 RRF 融合算法

```python
def fuse_results(platform_results, user_results, k=60):
    """Reciprocal Rank Fusion"""
    scores = {}
    for rank, item in enumerate(platform_results):
        scores[item.id] = scores.get(item.id, 0) + 1.0 / (k + rank + 1)
    for rank, item in enumerate(user_results):
        scores[item.id] = scores.get(item.id, 0) + 1.0 / (k + rank + 1)
    return sorted(items, key=lambda x: scores[x.id], reverse=True)
```

### 10.3 fetch_content (平台内容详情)

```
GET /api/v1/content/{content_id}
Response:
{
    "id": "stratum-content-01HY...",
    "title": "凯利公式在 BTC 投资的实战检验",
    "body_markdown": "...",                # 完整正文 (用户已订阅)
    "audio_url": "https://cdn.stratum.../audio.mp3",
    "duration_seconds": 1800,
    "version": 3,
    "published_at": "...",
    "user_progress": {
        "view_count": 2,
        "completed": false,
        "last_position": "section-3"
    },
    "user_highlights": [...],              # 该用户的高亮
    "user_notes": [...],                   # 该用户对此内容的笔记
    "related_user_substrate": [            # 用户自有资料里的相关内容
        {"id": "01HZ...", "title": "随机漫步的傻瓜", "relevance": 0.78}
    ],
    "related_concepts": [
        {"id": "stratum-concept-...", "label": "凯利公式"},
        {"id": "stratum-concept-...", "label": "资金管理"}
    ],
    "related_platform_content": [...]      # 平台内的相关内容
}
```

**这是 Stratum 的核心差异化体现**: 一个 API 返回 4 层关联 (用户进度 + 用户笔记 + 用户自有资料 + 平台关联), 得到 / 喜马拉雅做不到。

### 10.4 fetch_substrate

(同 v0.3 §8.2, 不重复)

### 10.5 concept 接口

```
GET /api/v1/concept/{concept_id}
Response:
{
    "id": "stratum-concept-01HY...",
    "label": "凯利公式",
    "type": "concept_idea",
    "owner": "platform",
    "summary": "...",
    "platform_view": {
        "definition": "...",
        "hevi_perspective": "...",          # hevi 解读
        "applicability": "...",
        "common_mistakes": "..."
    },
    "user_view": {                           # 跟用户数据融合
        "in_user_substrate": [...],          # 用户上传资料里有提及
        "in_user_notes": [...],              # 用户笔记里
        "user_marked_status": "learning"     # 用户标记的学习状态
    },
    "related_concepts": [...],
    "platform_content_using": [...]          # 哪些平台内容用到了这个概念
}
```

### 10.6 graph 接口 (概念图谱)

```
GET /api/v1/graph/concept/{concept_id}?depth=2
Response:
{
    "center": {...concept...},
    "nodes": [
        {"id": "...", "type": "concept", "label": "..."},
        {"id": "...", "type": "platform_content", "title": "..."},
        {"id": "...", "type": "user_substrate", "title": "..."},
        {"id": "...", "type": "user_note", "title": "..."}
    ],
    "edges": [
        {"from": "...", "to": "...", "type": "uses_concept"},
        {"from": "...", "to": "...", "type": "user_authored"},
        ...
    ]
}
```

### 10.7 MCP tool 暴露

按实证 #4 用 `mcp.server.fastmcp.FastMCP`:

- `stratum.search` (融合搜索)
- `stratum.fetch_content` (平台内容)
- `stratum.fetch_substrate` (用户内容)
- `stratum.fetch_concept` (概念)
- `stratum.fetch_graph` (图谱)
- `stratum.list_notes`
- `stratum.recent_changes`

### 10.8 离线降级

- 平台内容: 本地 platform_cache 有的可读, 没有的提示 "需联网"
- 用户内容: 本地完整可读
- 搜索: 本地索引命中 + sync_status 提示

---

## §11 流水线

### 11.1 平台内容入库流水线

```
hevi-content-repo (git push 触发):
↓
Stratum 服务端 cron (每 5 分钟) 检查更新
↓
拉新提交的 markdown + meta.yaml
↓
Step 1: parse markdown + meta validation
↓
Step 2: 切 chunks (按段落或固定 token)
↓
Step 3: Qwen3 计算 embedding
↓
Step 4: 提取概念 (LLM 调用)
    - 跟现有 platform_concept 去重
    - 新概念入 platform_concept 表
↓
Step 5: 生成 TTS 音频 (异步)
    - Phase 2 实施, 用 Azure Speech / 阿里 TTS / OpenAI TTS
    - 音频上 CDN
↓
Step 6: 写 platform_content + platform_content_chunk
↓
Step 7: 触发推送给已订阅用户:
    - 微信小程序订阅消息
    - app push notification
    - 邮件 (可选)
↓
对用户可见
```

### 11.2 用户 substrate 入库流水线

(同 v0.3 §9.1, 不重复主流程)

### 11.3 用户跟平台内容交互流水线

```
用户在平台内容上 highlight 一段文字:
↓
客户端 POST /api/v1/highlights
{
    "content_id": "stratum-content-01HY...",
    "anchor": {
        "version": 3,            # 内容版本
        "section": "...",
        "char_start": 1234,
        "char_end": 1267,
        "text": "凯利公式假设..."
    },
    "color": "yellow",
    "note": "实测不适合 BTC"      # 可选
}
↓
服务器:
    - 验证 user 已订阅 / 有权访问
    - 写 user_content_interaction 表
    - 异步: 把 highlight 同步到用户网盘 /Stratum/highlights/{content_id}/highlights.json
↓
changefeed event: {type: "highlight_added", content_id, highlight_id}
↓
其他设备同步
```

### 11.4 推荐流水线

基于用户行为 + 内容关联:

```
用户行为信号:
- 最近 30 天访问 content_ids
- bookmark 的 content
- 高亮密度高的 content
- 笔记中提及的 concepts

候选生成:
- 跟最近访问 content 相关的新 content (按 related_content_ids)
- 跟用户标记 "learning" 的 concept 相关的 content
- hevi 新发布且 domain 匹配的 content

排序:
- 用 LLM 简单 rerank (Top 20 → Top 5)
- 或 embedding 相似度 (用户兴趣向量 vs content embedding)

输出:
- 发现页 (混排)
- push notification 推荐 (高分项)
```

**v1.0 简化版**: 不做 ML 模型, 用规则 + embedding 相似度.

### 11.5 删除流水线

(同 v0.3 §9.5)

平台内容删除 (hevi 撤稿):
- 平台 content 标记 deleted_at
- 用户对该内容的高亮 / 笔记**保留** (用户的思考归用户)
- UI 提示 "原内容已删除, 你的笔记仍可访问"

---

## §12 多端同步

### 12.1 同步范围分层

| 数据 | 同步机制 | push 触发 |
|---|---|---|
| 用户 substrate / derivative | 用户网盘 + changefeed | ingest event |
| 用户 notes / highlights | 用户网盘 + changefeed | note_create event |
| 用户 concept | 用户网盘 + changefeed | concept_create event |
| 平台内容 metadata | 服务器端, 客户端按需拉 | new_content event |
| 平台内容 body | CDN 流式 + 本地缓存 | 用户访问触发 |
| 订阅状态 | 服务器端 | subscription_change event |

### 12.2 changefeed 协议

```json
{
    "seq": 12345,
    "user_id": "user_abc",
    "device_id": "device_xyz",
    "timestamp": "2026-05-17T14:30:00Z",
    "event_type": "ingest" | "note_create" | "highlight_added" | ...,
    "payload": {...}
}
```

### 12.3 event 类型

(扩展 v0.3 §10.2)

用户事件:
- `ingest` / `derivative_added` / `update_metadata` / `move` / `delete` / `physical_delete`
- `note_create` / `note_update` / `note_delete`
- `concept_create` / `concept_merge` / `concept_split`
- `storage_added` / `storage_removed`
- `snapshot_created`
- `highlight_added` / `highlight_removed`
- `bookmark_added` / `bookmark_removed`

平台事件 (服务器 push 给客户端):
- `platform_content_new` (有新文章)
- `platform_content_updated` (文章更新)
- `platform_concept_updated`
- `subscription_changed`

### 12.4 push 通知机制

| 平台 | 机制 |
|---|---|
| iOS app | APNs |
| Android app | FCM + 国内 (小米 / 华为 push) |
| Web | Web Push API + Service Worker |
| 桌面 | WebSocket 长连接 |
| 微信小程序 | 微信订阅消息 |

降级: 失败时客户端 polling (5 分钟一次).

### 12.5 冲突处理

(同 v0.3 §10.5)

新增:
- 用户在多设备同时给同一内容高亮同一文本 → 合并 (取并集)
- 用户在多设备同时写笔记 → 两个独立笔记 (不合并, 用户决定)

---

## §13 安全与隐私

### 13.1 用户身份

- 邮箱 + 密码 (主要)
- 微信登录 (国内主推)
- Apple / Google OAuth (国际)
- 密码用 Argon2id

### 13.2 OAuth token 管理

用户网盘 OAuth token 加密存储:
- 主密钥派生自用户密码 (Argon2)
- 服务器只存密文 + salt
- 用户改密码 → token 重加密

### 13.3 平台内容版权保护

- 内容 body 不写入用户网盘 (防止用户导出分发)
- audio 流式访问 (短期签名 URL, 5 分钟 TTL)
- 客户端**不缓存到用户可见目录** (隐藏 ~/.stratum/cache/platform_cache/)
- 用户截屏 / 摘抄 → 不阻止 (摩擦只能挡 90%)
- 用户大量复制粘贴 → 服务端检测 + rate limit

### 13.4 用户数据隐私

- 服务器不持有 substrate 原始 bytes
- 临时下载 (embedding 计算 / LLM 调用) 30 分钟 TTL
- 临时文件加密 (用户独立 key)
- audit log 用户可查

### 13.5 LLM 调用的数据流

- 服务器调 Qwen3 DashScope: 用户 query + content chunks → embedding 返回
- DashScope 承诺不留存用户输入 (合规层面)
- 用户可选 "本地 embedding" (用 Qwen3-0.6B 本地跑), 但性能差

### 13.6 用户卸载场景

1. 注销账号 → 服务器 account + changefeed 30 天宽限
2. 用户网盘 /Stratum/ 保留 (含 substrate / 笔记 / 高亮)
3. 平台内容不可访问 (订阅取消)
4. 重新注册 → 可从网盘 snapshot 恢复用户自有数据 (平台内容需重新订阅)

### 13.7 监管合规

- 中国大陆: ICP 备案 + 微信小程序合规 + 内容备案 (平台 hevi 出品内容需备案)
- 用户内容: 不存我们服务器 → 大幅降低内容审核责任
- LLM 调用走合规服务 (Qwen3 / 文心 / DeepSeek 已备案)

---

## §14 微信集成

### 14.1 微信是国内主入口

合规路径:
- ✅ 微信小程序: 主战场
- ✅ 微信公众号: 推送通知 + 兜底入口
- ✅ 微信支付: 订阅付费
- ❌ 个人微信 API / Hook / WeChaty: 严禁

### 14.2 微信小程序功能

**核心页面**:
- 发现 (平台内容 feed)
- 我的库 (用户自有资料)
- 概念图谱
- 笔记
- 个人中心 (订阅 / 付费 / 设置)

**capture 入口** (用户自有内容):
- `wx.chooseMessageFile` - 从聊天选文件
- `wx.chooseImage` / `wx.chooseMedia`
- `wx.startRecord` - 录音
- `wx.scanCode` - 扫码

**内容消费**:
- 阅读平台文章 (markdown 渲染)
- 听音频 (内置 audio player)
- 高亮 / 笔记
- 概念跳转

**付费**:
- 微信支付 H5 / 小程序支付
- 订阅管理

### 14.3 微信公众号功能

- 用户绑定: 关注公众号 + 扫码绑定
- 推送: 新内容 / 同步状态 / 订阅提醒
- 发文件: 用户给公众号发文件 → 触发 ingest (兜底)
- 简单查询: 文字发"找凯利公式" → 返回结果链接

### 14.4 文件大小限制

- 小程序单文件 100 MB (HTTPS 上传)
- 公众号文件 20 MB
- 大文件引导桌面 / 移动 app

---

## §15 付费系统

### 15.1 订阅档位

| 档位 | 价格 | 内容范围 |
|---|---|---|
| **Free** | ¥0 | hevi 部分免费内容 + Stratum 工具基础 (容量 1 GB) |
| **Plus** | ¥29/月 / ¥299/年 | 全部 hevi 独有内容 + 工具完整版 (容量 20 GB 缓存) |
| **Pro** | ¥99/月 / ¥999/年 | Plus + Wiki 答疑 (受限) + 早鸟内容 (新内容先看 7 天) |
| **学生 Plus** | ¥149/年 (.edu 验证) | 同 Plus |

### 15.2 付费流程

```
用户点 "升级 Plus"
↓
选择 月付 / 年付
↓
调起微信支付 / Apple Pay / Stripe (海外)
↓
支付成功 → 服务器更新 subscription
↓
changefeed: {type: "subscription_changed", new_tier: "plus"}
↓
客户端解锁 access_tier=plus 的内容
↓
微信订阅消息: "Plus 已开通"
```

### 15.3 access_tier 控制

平台 content 表的 `access_tier` 字段决定:
- `free`: 所有用户可访问
- `plus`: Plus + Pro 可访问
- `pro`: Pro 独占

API 层校验:
```python
async def fetch_content(content_id: str, user: User):
    content = await db.get_platform_content(content_id)
    if not user.can_access(content.access_tier):
        return {"locked": True, "preview": content.body_markdown[:500], "upgrade_url": "..."}
    return content
```

### 15.4 订阅状态同步

- 服务器是 source of truth
- 客户端缓存 subscription 状态 (含过期时间)
- 离线时按缓存判断, 重新联网后校准
- 订阅过期 → 平台内容 lock, 用户自有数据不受影响

### 15.5 优惠 / 推荐

(v1.0 简化, 不做复杂优惠)
- 学生优惠 (.edu 邮箱)
- 早鸟优惠 (前 1000 用户终身 50% off)
- 推荐返佣 (用户推荐成功 → 双方各 1 个月)

---

## §16 实施路线 (依赖关系)

### Phase 1: 基础设施

**前置**: 无
**产出**: 4O 库 + 单机版 Stratum (用户工具核心)

- obase 实施
- oprim / oskill / omodul
- 用户 schema (substrate / derivative / concept / note)
- DuckDB + Tantivy + LanceDB 本地索引
- 入库流水线 (Layer 1+2 分类器, 不含 LLM)

### Phase 2: 网盘 + 同步

**前置**: Phase 1
**产出**: 多设备同步可用

- OneDrive adapter (P0)
- 本地文件夹 adapter (P0)
- storage_adapter 抽象
- OAuth + token 加密
- 服务器 changefeed API
- 本地 outbox + flush
- WebSocket push (桌面)

### Phase 3: 平台内容流水线

**前置**: Phase 2 + hevi-content-repo 协议商定
**产出**: hevi 内容可入 Stratum 平台

- hevi-content-repo 拉取 cron
- platform_content 流水线 (parse / chunk / embed)
- 平台索引 (pgvector + PostgreSQL FTS)
- 平台 concept 抽取
- 内容版本管理

### Phase 4: 微信小程序 MVP

**前置**: Phase 3
**产出**: 用户可通过微信小程序消费内容 + 上传资料

- 微信小程序 (发现 / 我的库 / 笔记 / 个人中心)
- 微信登录
- substrate 入库 (走 §11.2)
- 平台内容阅读
- 高亮 / 笔记

### Phase 5: 付费系统

**前置**: Phase 4
**产出**: 商业化可用

- 订阅档位 (Free / Plus / Pro)
- 微信支付集成
- access_tier 校验
- 订阅状态同步

### Phase 6: 融合检索

**前置**: Phase 5
**产出**: 核心差异化能力

- 跨层 search API (融合 platform + substrate + note + concept)
- RRF 融合算法
- fetch_content 含跨层关联
- 概念图谱 API

### Phase 7: 公众号 + 推送

**前置**: Phase 6
**产出**: 完整微信生态

- 微信公众号绑定
- 订阅消息推送
- 公众号发文件入库 (兜底)
- 推荐流水线 (规则版)

### Phase 8: TTS 音频生成

**前置**: Phase 7
**产出**: hevi 文章自动音频化

- TTS 服务接入 (Azure / 阿里 / OpenAI)
- 音频 CDN
- 客户端 audio player

### Phase 9: 第二批网盘适配

**前置**: Phase 5
**产出**: 国内网盘 + 国际网盘完整

- 阿里云盘 adapter (前置: 开放平台凭证)
- Dropbox adapter
- Google Drive adapter
- WPS 云空间 (P2)

### Phase 10: LLM 增强

**前置**: Phase 6
**产出**: 三层分类器完整 + 高级 derivative

- 分类器 Layer 3 (LLM 兜底)
- 高级 derivative (summary / key_quotes / entities 完整)
- 用户内容 concept 自动抽取

### Phase 11: 移动端

**前置**: Phase 8 + Phase 10
**产出**: iOS / Android app

- iOS app (Swift + share extension)
- Android app (Kotlin + share intent)
- 复用后端

### Phase 12: 桌面 + 浏览器扩展

**前置**: Phase 11
**产出**: 全平台覆盖

- 桌面 app (Tauri)
- Chrome / Safari / Firefox 扩展

---

## §17 关键技术决策来源

| 决策 | 来源 |
|---|---|
| MCP 框架 = `mcp.server.fastmcp.FastMCP` | 实证 #4 |
| PDF 解析 = pymupdf4llm + Marker + MinerU 分层 | 实证 #1 |
| 用户向量库 = LanceDB | 实证 #2 |
| 平台向量库 = pgvector / PostgreSQL | 选型决策 (服务端单一数据库) |
| Embedding = Qwen3-Embedding (DashScope) | 实证 #3 |
| 数据存用户网盘 + 本地 + 服务器 changefeed | 实证 #5 |
| OneDrive P0 / 阿里云盘 P1 / 弃百度 | 实证 #5 |
| 微信小程序 + 公众号, 不碰个人号 | 实证 #5 |
| 平台内容跟 hevi 通过 git repo 对接 | 工程实施决策 |
| RRF 融合用户 + 平台检索结果 | Helios v5 已验证 |

完整实证报告:
- /mnt/user-data/outputs/batch2-experiment-01..05/REPORT.md

---

## §18 未决问题

### Q1: hevi-content-repo 协议细节

**问题**: meta.yaml 字段完整 schema / git 分支策略 / 版本号约定

**影响**: Phase 3 启动前必须商定, 否则 hevi 和 Stratum 对接不上

**决定时机**: Phase 3 启动前 (跟 hevi advisor 协商)

### Q2: 阿里云盘开放平台凭证可行性

**问题**: 个人 / 初创能否拿到 client_id + client_secret

**影响**: 拿不到 → 国内用户主要靠 OneDrive (国内慢) + WPS

**决定时机**: Phase 9 启动前必须先确认

### Q3: 服务器部署区域

**问题**: 中国大陆 / 海外 / 双区

**影响**:
- 中国: 阿里云 / 腾讯云 + 完整备案
- 海外: AWS / Cloudflare + GDPR
- 双区: 工程复杂度翻倍

**决定时机**: Phase 2 启动前

### Q4: 平台内容防盗版强度

**问题**: §13.3 用流式 + 短期 URL, 但用户截屏 / 摘抄无法阻止

**选项**:
- (a) 接受 90% 防护, 不做额外措施
- (b) 加 DRM (Widevine / FairPlay, 复杂度高)
- (c) 加水印 (用户 ID 水印, 可追溯但用户体验差)

**决定时机**: Phase 4 启动前

### Q5: TTS 服务选型

**问题**: Azure Speech / 阿里 TTS / OpenAI TTS / ElevenLabs / 本地 (XTTS / Kokoro)

**影响**: 价格 + 中文音质 + 部署

**决定时机**: Phase 8 启动前 (单独做实证)

### Q6: 推荐算法 v1.x 升级

**问题**: v1.0 用规则 + embedding, v1.x 是否上 ML 模型

**影响**: 工程量 + 数据需求 + 团队

**决定时机**: Phase 7 完成后看用户量

### Q7: 移动端跨平台 vs 原生

**问题**: React Native / Flutter (跨平台) vs Swift + Kotlin (原生)

**影响**: 工程量 / 性能 / 平台特性

**决定时机**: Phase 11 启动前

### Q8: E2EE 是否纳入

**问题**: §13 没做 E2EE, 是否补?

**影响**: 隐私强但 LLM / embedding 必须本地, 性能差

**决定时机**: Phase 2 启动前 (影响架构基础)

### Q9: 内容备案合规细节

**问题**: hevi 出品内容是否需逐篇备案? 平台主体备案够不够?

**影响**: 国内合规 + 上线时间

**决定时机**: Phase 3 启动前 (找合规律师确认)

### Q10: 公开 API 开放范围

**问题**: §10.7 MCP tool 是否对外部第三方开发者开放?

**影响**: 生态 vs 内容保护

**决定时机**: Phase 10 完成后

---

**End of STRATUM_SPEC v0.5**
