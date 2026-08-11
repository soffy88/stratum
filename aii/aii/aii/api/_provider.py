import asyncio
import concurrent.futures
import itertools
import os
import logging
import threading
import httpx
from obase import ProviderRegistry
from oprim import vector_encode

# ★全局 Ollama 串行锁: 本地单 GPU 一次只能可靠跑 1 个 gemma 请求; 并发请求会让 gemma4
# 输出垃圾(如 '{"'). 管道多处 gather/Semaphore(synth=8, readout=∞, cross=5)对云端
# DeepSeek 没事, 但对本地 Ollama 必须串行. 在 caller 层加锁, 不必改各步骤并发参数.
_OLLAMA_CALL_LOCK = threading.Lock()

logger = logging.getLogger(__name__)


def _traj_fire_and_forget(phase: str, failure_mode: str, error_sig: str,
                          context: dict | None = None) -> None:
    """失败事件异步落 trajectory_logs(不阻塞主流程, 任何异常静默)。"""
    import importlib.util as _ilu
    import pathlib as _pl
    try:
        p = _pl.Path(__file__).resolve().parents[3] / "scripts" / "traj_log.py"
        if not p.exists():
            return
        spec = _ilu.spec_from_file_location("traj_log_embed", p)
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        flywheel = os.getenv("AII_FLYWHEEL", "unknown")
        asyncio.get_event_loop().create_task(
            mod.traj_log(flywheel, phase, failure_mode, error_sig, context or {})
        )
    except Exception:  # noqa: BLE001 — 埋点绝不影响主流程
        pass


def _read_opencode_key() -> str:
    """读 pi 的 opencode-keys.txt(第一行非注释 key, 轮换友好)。"""
    try:
        from pathlib import Path as _P
        p = _P.home() / ".pi/agent/opencode-keys.txt"
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    except Exception:
        pass
    return ""


def _extract_content(resp) -> str:
    """v4-flash 等推理模型的 content 可能为空, 答案在 reasoning_content。"""
    try:
        msg = resp.json()["choices"][0]["message"]
    except Exception:
        return ""
    return (msg.get("content") or msg.get("reasoning_content") or "")

def _make_deepseek_caller(
    api_key: str,
    model: str = "deepseek-v4-flash",
    base_url: str = "https://api.deepseek.com/chat/completions",
    rpm: float = 0,
    fallback: tuple[str, str, str] | None = None,
) -> callable:
    """Return an async callable compatible with both omodul (messages/system/max_tokens kwargs)
    and the legacy synthesis_engine (single positional prompt string via executor).

    Signature: async (messages=None, *, system='', max_tokens=4096, **_) -> dict
    The returned dict has the Anthropic shape: {"content": [{"type": "text", "text": "..."}]}
    Legacy callers may also call the inner _call_sync_json(prompt: str) -> str directly.
    _call_sync_json uses response_format=json_object to fix ~70% retry rate in llm_extract_ku.
    _call_sync (used internally by _call_async for synthesis) does NOT force JSON mode.
    """
    _client = httpx.Client(trust_env=True, timeout=600)

    # ★2026-08-10 多 key 池轮询: NIM_KEY_POOL 存在时(逗号分隔), 每次请求/重试轮换 key —
    #   单 key 免费层 40/min 是 misc 781 次 504 的根因; 池化后总配额 = 40 × key数。
    _key_pool = [k for k in os.getenv("NIM_KEY_POOL", "").split(",") if k.strip()] or [api_key]
    _key_iter = itertools.cycle(_key_pool)

    # ★全局限流: NVIDIA NIM 免费层 40 req/min. rpm>0 时所有并发调用排队, 间隔 60/rpm 秒,
    #   防 readout(无限并发)等步骤爆 429. 给每个调用分配一个时间槽, 锁外 sleep.
    _min_int = (60.0 / (rpm * len(_key_pool))) if rpm else 0.0
    _rl_lock = threading.Lock()
    _rl_next = [0.0]

    def _throttle() -> None:
        if not _min_int:
            return
        import time as _t

        with _rl_lock:
            start = max(_t.monotonic(), _rl_next[0])
            _rl_next[0] = start + _min_int
        w = start - _t.monotonic()
        if w > 0:
            _t.sleep(w)

    def _post_with_retry(payload: dict, max_retries: int = 5):
        # ★429限流是瞬时的(尤其NIM key被econ_zh/misc/BU等多个进程共用, _throttle()只在
        # 单进程内生效, 挡不住跨进程撞车), 之前遇到429直接抛异常、整本书(哪怕[1/5]已经
        # 抽出了几十条好KU)被判 pipeline_error 永久放弃——实测撞过好几次。重试等窗口过去。
        # ★2026-08-04: 除429外, 网络层瞬时错误(服务器断连/连接重置/读超时等)同样会整本
        #   判 exit(2) 隔离——实测 misc 飞轮 34 本书全毁于 httpx.RemoteProtocolError。
        #   现在对 httpx.HTTPError(TransportError/RemoteProtocolError/ConnectError/Timeout
        #   等)一视同仁重试, 仅 4xx(除429)/5xx 非瞬时语义不重试。
        import time as _t
        import httpx as _httpx

        def _fallback(payload: dict):
            if not fallback:
                raise RuntimeError("LLM 主 provider 失败且无 fallback")
            fb_url, fb_key, fb_model = fallback
            import time as _t2
            print(f"  ⚠ NIM 重试耗尽 → fallback opencode({fb_model})", flush=True)
            last2 = None
            for _attempt2 in range(3):
                try:
                    _resp2 = _client.post(
                        fb_url,
                        headers={"Authorization": f"Bearer {fb_key}",
                                 "Content-Type": "application/json"},
                        json={**payload, "model": fb_model},
                    )
                    if _resp2.status_code >= 500 and _attempt2 < 2:
                        _t2.sleep(5 * (_attempt2 + 1))
                        continue
                    if _resp2.status_code >= 400:
                        last2 = _resp2.status_code
                        if _attempt2 >= 2:
                            break
                        _t2.sleep(5 * (_attempt2 + 1))
                        continue
                    return _resp2
                except Exception as _e2:
                    last2 = _e2
                    if _attempt2 >= 2:
                        break
                    _t2.sleep(5 * (_attempt2 + 1))
            raise RuntimeError(f"fallback opencode 失败: {str(last2)[:80]}")


        for attempt in range(max_retries):
            key = next(_key_iter)  # 轮换 key(池>1 时每次尝试用不同 key, 撞 504/429 换槽位)
            try:
                resp = _client.post(
                    base_url,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json=payload,
                )
            except _httpx.HTTPError as e:
                # 网络瞬时错误: 服务器断连/连接重置/超时 → 退避重试, 耗尽→fallback
                if attempt < max_retries - 1:
                    wait = min(10 * (attempt + 1), 45)
                    print(f"  ⚠ LLM网络错误({type(e).__name__}) 重试 {attempt + 1}/{max_retries - 1} 等待{wait}s...", flush=True)
                    _t.sleep(wait)
                    continue
                return _fallback(payload)
            if resp.status_code == 429 and attempt < max_retries - 1:
                wait = float(resp.headers.get("retry-after", 0)) or min(15 * (attempt + 1), 60)
                _t.sleep(wait)
                continue
            # 5xx 服务端瞬时错误同样可重试
            if resp.status_code >= 500 and attempt < max_retries - 1:
                wait = min(15 * (attempt + 1), 60)
                print(f"  ⚠ LLM服务端错误({resp.status_code}) 重试 {attempt + 1}/{max_retries - 1} 等待{wait}s...", flush=True)
                _t.sleep(wait)
                continue
            if resp.status_code >= 400:
                # 4xx(非429, 如 401/404/400)不重试 → 直接 fallback
                return _fallback(payload)
            resp.raise_for_status()
            return resp
        # 循环耗尽(理论上不可达, 防御) → fallback
        return _fallback(payload)
        # ★2026-08-10 fallback 内部函数: NIM 任何失败(4xx/5xx/网络)耗尽重试后, 切本地 opencode 网关
        # ★轨迹埋点: 重试耗尽(失败事件落 aii.trajectory_logs)
        _traj_fire_and_forget(
            "llm_call", "llm_retry_exhausted",
            f"{type(last_err).__name__ if 'last_err' in dir() else 'exhausted'}",
            {"base_url": base_url, "model": model, "attempts": max_retries,
             "last_status": getattr(last_err, "code", None) if "last_err" in dir() else None},
        )
        raise RuntimeError("LLM 调用失败(无响应)")

    def _call_sync(prompt: str) -> str:
        """Synchronous DeepSeek call for synthesis (plain text, no JSON mode)."""
        _throttle()
        resp = _post_with_retry({"model": model, "messages": [{"role": "user", "content": prompt}]})
        return _extract_content(resp)

    def _call_sync_json(prompt: str) -> str:
        """Synchronous DeepSeek call for extraction (JSON mode → eliminates markdown fence retries)."""
        _throttle()
        resp = _post_with_retry(
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"},
            }
        )
        return _extract_content(resp)

    async def _call_async(messages=None, *, system: str = "", max_tokens: int = 4096, **_):
        """Async omodul-compatible LLM caller (Anthropic message format → Anthropic response dict).
        Uses plain-text _call_sync (not JSON mode) for synthesis compatibility."""
        parts: list[str] = []
        if system:
            parts.append(system)
        for msg in messages or []:
            if isinstance(msg, dict) and msg.get("role") == "user":
                parts.append(msg.get("content", ""))
        combined = "\n\n".join(p for p in parts if p)
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            answer = await loop.run_in_executor(ex, _call_sync, combined)
        # ★NIM API偶发返回 message.content=null(见 nemotron-super-49b reasoning 模型),
        #   None 会一路传到消费方的 "".join(...text...) 直接崩 "expected str, NoneType"。
        #   在源头挡掉, 消费方多处调用不用各自防御.
        return {"content": [{"type": "text", "text": answer or ""}]}

    # Extraction callers (llm_extract_ku) use call_sync → JSON mode
    _call_async.call_sync = _call_sync_json
    return _call_async


def _make_ollama_caller(
    model: str = "qwen2.5:7b", base_url: str = "http://localhost:11434"
) -> callable:
    """Return a caller backed by local Ollama.

    _call_async (synthesis path): plain text, no format=json, 8 k char limit.
    call_sync (extraction path, llm_extract_ku): format=json for clean JSON output.
    """
    _client = httpx.Client(trust_env=True, timeout=600)  # local models: 8 concurrent × ~60s each
    # 提示字符上限: qwen2.5:7b 默认 8000 够; 大context模型(gemma 128K)可经 env 调大避免裁掉WHY窗口/规划全章
    _max_chars = int(os.getenv("OLLAMA_PROMPT_CHARS", "8000"))

    def _call_sync(prompt: str) -> str:
        """KU 抽取用: format=json 强制结构化输出."""
        import time as _t
        import httpx as _httpx
        last_err = None
        for attempt in range(3):
            try:
                with _OLLAMA_CALL_LOCK:  # ★串行: 单 GPU 并发会让 gemma 输出垃圾
                    resp = _client.post(
                        f"{base_url}/api/generate",
                        json={
                            "model": model,
                            "prompt": prompt[:_max_chars],
                            "stream": False,
                            "format": "json",
                        },
                    )
                resp.raise_for_status()
                return resp.json()["response"]
            except _httpx.HTTPError as e:
                last_err = e
                if attempt < 2:
                    _t.sleep(5 * (attempt + 1))
        raise last_err

    def _call_sync_plain(prompt: str) -> str:
        """合成/纯文本用: 不加 format=json, 直接返回自然语言."""
        import time as _t
        import httpx as _httpx
        last_err = None
        for attempt in range(3):
            try:
                with _OLLAMA_CALL_LOCK:  # ★串行: 单 GPU 并发会让 gemma 输出垃圾
                    resp = _client.post(
                        f"{base_url}/api/generate",
                        json={"model": model, "prompt": prompt[:_max_chars], "stream": False},
                    )
                resp.raise_for_status()
                return resp.json()["response"]
            except _httpx.HTTPError as e:
                last_err = e
                if attempt < 2:
                    _t.sleep(5 * (attempt + 1))
        raise last_err

    async def _call_async(messages=None, *, system: str = "", max_tokens: int = 4096, **_):
        """Async wrapper. Uses JSON mode when system prompt requests structured JSON output."""
        parts: list[str] = []
        if system:
            parts.append(system)
        for msg in messages or []:
            if isinstance(msg, dict) and msg.get("role") == "user":
                parts.append(msg.get("content", ""))
        combined = "\n\n".join(p for p in parts if p)
        # Use JSON mode for planning/extraction; plain text for synthesis
        wants_json = "output valid json" in system.lower() or "output json" in system.lower()
        caller = _call_sync if wants_json else _call_sync_plain
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            answer = await loop.run_in_executor(ex, caller, combined)
        return {"content": [{"type": "text", "text": answer or ""}]}

    _call_async.call_sync = _call_sync  # extraction: JSON mode
    _call_async.call_sync_plain = _call_sync_plain  # dedup/plain-text
    return _call_async


def _pipeline_nim_key(name: str) -> str | None:
    """从 aii/.pipeline_keys.json 读命名 NIM key(飞轮共用的密钥池)。找不到返回 None。"""
    import json
    import pathlib

    for base in pathlib.Path(__file__).resolve().parents:
        f = base / ".pipeline_keys.json"
        if f.exists():
            try:
                return json.loads(f.read_text()).get(name) or None
            except Exception:
                return None
    return None


def register_providers():
    """Register computational providers for AII (A24 Routing).

    ECON_LLM_PROVIDER=ollama  → Ollama becomes the "default" provider (for local testing).
    OLLAMA_MODEL env var selects the model (default: qwen2.5:7b).
    """
    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    use_ollama_as_default = os.getenv("ECON_LLM_PROVIDER", "").lower() == "ollama"

    # 1. LLM Provider (DeepSeek v4) — default=flash (实测够用且最省); pro 备用
    #    deepseek-chat 别名 2026/07/24 下线, 已显式改 deepseek-v4-flash.
    api_key = os.getenv("DEEPSEEK_API_KEY")
    ProviderRegistry.register(
        "llm", "deepseek-flash", _make_deepseek_caller(api_key, model="deepseek-v4-flash")
    )
    ProviderRegistry.register(
        "llm", "deepseek-pro", _make_deepseek_caller(api_key, model="deepseek-v4-pro")
    )

    # ★NVIDIA NIM (云端 OpenAI 兼容; 快 + 可并发, 避开本地单 GPU 串行瓶颈, 无需 DeepSeek 余额).
    #   设 NVIDIA_NIM_API_KEY 即作 default(优先于 DeepSeek); 模型经 NIM_MODEL 选.
    nim_key = os.getenv("NVIDIA_NIM_API_KEY")
    use_nim = bool(nim_key) and not use_ollama_as_default
    if nim_key:
        # ★模型选型(2026-07-07实测对比, advmath频道发现): 默认 meta/llama-3.1-70b-instruct 讲得干、
        #   偶发限流; nemotron-super-49b 明显更好且更快/不容易被限流(小尺寸对同一免费层配额压力小)——
        #   econ_zh/misc/math_prog/advmath 四飞轮已各自显式设NIM_MODEL对齐, 这里改全局兜底默认值,
        #   让没显式设的调用方(如未来新脚本)也受益, 不用逐个飞轮脚本单独配.
        nim_model = os.getenv("NIM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
        nim_rpm = float(os.getenv("NIM_RPM", "36"))  # NIM 免费层 40/min, 留余量
        # ★2026-08-10 opencode-go(v4-flash, pi 同款) — 有 key 时升为主 provider(NIM 免费层
        #   504/限流是慢的根因); 端点/模型/key 与 ~/.pi/agent 配置一致, key 走 opencode-keys.txt 轮换
        oc_base = os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1/chat/completions")
        oc_key = os.getenv("OPENCODE_API_KEY") or _read_opencode_key()
        oc_model = os.getenv("OPENCODE_MODEL", "deepseek-v4-flash")
        nim_caller = _make_deepseek_caller(
            nim_key,
            model=nim_model,
            base_url="https://integrate.api.nvidia.com/v1/chat/completions",
            rpm=nim_rpm,
            fallback=((oc_base, oc_key, oc_model) if oc_key else None),
        )
        ProviderRegistry.register("llm", "nim", nim_caller)
        if use_nim:
            if oc_key:
                # ★opencode v4-flash 主, NIM 免费层备用(平时不碰, 省限流)
                oc_caller = _make_deepseek_caller(
                    oc_key, model=oc_model, base_url=oc_base, rpm=0,
                    fallback=("https://integrate.api.nvidia.com/v1/chat/completions",
                              nim_key, nim_model),
                )
                ProviderRegistry.register("llm", "default", oc_caller)
                logger.info("opencode-go(%s) DEFAULT, NIM fallback", oc_model)
            else:
                ProviderRegistry.register("llm", "default", nim_caller)
                logger.info("NVIDIA NIM registered as DEFAULT: %s", nim_model)
    if not use_ollama_as_default and not use_nim:
        ProviderRegistry.register(
            "llm", "default", _make_deepseek_caller(api_key, model="deepseek-v4-flash")
        )

    # ★学习助手专用 NIM provider(交互式 AI 教练/裁判/出题)——只影响学习模块, 后端 default
    #   (检索问答/入库/去重)保持不变。learning.py 调 llm("learning"); 未注册时注册表自动回落到
    #   default(DeepSeek), 安全。key 复用 econ(池在 aii/.pipeline_keys.json 的 learning 槽位, 可换独立key),
    #   可经 LEARNING_NIM_API_KEY / LEARNING_NIM_MODEL 覆盖。
    learning_key = (
        os.getenv("LEARNING_NIM_API_KEY")
        or _pipeline_nim_key("learning")
        or _pipeline_nim_key("econ")
    )
    if learning_key:
        learning_model = os.getenv("LEARNING_NIM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
        learning_rpm = float(os.getenv("LEARNING_NIM_RPM", "36"))  # NIM 免费层 40/min, 留余量
        ProviderRegistry.register(
            "llm",
            "learning",
            _make_deepseek_caller(
                learning_key,
                model=learning_model,
                base_url="https://integrate.api.nvidia.com/v1/chat/completions",
                rpm=learning_rpm,
            ),
        )
        logger.info("学习助手 NIM provider registered: %s", learning_model)

    # 2. LLM Provider (Ollama) — low-trust sources OR local testing (ECON_LLM_PROVIDER=ollama)
    try:
        ollama_caller = _make_ollama_caller(ollama_model, ollama_base)
        ProviderRegistry.register("llm", "ollama-local", ollama_caller)
        if use_ollama_as_default:
            ProviderRegistry.register("llm", "default", ollama_caller)
            logger.info("Ollama-local registered as DEFAULT: %s @ %s", ollama_model, ollama_base)
        else:
            logger.info("Ollama-local provider registered: %s @ %s", ollama_model, ollama_base)
    except Exception as e:
        logger.warning("Ollama-local registration failed (non-fatal): %s", e)
        if use_ollama_as_default:
            raise RuntimeError(f"ECON_LLM_PROVIDER=ollama but Ollama unavailable: {e}") from e

    # 3. Embedding Provider
    #    设 AII_EMBED_URL → 调共享 aii-embed 微服务(不在本进程加载模型, 去冗余/省内存);
    #    否则 → 进程内 BGE-M3(单机/服务未起时的兜底).
    embed_url = os.getenv("AII_EMBED_URL")
    try:
        if embed_url:
            from oprim.embedding.aii_remote import AiiRemoteEmbedder

            # ★降级链: 笔记本 GPU 服务间歇 502(idle-unload 重载窗口)时退到本机 8102。
            # 2026-08-10: 平台包 oprim 该版本 __init__ 只收 (base_url, timeout), 不认
            #   fallback_base_url → TypeError 导致嵌入 provider 注册失败; 参数兼容降级。
            try:
                embedder = AiiRemoteEmbedder(embed_url, fallback_base_url="http://127.0.0.1:8102")
            except TypeError:
                embedder = AiiRemoteEmbedder(embed_url)
            ProviderRegistry.register("embedding", "default", embedder.embed)
            logger.info("Remote embed Provider registered: %s (fallback 127.0.0.1:8102)", embed_url)
        else:
            from oprim.embedding.bge_m3 import BgeM3Embedder

            embedder = BgeM3Embedder()
            ProviderRegistry.register("embedding", "default", embedder.embed)
            logger.info("REAL BGE-M3 Provider registered (in-process).")
    except Exception as e:
        logger.error(f"Failed to register embedding provider: {e}")

    default_lbl = f"Ollama({ollama_model})" if use_ollama_as_default else "DeepSeek"
    logger.info("AII Providers registered: llm/default(%s), embedding/default", default_lbl)


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    register_providers()
    print(f"LLM default registered: {ProviderRegistry.has('llm', 'default')}")
    print(f"Embedding default registered: {ProviderRegistry.has('embedding', 'default')}")
