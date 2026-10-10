import asyncio
import concurrent.futures
import itertools
import os
import uuid
import logging
import threading
import httpx
from urllib.parse import urlparse
from obase import ProviderRegistry

# ★全局 Ollama 串行锁: 本地单 GPU 一次只能可靠跑 1 个 gemma 请求; 并发请求会让 gemma4
# 输出垃圾(如 '{"'). 管道多处 gather/Semaphore(synth=8, readout=∞, cross=5)对云端
# DeepSeek 没事, 但对本地 Ollama 必须串行. 在 caller 层加锁, 不必改各步骤并发参数.
_OLLAMA_CALL_LOCK = threading.Lock()

logger = logging.getLogger(__name__)


def _traj_fire_and_forget(
    phase: str, failure_mode: str, error_sig: str, context: dict | None = None
) -> None:
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


def _read_opencode_keys() -> str:
    """★2026-08-16 提速: 读 opencode-keys.txt **全部** key(逗号拼接) — 多 key 池轮换,
    分摊并发限流(2 key = 2× 并发容量; 此前只用第一行, 6 worker 并发撞同一 key 429)。
    兼容: 单 key 时行为不变; OPENCODE_KEY_POOL 环境变量可显式覆盖。"""
    pool = os.getenv("OPENCODE_KEY_POOL", "").strip()
    if pool:
        return pool
    try:
        from pathlib import Path as _P

        p = _P.home() / ".pi/agent/opencode-keys.txt"
        keys = [
            ln.strip()
            for ln in p.read_text().splitlines()
            if ln.strip() and not ln.strip().startswith("#")
        ]
        return ",".join(keys)
    except Exception:
        return ""


def _extract_content(resp) -> str:
    """v4-flash 等推理模型的 content 可能为空, 答案在 reasoning_content。"""
    try:
        msg = resp.json()["choices"][0]["message"]
    except Exception:
        return ""
    return msg.get("content") or msg.get("reasoning_content") or ""


def _fix_local_url(url: str) -> str:
    """★2026-09-21: 飞轮脚本默认 OPENCODE_BASE_URL=http://192.168.80.1:8791, 但 veya
    网关只绑 127.0.0.1(实测直连 192.168.80.1 被拒)。不断重试 5 次≈浪费 2.5min/调用后
    才落到 NIM fallback——合成实际全跑在 NIM 上, 还慢。回环归一, 一处修全部飞轮生效。"""
    return url.replace("192.168.80.1", "127.0.0.1") if url else url


def _make_deepseek_caller(
    api_key: str,
    model: str = "deepseek-v4-flash",
    base_url: str = "https://api.deepseek.com/chat/completions",
    rpm: float = 0,
    fallback: tuple[str, str, str] | list[tuple[str, str, str]] | None = None,
    # ★2026-10-01 支持多级 fallback(列表按序尝试); 传单个三元组向后兼容。
    key_pool_env: str = "NIM_KEY_POOL",  # ★2026-08-16: 多 key 池 env 名可配(opencode 用 OPENCODE_KEY_POOL)
) -> callable:
    """Return an async callable compatible with both omodul (messages/system/max_tokens kwargs)
    and the legacy synthesis_engine (single positional prompt string via executor).

    Signature: async (messages=None, *, system='', max_tokens=4096, **_) -> dict
    The returned dict has the Anthropic shape: {"content": [{"type": "text", "text": "..."}]}
    Legacy callers may also call the inner _call_sync_json(prompt: str) -> str directly.
    _call_sync_json uses response_format=json_object to fix ~70% retry rate in llm_extract_ku.
    _call_sync (used internally by _call_async for synthesis) does NOT force JSON mode.
    """
    # 本机 Veya 网关必须绕过 7890 代理；NIM/其它公网 fallback 仍需保留代理。
    # 仅依赖 NO_PROXY 很容易被飞轮脚本后续 export 覆盖，因此在 provider 层再兜底。
    _proxy_client = httpx.Client(trust_env=True, timeout=600)
    _direct_client = httpx.Client(trust_env=False, timeout=600)

    def _client_for(url: str):
        host = (urlparse(url).hostname or "").lower()
        return _direct_client if host in {"127.0.0.1", "localhost", "192.168.80.1"} else _proxy_client

    # ★2026-08-10 多 key 池轮询: NIM_KEY_POOL 存在时(逗号分隔), 每次请求/重试轮换 key —
    #   单 key 免费层 40/min 是 misc 781 次 504 的根因; 池化后总配额 = 40 × key数。
    _key_pool = [k for k in os.getenv(key_pool_env, "").split(",") if k.strip()] or [api_key]
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

    def _headers_for(url: str, key: str) -> dict:
        """请求头。opencode 端点要求 x-opencode-session, 缺了直接 400 拒绝路由。

        ★2026-09-29: opencode.ai/zen/go 对本项目所有请求返回
          HTTP 400 {"type":"MissingSessionID","message":"Request is missing
          x-opencode-session and cannot be routed efficiently"}
        —— 这是主 provider, 它一挂就 fallback 到 NIM; 而 NIM 的默认模型
        deepseek-ai/deepseek-v4-flash-0731 已于 2026-09-21 EOL(HTTP 410 Gone),
        两条路同时断 → 抽取全线拿不到 LLM → KU 停产 17.7 小时。
        实测补上该头后同一请求 HTTP 200 正常返回。
        """
        h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        if "opencode" in (urlparse(url).hostname or "").lower():
            h["x-opencode-session"] = os.getenv(
                "OPENCODE_SESSION_ID", f"aiii-{os.getpid()}-{uuid.uuid4().hex[:8]}"
            )
        return h

    def _sneaky(r) -> str:
        """尽力读出响应体文本, 用于识别"错误伪装成 200 内容"的响应."""
        try:
            return r.text or ""
        except Exception:  # noqa: BLE001
            return ""

    def _content_of(r) -> str:
        """只取 message.content(正式答案)。刻意【不】回退 reasoning_content——
        那是思考过程, 不是答案: 推理模型预算被吃光时 content=None 而 reasoning 有
        15k 字思考, 当成答案会让上层 json.loads 报 "Expecting value: char 0"。"""
        try:
            msg = r.json()["choices"][0]["message"]
        except Exception:  # noqa: BLE001
            return ""
        c = msg.get("content")
        return c if isinstance(c, str) else ""

    def _finish_of(r) -> str:
        try:
            return str(r.json()["choices"][0].get("finish_reason"))
        except Exception:  # noqa: BLE001
            return "?"

    def _post_with_retry(payload: dict, max_retries: int = 5):
        # ★429限流是瞬时的(尤其NIM key被econ_zh/misc/BU等多个进程共用, _throttle()只在
        # 单进程内生效, 挡不住跨进程撞车), 之前遇到429直接抛异常、整本书(哪怕[1/5]已经
        # 抽出了几十条好KU)被判 pipeline_error 永久放弃——实测撞过好几次。重试等窗口过去。
        # ★2026-08-04: 除429外, 网络层瞬时错误(服务器断连/连接重置/读超时等)同样会整本
        #   判 exit(2) 隔离——实测 misc 飞轮 34 本书全毁于 httpx.RemoteProtocolError。
        #   现在对 httpx.HTTPError(TransportError/RemoteProtocolError/ConnectError/Timeout
        #   等)一视同仁重试, 仅 4xx(除429)/5xx 非瞬时语义不重试。
        import re as _re
        import time as _t
        import httpx as _httpx

        # 网关在上游配额/限流时, 常把错误文本包成 HTTP 200 的 choices[].content
        _ERR_TEXT = _re.compile(
            r"rejected the request|usage limit has been reached|rate_limit_exceeded"
            r"|GoUsageLimitError|FreeTierError|insufficient_quota"
            r"|(?<!\w)model .{0,80}end of life"
            # veya 网关把内部兜底失败也包成 200 内容: "gpt-5.6-luna 兜底失败"
            r"|兜底失败|全部候选(模型)?无效|all candidates? invalid",
            _re.I,
        )

        def _fb_specs() -> list[tuple[str, str, str]]:
            """fallback 规范: 单个三元组 或 三元组列表(后者按序逐个尝试)."""
            if not fallback:
                return []
            if isinstance(fallback, (list, tuple)) and fallback and isinstance(fallback[0], (list, tuple)):
                return [tuple(x) for x in fallback]  # type: ignore[misc]
            return [tuple(fallback)]  # type: ignore[arg-type]

        # ★2026-10-04 兜底级专用超时/次数: 兜底上游(NIM 63~90s、CPA)本来就慢, 再叠上
        #   client 级 600s 超时, 一次兜底能空转十几分钟 —— 实测 BU 分批第二步在
        #   _post_with_retry × _fallback 的嵌套里29 分钟不出新日志(同一个 response id
        #   反复出现), 单本书 BU 收敛不了。兜底给独立且短得多的预算, 失败快、可观测。
        _fb_timeout = float(os.getenv("AII_LLM_FB_TIMEOUT", "120"))
        _fb_attempts = max(1, int(os.getenv("AII_LLM_FB_ATTEMPTS", "2")))

        def _fallback(payload: dict):
            specs = _fb_specs()
            if not specs:
                raise RuntimeError("LLM 主 provider 失败且无 fallback")
            import time as _t2

            last2 = None
            # ★2026-10-01 支持多级兜底: 按序逐个尝试, 前一个彻底失败才用后一个。
            #   实测各上游都会整片耗尽(veya-free 池候选轮换、openai 日配额、
            #   opencode-go 月配额、NIM 401), 单层兜底在这种局面下等于没有。
            for fb_url, fb_key, fb_model in specs:
                print(f"  ⚠ 主 LLM 重试耗尽 → fallback({fb_model})", flush=True)
                last2 = None
                for _attempt2 in range(_fb_attempts):
                    try:
                        _resp2 = _client_for(fb_url).post(
                            fb_url,
                            headers=_headers_for(fb_url, fb_key),
                            json={**payload, "model": fb_model},
                            timeout=_fb_timeout,
                        )
                        if _resp2.status_code >= 500 and _attempt2 < _fb_attempts - 1:
                            _t2.sleep(5 * (_attempt2 + 1))
                            continue
                        if _resp2.status_code >= 400:
                            last2 = _resp2.status_code
                            if _attempt2 >= _fb_attempts - 1:
                                break
                            _t2.sleep(5 * (_attempt2 + 1))
                            continue
                        # 兜底链路自身也可能"错误伪装成 200 内容", 同口径识别
                        _b2 = _sneaky(_resp2)
                        if _ERR_TEXT.search(_b2 or ""):
                            last2 = _b2[:100]
                            print(
                                f"  ⚠ fallback({fb_model}) 返回错误文本 → 试下一级: "
                                f"{_b2[:100]}",
                                flush=True,
                            )
                            break
                        # ★2026-10-03 同口径: 兜底级空 content 也不算成功, 继续下一级。
                        if not _content_of(_resp2).strip():
                            last2 = "空 content"
                            print(
                                f"  ⚠ fallback({fb_model}) 返回空 content → 试下一级",
                                flush=True,
                            )
                            break
                        return _resp2
                    except Exception as _e2:
                        last2 = _e2
                        if _attempt2 >= _fb_attempts - 1:
                            break
                        _t2.sleep(5 * (_attempt2 + 1))
                print(f"  ⚠ fallback({fb_model}) 也失败({str(last2)[:80]})", flush=True)
            raise RuntimeError(f"全部 {len(specs)} 级 fallback 均失败: {str(last2)[:80]}")

        # ★2026-10-04 主路单次超时/重试次数改为 env 可调: 推理模型在长提示词上一次要跑
        #   几十秒到几分钟, client 级 600s 兜底太宽, 一次卡死就把整批拖成几十分钟。
        #   BU 分批场景实测主路 35~75s 就该回, 给 180s 足够。
        _req_timeout = float(os.getenv("AII_LLM_TIMEOUT", "180"))
        _max_retries = max(1, int(os.getenv("AII_LLM_MAX_RETRIES", str(max_retries))))
        _empty_budget = max(0, int(os.getenv("AII_LLM_EMPTY_RETRY", "2")))
        _empty_left = [_empty_budget]

        for attempt in range(_max_retries):
            key = next(_key_iter)  # 轮换 key(池>1 时每次尝试用不同 key, 撞 504/429 换槽位)
            try:
                resp = _client_for(base_url).post(
                    base_url,
                    headers=_headers_for(base_url, key),
                    json=payload,
                    timeout=_req_timeout,
                )
            except _httpx.HTTPError as e:
                # 网络瞬时错误: 服务器断连/连接重置/超时 → 退避重试, 耗尽→fallback
                if attempt < _max_retries - 1:
                    wait = min(10 * (attempt + 1), 45)
                    print(
                        f"  ⚠ LLM网络错误({type(e).__name__}) 重试 {attempt + 1}/{_max_retries - 1} 等待{wait}s...",
                        flush=True,
                    )
                    _t.sleep(wait)
                    continue
                return _fallback(payload)
            if resp.status_code == 429 and attempt < _max_retries - 1:
                wait = float(resp.headers.get("retry-after", 0)) or min(15 * (attempt + 1), 60)
                _t.sleep(wait)
                continue
            # 5xx 服务端瞬时错误同样可重试
            # ★2026-09-27 退避从 min(15*(n+1),60)=15/30/45/60s 压到 5/10/15/20s:
            #   advmath 日志实测 53850 次 502 + 53808 次重试, 单轮空转 2.5~3 分钟才 fallback,
            #   并发 2 时 worker 绝大多数时间在 sleep。502 是上游瞬时抖动, 等 60s 没有意义。
            if resp.status_code >= 500 and attempt < _max_retries - 1:
                wait = min(5 * (attempt + 1), 20)
                print(
                    f"  ⚠ LLM服务端错误({resp.status_code}) 重试 {attempt + 1}/{_max_retries - 1} 等待{wait}s...",
                    flush=True,
                )
                _t.sleep(wait)
                continue
            if resp.status_code >= 400:
                # 4xx(非429, 如 401/404/400)不重试 → 直接 fallback
                return _fallback(payload)
            resp.raise_for_status()

            # ★2026-10-01 网关把上游错误【当正常内容】用 HTTP 200 返回, 于是
            #   上面所有状态码分支都不命中, fallback 永远不触发:
            #     200 {"choices":[{"message":{"content":"openai rejected the
            #          request (HTTP 429): {"error":{"message":"The usage limit
            #          has been reached","code":"rate_limit_exceeded"}}"}}]}
            #   实测后果: openai 配额早已耗尽, 但所有调用都被当成"成功且回复是
            #   这段错误文本" → 规划器解析不出 JSON → 报"规划未返回知识点",
            #   整章 FAILED, 而日志里既没有 429 也没有 fallback, 排查绕了很大弯。
            #   识别这类"错误伪装成内容"的响应, 当失败处理并走 fallback。
            _body = _sneaky(resp)
            if _ERR_TEXT.search(_body or ""):
                print(
                    f"  ⚠ 网关以 200 返回错误文本(配额/限流) → fallback: "
                    f"{_body[:110]}",
                    flush=True,
                )
                return _fallback(payload)
            # ★2026-10-03 空内容也是失败: 网关/推理模型在上游挤不进来、或预算被
            #   reasoning_content 吃光(finish_reason=length)时, 会回 200 但
            #   message.content 为空/None。之前这里直接 return resp →
            #   _extract_content 回退到 reasoning_content(思考过程), 调用方
            #   json.loads(思考) 抛 "Expecting value: line 1 column 1 (char 0)",
            #   generate_bu 记成 "学习层 JSON 解析失败" 并写空层, BU 静默变空壳
            #   (实测 10/11 个新 BU 是 insufficient_data)。空 content 当失败处理。
            #   注意只认 content: reasoning_content 是思考过程, 不是答案。
            if not _content_of(resp).strip():
                print(
                    f"  ⚠ 网关以 200 返回空 content(finish={_finish_of(resp)}) → fallback: "
                    f"{_body[:100]}",
                    flush=True,
                )
                # ★2026-10-04 先重试主路再兜底: finish=length 是"这个模型这次想太久",
                #   不是"这个上游挂了"—— 实测同提示词重试成功率约 80%。而一旦直接兜底,
                #   NIM(120s×2 读超时) + CPA(120s×2 全 429) 要空转 300~480s 几乎必然
                #   失败, BU 一步因此要 100 分钟(实测 05:10→06:14 才跑完一次尝试链),
                #   超过 ECON_PIPELINE_TIMEOUT=5400 被 SIGTERM。重试主路 ~40~70s 就换到
                #   一次成功, 便宜得多。
                _empty_left[0] -= 1
                if _empty_left[0] > 0 and attempt < _max_retries - 1:
                    _t.sleep(3)
                    continue
                return _fallback(payload)
            return resp
        # 循环耗尽(理论上不可达, 防御) → fallback
        return _fallback(payload)
        # ★2026-08-10 fallback 内部函数: NIM 任何失败(4xx/5xx/网络)耗尽重试后, 切本地 opencode 网关
        # ★轨迹埋点: 重试耗尽(失败事件落 aii.trajectory_logs)
        _traj_fire_and_forget(
            "llm_call",
            "llm_retry_exhausted",
            f"{type(last_err).__name__ if 'last_err' in dir() else 'exhausted'}",
            {
                "base_url": base_url,
                "model": model,
                "attempts": _max_retries,
                "last_status": getattr(last_err, "code", None) if "last_err" in dir() else None,
            },
        )
        raise RuntimeError("LLM 调用失败(无响应)")

    def _call_sync(prompt: str, max_tokens: int | None = None) -> str:
        """Synchronous DeepSeek call for synthesis (plain text, no JSON mode)."""
        _throttle()
        payload: dict = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        # ★2026-09-27 修: max_tokens 之前只在 _call_async 签名里被接收、函数体里从未使用,
        #   请求体根本不带该字段 → 各合成脚本传的 1100/3200 全是无效值, 上游按自己的默认
        #   输出上限截断, 双语("English then 中文")KU 的英文半边在词中间断掉, 被质检判退。
        #   实测 cs 日志 2666 个判退里 990 个(37%)是截断, 另有 724/1528 次整书 DONE: 0 KU。
        if max_tokens and max_tokens > 0:
            payload["max_tokens"] = int(max_tokens)
        resp = _post_with_retry(payload)
        return _extract_content(resp)

    def _call_sync_json(prompt: str, max_tokens: int = 0) -> str:
        """Synchronous DeepSeek call for extraction (JSON mode → eliminates markdown fence retries).

        max_tokens>0 时按调用点给定的预算走(见 generate_bu 的七项分批: 给 6000 而不是
        全局大值 —— 实测同一提示词下 6000 的 finish=stop 率 4/5, 32000 只有 ~1/4:
        网关把【总输出】夹在 ~16k, 推理长度随机 5.3k~15.2k, 给大预算反而让模型放心长想
        然后撞上限 content 空; 小预算把它逼着说结论)。
        """
        _throttle()
        _json_mt = int(max_tokens) or int(os.getenv("AII_LLM_JSON_MAX_TOKENS", "32000"))
        _payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        if _json_mt > 0:
            _payload["max_tokens"] = _json_mt
        resp = _post_with_retry(_payload)
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
            answer = await loop.run_in_executor(ex, _call_sync, combined, max_tokens)
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
        nim_model = os.getenv("NIM_MODEL", "deepseek-ai/deepseek-v4-flash-0731")
        nim_rpm = float(os.getenv("NIM_RPM", "36"))  # NIM 免费层 40/min, 留余量
        # ★2026-08-10 opencode-go(v4-flash, pi 同款) — 有 key 时升为主 provider(NIM 免费层
        #   504/限流是慢的根因); 端点/模型/key 与 ~/.pi/agent 配置一致, key 走 opencode-keys.txt 轮换
        oc_base = _fix_local_url(
            os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1/chat/completions")
        )
        oc_key = os.getenv("OPENCODE_API_KEY") or _read_opencode_key()
        oc_pool = os.getenv("OPENCODE_API_KEY") or _read_opencode_keys()  # ★全 key 池(2 key 轮换)
        oc_model = os.getenv("OPENCODE_MODEL", "deepseek-v4-flash")
        # ★2026-08-26: opencode.ai 对当前出口 IP 返回 CF 1010/403, 每次请求先空转 5 次
        #   重试再 fallback, 章节抽取几乎停滞。AII_LLM_PRIMARY=nim 可强制 NIM 为主。
        prefer_nim = os.getenv("AII_LLM_PRIMARY", "").strip().lower() in {
            "nim",
            "nvidia",
            "minimax",
        }
        if oc_pool and not os.getenv("OPENCODE_KEY_POOL"):
            os.environ["OPENCODE_KEY_POOL"] = oc_pool  # ★必须早于 caller 创建(内部读 env)
        # ★2026-10-01 第三道防线: CLIProxyAPI(本地 8317, Antigravity 订阅)。
        #   实测该端点 13 个模型里 3 个可用且 3/3 稳定: claude-sonnet-4-6(1.4s)、
        #   gpt-oss-120b-medium(1.5s)、claude-opus-4-6-thinking(3.2s);
        #   gemini 全系因地域封锁不可用("User location is not supported"),
        #   gpt-5.6-luna 配额冷却。claude-sonnet-4-6 抽中文知识点 7 点含 2 个
        #   rationale, 比 NIM nemotron(23s)还快 5 倍。
        #   之所以放最后: 它是本地服务, 只有在外部上游全挂时才该被用到。
        cpa_base = _fix_local_url(os.getenv("CPA_BASE_URL", "http://127.0.0.1:8317/v1/chat/completions"))
        cpa_key = os.getenv("CPA_API_KEY", "")
        cpa_model = os.getenv("CPA_MODEL", "claude-sonnet-4-6")
        cpa_spec = [(cpa_base, cpa_key, cpa_model)] if cpa_key else []

        # ★2026-10-03 NIM 也走key 池: .pipeline_keys.json 有 8 个 nvapi 槽位, 单 key
        #   免费层限流后整条链就断。_make_deepseek_caller 内部按 key_pool_env 逗号分隔轮换,
        #   且限流间隔按 60/(rpm×池大小) 摊薄(rpm=30 × 8 key → 0.25s/次)。
        nim_caller = _make_deepseek_caller(
            nim_key,
            model=nim_model,
            base_url="https://integrate.api.nvidia.com/v1/chat/completions",
            rpm=nim_rpm,
            key_pool_env="NIM_KEY_POOL",
            fallback=([(oc_base, oc_key, oc_model)] if oc_key else None) + cpa_spec,
        )
        ProviderRegistry.register("llm", "nim", nim_caller)
        if use_nim:
            if oc_key and not prefer_nim:
                # ★opencode v4-flash 主, NIM 免费层备用(平时不碰, 省限流)
                # ★2026-08-16 提速: key_pool_env=OPENCODE_KEY_POOL → 全部 opencode key 轮换,
                #   6 worker 并发不再撞同一 key 429 静默重试→NIM fallback 拖慢。
                oc_caller = _make_deepseek_caller(
                    oc_key,
                    model=oc_model,
                    base_url=oc_base,
                    rpm=0,
                    key_pool_env="OPENCODE_KEY_POOL",
                    fallback=[
                        (
                            "https://integrate.api.nvidia.com/v1/chat/completions",
                            nim_key,
                            nim_model,
                        )
                    ]
                    + cpa_spec,
                )
                ProviderRegistry.register("llm", "default", oc_caller)
                logger.info(
                    "opencode-go(%s) DEFAULT, fallback 链: NIM(%s)%s",
                    oc_model,
                    nim_model,
                    f" → CPA({cpa_model})" if cpa_spec else "",
                )
            else:
                ProviderRegistry.register("llm", "default", nim_caller)
                logger.info(
                    "NVIDIA NIM registered as DEFAULT: %s (prefer_nim=%s)", nim_model, prefer_nim
                )
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
        learning_model = os.getenv("LEARNING_NIM_MODEL", "deepseek-ai/deepseek-v4-flash-0731")
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

    # ★本地 Veya 免费池: 独立 provider，不依赖 NVIDIA_NIM_API_KEY 是否存在。
    # 8791 网关负责健康模型轮询与 gpt-5.6-luna 兜底；这里给 AII 一个可显式选择的
    # ``veya1.2-free`` provider，避免把免费池误当成 opencode-go 的单模型直连。
    local_veya_base = _fix_local_url(
        os.getenv("VEYA_LLM_BASE_URL", "http://192.168.80.1:8791/v1/chat/completions")
    )
    # 8791 网关的免费池在长提示词/并发下容易返回 502；稳定模型作为本地
    # Veya provider 的默认路由，仍保留 ``veya1.2-free`` 这个 provider 名称
    # 供旧调用方兼容。
    local_veya_model = os.getenv("VEYA_LLM_MODEL", "gpt-5.6-luna")
    local_veya_fallback = (
        ("https://integrate.api.nvidia.com/v1/chat/completions", nim_key, nim_model)
        if nim_key
        else None
    )
    local_veya_caller = _make_deepseek_caller(
        "sk-veya",
        model=local_veya_model,
        base_url=local_veya_base,
        fallback=local_veya_fallback,
        key_pool_env="VEYA_LLM_KEY_POOL",
    )
    ProviderRegistry.register("llm", "veya1.2-free", local_veya_caller)
    if os.getenv("AII_LLM_PRIMARY", "").strip().lower() in {
        "veya1.2-free",
        "veya-free",
        "local-veya",
    }:
        ProviderRegistry.register("llm", "default", local_veya_caller)
        logger.info("Veya local free pool registered as DEFAULT: %s @ %s", local_veya_model, local_veya_base)

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
            # CPU fallback 的一个批次可能超过默认 90s；过短会把正常忙碌误判为
            # unreachable，随后让章节重试/掉回错误路径。默认 300s，仍由调用方
            # 的章节超时和 healer 的“有生产连接不重启”策略兜底。
            embed_timeout = float(os.getenv("AII_EMBED_TIMEOUT", "300"))
            try:
                embedder = AiiRemoteEmbedder(
                    embed_url,
                    timeout=embed_timeout,
                    fallback_base_url="http://127.0.0.1:8102",
                )
            except TypeError:
                embedder = AiiRemoteEmbedder(embed_url, timeout=embed_timeout)
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
