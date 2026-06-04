# PHASE_1_4O_IMPLEMENTATION_INSTRUCTIONS_v0.1.md

**任务**: 实施 Stratum Phase 1 必备 4O 元素
**执行模式**: Claude Code FULL AUTO 或 半自动
**SPEC 依据**:
- STRATUM_SPEC v0.5 (1214 行)
- 4O 扩充清单 v0.2 (583 行)
- 实证 #1-#5 (具体 provider 选型依据)

**预期产物**:
- GitHub repo `oprim` (扩充 Phase 1 oprim 子集)
- GitHub repo `oskill` (扩充 Phase 1 oskill 子集)
- GitHub repo `omodul` (扩充 Phase 1 omodul 子集)
- 三层一次性 verify 通过

**前置**:
- obase v0.1 已完成 (hevi advisor sign-off)
- 仓库位置: `~/projects/oprim` / `~/projects/oskill` / `~/projects/omodul` (基于 helios-plat polyrepo 风格)
- License: 跟 obase 一致

**实施节奏**:
```
Step 1: 实施全部 §1 oprim 层 → Wiki 验收 (验收门 A)
Step 2: 实施全部 §2 oskill 层 → Wiki 验收 (验收门 B)
Step 3: 实施全部 §3 omodul 层 → Wiki 验收 (Phase 1 完成)
```

每个验收门 Wiki 必须 sign-off 才能进入下一步。

---

## §0 FULL AUTO 头部规则 (必读)

### 0.1 红线 (绝对不允许)

**R-1: 失败不静默** (STRATUM_SPEC §2.5 实施保障)

任何场景下绝对禁止以下反模式:
- `except Exception: return <default>` 而不 emit 任何日志
- provider 失败时返回占位结果 (假数据 / 默认零值 / None 代替异常)
- cache 失败时无声跳过 (必须 emit cache_error 事件)
- "为了让 demo 跑通" 加 fallback

如发现某场景**确实**需要降级, 必须满足三个条件:
1. 调用方显式参数控制 (例 `strict=False`)
2. obase.logging emit 显式 error/warning 事件
3. 调用方可区分"成功"和"降级成功"

不满足三条件的 fallback 立即停止报告, 不要"善意地"加。

**R-2: SPEC 是真理源**

STRATUM_SPEC v0.5 + 4O 扩充清单 v0.2 + 实证报告 = 本次实施的三重真理源。如发现冲突或不一致, **停止实施, 报告 chief advisor**, 不要"凭判断"自行解决。

具体禁止:
- 不按 4O 清单 §2.5 选 LanceDB 作为默认 (例如默认改用 chroma)
- 不按 4O 清单 §2.3 选 Qwen3-Embedding 作为主推 (例如默认改用 OpenAI)
- 不按 4O 清单 §2.2 PDF 分层策略 (例如只实施一个 provider 跳过其他)
- 不按 4O 清单 §5 删除项实施 (例如又实施了 e5_mistral / CLIP / qdrant_embedded)
- 不按 STRATUM_SPEC §2.3 实施 ID 不可变 (例如允许 ULID 重新生成)

**R-3: 测试覆盖率硬指标**

关键 oprim 元素 (classifier / parser / embedding / vector_db) **必须 ≥ 90% 测试覆盖率**。
其他 oprim 包装 (storage / fulltext / meta_db / llm) ≥ 70%。
oskill / omodul ≥ 80%。

**不允许跳过 test 提速**。模块实施 = 代码 + test, 二者并重。

**R-4: 禁止扩大范围**

只实施本指令书 §1-§3 列出的 Phase 1 必备元素, **不要**:
- 实施 Phase 2+ 元素 (storage.* / wechat.* / changefeed.* 等不在本范围)
- 实施 4O 清单 §5 删除项 (e5_mistral / clip / imagebind / qdrant_embedded / baidu / wechat_files)
- 在 oprim 加平台内容 / 商业化逻辑 (那是 omodul 上层的事)
- 写 example 之外的 "试用 Stratum" 代码

**R-5: 严格遵守 4O 命名 + 层级**

- oprim = 原子操作 (单一职责, 无 side effect 外的状态)
- oskill = 技能工作流 (调用多个 oprim, 有业务编排逻辑)
- omodul = 业务模块 (端到端流程, 暴露给外部调用)

**禁止**:
- 在 oprim 调用 oskill (反向依赖)
- 在 oskill 调用 omodul (反向依赖)
- 在 oprim 实施业务流程 (例如 oprim.classifier 不应该自己写 substrate 入库)

**R-6: 跨 4O 调用必须显式**

oskill 调用 oprim, omodul 调用 oskill 必须显式 import + 调用, **不允许**:
- monkey patching
- 全局单例隐式依赖
- 反射式动态加载 (除非 provider 模式有明确说明)

provider 模式 (例 storage_adapter / embed_text) **允许**通过 config 字符串选 provider, 但 dispatch 必须显式。

### 0.2 协作模式

实施由 Claude Code 主导, Wiki 控制验收门, Stratum chief advisor (Claude) 提供 spec + review。

**模式**:
1. CC 按本指令书实施一层 (oprim / oskill / omodul)
2. CC push 到 GitHub repo
3. CC 给 Wiki 报告 "X 层完工 + 测试覆盖率 + 关键决策"
4. Wiki 转给 Stratum advisor review
5. advisor review 通过 → Wiki sign-off → 进入下一层
6. advisor review 不通过 → CC 修订 → 回到 4

**关键**: CC 遇到 SPEC 矛盾或不清的时刻, **立刻报告**, 不要"凭判断"自行解决。

### 0.3 obase 依赖 + 公共约定

所有 oprim / oskill / omodul 元素必须:

1. **使用 obase.config** 读配置 — 不要自己 os.environ
2. **使用 obase.logging** 写日志 — 不要 print 或 logging.basicConfig
3. **使用 obase.errors** 抛异常 — 复用 obase 的 10 个标准异常类
4. **使用 obase.cost_tracker** 追踪 LLM 调用 — 不要自己累加成本
5. **使用 obase.bootstrap** 启动 — 任何 entrypoint 第一行调 bootstrap

**Provider 模式 (跟 obase 一致)**:
```python
# 抽象层 (4O 清单中标 "provider 接口")
class StorageAdapter(Protocol):
    async def upload(...) -> RemoteFileRef: ...
    ...

# 具体实现
class OneDriveAdapter:
    def __init__(self, config: dict): ...
    async def upload(...): ...

# 选型 (config 驱动)
def get_storage_adapter(name: str) -> StorageAdapter:
    if name == "onedrive": return OneDriveAdapter(...)
    elif name == "local": return LocalAdapter(...)
    else: raise ConfigError(f"Unknown storage adapter: {name}")
```

### 0.4 仓库结构

```
~/projects/oprim/
├── pyproject.toml
├── README.md
├── oprim/
│   ├── __init__.py
│   ├── classifier/         # §1.1
│   │   ├── __init__.py
│   │   ├── detect_mime.py
│   │   ├── detect_pdf_features.py
│   │   ├── detect_image_exif.py
│   │   └── extract_text_sample.py
│   ├── parser/             # §1.2
│   │   ├── __init__.py
│   │   ├── parse_pdf.py
│   │   ├── parse_epub.py
│   │   └── parse_html.py
│   ├── embedding/          # §1.3
│   │   ├── __init__.py
│   │   ├── embed_text.py
│   │   ├── qwen3_dashscope.py
│   │   └── bge_m3.py
│   ├── vector_db/          # §1.4
│   │   ├── __init__.py
│   │   └── lancedb.py
│   ├── fulltext/           # §1.5
│   │   ├── __init__.py
│   │   └── tantivy.py
│   ├── meta_db/            # §1.6
│   │   ├── __init__.py
│   │   └── duckdb.py
│   ├── llm/                # §1.7
│   │   ├── __init__.py
│   │   └── llm_call.py     # 已在 obase 范围? 若是, 跳过
│   └── mcp/                # §1.8
│       ├── __init__.py
│       └── mcp_server.py
└── tests/
    ├── classifier/
    ├── parser/
    ├── embedding/
    ├── vector_db/
    ├── fulltext/
    ├── meta_db/
    └── mcp/

~/projects/oskill/         # 类似结构, 见 §2

~/projects/omodul/         # 类似结构, 见 §3
```

**注意**: 三个 repo 是 polyrepo, 互相通过 PyPI / 私有 index 依赖。oprim 不依赖 oskill / omodul, oskill 依赖 oprim, omodul 依赖 oprim + oskill。

---

## §1 oprim 层 (验收门 A)

按 4O 清单 v0.2 §2 Phase 1 必备元素。

### §1.1 oprim.classifier

**包**: `oprim.classifier`
**SPEC 依据**: 4O 清单 §2.1, STRATUM_SPEC §11.2 三层分类器

#### §1.1.1 detect_mime

**接口**:
```python
from pathlib import Path

def detect_mime(path: Path) -> str:
    """检测文件真实 MIME 类型 (不信赖扩展名)

    Args:
        path: 文件路径

    Returns:
        MIME 类型字符串, e.g. 'application/pdf', 'image/jpeg', 'text/plain'

    Raises:
        FileNotFoundError: 文件不存在
        PermissionError: 无读权限
    """
```

**实施要点**:
- 用 `python-magic` 库 (依赖 libmagic, Ubuntu 需 `apt install libmagic1`)
- 不能用 `mimetypes.guess_type` (那个只看扩展名)
- 必须真实读取文件 magic bytes

**测试要求** (90% coverage):
- 测真实 PDF 文件 → `application/pdf`
- 测扩展名为 `.pdf` 但内容是文本的文件 → `text/plain` (验证不信赖扩展名)
- 测扩展名为 `.txt` 但内容是 PDF → `application/pdf`
- 测图像 (PNG / JPEG / WebP) → 对应 MIME
- 测音视频 (MP3 / MP4) → 对应 MIME
- 测 EPUB → `application/epub+zip`
- 测不存在的文件 → FileNotFoundError

#### §1.1.2 detect_pdf_features

**接口**:
```python
from pathlib import Path
from dataclasses import dataclass

@dataclass
class PDFFeatures:
    page_count: int
    first_page_text: str          # 前 N 字符 (默认 1000)
    has_cjk: bool                  # CJK 字符占比 > 10%
    is_scanned: bool               # 文字层为空或极少 (< 50 chars per page)
    has_tables: bool               # 检测到表格 (简易启发式)
    is_two_column: bool            # 双栏布局检测

def detect_pdf_features(path: Path, sample_chars: int = 1000) -> PDFFeatures:
    """提取 PDF 启发式特征, 供 classifier 决定 medium 用

    Args:
        path: PDF 文件路径
        sample_chars: 首页采样字符数

    Returns:
        PDFFeatures dataclass

    Raises:
        FileNotFoundError
        PDFParseError: PDF 损坏或加密
    """
```

**实施要点**:
- 用 `pymupdf` (fitz)
- CJK 检测: Unicode 范围 U+4E00-U+9FFF + U+3000-U+303F + U+3040-U+30FF
- is_scanned: 前 3 页文字字符总数 < 150 视为扫描件
- has_tables: 看是否检测到 `page.find_tables()` 返回 > 0
- is_two_column: 分析首页文字块 x 坐标分布, 若聚集在左右两块视为双栏 (简易实现可)

**测试要求** (90%):
- 真实学术论文 PDF → has_cjk False / is_scanned False
- 真实中文 PDF → has_cjk True
- 扫描件 PDF (无文字层) → is_scanned True
- 双栏论文 → is_two_column True
- 单栏文档 → is_two_column False

#### §1.1.3 detect_image_exif

**接口**:
```python
from pathlib import Path
from dataclasses import dataclass

@dataclass
class ImageExif:
    has_exif: bool
    camera_make: str | None        # e.g. "Apple", "Canon"
    camera_model: str | None       # e.g. "iPhone 14 Pro"
    datetime_taken: str | None     # ISO 8601 if available
    width: int
    height: int
    is_screenshot_likely: bool     # 启发式判断

def detect_image_exif(path: Path) -> ImageExif:
    """提取图像 EXIF 信息

    Args:
        path: 图像文件路径

    Returns:
        ImageExif dataclass

    Raises:
        FileNotFoundError
        UnsupportedImageError: 不是图像或格式不支持
    """
```

**实施要点**:
- 用 `Pillow` (PIL)
- has_exif: EXIF 数据存在且非空
- camera_make / camera_model: EXIF tag 0x010F / 0x0110
- is_screenshot_likely: PNG 格式 + 无 EXIF + 尺寸跟常见屏幕分辨率匹配 (1920x1080 / 2560x1440 / 3024x1964 等)

**测试要求** (90%):
- iPhone 拍照 (含 EXIF) → has_exif True, camera_make "Apple"
- 截图 PNG (无 EXIF) → has_exif False, is_screenshot_likely True
- WebP 图像 → 正常处理 (Pillow 支持)
- 损坏图像 → UnsupportedImageError

#### §1.1.4 extract_text_sample

**接口**:
```python
from pathlib import Path

def extract_text_sample(path: Path, mime: str, max_chars: int = 2000) -> str:
    """从文件提取文本采样供启发式 / LLM 用

    Args:
        path: 文件路径
        mime: MIME 类型 (从 detect_mime 来, 避免重复检测)
        max_chars: 最大返回字符数

    Returns:
        采样文本, 可能截断
        如文件不含可提取文本 (二进制 / 已是文本但乱码), 返回空字符串

    Raises:
        FileNotFoundError
        UnsupportedFileTypeError: MIME 类型无文本采样实现
    """
```

**支持的 MIME**:
- `application/pdf` → pymupdf 提取首 N 页
- `text/plain` / `text/markdown` → 直接读 (chardet 检测编码)
- `text/html` → trafilatura 抽取主文
- `application/epub+zip` → ebooklib 抽取首章节
- 其他 → UnsupportedFileTypeError

**测试要求** (90%):
- 测各类 MIME 的采样
- 测乱码 / 编码混合 → chardet 处理
- 测空文件 → 空字符串
- 测超长文件 → 正确截断到 max_chars

---

### §1.2 oprim.parser

**包**: `oprim.parser`
**SPEC 依据**: 4O 清单 §2.2, 实证 #1 PDF 解析

#### §1.2.1 parse_pdf (provider 接口)

**接口**:
```python
from pathlib import Path
from dataclasses import dataclass, field
from typing import Protocol

@dataclass
class ParsedContent:
    markdown: str                          # 主输出, markdown 格式
    plaintext: str                         # 纯文本版
    page_count: int
    images: list[dict] = field(default_factory=list)  # [{page: 1, bytes: ..., caption: ...}]
    tables: list[dict] = field(default_factory=list)
    chapters: list[dict] = field(default_factory=list)  # [{title: ..., page: ...}]
    metadata: dict = field(default_factory=dict)        # 原始 metadata
    parser_name: str = ""                   # 用了哪个 provider
    parse_quality_score: float = 0.0        # 0-1, parser 自评质量

class PDFParser(Protocol):
    def parse(self, path: Path, hint: dict | None = None) -> ParsedContent: ...

def parse_pdf(
    path: Path,
    provider: str = "auto",
    hint: dict | None = None
) -> ParsedContent:
    """PDF 解析, 支持多 provider

    Args:
        path: PDF 路径
        provider: "auto" / "pymupdf4llm" / "marker" / "mineru"
                  "auto" 时按 hint 选 provider (见 dispatch 规则)
        hint: 可选 hint dict, 含 {"language": "zh"/"en", "is_scanned": bool, ...}

    Returns:
        ParsedContent

    Raises:
        FileNotFoundError
        PDFParseError: 所有 provider 都失败
    """
```

**dispatch 规则** (auto 时):
```python
def dispatch(path: Path, hint: dict | None) -> str:
    features = detect_pdf_features(path)
    if hint and hint.get("language") == "zh" and features.has_cjk:
        return "mineru"        # 中文用 MinerU
    elif features.is_scanned:
        return "marker"        # 扫描件用 Marker
    else:
        return "pymupdf4llm"   # 默认 90% 场景
```

#### §1.2.2 parse_pdf.pymupdf4llm

**实施要点**:
- 用 `pymupdf4llm.to_markdown(path)`
- 解析 images: `pymupdf4llm.to_markdown(path, write_images=True, image_path="...")`
- 解析 tables: pymupdf 的 `page.find_tables()`
- chapters: pymupdf 的 `doc.get_toc()` (若 TOC 存在)
- parse_quality_score: 简易启发式 (output 长度 / 期望长度比)

**测试要求** (90%):
- 测简单 PDF (Lorem ipsum) → markdown 输出
- 测含表格 PDF → tables 字段非空
- 测含图像 PDF → images 字段非空
- 测有 TOC 的 PDF → chapters 字段非空
- 测扫描件 PDF → 输出短但不报错 (跑通即可, 质量不强求)
- 测加密 PDF → PDFParseError

#### §1.2.3 parse_pdf.marker

**实施要点**:
- 用 `marker-pdf` 库 (`pip install marker-pdf`)
- `from marker.convert import convert_single_pdf`
- 支持 LLM boost (但 Phase 1 不接 LLM, 用纯启发式版)
- 注意: Marker 启动慢 (加载模型), 第一次调用 30s+, 后续快

**测试要求** (90%):
- 测扫描件 → markdown 输出 (OCR 已应用)
- 测复杂排版 → 跑通
- 跑通 = 不崩溃 + 有输出, 不强求质量精确比对

#### §1.2.4 parse_pdf.mineru

**实施要点**:
- 用 `magic-pdf` 库 (MinerU 的 pip 包名)
- CJK 优化路径
- 注意: MinerU 依赖 PaddleOCR, 安装较重 (~2GB), 配置 GPU 可选

**测试要求** (90%):
- 测中文论文 → markdown 输出, CJK 正确
- 测中文古籍扫描 → OCR 跑通

**降级**: 若 mineru 装机失败 (例如 PaddleOCR 依赖问题), 暂时 fallback 到 marker, **必须 obase.logging emit warning** "mineru unavailable, fallback to marker"。

#### §1.2.5 parse_epub

**接口**:
```python
def parse_epub(path: Path) -> ParsedContent:
    """EPUB 解析"""
```

**实施要点**:
- 用 `ebooklib`
- 章节 = EPUB 的 spine 顺序
- markdown 输出含章节标题 + 正文

**测试要求** (70%):
- 测简单 EPUB → markdown + chapters 字段
- 测加密 EPUB → 报错

#### §1.2.6 parse_html

**接口**:
```python
def parse_html(html_content: str | bytes, base_url: str | None = None) -> ParsedContent:
    """HTML 解析, 抽取主文内容"""
```

**实施要点**:
- 用 `trafilatura` (主文抽取最佳)
- fallback: `readability-lxml`
- 输出 markdown (用 `markdownify` 或 trafilatura 内置)

**测试要求** (70%):
- 测新闻文章 HTML → 主文抽取
- 测博客 HTML → 主文抽取
- 测纯导航页 → 输出可为空, 不报错

---

### §1.3 oprim.embedding

**包**: `oprim.embedding`
**SPEC 依据**: 4O 清单 §2.3, 实证 #3 embedding

#### §1.3.1 embed_text (provider 接口)

**接口**:
```python
from typing import Protocol, Sequence

class TextEmbedder(Protocol):
    def embed(self, texts: Sequence[str], dim: int = 1024) -> list[list[float]]: ...
    @property
    def model_name(self) -> str: ...
    @property
    def native_dim(self) -> int: ...

def embed_text(
    texts: Sequence[str],
    provider: str = "qwen3_dashscope",
    dim: int = 1024,
    batch_size: int = 32
) -> list[list[float]]:
    """文本 embedding

    Args:
        texts: 文本列表
        provider: "qwen3_dashscope" / "bge_m3" / "qwen3_local"
        dim: 输出维度 (Qwen3 支持 Matryoshka, 1024 是推荐默认)
        batch_size: 批大小

    Returns:
        list of embedding vectors

    Raises:
        EmbeddingError: provider 失败
        QuotaExceededError: API 配额超
    """
```

#### §1.3.2 embed_text.qwen3_dashscope (默认主推)

**实施要点**:
- 用 `dashscope` Python SDK 或 OpenAI-compatible endpoint
- API base: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- 模型: `text-embedding-v3` 或更新版 (查 Wiki 当前 DashScope 文档)
- 维度: 1024 默认 (支持 Matryoshka 降维)
- 通过 `obase.cost_tracker` 追踪成本
- API key 通过 `obase.config` 读 `DASHSCOPE_API_KEY`

**重要**:
- 必须支持 batching (DashScope 单次最多 10 个 texts, 内部分批)
- 失败重试: 3 次 + exponential backoff
- 通过 obase.logging emit cost event

**测试要求** (90%, 含 mock):
- mock DashScope API → 验证调用格式
- mock 失败场景 → 验证重试
- mock 配额超 → QuotaExceededError
- (可选, 需 API key) 真实调用 → 维度正确

#### §1.3.3 embed_text.bge_m3 (备选)

**实施要点**:
- 用 `sentence-transformers` 或 `FlagEmbedding`
- 模型: `BAAI/bge-m3`
- 本地 GPU 推荐, CPU 慢但可
- 维度: 1024 原生

**测试要求** (70%):
- 测装机 + 简单 embedding
- (本地跑通即可, 不要求 production performance)

---

### §1.4 oprim.vector_db

**包**: `oprim.vector_db`
**SPEC 依据**: 4O 清单 §2.5, 实证 #2 向量库

#### §1.4.1 vector_upsert (provider 接口)

**接口**:
```python
from pathlib import Path
from dataclasses import dataclass
from typing import Protocol

@dataclass
class VectorRecord:
    id: str                        # composite, e.g. "substrate_id#chunk_idx"
    embedding: list[float]
    metadata: dict                 # 任意 JSON-serializable

class VectorDB(Protocol):
    def upsert(self, records: list[VectorRecord]) -> None: ...
    def search(self, query_vec: list[float], top_k: int = 20, filter: dict | None = None) -> list[VectorRecord]: ...
    def delete(self, ids: list[str]) -> None: ...
    def count(self) -> int: ...

def open_vector_db(
    path: Path,
    table_name: str,
    dim: int,
    provider: str = "lancedb"
) -> VectorDB:
    """打开 vector_db (创建或加载现有)

    Args:
        path: 数据库目录
        table_name: 表名 (e.g. "vectors_text")
        dim: 向量维度
        provider: "lancedb" (默认)

    Returns:
        VectorDB instance

    Raises:
        VectorDBError
    """
```

#### §1.4.2 vector_upsert.lancedb (默认主推)

**实施要点**:
- 用 `lancedb` 库
- table schema:
```python
import pyarrow as pa
schema = pa.schema([
    pa.field("id", pa.string()),
    pa.field("embedding", pa.list_(pa.float32(), dim)),
    pa.field("metadata", pa.string()),    # JSON serialized
])
```
- upsert 用 `tbl.merge_insert(on="id").when_matched_update_all().when_not_matched_insert_all().execute(...)`
- search: `tbl.search(query_vec).limit(top_k).to_list()`
- filter: `tbl.search(query_vec).where("metadata LIKE '%xxx%'").limit(top_k)` (简易实现, 复杂 filter 可后续优化)

**测试要求** (90%):
- 测 upsert 100 条 → 验证 count
- 测 upsert 同 id (update 语义) → 验证不重复
- 测 search → 验证返回 top_k
- 测 filter search → 验证过滤生效
- 测 delete → 验证 count 减少
- 测持久化 → 重开 db 后数据仍在
- 性能 sanity check: 1000 条 upsert < 1 秒 (按实证 #2 应该 ~20ms)

---

### §1.5 oprim.fulltext

**包**: `oprim.fulltext`
**SPEC 依据**: 4O 清单 §2.6

#### §1.5.1 fulltext_index (provider 接口)

**接口**:
```python
from pathlib import Path
from dataclasses import dataclass
from typing import Protocol

@dataclass
class FulltextDoc:
    id: str
    fields: dict[str, str]         # {"title": "...", "content": "...", "tags": "..."}

@dataclass
class FulltextHit:
    id: str
    score: float
    highlight: str | None

class FulltextIndex(Protocol):
    def add(self, docs: list[FulltextDoc]) -> None: ...
    def search(self, query: str, top_k: int = 20, fields: list[str] | None = None) -> list[FulltextHit]: ...
    def delete(self, ids: list[str]) -> None: ...

def open_fulltext_index(
    path: Path,
    provider: str = "tantivy"
) -> FulltextIndex:
    """打开全文索引"""
```

#### §1.5.2 fulltext_index.tantivy

**实施要点**:
- 用 `tantivy-py` (Rust Tantivy 的 Python binding)
- schema:
```python
import tantivy
schema_builder = tantivy.SchemaBuilder()
schema_builder.add_text_field("id", stored=True, tokenizer_name="raw")
schema_builder.add_text_field("title", stored=True, tokenizer_name="default")
schema_builder.add_text_field("content", stored=True, tokenizer_name="default")
schema_builder.add_text_field("tags", stored=True, tokenizer_name="default")
schema = schema_builder.build()
```
- 中文分词: tantivy-py 1.0+ 支持 jieba tokenizer (若可用), 否则 default tokenizer (按空格 + 标点切)
- BM25 是 tantivy 默认评分

**测试要求** (90%):
- 测 add 100 docs → 验证可搜
- 测中文搜索 → 验证 jieba 切词正确 (若用 default tokenizer 接受降级)
- 测多字段搜索 → 验证 fields 限制生效
- 测 delete → 验证不再搜到
- 测持久化 → 重开后搜得到

---

### §1.6 oprim.meta_db

**包**: `oprim.meta_db`
**SPEC 依据**: 4O 清单 §2.7

#### §1.6.1 meta_db.duckdb (用户本地)

**接口**:
```python
from pathlib import Path
import duckdb

class MetaDB:
    def __init__(self, path: Path): ...
    def connect(self) -> duckdb.DuckDBPyConnection: ...
    def execute(self, sql: str, params: list | None = None): ...
    def fetchall(self, sql: str, params: list | None = None) -> list[tuple]: ...
    def migrate(self, migrations_dir: Path) -> None: ...
    def close(self) -> None: ...

def open_meta_db(path: Path) -> MetaDB:
    """打开本地 DuckDB"""
```

**初始 schema (按 STRATUM_SPEC §8.4 用户索引 schema)**:

提供 SQL 文件 `migrations/001_initial.sql`:
```sql
CREATE TABLE IF NOT EXISTS substrate (
    id TEXT PRIMARY KEY,
    medium TEXT NOT NULL,
    title TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP,
    source_type TEXT,
    source_meta JSON,
    storage_adapter TEXT,
    storage_path TEXT,
    storage_ref JSON,
    file_hash TEXT,
    file_size BIGINT,
    mime_type TEXT,
    language TEXT
);

CREATE INDEX IF NOT EXISTS idx_substrate_medium ON substrate(medium);
CREATE INDEX IF NOT EXISTS idx_substrate_hash ON substrate(file_hash);
CREATE INDEX IF NOT EXISTS idx_substrate_created ON substrate(created_at);

CREATE TABLE IF NOT EXISTS derivative (
    id TEXT PRIMARY KEY,
    substrate_id TEXT NOT NULL,
    type TEXT NOT NULL,
    storage_path TEXT,
    content_hash TEXT,
    generated_at TIMESTAMP,
    generator_version TEXT,
    FOREIGN KEY (substrate_id) REFERENCES substrate(id)
);

CREATE INDEX IF NOT EXISTS idx_derivative_substrate ON derivative(substrate_id);
CREATE INDEX IF NOT EXISTS idx_derivative_type ON derivative(type);

CREATE TABLE IF NOT EXISTS concept (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    label TEXT NOT NULL,
    label_aliases JSON,
    description TEXT,
    related_substrate_ids JSON
);

CREATE INDEX IF NOT EXISTS idx_concept_type ON concept(type);
CREATE INDEX IF NOT EXISTS idx_concept_label ON concept(label);

CREATE TABLE IF NOT EXISTS note (
    id TEXT PRIMARY KEY,
    title TEXT,
    content_markdown TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    substrate_refs JSON,
    concept_refs JSON
);

CREATE INDEX IF NOT EXISTS idx_note_created ON note(created_at);

CREATE TABLE IF NOT EXISTS changefeed_local (
    seq BIGINT PRIMARY KEY,
    event_type TEXT,
    payload JSON,
    created_at TIMESTAMP,
    synced_at TIMESTAMP
);

CREATE SEQUENCE IF NOT EXISTS changefeed_seq START 1;
```

**测试要求** (70%):
- 测 open / close
- 测 migrate (初始 schema)
- 测 CRUD 各表
- 测事务

---

### §1.7 oprim.llm (复用 obase 或扩充)

**注意**: 若 obase 已有 `obase.llm.llm_call`, 跳过本节, 标记"复用 obase"。
否则:

#### §1.7.1 llm_call

**接口** (与 obase pattern 一致):
```python
from dataclasses import dataclass
from typing import Iterator

@dataclass
class LLMResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float

def llm_call(
    prompt: str,
    provider: str = "qwen3_dashscope",
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    system: str | None = None
) -> LLMResponse:
    """LLM 调用"""
```

**支持的 provider**:
- `qwen3_dashscope` (默认) — Wiki 已接入
- `claude` — 复杂任务

**实施要点**:
- 用 `obase.cost_tracker` 追踪成本
- 用 `obase.errors.LLMError` / `LLMRateLimitError`
- 失败重试 3 次

**测试要求** (70%, mock):
- mock 调用 → 验证格式
- mock 失败 → 验证重试
- 真实调用 (可选) → 验证 cost track

---

### §1.8 oprim.mcp

**包**: `oprim.mcp`
**SPEC 依据**: 4O 清单 §2.10, 实证 #4 MCP 框架

#### §1.8.1 mcp_server

**接口**:
```python
from mcp.server.fastmcp import FastMCP

def create_mcp_server(name: str, version: str) -> FastMCP:
    """创建 MCP server 实例 (官方内置高阶 API)

    Returns:
        FastMCP instance, 可后续注册 tools
    """
    return FastMCP(name, version=version)
```

**实施要点**:
- 用 `mcp.server.fastmcp.FastMCP` (按实证 #4 结论)
- **不用** `fastmcp` 社区包 (不同包)
- **不用** `mcp.server.Server` 底层 API (太底层)

#### §1.8.2 mcp_tool_register (helper)

```python
from mcp.server.fastmcp import FastMCP

def register_tool(server: FastMCP, name: str, fn, description: str | None = None):
    """注册 tool 到 server"""
    decorator = server.tool(name=name, description=description)
    decorator(fn)
```

**测试要求** (70%):
- 测创建 server
- 测注册 tool
- 测 tool 列表

---

### §1.9 oprim 层验收清单 (验收门 A)

CC 完成 §1.1-§1.8 后, 报告:

- [ ] 所有 oprim 元素已实施 (按上述 §1.1-§1.8)
- [ ] 测试覆盖率达标:
  - classifier / parser / embedding / vector_db ≥ 90%
  - fulltext / meta_db / llm / mcp ≥ 70%
- [ ] 所有元素使用 obase.config / logging / errors / cost_tracker
- [ ] 没实施任何 4O 清单 §5 删除项
- [ ] 没实施 Phase 2+ 元素 (storage / wechat / changefeed 等)
- [ ] Provider 模式正确 (抽象 + 具体 + dispatch)
- [ ] GitHub repo `oprim` 已 push, tag `v0.1.0`
- [ ] README 含安装 + 用法示例
- [ ] PyPI (或私有 index) 已发布

报告格式:

```markdown
# oprim Phase 1 完工报告

## 实施总结
- 实施模块数: X
- 总代码行数 (含 test): Y
- 测试覆盖率明细: ...

## 关键决策 (CC 自主决定的部分)
- ...

## 偏离 SPEC 的地方 (含理由)
- ...

## 已知问题 / 限制
- ...

## 安装验证步骤
- ...
```

Wiki 转 advisor review → sign-off → 进入 §2 oskill 层。

---

## §2 oskill 层 (验收门 B)

**前置**: §1 oprim 层验收 sign-off

按 4O 清单 v0.2 §3 Phase 1 必备 oskill。

### §2.1 oskill.knowledge.classify_inbox_file

**包**: `oskill.knowledge.classify_inbox_file`
**SPEC 依据**: 4O 清单 §3.1, STRATUM_SPEC §11.2

**接口**:
```python
from pathlib import Path
from dataclasses import dataclass
from typing import Literal

@dataclass
class ClassifyResult:
    medium: str | None              # 18 medium 之一, None 表示无法定
    confidence: float               # 0.0 - 1.0
    layer: Literal["extension", "heuristic", "llm", "needs_review"]
    reason: str
    candidates: list[tuple[str, float]]  # ranked

def classify_inbox_file(
    path: Path,
    use_llm: bool = False           # Phase 1 不启用 LLM 兜底
) -> ClassifyResult:
    """三层分类器"""
```

**实施要点** (按 inbox 设计 + STRATUM_SPEC §11.2):

**Layer 1 (扩展名 + MIME + 文件名前缀)**:
- 调 `oprim.classifier.detect_mime`
- 检查文件名前缀 hint (e.g. `podcast--xxx.mp3` → podcast 99% 置信)
- 按 mime 决定 candidates:
  - `audio/*` → [podcast, lecture, audiobook, music]
  - `video/*` → [video_lecture, interview, documentary]
  - `image/*` → [photograph, diagram, artwork]
  - `application/pdf` → [paper, book, diagram, webpage]
  - `application/epub+zip` → book (0.95)
  - `text/markdown` → markdown_note (0.9)
  - `text/html` → webpage (0.85)
  - `text/csv` / `application/json` → dataset (0.9)
  - `text/x-python` / 其他代码 → code (0.95)

**Layer 2 (启发式)**:
- PDF: 调 `oprim.classifier.detect_pdf_features` → 用 features 判断 paper / book / diagram
- 图像: 调 `oprim.classifier.detect_image_exif` → 有 EXIF camera_make → photograph
- audio: 时长 < 30 min → podcast / lecture, > 60 min → audiobook (用 `oprim.classifier.detect_audio_metadata`, 但该 oprim 是 P1, Phase 1 可不实施 audio 启发式)

**Layer 3 (LLM 兜底)**:
- Phase 1 不实施 (use_llm=False 时跳过)
- Phase 10 加上 (此处留接口, 但不调用)

**判定逻辑**:
```python
def classify_inbox_file(path, use_llm=False):
    layer1 = classify_by_extension(path)
    if layer1.confidence >= 0.85:
        return layer1
    
    layer2 = classify_by_heuristic(path, layer1)
    if layer2.confidence >= 0.65:
        return layer2
    
    if use_llm:
        return classify_by_llm(path, layer2.candidates)
    
    # Phase 1 fallback: 返回中等置信度 + needs_review
    return ClassifyResult(
        medium=None,
        confidence=layer2.confidence,
        layer="needs_review",
        reason=f"low confidence, need LLM or user confirmation (best: {layer2.candidates[0] if layer2.candidates else None})",
        candidates=layer2.candidates,
    )
```

**测试要求** (90%):
- 准备 fixture 文件 (跟之前 inbox 设计的 12 fixtures 类似)
- 测每个 medium 至少 1 case
- 测扩展名 hint 命中
- 测启发式 fallback
- 测 low confidence → needs_review

### §2.2 oskill.knowledge.ingest_substrate

**SPEC 依据**: 4O 清单 §3.2, STRATUM_SPEC §11.2

**接口**:
```python
from pathlib import Path
from dataclasses import dataclass

@dataclass
class IngestResult:
    substrate_id: str
    medium: str
    derivatives: list[str]          # 生成的 derivative type 列表
    duplicate_of: str | None        # 若是重复, 返回原 ULID
    elapsed_seconds: float
    cost_usd: float

async def ingest_substrate(
    path: Path,
    source: dict,                   # {"type": "inbox_local", "device_id": "..."}
    target_storage: str = "local",  # Phase 1 只支持 local
    user_hint: dict | None = None
) -> IngestResult:
    """端到端入库流水线"""
```

**实施流程** (按 STRATUM_SPEC §11.2):

```python
async def ingest_substrate(path, source, target_storage="local", user_hint=None):
    # Step 1: 计算 file_hash (sha256)
    file_hash = await compute_sha256(path)
    
    # Step 2: 查重
    existing = await detect_duplicate_substrate(file_hash, embedding=None)
    if existing:
        return IngestResult(substrate_id=existing, duplicate_of=existing, ...)
    
    # Step 3: 分类
    classify_result = classify_inbox_file(path, use_llm=False)
    
    # Step 4: 分配 ULID
    substrate_id = generate_ulid()  # 用 ulid-py
    
    # Step 5: 存到 target_storage (Phase 1 只支持 local)
    #   - 移到 ~/.stratum/data/substrate/{medium}/{ulid}--{slug}.{ext}
    
    # Step 6: 生成 derivatives (按 medium 选适用类型)
    derivatives = await generate_derivative(substrate_id, path, medium)
    
    # Step 7: 计算 embedding
    chunks = await chunk_text(derivatives.markdown or "")
    embeddings = oprim.embedding.embed_text([c.text for c in chunks])
    
    # Step 8: 写入索引
    #   - meta.duckdb: substrate + derivative
    #   - tantivy: fulltext
    #   - lance: vectors-text
    
    # Step 9: emit changefeed event (写本地 outbox, 不上传)
    
    return IngestResult(substrate_id=substrate_id, medium=medium, ...)
```

**Phase 1 简化**:
- target_storage 只支持 "local" (Phase 2 加 onedrive / aliyundrive)
- 不上传到我们服务器 (Phase 2 加 changefeed)
- changefeed event 写本地 outbox 表 (changefeed_local), 不 flush

**测试要求** (90%):
- 测各类 medium 入库
- 测重复检测
- 测端到端 (input file → 索引可搜)

### §2.3 oskill.knowledge.detect_duplicate_substrate

**接口**:
```python
async def detect_duplicate_substrate(
    file_hash: str,
    embedding: list[float] | None = None,
    similarity_threshold: float = 0.95
) -> str | None:
    """去重检测

    Returns:
        existing substrate_id 若是重复, 否则 None
    """
```

**实施**:
- 优先 sha256 完全匹配 → 直接返回
- 次选 embedding 相似度 > threshold → 返回 (Phase 1 简化: 仅 sha256, 不查 embedding)

**测试要求** (80%):
- 测 sha256 命中
- 测无命中

### §2.4 oskill.knowledge.generate_derivative

**接口**:
```python
async def generate_derivative(
    substrate_id: str,
    path: Path,
    medium: str
) -> dict[str, str]:
    """生成衍生物

    Returns:
        {"markdown": "...", "plaintext": "...", "summary": "...", ...}
    """
```

**实施 (Phase 1 范围)**:

按 medium 调用不同 parser:
- `paper` / `book` / `webpage` (PDF) → `oprim.parser.parse_pdf` → markdown + plaintext + chapters
- `markdown_note` → 直接读 → markdown + plaintext
- `webpage` (HTML) → `oprim.parser.parse_html` → markdown + plaintext
- `book` (EPUB) → `oprim.parser.parse_epub` → markdown + chapters
- 其他 medium → 暂跳过 (Phase 10 加 audio / video transcript)

derivative types (Phase 1):
- `markdown`
- `plaintext`
- `chapters` (PDF/EPUB)
- `thumbnail` (PDF 首页, image)

**不在 Phase 1**:
- summary (Phase 10)
- key_quotes (Phase 10)
- entities (Phase 10)
- transcript (Phase 11)

**测试要求** (80%):
- 测 PDF → markdown + plaintext
- 测 HTML → markdown
- 测 EPUB → markdown + chapters

### §2.5 oskill.knowledge.hybrid_search (本地版)

**接口**:
```python
from dataclasses import dataclass

@dataclass
class SearchResult:
    type: str                       # "substrate" / "concept" / "note"
    id: str
    title: str
    score: float
    highlight: str | None
    metadata: dict

async def hybrid_search(
    query: str,
    top_k: int = 20,
    medium_filter: list[str] | None = None,
    type_filter: list[str] | None = None  # ["substrate", "concept", "note"]
) -> list[SearchResult]:
    """本地混合检索 (Phase 1 仅查用户本地, 不查平台)"""
```

**实施**:
1. 调 `oprim.fulltext.search` 拿 BM25 结果
2. 调 `oprim.embedding.embed_text([query])` 拿 query vector
3. 调 `oprim.vector_db.search` 拿向量结果
4. RRF 融合 (复用 `oprim.search.rrf_fuse`, 若没有则 inline 实现)
5. 按 medium / type filter
6. 返回 top_k

**RRF 实现** (若 oprim.search.rrf_fuse 不在 Phase 1 范围, inline):
```python
def rrf_fuse(*result_lists, k=60):
    scores = {}
    for results in result_lists:
        for rank, item in enumerate(results):
            scores[item.id] = scores.get(item.id, 0) + 1.0 / (k + rank + 1)
    return sorted(items, key=lambda x: scores[x.id], reverse=True)
```

**测试要求** (80%):
- 测纯 BM25 命中
- 测纯 vector 命中
- 测混合命中
- 测 filter 生效

### §2.6 oskill.knowledge.lint

**接口**:
```python
from dataclasses import dataclass

@dataclass
class LintIssue:
    severity: str                   # "error" / "warning"
    rule: str                       # "schema_consistency" / "reference_integrity" / ...
    target_id: str
    message: str

async def lint(scope: str = "all") -> list[LintIssue]:
    """检查仓库一致性

    Args:
        scope: "all" / "substrate" / "concept" / "note"

    Returns:
        issue list (空表示 clean)
    """
```

**实施 (Phase 1 必含规则)**:

按 STRATUM_SPEC §9 lint 规则:
- substrate 必有 medium (18 之一)
- derivative 必 reference 存在的 substrate
- concept.related_substrate_ids 引用必须存在
- note.substrate_refs / concept_refs 引用必须存在
- ULID 格式正确 (26 字符 Crockford base32)
- 文件名 (网盘内) 符合 `{ulid}--{slug}.{ext}` 格式

**测试要求** (80%):
- 测各规则各 1 case
- 测 clean 仓库 → 0 issue
- 测有问题仓库 → 报对应 issue

### §2.7 oskill 层验收清单 (验收门 B)

CC 完成 §2.1-§2.6 后, 报告:

- [ ] 所有 oskill 元素已实施
- [ ] 测试覆盖率达标 (≥ 80%)
- [ ] 使用 oprim (不绕过)
- [ ] 使用 obase.* (config / logging / errors / cost_tracker)
- [ ] 没扩大范围 (LLM 兜底分类器 / summary derivative / etc. 都不在 Phase 1)
- [ ] 端到端测试: file → ingest_substrate → hybrid_search 可搜到
- [ ] GitHub repo `oskill` push, tag `v0.1.0`

报告格式同 §1.9。

---

## §3 omodul 层 (Phase 1 完成)

**前置**: §2 oskill 层验收 sign-off

按 4O 清单 v0.2 §4 Phase 1 必备 omodul.

### §3.1 omodul.knowledge.process_inbox

**包**: `omodul.knowledge.process_inbox`
**SPEC 依据**: 4O 清单 §4.1, STRATUM_SPEC §11.2

**接口**:
```python
from pathlib import Path
from dataclasses import dataclass

@dataclass
class ProcessInboxResult:
    processed: list[IngestResult]
    failed: list[dict]              # {"path": ..., "error": ...}
    needs_review: list[dict]        # 分类器低置信度

async def process_inbox(
    inbox_dir: Path,
    archive_after_process: bool = True
) -> ProcessInboxResult:
    """处理 inbox 目录中的所有文件

    Args:
        inbox_dir: 监听的目录 (例如 ~/.stratum/inbox/)
        archive_after_process: 处理后移到 archive/

    Returns:
        ProcessInboxResult
    """
```

**实施**:
```python
async def process_inbox(inbox_dir, archive_after_process=True):
    processed = []
    failed = []
    needs_review = []
    
    for file_path in sorted(inbox_dir.glob("*")):
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        try:
            result = await oskill.knowledge.ingest_substrate(
                path=file_path,
                source={"type": "inbox_local", "filename": file_path.name},
                target_storage="local"
            )
            if result.classify_result.layer == "needs_review":
                needs_review.append({"path": str(file_path), "candidates": result.classify_result.candidates})
            else:
                processed.append(result)
            
            if archive_after_process:
                archive_dir = inbox_dir / "_archive"
                archive_dir.mkdir(exist_ok=True)
                file_path.rename(archive_dir / file_path.name)
        except Exception as e:
            logging.error(f"process_inbox failed for {file_path}: {e}")
            failed.append({"path": str(file_path), "error": str(e)})
    
    return ProcessInboxResult(processed=processed, failed=failed, needs_review=needs_review)
```

**测试要求** (80%):
- 测端到端 inbox 处理
- 测含失败文件 → 不阻塞其他
- 测 archive 移动
- 测 needs_review 标记

### §3.2 omodul.knowledge.start_mcp_server

**包**: `omodul.knowledge.start_mcp_server`
**SPEC 依据**: 4O 清单 §4.2, STRATUM_SPEC §10.7

**接口**:
```python
def start_mcp_server(host: str = "0.0.0.0", port: int = 8765):
    """启动 Stratum MCP server, 暴露检索 tools 供外部 LLM / agent 调用"""
```

**实施**:
```python
from oprim.mcp import create_mcp_server, register_tool
from oskill.knowledge import hybrid_search

def start_mcp_server(host="0.0.0.0", port=8765):
    server = create_mcp_server("stratum", version="0.1.0")
    
    register_tool(server, "stratum.search", search_handler,
                  description="Hybrid search across substrate / concept / note")
    register_tool(server, "stratum.fetch_substrate", fetch_substrate_handler, ...)
    register_tool(server, "stratum.list_notes", list_notes_handler, ...)
    register_tool(server, "stratum.recent_changes", recent_changes_handler, ...)
    
    # Phase 1 不暴露:
    # - stratum.fetch_content (平台内容, Phase 3+)
    # - stratum.fetch_concept (Phase 10)
    # - stratum.fetch_graph (Phase 6)
    
    server.run(host=host, port=port)
```

**Phase 1 暴露 4 个 tool**:
- `stratum.search` — 调 `oskill.knowledge.hybrid_search`
- `stratum.fetch_substrate` — 直接查 DuckDB
- `stratum.list_notes` — 查 note 表
- `stratum.recent_changes` — 查 changefeed_local

**测试要求** (80%):
- 测 server 启动
- 测各 tool 可调用
- 测 search tool 返回正确格式

### §3.3 omodul 层验收清单 (Phase 1 完成)

CC 完成 §3.1-§3.2 后, 报告:

- [ ] 所有 omodul 元素已实施
- [ ] 测试覆盖率达标 (≥ 80%)
- [ ] 使用 oskill (不绕过)
- [ ] end-to-end demo 可跑: 把文件丢进 inbox/ → 自动入库 → MCP search 能搜到
- [ ] GitHub repo `omodul` push, tag `v0.1.0`
- [ ] Phase 1 完成报告 (含整体功能展示)

---

## §4 全局验收 (Phase 1 整体)

CC 完成 §1+§2+§3 后, Phase 1 整体验收:

### 4.1 功能 demo (CC 必须验证)

完整端到端流程:

```bash
# 1. 安装
pip install obase oprim oskill omodul

# 2. 初始化
stratum init  # 创建 ~/.stratum/ 目录结构 + meta.duckdb 初始化

# 3. 配置 (~/.stratum/config.yaml)
# DASHSCOPE_API_KEY=sk-...
# storage:
#   type: local
#   path: ~/.stratum/data

# 4. 入库 (放文件到 inbox)
cp some.pdf ~/.stratum/inbox/
cp note.md ~/.stratum/inbox/

# 5. 处理 inbox
python -m omodul.knowledge.process_inbox

# 6. 搜索
python -m oskill.knowledge.hybrid_search "凯利公式"

# 7. 启动 MCP server (供 Claude Desktop 等接入)
python -m omodul.knowledge.start_mcp_server

# 8. lint
python -m oskill.knowledge.lint
```

### 4.2 验收标准

- [ ] 三层 (oprim / oskill / omodul) 都已 sign-off
- [ ] 上述 demo 全部跑通
- [ ] 不依赖 Phase 2+ 元素
- [ ] 三个 GitHub repo 都有 README + 安装说明 + 示例
- [ ] 测试覆盖率分别达标
- [ ] obase 集成正确 (config / logging / errors / cost_tracker 都用上)

---

## §5 实施时间估算

| 阶段 | 工作量 | 估算 |
|---|---|---|
| §1 oprim (8 个子包) | 中等 | 7-10 天 CC FULL AUTO |
| §2 oskill (6 个 skill) | 较小 (复用 oprim) | 4-5 天 |
| §3 omodul (2 个 modul) | 小 | 2 天 |
| **小计** | | **13-17 天** |

**Wiki 验收时间** (每层):
- oprim 层: 1-2 天 (review + 试跑)
- oskill 层: 1 天
- omodul 层: 1 天

**Phase 1 完整周期**: ~3-4 周

---

## §6 已知风险 + 缓解

### 风险 1: MinerU 安装重 (~2 GB + PaddleOCR)

**缓解**: §1.2.4 已写 fallback 到 Marker, 必须 emit warning。

### 风险 2: DashScope API key 未配置

**缓解**: 测试用 mock, 真实调用要求 Wiki 提供 key。文档明确说明。

### 风险 3: tantivy-py 中文分词支持

**缓解**: 若 jieba tokenizer 不可用, 用 default tokenizer 跑通 (中文搜索质量降级, Phase 1 可接受)。

### 风险 4: CC 自主决策导致偏离

**缓解**:
- 每层验收门强制 review
- CC 报告必须含 "关键决策" 部分
- 偏离 SPEC 必须报告

---

## §7 不在 Phase 1 范围 (明确不做)

按 R-4 禁止扩大范围, **不做**:

- oprim.storage.* (Phase 2)
- oprim.changefeed.* (Phase 2)
- oprim.fulltext.postgresql (Phase 3, 平台索引)
- oprim.meta_db.postgresql (Phase 3)
- oprim.vector_db.pgvector (Phase 3)
- oprim.wechat.* (Phase 4-7)
- oprim.tts.* (Phase 8)
- oprim.push.* (Phase 11+)
- oskill.knowledge.classify_by_llm (Layer 3, Phase 10)
- oskill.knowledge.extract_concepts (Phase 10)
- oskill.platform.* (Phase 3+)
- oskill.payment.* (Phase 5)
- oskill.sync.* (Phase 2)
- omodul.platform.* (Phase 3+)
- omodul.sync.bg_sync (Phase 2)
- omodul.wechat.* (Phase 4-7)
- 所有 4O 清单 §5 删除项

---

**End of Phase 1 4O 实施指令书 v0.1**
