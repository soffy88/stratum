# PHASE_10_TRANSLATION_IMPLEMENTATION_INSTRUCTIONS_v0.1.md

**任务**: 实施 Stratum Phase 10 Translation 能力
**执行者**: CC-B (跟 CC-A Phase 2 并行)
**执行模式**: Claude Code FULL AUTO
**SPEC 依据**:
- STRATUM_SPEC v0.5 + v0.6 PATCH (§3.3 derivative.translation)
- 4O 扩充清单 v0.3 PATCH §D (Phase 10)
- ADR-018 (Translation 核心能力)
- 翻译选型实证报告 (DeepSeek 主 / Claude 次 / Qwen3 备)

**起步范围** (Wiki 拍板):
- ✅ DeepSeek V3.2 (默认主 provider)
- ✅ Claude Opus 4.7 / Sonnet 4.6 (高质量场景)
- ✅ Qwen3-Max (国内合规备选)
- ⏸ Gemini 3 Pro (Phase 11, 不在 Phase 10)

**预期产物**:
- platform/oprim 新增 sub-package: `translate` (含 4 模块: provider / chunker / checkpoint / format)
- platform/oprim version bump: v2.2.0 → v2.3.0
- platform/oskill 新增 sub-package: `knowledge.translate_substrate`
- platform/oskill version bump: v2.3.0 → v2.4.0
- derivative.translation type 已实施 (通过既有 generate_derivative skill)
- 端到端 demo: 一段英文 substrate → 中文 translation derivative
- 单元测试 + 集成测试 全部通过

**前置**:
- ✅ Phase 1 完工 (v2.2.0 / v2.3.0 / v1.2.0 已 tag)
- ✅ DeepSeek API key (Wiki 已申请)
- ✅ Anthropic API key (Wiki 已有)
- ✅ DashScope key (Wiki 已有)

**并行协调** (跟 CC-A Phase 2 共仓库):
- 同 branch (main), 不分叉
- 模块隔离: CC-B 只动 `oprim/translate/` + `oskill/knowledge/translate_substrate.py`, **绝不动** `oprim/storage/` / `oprim/changefeed/` / `oprim/push/` / `oskill/sync/`
- pyproject.toml 修改需小心 (deps 加新行不删既有, version bump 走 sub-package private version)
- 每完成一个 Wave 立即 commit + push
- CC-A 跟 CC-B 用各自的 PR, 不互相 review (Wiki 集中验收)

---

## §0 FULL AUTO 头部规则 (必读)

### 0.1 红线 (绝对不允许)

**R-1: 失败不静默**

任何场景下禁止:
- `except Exception: return <default>` 不 emit 日志
- provider 失败时返回占位翻译 (假数据 / 原文返回 / None 当成功)
- LLM 输出为空时静默跳过
- 字数对不上时 "假装" 成功
- chunking 失败时合并成单 chunk 强翻 (会爆 context)

降级必须满足三条件 (跟 Phase 1 同标准):
1. 调用方显式参数控制
2. obase.logging emit 显式 error/warning
3. 调用方可区分成功 vs 降级成功

**R-2: SPEC 是真理源**

冲突时**停止报告**, 不要自行解决。具体禁止:

- 不按翻译选型实证选 DeepSeek 作主 provider (例: 改默认到 Claude)
- 不按 ADR-018 实施 chunking (例: 用普通 RAG chunker)
- 不按 4O v0.3 §D.1 接口契约 (例: TranslationProvider 缺失字段)
- 不按 SPEC v0.6 PATCH §3.3 type=translation (例: 改成 type=translated_text)
- 不集成 hydropix 代码 (AGPL, 借鉴 ≠ 集成)

**R-4: 禁止扩大范围**

Phase 10 范围严格如下, 任何超出立即停止:

✅ 允许:
- DeepSeek / Claude / Qwen3 三个 provider
- 翻译 chunking (markdown / plaintext / epub)
- 断点续传 (checkpoint)
- 术语字典 (跨 chunk 一致)
- Router 路由
- translate_substrate skill 端到端
- derivative.translation 类型 (通过既有 generate_derivative 调用)

❌ 禁止 (留给后续 Phase):
- Gemini provider (Phase 11)
- TTS audio_narration (Phase 11)
- Agent / Scheduled Job (Phase 11)
- substrate.is_pinned (Phase 1.5 干, 不归你)
- hybrid_search mode 参数 (Phase 1.5)
- 网盘同步 (Phase 2, CC-A 干)
- 浏览器扩展 (Phase 4)
- back-translation 质量自检 (Phase 11+ Agent)
- 中英对照 UI (前端事, 不归 CC)
- 翻译 derivative 的 embedding (Wiki Q3 待拍, 默认实施)

如发现超范围, **立即停止报告**, 不要"顺手做了"。

**R-5: namespace 隔离**

绝不动 (CC-A 负责):
- `oprim/storage/` (CC-A 扩展 gdrive)
- `oprim/changefeed/`
- `oprim/push/`
- `oskill/sync/`
- `omodul/sync/`

只动:
- `oprim/translate/` (新建整个目录)
- `oskill/knowledge/translate_substrate.py` (新建文件)
- `oprim/pyproject.toml` (加 deps, 改 version)
- `oskill/pyproject.toml` (加 deps, 改 version)

如发现需要改隔离区文件 (e.g. errors / logging 添加新异常类), 先 commit & push 当前进度, 然后**停止报告**让 Wiki 协调跨 CC 修改。

### 0.2 工作流程

```
Wave 0: 准入检查 + 环境验证
  ↓
Wave 1: oprim.translate 基础设施 (protocol + chunker + checkpoint + router)
  ↓ verify
Wave 2: 3 provider 实施 (deepseek 优先 → claude → qwen3)
  ↓ verify
Wave 3: format 保留 (markdown / plaintext / epub)
  ↓ verify
Wave 4: oskill.knowledge.translate_substrate 端到端
  ↓ verify
Wave 5: 测试 + 端到端 demo + Gate 验收
  ↓
报告完工
```

每个 Wave 完成立即 commit, 内部 self-verify 通过才进下一 Wave。Gate 验收 Wiki sign-off。

### 0.3 输出要求

- 每个 Wave 完成报告: 完工内容 + 测试结果 + commit hash
- 测试覆盖率 ≥ 80%
- 不要"打太极", 失败就报告失败
- 不要在 Wave 中间问 Wiki 问题, 攒到 Wave 末尾或停止报告

---

## §1 Wave 0 — 准入检查

### 1.1 环境验证

```bash
cd ~/projects/platform/oprim
git status   # 应该是 clean 或只有 CC-A 的 storage/changefeed 进行中
git pull
git log --oneline -5

cd ~/projects/platform/oskill
git status
git pull
git log --oneline -5
```

### 1.2 验证 Phase 1 状态

```bash
cd ~/projects/platform/oprim
python -c "import oprim; print(oprim.__version__)"   # 期待 2.2.0
python -c "from oprim import classifier, parser, embedding, vector_db, fulltext, meta_db, llm, mcp; print('OK')"

cd ~/projects/platform/oskill
python -c "import oskill; print(oskill.__version__)"   # 期待 2.3.0
python -c "from oskill.knowledge import (
    classify_inbox_file, detect_duplicate_substrate, generate_derivative,
    hybrid_search, ingest_substrate, lint
); print('OK')"

cd ~/projects/platform/omodul
python -c "import omodul; print(omodul.__version__)"   # 期待 1.2.0
```

如任一验证失败, **停止报告**: Phase 1 状态异常, 不能进 Phase 10。

### 1.3 API key 验证

```bash
# DeepSeek
python <<'EOF'
import os
from openai import OpenAI
client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
r = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role":"user","content":"hi"}],
    max_tokens=10,
)
print("DeepSeek OK:", r.choices[0].message.content)
EOF

# Anthropic
python <<'EOF'
import os
from anthropic import Anthropic
c = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
r = c.messages.create(model="claude-sonnet-4-5", max_tokens=10, messages=[{"role":"user","content":"hi"}])
print("Anthropic OK:", r.content[0].text)
EOF

# DashScope
python <<'EOF'
import os, dashscope
dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
r = dashscope.Generation.call(model="qwen-max", messages=[{"role":"user","content":"hi"}], max_tokens=10)
print("DashScope OK:", r.output.text if hasattr(r.output, "text") else r.output.choices[0].message.content)
EOF
```

任一 key 失败, **立即停止报告**。

### 1.4 Wave 0 完成报告

```
=== Wave 0 完成 ===
- Phase 1 baseline OK (oprim 2.2.0 / oskill 2.3.0 / omodul 1.2.0)
- DeepSeek API key OK
- Anthropic API key OK
- DashScope API key OK
- CC-A 当前 branch 状态: <pull 后 log>
- 进入 Wave 1
```

---

## §2 Wave 1 — oprim.translate 基础设施

### 2.1 目录结构

```
platform/oprim/oprim/translate/
├── __init__.py
├── protocol.py          # TranslationProvider Protocol + dataclass
├── router.py            # TranslationRouter
├── chunker.py           # TranslationChunker
├── checkpoint.py        # TranslationCheckpoint
├── terminology.py       # 跨 chunk 术语字典
├── errors.py            # Translation 专用异常
└── _prompts.py          # 共享 prompt 模板
```

### 2.2 protocol.py 实施

```python
# oprim/translate/protocol.py
from typing import Protocol, Literal, AsyncIterator
from dataclasses import dataclass, field

@dataclass
class TranslationContext:
    """跨 chunk 上下文"""
    previous_chunks_summary: str | None = None
    next_chunk_preview: str | None = None     # 前 100 字
    document_metadata: dict = field(default_factory=dict)
    established_proper_nouns: dict[str, str] = field(default_factory=dict)
    chunk_index: int = 0
    total_chunks: int = 1


@dataclass
class TranslationResult:
    """单 chunk 翻译结果"""
    translation: str
    extracted_terminology: dict[str, str]    # 本 chunk 新建立术语
    detected_proper_nouns: dict[str, str]
    input_tokens: int
    output_tokens: int
    elapsed_seconds: float
    provider_name: str
    model: str
    cost_usd: float


@dataclass
class TranslationRequest:
    """路由层用"""
    text: str
    source_lang: str = "en"
    target_lang: str = "zh-CN"
    estimated_tokens: int = 0
    quality: Literal["fast", "balanced", "premium"] = "balanced"
    user_preference: Literal["default", "domestic", "international"] = "default"


class TranslationProvider(Protocol):
    """Provider 接口契约"""
    name: str
    cost_per_million_input: float
    cost_per_million_output: float
    max_input_tokens: int
    supports_streaming: bool

    async def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "zh-CN",
        context: TranslationContext | None = None,
        terminology: dict[str, str] | None = None,
        temperature: float = 0.2,
    ) -> TranslationResult: ...

    async def health_check(self) -> bool: ...
```

### 2.3 chunker.py 实施

```python
# oprim/translate/chunker.py
from typing import Literal
from dataclasses import dataclass
import tiktoken
import re

@dataclass
class TranslationChunk:
    chunk_id: str                # e.g. "chunk_0001"
    index: int
    total: int
    text: str
    token_count: int
    metadata: dict               # 章节标题 / 段落起止 etc.


class TranslationChunker:
    """翻译专用 chunker, 不同于 RAG chunker"""

    def __init__(
        self,
        max_tokens: int = 3000,
        min_tokens: int = 500,
        overlap_tokens: int = 200,
        prefer_paragraph_boundary: bool = True,
        tokenizer_model: str = "cl100k_base",
    ):
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens
        self.overlap_tokens = overlap_tokens
        self.prefer_paragraph_boundary = prefer_paragraph_boundary
        self.tokenizer = tiktoken.get_encoding(tokenizer_model)

    def chunk(
        self,
        text: str,
        format: Literal["markdown", "plaintext", "epub_chapter", "srt"],
    ) -> list[TranslationChunk]:
        """
        策略 (按 format):
        - markdown: 按 header (## / ###) 切分, 不破坏 code block / list / link
        - plaintext: 按段落 (\\n\\n) 切分, 不切句子中间
        - epub_chapter: 单 chapter 按章节切, 不跨 chapter
        - srt: 按 cue boundary 切, 不切 cue 中间
        """
        if format == "markdown":
            return self._chunk_markdown(text)
        elif format == "plaintext":
            return self._chunk_plaintext(text)
        elif format == "epub_chapter":
            return self._chunk_epub_chapter(text)
        elif format == "srt":
            return self._chunk_srt(text)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _chunk_markdown(self, text: str) -> list[TranslationChunk]:
        """
        1. 按 ## header 找一级边界
        2. 每个段落用 token count 累加
        3. 超 max_tokens 时回退到最近段落边界切
        4. 单段超 max_tokens 时按句子切 (中文按 。 ！ ？, 英文按 . ! ?)
        """
        # 实施时注意: code block (```) 不能切断
        ...

    def _chunk_plaintext(self, text: str) -> list[TranslationChunk]:
        """按段落 \n\n 切分"""
        ...

    def _chunk_epub_chapter(self, text: str) -> list[TranslationChunk]:
        ...

    def _chunk_srt(self, text: str) -> list[TranslationChunk]:
        ...

    def count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))
```

### 2.4 checkpoint.py 实施

```python
# oprim/translate/checkpoint.py
import json
from pathlib import Path
from datetime import datetime

class TranslationCheckpoint:
    """断点续传 (sqlite + json file 双存储)"""

    def __init__(self, substrate_id: str, checkpoint_dir: Path):
        self.substrate_id = substrate_id
        self.checkpoint_path = checkpoint_dir / f"{substrate_id}.checkpoint.json"
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    def _load(self) -> dict:
        if self.checkpoint_path.exists():
            return json.loads(self.checkpoint_path.read_text())
        return {
            "substrate_id": self.substrate_id,
            "total_chunks": 0,
            "completed_chunks": {},        # chunk_id → {translation, metadata}
            "established_terminology": {},
            "established_proper_nouns": {},
            "current_provider": None,
            "started_at": datetime.utcnow().isoformat(),
            "last_chunk_at": None,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost_usd": 0.0,
        }

    def _save(self):
        self.checkpoint_path.write_text(json.dumps(self._state, ensure_ascii=False, indent=2))

    def save_chunk(self, chunk_id: str, result: "TranslationResult"):
        self._state["completed_chunks"][chunk_id] = {
            "translation": result.translation,
            "metadata": {
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "cost_usd": result.cost_usd,
                "provider": result.provider_name,
            }
        }
        self._state["established_terminology"].update(result.extracted_terminology)
        self._state["established_proper_nouns"].update(result.detected_proper_nouns)
        self._state["total_input_tokens"] += result.input_tokens
        self._state["total_output_tokens"] += result.output_tokens
        self._state["total_cost_usd"] += result.cost_usd
        self._state["last_chunk_at"] = datetime.utcnow().isoformat()
        self._save()

    def get_completed_chunks(self) -> dict[str, dict]:
        return self._state["completed_chunks"]

    def get_terminology(self) -> dict[str, str]:
        return self._state["established_terminology"]

    def get_proper_nouns(self) -> dict[str, str]:
        return self._state["established_proper_nouns"]

    def is_complete(self) -> bool:
        return len(self._state["completed_chunks"]) == self._state["total_chunks"] > 0

    def set_total_chunks(self, total: int):
        self._state["total_chunks"] = total
        self._save()

    def clear(self):
        self.checkpoint_path.unlink(missing_ok=True)
        self._state = self._load()
```

### 2.5 terminology.py 实施

```python
# oprim/translate/terminology.py
import re

class TerminologyExtractor:
    """从翻译输出中提取术语 + 专有名词"""

    @staticmethod
    def extract_from_response(
        en_source: str,
        zh_translation: str,
    ) -> tuple[dict[str, str], dict[str, str]]:
        """
        约定 LLM 输出格式:
        翻译正文

        ===术语===
        Sharpe ratio → 夏普比率
        Deflated Sharpe Ratio (DSR) → 通缩夏普比率

        ===人名地名===
        Sayuri → 小百合
        Bailey → 贝利
        """
        terminology = {}
        proper_nouns = {}

        # 解析 ===术语=== 段
        term_match = re.search(r"===术语===\s*\n(.*?)(?=\n===|\Z)", zh_translation, re.DOTALL)
        if term_match:
            for line in term_match.group(1).strip().split("\n"):
                if "→" in line:
                    en, zh = line.split("→", 1)
                    terminology[en.strip()] = zh.strip()

        # 解析 ===人名地名=== 段
        proper_match = re.search(r"===人名地名===\s*\n(.*?)(?=\n===|\Z)", zh_translation, re.DOTALL)
        if proper_match:
            for line in proper_match.group(1).strip().split("\n"):
                if "→" in line:
                    en, zh = line.split("→", 1)
                    proper_nouns[en.strip()] = zh.strip()

        return terminology, proper_nouns

    @staticmethod
    def strip_terminology_sections(translation: str) -> str:
        """从翻译正文中移除 ===术语=== ===人名地名=== 段"""
        cleaned = re.sub(r"\n*===术语===\s*\n.*?(?=\n===|\Z)", "", translation, flags=re.DOTALL)
        cleaned = re.sub(r"\n*===人名地名===\s*\n.*?(?=\n===|\Z)", "", cleaned, flags=re.DOTALL)
        return cleaned.strip()
```

### 2.6 router.py 实施

```python
# oprim/translate/router.py
from .protocol import TranslationProvider, TranslationRequest

class TranslationRouter:
    def __init__(self, providers: dict[str, TranslationProvider]):
        """providers: {"deepseek": DeepSeekProvider(), "claude": ..., "qwen3": ...}"""
        self.providers = providers
        if "deepseek" not in providers:
            raise ValueError("DeepSeek provider is required as default")

    def route(self, request: TranslationRequest) -> TranslationProvider:
        """
        路由规则:
        1. quality="premium" → claude (如有)
        2. user_preference="domestic" → qwen3 (如有)
        3. 默认 → deepseek
        """
        if request.quality == "premium" and "claude" in self.providers:
            return self.providers["claude"]
        if request.user_preference == "domestic" and "qwen3" in self.providers:
            return self.providers["qwen3"]
        return self.providers["deepseek"]
```

### 2.7 _prompts.py 实施

```python
# oprim/translate/_prompts.py

SYSTEM_PROMPT = """你是专业的中英翻译家, 擅长准确传意 + 自然流畅的中文译文。"""

USER_PROMPT_TEMPLATE = """请将以下英文翻译成中文。

【翻译要求】
1. 准确传达原意, 不增不减
2. 译文自然流畅, 符合中文表达习惯
3. 保留专业术语, 必要时加注英文原词
4. 代码标识符 / API 名称 / 缩写 (如 PostgreSQL, MVCC, VACUUM) 保留英文不译
5. 保持原文 markdown 格式 (## header, **bold**, > quote, ```code```, - list 等)

【上下文】
- 这是文档第 {chunk_index}/{total_chunks} 段
{context_block}

【已建立的术语对照】(请保持一致):
{terminology_block}

【已建立的人名地名】(请保持一致):
{proper_nouns_block}

【正在翻译的内容】:
{text}

【输出格式】
先输出译文正文, 然后用以下格式列出本段新建立的术语和人名地名 (如无可省略):

===术语===
术语英文 → 中文译法
...

===人名地名===
人名英文 → 中文译法
...
"""

CONTEXT_BLOCK_TEMPLATE = """
- 前文摘要 (帮助理解上下文, 不需要翻译): {previous_chunks_summary}
- 接下来的内容预览 (帮助句尾过渡, 不需要翻译): {next_chunk_preview}
"""
```

### 2.8 errors.py 实施

```python
# oprim/translate/errors.py
from obase.errors import OBaseError

class TranslationError(OBaseError):
    """翻译模块基础异常"""

class ProviderUnavailableError(TranslationError):
    """provider 不可用 (API 失败 / key 错误等)"""

class TokenLimitExceededError(TranslationError):
    """文本超过 provider max_input_tokens"""

class CheckpointCorruptedError(TranslationError):
    """checkpoint 文件损坏"""

class FormatPreservationError(TranslationError):
    """格式保留失败 (markdown 结构被破坏)"""

class ChunkingError(TranslationError):
    """chunking 失败"""
```

### 2.9 __init__.py

```python
# oprim/translate/__init__.py
from .protocol import (
    TranslationProvider,
    TranslationContext,
    TranslationResult,
    TranslationRequest,
)
from .router import TranslationRouter
from .chunker import TranslationChunker, TranslationChunk
from .checkpoint import TranslationCheckpoint
from .terminology import TerminologyExtractor
from . import errors

__all__ = [
    "TranslationProvider", "TranslationContext", "TranslationResult", "TranslationRequest",
    "TranslationRouter", "TranslationChunker", "TranslationChunk",
    "TranslationCheckpoint", "TerminologyExtractor", "errors",
]
```

### 2.10 Wave 1 验证

```bash
cd ~/projects/platform/oprim
pip install tiktoken --upgrade
python -c "from oprim.translate import (
    TranslationProvider, TranslationContext, TranslationResult,
    TranslationRouter, TranslationChunker, TranslationCheckpoint,
    TerminologyExtractor, errors
); print('imports OK')"

# 跑 chunker 测试 (mock 数据)
python -c "
from oprim.translate import TranslationChunker
c = TranslationChunker()
sample = '## H1\n\nPara 1.\n\nPara 2.\n\n## H2\n\nPara 3.'
chunks = c.chunk(sample, format='markdown')
print(f'chunks: {len(chunks)}')
for ch in chunks:
    print(f'  {ch.chunk_id}: tok={ch.token_count}')
"
```

### 2.11 Wave 1 完成报告

```
=== Wave 1 完成 ===
- oprim/translate/ 模块结构搭建完成 (8 文件)
- protocol.py: 4 dataclass + Protocol
- chunker.py: TranslationChunker 4 format
- checkpoint.py: 持久化 JSON
- terminology.py: 提取 + 清理
- router.py: 3 provider 路由
- _prompts.py: 标准 prompt 模板
- imports 验证 OK
- chunker mock 测试: <chunk 数> chunks
- commit hash: <xxx>
```

---

## §3 Wave 2 — 3 Provider 实施

### 3.1 DeepSeek Provider (优先实施)

```python
# oprim/translate/providers/deepseek.py
import os
import time
from openai import AsyncOpenAI
from ..protocol import TranslationProvider, TranslationContext, TranslationResult
from ..terminology import TerminologyExtractor
from ..errors import ProviderUnavailableError, TokenLimitExceededError
from .._prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, CONTEXT_BLOCK_TEMPLATE
from obase.logging import get_logger

logger = get_logger(__name__)

class DeepSeekTranslateProvider:
    name = "deepseek"
    cost_per_million_input = 0.28
    cost_per_million_output = 0.42
    max_input_tokens = 128000
    supports_streaming = True

    def __init__(self, api_key: str | None = None, model: str = "deepseek-chat"):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ProviderUnavailableError("DEEPSEEK_API_KEY not set")
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = model

    async def translate(
        self,
        text: str,
        source_lang: str = "en",
        target_lang: str = "zh-CN",
        context: TranslationContext | None = None,
        terminology: dict[str, str] | None = None,
        temperature: float = 0.2,
    ) -> TranslationResult:
        ctx = context or TranslationContext()
        terminology = terminology or {}

        # build context block
        if ctx.previous_chunks_summary or ctx.next_chunk_preview:
            ctx_block = CONTEXT_BLOCK_TEMPLATE.format(
                previous_chunks_summary=ctx.previous_chunks_summary or "(无, 这是第一段)",
                next_chunk_preview=ctx.next_chunk_preview or "(无, 这是最后一段)",
            )
        else:
            ctx_block = "(无上下文)"

        term_block = "\n".join(f"  {en} → {zh}" for en, zh in terminology.items()) or "(无)"
        proper_block = "\n".join(f"  {en} → {zh}" for en, zh in ctx.established_proper_nouns.items()) or "(无)"

        user_prompt = USER_PROMPT_TEMPLATE.format(
            chunk_index=ctx.chunk_index + 1,
            total_chunks=ctx.total_chunks,
            context_block=ctx_block,
            terminology_block=term_block,
            proper_nouns_block=proper_block,
            text=text,
        )

        start = time.time()
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=8000,
            )
        except Exception as e:
            logger.error("deepseek_translate_failed", error=str(e), text_length=len(text))
            raise ProviderUnavailableError(f"DeepSeek API failed: {e}") from e

        elapsed = time.time() - start
        raw = resp.choices[0].message.content
        input_tok = resp.usage.prompt_tokens
        output_tok = resp.usage.completion_tokens
        cost = (input_tok / 1_000_000) * self.cost_per_million_input + (output_tok / 1_000_000) * self.cost_per_million_output

        # extract terminology + clean translation
        extracted_term, extracted_proper = TerminologyExtractor.extract_from_response(text, raw)
        clean_translation = TerminologyExtractor.strip_terminology_sections(raw)

        return TranslationResult(
            translation=clean_translation,
            extracted_terminology=extracted_term,
            detected_proper_nouns=extracted_proper,
            input_tokens=input_tok,
            output_tokens=output_tok,
            elapsed_seconds=elapsed,
            provider_name=self.name,
            model=self.model,
            cost_usd=cost,
        )

    async def health_check(self) -> bool:
        try:
            r = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role":"user","content":"ping"}],
                max_tokens=5,
            )
            return bool(r.choices)
        except Exception as e:
            logger.warning("deepseek_health_check_failed", error=str(e))
            return False
```

### 3.2 Claude Provider

```python
# oprim/translate/providers/claude.py
import os, time
from anthropic import AsyncAnthropic
from ..protocol import TranslationProvider, TranslationContext, TranslationResult
from ..terminology import TerminologyExtractor
from ..errors import ProviderUnavailableError
from .._prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, CONTEXT_BLOCK_TEMPLATE
from obase.logging import get_logger

logger = get_logger(__name__)

class ClaudeTranslateProvider:
    name = "claude"
    # Sonnet 4.6 默认 (性价比), Opus 用户显式选
    cost_per_million_input = 3.0   # Sonnet 4.6
    cost_per_million_output = 15.0
    max_input_tokens = 200000
    supports_streaming = True

    def __init__(self, api_key: str | None = None, model: str = "claude-sonnet-4-5"):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ProviderUnavailableError("ANTHROPIC_API_KEY not set")
        self.client = AsyncAnthropic(api_key=self.api_key)
        self.model = model
        # Opus 价格不同
        if "opus" in model.lower():
            self.cost_per_million_input = 15.0
            self.cost_per_million_output = 75.0

    async def translate(self, text, source_lang="en", target_lang="zh-CN",
                       context=None, terminology=None, temperature=0.2):
        # 跟 deepseek 同构, prompt 一样, 走 anthropic messages.create
        ...

    async def health_check(self) -> bool:
        try:
            r = await self.client.messages.create(
                model=self.model, max_tokens=5,
                messages=[{"role":"user","content":"ping"}],
            )
            return bool(r.content)
        except Exception as e:
            logger.warning("claude_health_check_failed", error=str(e))
            return False
```

### 3.3 Qwen3 Provider (DashScope)

```python
# oprim/translate/providers/qwen3.py
import os, time
import dashscope
from dashscope import Generation
from ..protocol import TranslationProvider, TranslationContext, TranslationResult
from ..terminology import TerminologyExtractor
from ..errors import ProviderUnavailableError
from .._prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from obase.logging import get_logger

logger = get_logger(__name__)

class Qwen3TranslateProvider:
    name = "qwen3"
    cost_per_million_input = 0.78    # Qwen3-Max via DashScope international
    cost_per_million_output = 3.90
    max_input_tokens = 262144         # Qwen3-Max context
    supports_streaming = False

    def __init__(self, api_key: str | None = None, model: str = "qwen-max"):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ProviderUnavailableError("DASHSCOPE_API_KEY not set")
        dashscope.api_key = self.api_key
        self.model = model

    async def translate(self, text, source_lang="en", target_lang="zh-CN",
                       context=None, terminology=None, temperature=0.2):
        # DashScope SDK 是同步, 用 asyncio.to_thread 包装
        ...

    async def health_check(self) -> bool:
        ...
```

### 3.4 Provider 目录组织

```
oprim/translate/
└── providers/
    ├── __init__.py        # export 三个 provider
    ├── deepseek.py
    ├── claude.py
    └── qwen3.py
```

### 3.5 Provider 单元测试

测试目录: `oprim/tests/translate/test_providers.py`

测试要求 (每 provider):
- mock API 响应, 验证 prompt 构建正确
- 验证 cost 计算正确
- 验证 TerminologyExtractor 整合
- 验证异常处理 (network error → ProviderUnavailableError)

集成测试 (跑真实 API, 各 1 次):
- 3 段 corpus (academic / literary / technical) 翻译, 验证输出非空
- 验证 input/output token 数返回正确
- 验证 cost 计算合理 (< $0.10 每段)

### 3.6 Wave 2 验证

```bash
cd ~/projects/platform/oprim
pip install openai anthropic dashscope --upgrade

# 单元测试
pytest oprim/tests/translate/test_providers.py -v

# 集成测试 (真实 API, 跑 3 段 corpus, 每 provider 各跑一次)
pytest oprim/tests/translate/test_providers_integration.py -v --runintegration
```

### 3.7 Wave 2 完成报告

```
=== Wave 2 完成 ===
- DeepSeek provider 实施 OK
- Claude provider 实施 OK
- Qwen3 provider 实施 OK
- 单元测试: <数>/通过
- 集成测试 (真实 API):
  - DeepSeek 3 corpus: <时间> <token> <成本>
  - Claude 3 corpus: <时间> <token> <成本>
  - Qwen3 3 corpus: <时间> <token> <成本>
- Router 路由测试 OK
- commit hash: <xxx>
```

---

## §4 Wave 3 — Format 保留

### 4.1 实施位置

```
oprim/translate/formats/
├── __init__.py
├── markdown.py
├── plaintext.py
└── epub.py            # Phase 10 实施
# srt 留 Phase 11
```

### 4.2 markdown.py

```python
# oprim/translate/formats/markdown.py
import re
from typing import NamedTuple

class MarkdownSegment(NamedTuple):
    kind: str           # "header" | "paragraph" | "code_block" | "list" | "quote"
    raw: str
    translatable: bool  # 是否需要翻译 (code_block / link URL 不翻)


class MarkdownFormatHandler:
    """保留 markdown 结构, 把 translatable 部分拆出来交给翻译"""

    def parse(self, text: str) -> list[MarkdownSegment]:
        """
        识别:
        - 标题 (#, ##, ###) → 翻
        - 代码块 (```) → 不翻, 保留
        - 行内代码 (`xxx`) → 不翻
        - 链接 [text](url) → 翻 text, 保留 url
        - 图片 ![alt](url) → 翻 alt, 保留 url
        - 列表 (- / *) → 翻列表项, 保留标记
        - 引用 (>) → 翻内容, 保留标记
        - 段落 → 翻
        """
        ...

    def reassemble(self, segments: list[MarkdownSegment], translations: dict[int, str]) -> str:
        """根据原结构重组, translations 是 {segment_idx: 译文}"""
        ...

    def extract_translatable_text(self, segments: list[MarkdownSegment]) -> str:
        """生成给翻译用的纯文本 (保留段落分隔, 略去代码块)"""
        ...
```

### 4.3 plaintext.py

简单, 直接按 \n\n 段落切, reassemble 时拼回。

### 4.4 epub.py (Phase 10 基础版)

```python
# oprim/translate/formats/epub.py
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

class EpubFormatHandler:
    """EPUB 翻译: 逐 chapter 提取 HTML, 翻 text node, 回写 HTML"""

    def __init__(self):
        ...

    def extract_chapters(self, epub_path: str) -> list[dict]:
        """返回 [{chapter_id, title, html, plaintext}, ...]"""
        ...

    def translate_chapter_html(
        self,
        chapter_html: str,
        translator_callback: callable,
    ) -> str:
        """
        1. 用 BeautifulSoup 解析
        2. 找到 <p> <h1>...<h6> <li> 等 text node
        3. 收集 text → 翻译 (batch)
        4. 替换回 HTML
        5. 保留 attribute (class, id, href)
        """
        ...

    def write_back(
        self,
        original_epub_path: str,
        translated_chapters: dict[str, str],
        output_path: str,
    ):
        """生成新 EPUB, metadata 保留 (title 加 [zh-CN] 后缀)"""
        ...
```

### 4.5 Wave 3 验证

测试:
- markdown: 含 code block + link + list 的样本翻译后结构 unchanged
- plaintext: 段落数对齐
- epub: 加载小型 EPUB → 翻一章 → 写回 → 重新加载 verify

### 4.6 Wave 3 完成报告

```
=== Wave 3 完成 ===
- markdown handler: parse + reassemble + extract_translatable
- plaintext handler: 段落切分 + 拼装
- epub handler: chapter 提取 + HTML 翻译 + 回写
- 测试: <数>/通过
- commit hash: <xxx>
```

---

## §5 Wave 4 — oskill.knowledge.translate_substrate 端到端

### 5.1 文件位置

```
platform/oskill/oskill/knowledge/translate_substrate.py
```

### 5.2 实施

```python
# oskill/knowledge/translate_substrate.py
from typing import Literal
from pathlib import Path
from oprim.translate import (
    TranslationRouter, TranslationChunker, TranslationCheckpoint,
    TranslationContext, TranslationRequest,
)
from oprim.translate.providers import (
    DeepSeekTranslateProvider, ClaudeTranslateProvider, Qwen3TranslateProvider,
)
from oprim.translate.formats import MarkdownFormatHandler, PlaintextFormatHandler
from oprim.translate.errors import TranslationError
from oprim.meta_db import get_substrate, create_derivative
from oskill.knowledge.generate_derivative import generate_derivative
from obase.logging import get_logger

logger = get_logger(__name__)


async def translate_substrate(
    substrate_id: str,
    target_lang: str = "zh-CN",
    provider_hint: str | None = None,
    quality: Literal["fast", "balanced", "premium"] = "balanced",
    embed_translation: bool = True,
    checkpoint_dir: Path = Path.home() / ".stratum" / "translation",
) -> dict:
    """
    端到端翻译流程:
    1. fetch substrate (DB)
    2. detect source language → 跳过非英文
    3. 根据 substrate.format 选 format handler
    4. chunking
    5. resume checkpoint if exists
    6. build router (3 provider)
    7. for each chunk:
       - build TranslationContext (前文摘要 + 术语)
       - router.route() → translate
       - update terminology in checkpoint
       - save chunk to checkpoint
    8. re-assemble preserving format
    9. write back as derivative (type=translation, source_substrate_id=...)
    10. if embed_translation → trigger embedding
    11. log changefeed event (Phase 2 后启用)
    12. return summary

    Returns: {
        "derivative_id": "...",
        "total_chunks": N,
        "total_input_tokens": ...,
        "total_output_tokens": ...,
        "total_cost_usd": ...,
        "provider_used": "deepseek" | ...,
        "elapsed_seconds": ...
    }
    """
    # 1. fetch substrate
    substrate = await get_substrate(substrate_id)
    if not substrate:
        raise TranslationError(f"Substrate not found: {substrate_id}")

    source_text = await _get_substrate_text(substrate)

    # 2. detect language (简单启发式: ASCII 占比 > 80% 视为英文)
    if not _is_english(source_text):
        logger.info("translate_substrate_skipped_non_english", substrate_id=substrate_id)
        return {"skipped": True, "reason": "not_english"}

    # 3. format handler
    format_handler = _get_format_handler(substrate.format)
    translatable_text = format_handler.extract_translatable_text_or_passthrough(source_text)

    # 4. chunking
    chunker = TranslationChunker()
    chunks = chunker.chunk(translatable_text, format=_chunker_format(substrate.format))
    logger.info("translate_chunks_created", substrate_id=substrate_id, count=len(chunks))

    # 5. checkpoint
    checkpoint = TranslationCheckpoint(substrate_id, checkpoint_dir)
    checkpoint.set_total_chunks(len(chunks))
    completed = checkpoint.get_completed_chunks()

    # 6. router
    providers = {
        "deepseek": DeepSeekTranslateProvider(),
        "claude": ClaudeTranslateProvider(),
        "qwen3": Qwen3TranslateProvider(),
    }
    router = TranslationRouter(providers)

    # 7. translate chunks
    translations = {}
    for ch in chunks:
        if ch.chunk_id in completed:
            translations[ch.chunk_id] = completed[ch.chunk_id]["translation"]
            continue

        # build context
        ctx = TranslationContext(
            previous_chunks_summary=_build_prev_summary(translations, chunks, ch.index),
            next_chunk_preview=chunks[ch.index + 1].text[:200] if ch.index + 1 < len(chunks) else None,
            document_metadata={"title": substrate.title, "medium": substrate.medium},
            established_proper_nouns=checkpoint.get_proper_nouns(),
            chunk_index=ch.index,
            total_chunks=len(chunks),
        )

        # route
        req = TranslationRequest(
            text=ch.text,
            estimated_tokens=ch.token_count,
            quality=quality,
            user_preference="default" if not provider_hint else "domestic" if provider_hint == "qwen3" else "default",
        )
        provider = router.route(req)
        if provider_hint:
            provider = providers.get(provider_hint, provider)

        # translate
        result = await provider.translate(
            text=ch.text,
            context=ctx,
            terminology=checkpoint.get_terminology(),
        )

        # save
        checkpoint.save_chunk(ch.chunk_id, result)
        translations[ch.chunk_id] = result.translation

        logger.info("translate_chunk_done",
                   substrate_id=substrate_id, chunk=ch.chunk_id,
                   provider=result.provider_name, cost=result.cost_usd)

    # 8. reassemble
    translation_idx = {ch.index: translations[ch.chunk_id] for ch in chunks}
    final_text = format_handler.reassemble_or_simple_join(translation_idx, chunks)

    # 9. write derivative
    derivative = await create_derivative(
        source_substrate_id=substrate_id,
        type="translation",
        content=final_text,
        metadata={
            "target_lang": target_lang,
            "source_lang": "en",
            "providers_used": list(set(c["metadata"]["provider"] for c in checkpoint.get_completed_chunks().values())),
            "total_input_tokens": checkpoint._state["total_input_tokens"],
            "total_output_tokens": checkpoint._state["total_output_tokens"],
            "total_cost_usd": checkpoint._state["total_cost_usd"],
            "terminology": checkpoint.get_terminology(),
            "proper_nouns": checkpoint.get_proper_nouns(),
        }
    )

    # 10. embed if requested
    if embed_translation:
        from oskill.knowledge.ingest_substrate import _embed_derivative
        await _embed_derivative(derivative.id)

    # 11. cleanup checkpoint (translation completed)
    checkpoint.clear()

    return {
        "derivative_id": derivative.id,
        "total_chunks": len(chunks),
        "total_input_tokens": checkpoint._state.get("total_input_tokens", 0),
        "total_output_tokens": checkpoint._state.get("total_output_tokens", 0),
        "total_cost_usd": checkpoint._state.get("total_cost_usd", 0.0),
        "providers_used": list(set(c["metadata"]["provider"] for c in checkpoint.get_completed_chunks().values())),
    }


# helpers
def _get_format_handler(format_name: str):
    if format_name == "markdown":
        return MarkdownFormatHandler()
    return PlaintextFormatHandler()

def _chunker_format(format_name: str):
    if format_name == "markdown":
        return "markdown"
    return "plaintext"

def _is_english(text: str) -> bool:
    sample = text[:1000]
    ascii_chars = sum(1 for c in sample if ord(c) < 128)
    return ascii_chars / max(len(sample), 1) > 0.8

def _build_prev_summary(translations: dict, chunks: list, current_index: int) -> str | None:
    if current_index == 0:
        return None
    # 取前一 chunk 的译文末尾 200 字作为 summary
    prev_chunk = chunks[current_index - 1]
    prev_translation = translations.get(prev_chunk.chunk_id, "")
    return prev_translation[-200:] if prev_translation else None

async def _get_substrate_text(substrate) -> str:
    """从 substrate 获取可翻译的文本内容"""
    # 优先 markdown derivative, fallback 到 raw text
    ...
```

### 5.3 oskill pyproject.toml 更新

```toml
# platform/oskill/pyproject.toml
[project]
version = "2.4.0"
dependencies = [
    # ... existing
    "oprim>=2.3.0",  # 需要 oprim translate
]
```

### 5.4 Wave 4 验证

```bash
cd ~/projects/platform/oskill
pip install -e .

# 端到端 demo (用 Phase 1 已有的 demo substrate)
python -c "
import asyncio
from oskill.knowledge import translate_substrate

# 先 ingest 一个英文 substrate
# ... (Phase 1 ingest_substrate 流程)

async def run():
    result = await translate_substrate(
        substrate_id='<英文 substrate id>',
        quality='balanced',
        embed_translation=True,
    )
    print(result)

asyncio.run(run())
"
```

### 5.5 Wave 4 完成报告

```
=== Wave 4 完成 ===
- oskill.knowledge.translate_substrate 实施 OK
- 端到端 demo:
  - substrate_id: <id>
  - chunks: <N>
  - provider: <deepseek>
  - input tokens: <数>
  - output tokens: <数>
  - cost: $<金额>
  - derivative_id: <id>
  - embedding: <ok>
- oskill version: 2.4.0
- commit hash: <xxx>
```

---

## §6 Wave 5 — 测试 + 端到端 demo + Gate 验收

### 6.1 完整测试矩阵

| 测试类型 | 文件 | 跑通要求 |
|---|---|---|
| 单元测试 (chunker) | `oprim/tests/translate/test_chunker.py` | 所有 format 切分正确 |
| 单元测试 (checkpoint) | `oprim/tests/translate/test_checkpoint.py` | 持久化 + resume |
| 单元测试 (terminology) | `oprim/tests/translate/test_terminology.py` | extract + strip |
| 单元测试 (router) | `oprim/tests/translate/test_router.py` | 路由规则 |
| 单元测试 (markdown handler) | `oprim/tests/translate/test_format_md.py` | 结构保留 |
| 单元测试 (epub handler) | `oprim/tests/translate/test_format_epub.py` | chapter 提取 + 回写 |
| 集成测试 (deepseek) | `oprim/tests/translate/test_deepseek_integration.py` | 真实 API, 3 段 corpus |
| 集成测试 (claude) | 同上 (claude) | 真实 API, 3 段 corpus |
| 集成测试 (qwen3) | 同上 (qwen3) | 真实 API, 3 段 corpus |
| 端到端 (translate_substrate) | `oskill/tests/test_translate_substrate.py` | 端到端含 derivative |

### 6.2 实证 corpus (来自翻译选型实证报告)

```
# 测试 corpus (3 段)
domain_1_academic = """The Sharpe ratio, despite its widespread adoption, ..."""
domain_2_literary = """The autumn rain fell on the old streets of Kyoto..."""
domain_3_technical = """PostgreSQL's MVCC (Multi-Version Concurrency Control)..."""

# 跑 3 provider × 3 corpus = 9 次集成测试
# 每次记录:
# - 翻译输出 (保存到 /tmp/translation-eval/{provider}_{domain}.md)
# - input/output tokens
# - elapsed time
# - cost
```

### 6.3 测试覆盖率验证

```bash
cd ~/projects/platform/oprim
pytest oprim/tests/translate/ --cov=oprim/translate --cov-report=term-missing
# 期待: ≥ 80%

cd ~/projects/platform/oskill
pytest oskill/tests/test_translate_substrate.py --cov=oskill/knowledge/translate_substrate
# 期待: ≥ 80%
```

### 6.4 Gate 验收

| 验收项 | 通过标准 |
|---|---|
| 3 provider 实施完成 | DeepSeek + Claude + Qwen3 各自单元测试 + 集成测试 通过 |
| chunker 4 format | markdown / plaintext / epub_chapter 单元测试 通过 (srt 跳过 Phase 10) |
| checkpoint 断点续传 | 中断 → resume 后正确从中断点继续 |
| terminology 跨 chunk 一致 | 多 chunk 翻译, 术语一致性测试通过 |
| 端到端 translate_substrate | 一段英文 substrate 翻译 → derivative 创建 + embedding 完成 |
| 单元测试 ≥ 80% 覆盖 | oprim/translate + translate_substrate skill |
| 集成测试通过 | 3 provider × 3 corpus 共 9 次, 全部输出非空 + cost < $0.10 |
| 端到端 demo 跑通 | 实际可执行命令 |
| derivative.translation 类型 | 在 derivative.type ENUM 中 (跟 generate_derivative 协同) |
| Phase 2 namespace 隔离 | 未动 storage / changefeed / push / sync 目录 |
| version bump | oprim 2.3.0 / oskill 2.4.0 |
| tag | `v2.3.0-translate` (oprim) + `v2.4.0-translate` (oskill) |

### 6.5 端到端 demo 验收脚本

```bash
# Wiki 验收用 (CC 提供)
cd ~/.stratum
echo "Creating English test substrate..."

cat > /tmp/test_paper.md <<'EOF'
# Test Paper: Sharpe Ratio

The Sharpe ratio, despite its widespread adoption, suffers from
several well-documented limitations when applied to financial returns
that exhibit non-normality, autocorrelation, or finite-sample bias.

Bailey, Borwein, and Lopez de Prado (2014) introduced the Deflated
Sharpe Ratio (DSR), which corrects for the inflationary effect of
multiple testing.
EOF

cp /tmp/test_paper.md ~/.stratum/inbox/
python -m omodul.knowledge.process_inbox
# 拿到 substrate_id

# 翻译
python -c "
import asyncio
from oskill.knowledge import translate_substrate

result = asyncio.run(translate_substrate(
    substrate_id='<substrate_id>',
    quality='balanced',
))
print(result)
"

# 验证 derivative 存在 + 内容是中文
python -m omodul.knowledge.start_mcp_server &
# 通过 MCP tool fetch_substrate 拿到 derivative.translation 内容
# 检查内容是中文 (含 "夏普比率" 等关键词)
```

### 6.6 Wave 5 完成报告

```
=== Phase 10 完工报告 ===

三层汇总
- platform/oprim v2.3.0
  - 新增 sub-package: translate (8 模块 + 3 provider + 3 format)
  - 测试: <数> (新增 <数>)
  - 覆盖率: <%>
- platform/oskill v2.4.0
  - 新增: knowledge.translate_substrate
  - 测试: <数> (新增 <数>)
  - 覆盖率: <%>

Gate 验收: 全部 ✓
- 3 provider 实施
- chunker 3 format
- checkpoint
- terminology 跨 chunk 一致
- 端到端 translate_substrate
- 单元 + 集成测试覆盖率 ≥ 80%
- Phase 2 namespace 隔离 (未动 storage/changefeed/push/sync)
- version + tag

集成测试结果 (3 provider × 3 corpus):
| Provider | Domain | Tokens (in/out) | Cost | Elapsed |
|---|---|---|---|---|
| DeepSeek | academic | <in>/<out> | $<x> | <s>s |
| DeepSeek | literary | ... | ... | ... |
| ... (9 行) ... |

样本翻译输出已保存: /tmp/translation-eval/

端到端 demo: OK
- 英文 paper (250 words) 翻译完成
- derivative.translation 创建 OK
- embedding OK
- 总成本 $<x>
- 总耗时 <s>s

tag:
- oprim/v2.3.0-translate
- oskill/v2.4.0-translate

commit hashes:
- oprim: <xxx>
- oskill: <xxx>
```

---

## §7 异常处理 + 报告规范

### 7.1 异常报告时机

立即停止 + 报告 (不要继续):
- 任一 API key 失败 → 报告 + 等 Wiki 处理
- chunker 在测试样本上输出异常 (chunk 数为 0 或破坏 markdown)
- provider 调用连续失败 ≥ 5 次 (即使重试)
- checkpoint 损坏无法恢复
- format handler 在 reassemble 时丢失内容 (前后字数差 > 10%)
- 集成测试中翻译质量明显异常 (输出不是中文 / 全是英文 / 报错占位文本)

非阻塞 (记录到 trace, 继续):
- 单 chunk LLM 调用失败 → retry 3 次后 raise (终止 task), 但不要 retry 时静默
- terminology extract 失败 → log warning, 继续 (空字典)
- embed_translation 失败 → log error, derivative 仍创建

### 7.2 报告格式 (每 Wave)

```
=== Wave N 完成 ===
状态: ✓ 通过 / ✗ 失败
完工内容: ...
测试结果: ...
commit: <hash>

(如失败:)
异常详情:
- 错误类型: ...
- 复现命令: ...
- 已尝试: ...
- 建议处理: ...
```

### 7.3 不接受的 CC 行为

不要做的事 (Phase 1 教训):
- 假装跑了测试但没跑 (诚实报告 "未跑")
- 静默改 SPEC (e.g. 把 DeepSeek 换成别的, 必须报告)
- 把验收门 P0 项目降级到 P1 ("先不实施了") — 必须实施
- 跨 namespace 修改 (动 storage/changefeed/push 目录)
- 为了过测试加宽松假设 (e.g. assert score > 0 → assert score >= 0)

---

## §8 Wiki 验收 sign-off 流程

每个 Wave CC 报告完, Wiki 复制下面 prompt 来验收:

```
"Phase 10 Wave <N> 验收:
1. 让我看 commit diff (最后 commit)
2. 跑测试 (相关测试套件)
3. 验证关键文件存在
4. 如有集成测试结果, 让我看 sample 翻译输出
5. 通过 → 进入 Wave <N+1>
   不通过 → 报告失败项 + 修复方案"
```

最终 Gate 验收 Wiki 跑端到端 demo 脚本 (§6.5) 验证。

---

**End of PHASE_10_TRANSLATION_IMPLEMENTATION_INSTRUCTIONS_v0.1.md**

**预估工程量**: 3-4 周 FULL AUTO 节奏 (Wave 1 一天, Wave 2 两天, Wave 3 两天, Wave 4 两天, Wave 5 两天, 加 buffer)
