# ADR_020_ASYNC_REFACTOR_INSTRUCTIONS_v0.1.md

**任务**: 偿还 ADR-020 技术债务 — oprim.translate 全 async 重构
**执行者**: 任一空闲 CC (推荐 CC-B Phase 10 / Phase 1.5 完工后续)
**执行模式**: Claude Code FULL AUTO
**触发**: ADR-020 (Phase 10 async provider 技术债务)

**范围 (advisor 决定, 不再问)**:
- ✅ oprim.translate.providers.* 4 个 provider 改 async (DeepSeek / Claude / Qwen3 / Gemini)
- ✅ DashScope SDK 用 asyncio.to_thread 包装 (该 SDK 是 sync)
- ✅ 保留 sync API 作 1 版本向后兼容 (用 deprecation warning)
- ✅ translate_document 加 async 版本: translate_document_async
- ✅ oskill.knowledge.translate_substrate 改调 async 版

- ❌ 不动 oprim.llm (即使它是 sync, 那是另一 Phase 的事)
- ❌ 不改 oprim.embedding (跟翻译解耦)
- ❌ 不改 oskill 任何其他 skill
- ❌ 不动 storage / changefeed / push (CC-A 可能在做)

**预期产物**:
- oprim version: 2.4.0 → 2.5.0 (minor, 加 async 接口, 保留 sync deprecated)
- oskill version: 2.4.0 → 2.4.1 (patch, 改调 async)
- 全量回归 0 regressions
- tag: v2.5.0-async-refactor

**工程量**: 3-5 天 FULL AUTO

---

## §0 FULL AUTO 规则

### R-1: 失败不静默
- async 包装 sync SDK 时, 异常必须穿透 (不 swallow)
- DashScope to_thread 调用失败 → 原异常 + log + raise
- sync API 加 deprecation warning 时, 也必须真正调用 async 实现, 不能空实现

### R-2: SPEC 是真理源
- 4O v0.3 §D.1 已规定 `async def translate(...)` Protocol — 这是真理源
- DashScope 用 asyncio.to_thread 包装的方案我之前指令书写过, 是真理源

### R-4: 禁止扩大范围
- **严格只动 oprim.translate + 必要的 oskill.knowledge.translate_substrate 调用点**
- 不顺手优化别的地方
- 发现 oprim.llm 问题或想"顺便重构"立即停止报告, 不要扩范围

### R-5: namespace 隔离
- 当前 CC-A 可能在做 Phase 2, 不动: storage / changefeed / push / sync
- 不动 oprim.llm / oprim.embedding (跟翻译解耦的其他 Phase)

### R-6: 向后兼容硬要求
- 所有 sync API 必须保留 (加 deprecation warning, 但行为不变)
- 测试: 用 sync API 调用仍能跑通
- Phase 10 oskill.knowledge.translate_substrate 在改 async 调用前的版本仍能工作

---

## §1 Wave 0 — 准入检查

### 1.1 验证 baseline

```bash
cd ~/projects/platform/oprim
git status   # 应该 clean 或仅有 CC-A storage/ 进行中
git pull
python -c "import oprim; print(oprim.__version__)"
# 期待 2.4.0 (housekeeping 后)

# 验证 translate 模块结构
python -c "
from oprim.translate import (
    TranslationProvider, TranslationRouter, TranslationChunker,
    TranslationCheckpoint, TerminologyGlossary,
    translate_markdown, translate_epub, translate_document,
)
from oprim.translate.providers import (
    DeepSeekProvider, ClaudeProvider, Qwen3Provider,
    get_provider,
)
print('translate baseline OK')
"

# 验证 Gemini provider 已被 R-4 cleanup 删除 (Phase 10 commit a105075)
python -c "
try:
    from oprim.translate.providers import GeminiProvider
    print('FAIL: GeminiProvider 应已删除, 但仍存在')
    raise SystemExit(1)
except (ImportError, AttributeError):
    print('GeminiProvider 已正确删除')
"
```

### 1.2 检查现状 sync vs async

```bash
# 检查 provider translate 方法是 sync 还是 async
python -c "
import inspect
from oprim.translate.providers import DeepSeekProvider, ClaudeProvider, Qwen3Provider
for p_cls in [DeepSeekProvider, ClaudeProvider, Qwen3Provider]:
    m = p_cls.translate if hasattr(p_cls, 'translate') else None
    is_async = inspect.iscoroutinefunction(m)
    print(f'{p_cls.__name__}.translate: {\"async\" if is_async else \"sync\"}')
"
# 期待: 3 个全部 sync
```

如果发现已经是 async (跟 ADR-020 描述冲突), **立即停止报告** — 说明前序 CC 已悄悄改了, 状态不一致, advisor 需要重新评估。

### 1.3 检查 oskill 调用点

```bash
cd ~/projects/platform/oskill
grep -rn "translate_document\|translate_markdown\|translate_epub" oskill/
```

记录所有调用点, 后续 Wave 3 改这些。

### 1.4 Wave 0 完成报告

```
=== Wave 0 完成 ===
- oprim baseline: <version>
- translate module: imports OK
- providers 现状: DeepSeek <sync/async>, Claude <sync/async>, Qwen3 <sync/async>
- oskill 调用点: <list>
- 进入 Wave 1
```

---

## §2 Wave 1 — Provider Protocol async 化

### 2.1 改 protocol.py

```python
# oprim/translate/protocol.py 修订
from typing import Protocol

class TranslationProvider(Protocol):
    """Provider 接口契约 (async 版)"""
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

### 2.2 改 router.py

```python
# oprim/translate/router.py 修订
class TranslationRouter:
    def __init__(self, providers: dict[str, TranslationProvider]):
        # 验证 deepseek 必须存在
        if "deepseek" not in providers:
            raise ValueError("DeepSeek provider is required as default")
        self.providers = providers

    def route(self, request: TranslationRequest) -> TranslationProvider:
        """同步路由 (只是选 provider, 不调 LLM, 保持 sync 即可)"""
        if request.quality == "premium" and "claude" in self.providers:
            return self.providers["claude"]
        if request.user_preference == "domestic" and "qwen3" in self.providers:
            return self.providers["qwen3"]
        return self.providers["deepseek"]
```

**注意**: router.route() 本身保持 sync (它只是路由决策, 不调 API), 调用方拿到 provider 后 await provider.translate(...)。

### 2.3 测试 protocol + router

更新现有测试, 验证:
- TranslationProvider Protocol 检查 (mypy / runtime)
- Router 路由规则
- Router 不依赖 async (mock provider 即可)

---

## §3 Wave 2 — 4 Provider async 实施

### 3.1 DeepSeek (改造)

```python
# oprim/translate/providers/deepseek.py 修订
import os, time, asyncio
from openai import AsyncOpenAI  # 改用 AsyncOpenAI
from ..protocol import TranslationContext, TranslationResult
from ..terminology import TerminologyExtractor
from ..errors import ProviderUnavailableError
from .._prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, CONTEXT_BLOCK_TEMPLATE
from obase.logging import get_logger

logger = get_logger(__name__)


class DeepSeekProvider:
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

        # build prompt (跟原 sync 版一致)
        if ctx.previous_chunks_summary or ctx.next_chunk_preview:
            ctx_block = CONTEXT_BLOCK_TEMPLATE.format(
                previous_chunks_summary=ctx.previous_chunks_summary or "(无)",
                next_chunk_preview=ctx.next_chunk_preview or "(无)",
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
            # 关键: AsyncOpenAI.chat.completions.create() 已经是 async
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
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return bool(r.choices)
        except Exception as e:
            logger.warning("deepseek_health_check_failed", error=str(e))
            return False
```

### 3.2 Claude (改造)

同样改用 `AsyncAnthropic`, 接口规范一致。

### 3.3 Qwen3 / DashScope (难点)

DashScope SDK 是同步, 用 `asyncio.to_thread` 包装:

```python
# oprim/translate/providers/qwen3.py 修订
import os, time, asyncio
import dashscope
from dashscope import Generation
from ..protocol import TranslationContext, TranslationResult
from ..errors import ProviderUnavailableError
from obase.logging import get_logger

logger = get_logger(__name__)


class Qwen3Provider:
    name = "qwen3"
    cost_per_million_input = 0.78
    cost_per_million_output = 3.90
    max_input_tokens = 262144
    supports_streaming = False

    def __init__(self, api_key: str | None = None, model: str = "qwen-max"):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
        if not self.api_key:
            raise ProviderUnavailableError("DASHSCOPE_API_KEY/QWEN_API_KEY not set")
        dashscope.api_key = self.api_key
        self.model = model

    async def translate(self, text, source_lang="en", target_lang="zh-CN",
                       context=None, terminology=None, temperature=0.2):
        # build prompt (同 DeepSeek)
        ...
        
        # 关键: DashScope SDK 是同步, 包到 thread
        try:
            response = await asyncio.to_thread(
                Generation.call,
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=temperature,
                max_tokens=8000,
            )
        except Exception as e:
            logger.error("qwen3_translate_failed", error=str(e), text_length=len(text))
            raise ProviderUnavailableError(f"Qwen3 API failed: {e}") from e

        # 解析 response (DashScope 格式特定)
        ...

    async def health_check(self) -> bool:
        try:
            response = await asyncio.to_thread(
                Generation.call,
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return response.status_code == 200
        except Exception as e:
            logger.warning("qwen3_health_check_failed", error=str(e))
            return False
```

### 3.4 测试更新

所有现有 provider 单元测试改 async, 用 `pytest-asyncio`:

```python
import pytest

@pytest.mark.asyncio
async def test_deepseek_translate_basic(mock_openai_async):
    provider = DeepSeekProvider(api_key="test-key")
    result = await provider.translate("Hello world")
    assert result.translation == "你好世界"
    assert result.provider_name == "deepseek"
```

集成测试 (跑真实 API) 同样改 async, 但仍保持 9 corpus 测试 (或可用的)。

### 3.5 Wave 2 完成报告

```
=== Wave 2 完成 ===
- DeepSeek provider 改 async (AsyncOpenAI)
- Claude provider 改 async (AsyncAnthropic)
- Qwen3 provider 改 async (asyncio.to_thread wrap DashScope)
- 单元测试改写完成: <数> pass
- 集成测试 (真实 API):
  - DeepSeek: <pass/fail>
  - Claude: <pass/fail/quota>
  - Qwen3: <pass/fail>
- commit: <hash>
```

---

## §4 Wave 3 — translate_document_async + format handlers

### 4.1 加 async 版顶层入口

```python
# oprim/translate/__init__.py 修订

# 保留原 sync 版作向后兼容 (deprecation warning)
import warnings

def translate_document(...) -> ...:
    """[Deprecated, use translate_document_async] Sync wrapper"""
    warnings.warn(
        "translate_document (sync) is deprecated, use translate_document_async. "
        "Sync API will be removed in next minor version.",
        DeprecationWarning,
        stacklevel=2,
    )
    import asyncio
    return asyncio.run(translate_document_async(...))


async def translate_document_async(
    text: str,
    format: str,
    provider: TranslationProvider,
    ...
) -> str:
    """新 async 版本, 主要入口"""
    ...
```

### 4.2 format handlers 改 async

```python
# oprim/translate/format_md.py
async def translate_markdown_async(
    text: str,
    provider: TranslationProvider,
    chunker: TranslationChunker | None = None,
    checkpoint: TranslationCheckpoint | None = None,
    terminology: TerminologyGlossary | None = None,
) -> str:
    """async 版本, async-iterate chunks"""
    chunker = chunker or TranslationChunker()
    chunks = chunker.chunk(text, format="markdown")
    
    translations = {}
    for ch in chunks:
        # 跳过已完成 (resume from checkpoint)
        if checkpoint and ch.chunk_id in checkpoint.get_completed_chunks():
            translations[ch.chunk_id] = checkpoint.get_completed_chunks()[ch.chunk_id]["translation"]
            continue
        
        # build context
        ctx = build_context(translations, chunks, ch.index, terminology)
        
        # 关键: await provider.translate(...)
        result = await provider.translate(
            text=ch.text,
            context=ctx,
            terminology=terminology.as_dict() if terminology else None,
        )
        
        translations[ch.chunk_id] = result.translation
        if checkpoint:
            checkpoint.save_chunk(ch.chunk_id, result)
        if terminology:
            terminology.update(result.extracted_terminology)
    
    return reassemble_markdown(chunks, translations)


# 保留 sync 版
def translate_markdown(...) -> str:
    """Deprecated sync wrapper"""
    warnings.warn("Use translate_markdown_async", DeprecationWarning, stacklevel=2)
    import asyncio
    return asyncio.run(translate_markdown_async(...))
```

### 4.3 translate_epub 同样改造

EPUB 处理跟 markdown 同模式, 但 chapter 级别 async iteration。

### 4.4 Wave 3 完成报告

```
=== Wave 3 完成 ===
- translate_document_async (主入口) 实施
- translate_markdown_async + sync deprecated wrapper
- translate_epub_async + sync deprecated wrapper
- DeprecationWarning 在 sync 调用时正确触发
- 测试覆盖率: <%>
- commit: <hash>
```

---

## §5 Wave 4 — oskill 切换到 async

### 5.1 oskill.knowledge.translate_substrate 改造

```python
# oskill/knowledge/translate_substrate.py 修订

async def translate_substrate(
    substrate_id: str,
    target_lang: str = "zh-CN",
    provider_hint: str | None = None,
    quality: str = "balanced",
    embed_translation: bool = True,
) -> dict:
    """
    端到端翻译, 全 async 路径.
    """
    # ... (前面 fetch substrate / detect language 等不变) ...

    # 关键改动: 调 async 版
    translated_text = await translate_document_async(
        text=source_text,
        format=format_name,
        provider=provider,
        chunker=chunker,
        checkpoint=checkpoint,
        terminology=terminology,
    )
    
    # ... (写 derivative / embed 等不变) ...
```

### 5.2 验证 oskill 测试

跑 oskill.knowledge 全量测试, 确保无 regression。

### 5.3 Wave 4 完成报告

```
=== Wave 4 完成 ===
- oskill.knowledge.translate_substrate 改调 async 版
- oskill 测试 <数> pass / 0 regressions
- 端到端 demo 跑通 (用 Phase 10 验证用的英文 substrate)
- commit: <hash>
```

---

## §6 Wave 5 — Gate 验收

### 6.1 验收矩阵

| 验收项 | 通过标准 |
|---|---|
| 4 provider 全 async | inspect.iscoroutinefunction 验证 |
| sync API 保留 + DeprecationWarning | filterwarnings 测试 |
| Router 路由仍正确 | 单元测试 |
| translate_document_async 工作 | 端到端 |
| oskill.knowledge.translate_substrate 用 async 路径 | 端到端 |
| 全量回归 0 regressions | oprim + oskill 完整跑 |
| 测试覆盖率 ≥ 80% (新代码) | pytest-cov |
| Phase 10 端到端 demo 仍可重现 | 跑一段英文翻译 |
| version bump: 2.4.0 → 2.5.0 (oprim) | pyproject.toml + _version.py |
| version bump: 2.4.0 → 2.4.1 (oskill) | pyproject.toml + _version.py |
| tag: v2.5.0-async-refactor (oprim) | git tag |
| tag: v2.4.1-async-refactor (oskill) | git tag |

### 6.2 完工报告格式

```
=== ADR-020 async 重构完工报告 ===

baseline: oprim 2.4.0 / oskill 2.4.0
完工: oprim 2.5.0 / oskill 2.4.1

完工内容:
- TranslationProvider Protocol async 化
- 4 provider 全 async (DeepSeek/Claude/Qwen3 + Gemini 在 a105075 已删, 不在 scope)
  *注: 实际 3 个 provider, 因为 Gemini 已被 R-4 cleanup 删除
- translate_document_async (新主入口) + sync wrapper (deprecated)
- format handlers async (markdown + epub)
- oskill.knowledge.translate_substrate 切到 async 路径

测试:
- oprim.translate: <数> tests, <%> coverage, 0 failed
- oprim 全量回归: <数> tests, 0 regressions
- oskill 全量回归: <数> tests, 0 regressions

集成测试 (真实 API):
- DeepSeek: <pass/fail + 数字>
- Claude: <pass/fail (可能配额仍未恢复)>
- Qwen3: <pass/fail + 数字>

sync API 向后兼容:
- 调用 translate_document() 触发 DeprecationWarning ✓
- 行为不变, 内部 asyncio.run(translate_document_async()) ✓
- 测试覆盖向后兼容路径 ✓

tags:
- oprim v2.5.0-async-refactor (<hash>)
- oskill v2.4.1-async-refactor (<hash>)

ADR-020 技术债务已偿还, 可启动 Phase 11.
```

---

## §7 异常处理

**立即停止 + 报告**:
- baseline 跟预期严重不符 (e.g. providers 已经是 async, 说明前序 CC 偷偷改了)
- DashScope to_thread 包装后阻塞主线程 (asyncio 死锁)
- sync wrapper 调用导致 nested event loop 错误
- Phase 10 端到端 demo 重现失败

**非阻塞**:
- DeprecationWarning 触发不影响功能, 只记录
- Claude API 配额仍未恢复 (走 mock 测试)

---

**预估工程量**: 3-5 天

Wave 1 (protocol + router): 0.5 天
Wave 2 (3 provider async): 1.5 天
Wave 3 (translate_document_async + formats): 1 天
Wave 4 (oskill 切换): 0.5 天
Wave 5 (Gate 验收): 0.5 天

---

**End of ADR_020_ASYNC_REFACTOR_INSTRUCTIONS_v0.1.md**
