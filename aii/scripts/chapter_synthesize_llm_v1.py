"""新范式章节合成(讲透 + 防漏): 按章切 → 规划知识点 → 每点讲透合成(双语+溯源) → 完整性校验防漏 → 补漏.
★规划喂全章(不截断), 合成改定向窗口: intro[:1000] + section[pos-WIN_PRE:pos+WIN_POST].
  对齐数学管道已验证的 section-windowing 方式, 削减 ~78% _synth input token.
  窗口够覆盖: WIN_POST=20000 chars ≈ 3-4x 知识点平均展开长度; pos 找不到则 fallback 40K.
★防漏: 用 planning_completeness(确定性, 不靠LLM)对照"应有黑体术语/小节"查漏, 漏的补抽.
Usage: chapter_synthesize.py <chapter_n>

★恢复自 f49e97d(经济飞轮切换成"程序骨架0LLM"忠实模式前的最后一版真讲透). 现役
chapter_synthesize.py 的 _synth 已改0LLM逐字抠(靠 _section_end 找 ## 小标题/习题当边界),
遇到无markdown小标题的散文体书(如翻译版科普/教材)边界找不到→ 退化成"从这点抠到全章末尾",
同一章内各点互相包含、且带出章末back-matter。这类书用回这版真LLM讲透合成更合适。
配 scripts/synthesize_book_llm_v1.py 使用, 不改动现役3个飞轮依赖的 chapter_synthesize.py。
"""

import asyncio
import json
import os
import re
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
import pathlib as _pl
import importlib.util as _ilu


def _traj_async(phase: str, failure_mode: str, error_sig: str, context: dict | None = None) -> None:
    """章级失败事件异步落 trajectory_logs(不阻塞, 静默)。"""
    try:
        p = _pl.Path(__file__).resolve().parent / "traj_log.py"
        if not p.exists():
            return
        spec = _ilu.spec_from_file_location("traj_log_ch", p)
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        flywheel = os.getenv("AII_FLYWHEEL", "unknown")
        asyncio.get_event_loop().create_task(
            mod.traj_log(flywheel, phase, failure_mode, error_sig, context or {})
        )
    except Exception:  # noqa: BLE001
        pass


from chapter_ingest import slice_chapter, SM
from aii.api._provider import register_providers
from aii.service.planning_completeness import check_completeness
from obase import ProviderRegistry


async def _call_with_retry(llm, retries=4, base_delay=8, **kwargs):
    """★NIM免费key(econ)被econ-zh/misc两个现役飞轮共用, 36rpm预算三边抢——429/超时是
    正常的资源争用, 不是坏调用. 指数退避重试, 不让单次限流拖垮整章."""
    for attempt in range(retries):
        try:
            return await llm(**kwargs)
        except Exception as e:
            if attempt == retries - 1:
                # ★轨迹埋点: 章级 LLM 调用重试耗尽(failure_mode 按类型签名)
                _traj_async(
                    "synth_chapter",
                    "llm_timeout" if "timed out" in str(e).lower() else "llm_error",
                    f"{type(e).__name__}: {str(e)[:120]}",
                    {"retries": retries, "chapter": kwargs.get("chapter", "")},
                )
                raise
            msg = str(e)
            if "429" not in msg and "timed out" not in msg.lower() and "timeout" not in msg.lower():
                raise
            await asyncio.sleep(base_delay * (2**attempt))


# _plan 仍用全章分块喂(规划不截断, 不影响 token).
_CTX = 130000
# ★定向窗口参数 — 每个 KU 合成只喂知识点所在小节, 不喂整章.
_WIN_PRE = 500  # 知识点 pos 前的 chars(捕获定义/段落引入)
_WIN_POST = 20000  # 知识点 pos 后的 chars(覆盖完整展开; 经济教材典型KU展开 3-8K chars)
_WIN_FALLBACK = 40000  # pos 未找到时的 fallback 窗口大小(章首)

PLAN_SYS = (
    "You identify the knowledge points a textbook chapter DIRECTLY AND SUBSTANTIVELY teaches. "
    "Output valid JSON only."
    # ★2026-09-27 质量门把 `rationale(why)=0` 当硬性报警, 整本书因此被隔离。
    #   _PLAN_TYPES 放宽到五分类后 rationale 已可达, 但 PLAN_SYS 从未要求过它,
    #   选不选 rationale 全看模型即兴 —— 实测 119/227/329 个 KU 的书照样栽在这条上。
    #   这里把要求写进规划指令: 章节里凡有"为什么成立/为何如此/机制/论据"的论述,
    #   都要至少产出一个 rationale 点。
    " For every chapter, you MUST include at least one point of type 'rationale' whenever the "
    "chapter contains any WHY content at all (why it is true, why it works, the mechanism or "
    "reasoning behind it, the evidence/causal argument). If a chapter has no WHY content, then no "
    "rationale point is needed for it."
)
# ★type枚举独立成模块全局(同PLAN_SYS一样可被覆盖) ——_plan()原来把它硬编码在JSON schema
# 字符串里, 子模块(如chapter_synthesize_advmath.py)覆盖PLAN_SYS时很容易漏改这行, 导致LLM
# 被限定在窄枚举里, 下游_TYPE_MAP即使支持更多类型也收不到(2026-07-11实测: advmath频道
# rationale永远是0, 而落库_TYPE_MAP明明按五分类写的——根因就是这里没跟着一起覆盖).
# ⚠2026-09-27 修复(与 2026-07-11 对 advmath 的同型修复): 此前这里是窄枚举
#   "concept|principle|method", 而 _TYPE_MAP 把它映射成 conceptual/conceptual/procedural
#   —— **rationale 永远产不出来**。质量门要求 `rationale≠0`(六分类rationale≠0),
#   于是 cs/misc/edu 每一本书都必然 exit=1 → 隔离 → pass_registered 恒为 0,
#   KU 总量冻结(实测 41806 全程不涨)。DB 里那 10987 条 rationale 全部来自
#   econ/advmath 等用宽枚举的频道。枚举必须与 _TYPE_MAP 的键对齐。
_PLAN_TYPES = "conceptual|rationale|procedural|positional|factual"
SYN_SYS = (
    "You synthesize ONE thorough KU by INTEGRATING the chapter's material. Use ONLY the chapter text. "
    "Cite [Ch{n}]. Write ONLY what IS substantively covered — skip any facet absent from this chapter "
    "(do NOT write placeholder text like 'not covered'). Integration not creation. Bilingual EN+中文. "
    "★ The Chinese MUST be Simplified Chinese (简体中文) only — NEVER Traditional characters (禁止繁体字)."
)


def _facets(typ):
    return {
        # ★2026-09-27: _PLAN_TYPES 已放宽到五分类(见该处注释), 原来只有 concept/principle/method
        #   三个键, canonical 名会全部落到兜底串。两种命名都留着, 兼容旧 checkpoint。
        "conceptual": "WHAT(内涵essence/外延boundary), WHY(why true/important), HOW(how applied), 用处use",
        "rationale": "WHY(为什么成立/为何如此), 论据evidence/推理reasoning, 前提与边界, IMPLICATION(这意味着什么)",
        "procedural": "WHAT, WHEN(适用条件), HOW(步骤), WHY, 常见坑",
        "positional": "主张claim, 立场holder, 支撑理由, 反对意见, 适用边界",
        "factual": "事实fact, 数值/条件, 出处source, 意义significance",
        "concept": "WHAT(内涵essence/外延boundary/用处use), WHY(why true/important), HOW(how applied)",
        "principle": "WHAT(meaning), WHY(rationale/evidence), IMPLICATION(what follows)",
        "method": "WHAT, WHEN, HOW(steps), WHY",
    }.get(typ, "WHAT, WHY, HOW")


def _find_pos(text_lo: str, name: str) -> int:
    """在小写章文本中定位知识点名称的首次出现位置. 未找到返回 -1."""
    # 先搜全名(前30字符)
    pos = text_lo.find(name.lower()[:30])
    if pos >= 0:
        return pos
    # 搜最长有意义词(>4字符), 按长度降序
    for word in sorted(name.split(), key=len, reverse=True):
        if len(word) > 4:
            pos = text_lo.find(word.lower())
            if pos >= 0:
                return pos
    return -1


def _parse_points(text: str) -> list[dict]:
    """Parse planner output, including fenced JSON and common model schemas.

    Planning is a control-plane step: an unparseable response must not silently
    become an empty chapter.  Keep the normal ``points`` schema, but tolerate
    local/relay models that call the field ``concepts`` or return nested items.
    """
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
    except (TypeError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        for key in ("points", "concepts", "knowledge_points", "items"):
            points = data.get(key)
            if isinstance(points, list) and points:
                return [
                    {**p, "name": _point_name(p)}
                    for p in points
                    if isinstance(p, dict) and _point_name(p)
                ]

    out: list[dict] = []

    def walk(value):
        if isinstance(value, dict):
            name = _point_name(value)
            if name:
                out.append({"name": name, "type": value.get("type", "concept")})
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return out


def _point_name(point: dict) -> str:
    for key in ("name", "concept", "term", "point", "title", "topic"):
        value = point.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


async def _plan(llm, text, n):
    """规划仍喂全章(不截断); 额外为每个知识点定位 pos 供 _synth 用."""
    # Keep the instruction before source text and bound each request.  Several
    # gateways/models truncate long prompts; with the old whole-chapter prompt
    # the instruction was truncated away and every chapter became 0 points.
    prompt_limit = int(os.getenv("OLLAMA_PROMPT_CHARS", str(_CTX)))
    chunk_size = min(_CTX, max(8000, prompt_limit - 2500), int(os.getenv("PLAN_CHUNK_CHARS", "14000")))
    chunks = [text] if len(text) <= chunk_size else [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]
    plan_sem = asyncio.Semaphore(int(os.getenv("AII_PLAN_CONCURRENCY", "3")))

    async def plan_one(ck):
        async with plan_sem:
            content = (
                f"List ONLY the concepts this chapter DIRECTLY AND SUBSTANTIVELY teaches — "
                f"concepts with their own definition or ≥2 paragraphs of explanation. "
                f"EXCLUDE concepts merely mentioned in passing, used as 1-sentence examples, "
                f"or previewed/introduced for a later chapter. "
                f'Output JSON only: {{"points":[{{"name":"..","type":"{_PLAN_TYPES}"}}]}}\n\n'
                f"Chapter {n} text (part):\n\n{ck}"
            )
            # ★JSON解析失败(常见于长列表被max_tokens截断)重试1次, 而不是让整章直接FAILED
            # ★2026-09-27 1500 → 4000: 该值此前因 _call_async 丢弃 max_tokens 而空转,
            #   实际吃上游默认上限(实测 ~5.4k tokens)。_call_async 修通后 1500 会真的截断
            #   长知识点列表 → JSON 解析失败 → 整章 return [] → 0 KU。必须同步抬高。
            parsed = None
            for parse_attempt in range(2):
                r = await _call_with_retry(
                    llm,
                    messages=[{"role": "user", "content": content}],
                    system=PLAN_SYS,
                    max_tokens=4000,
                )
                t = "".join(
                    b.get("text", "") for b in r.get("content", []) if b.get("type") == "text"
                )
                parsed_points = _parse_points(t)
                if parsed_points:
                    return parsed_points
            return []

    planned = await asyncio.gather(*(plan_one(ck) for ck in chunks))
    pts = [p for chunk_points in planned for p in chunk_points]
    # dedup by normalized name (单复数/大小写归一)
    seen, out = set(), []
    for p in pts:
        k = re.sub(r"s\b", "", re.sub(r"\s+", " ", p.get("name", "").strip().lower()))[:40]
        if k and k not in seen:
            seen.add(k)
            out.append(p)
    # ★为每个知识点定位 pos (供 _synth 定向窗口用)
    text_lo = text.lower()
    for p in out:
        found = _find_pos(text_lo, p.get("name", ""))
        p["pos"] = found if found >= 0 else 0
    return out


async def _synth(llm, text, n, name, typ, pos: int = 0, narrow: bool = False):
    """★定向窗口合成: intro[:1000] + section[pos-WIN_PRE:pos+WIN_POST].
    pos 未找到(=0且非章首): fallback 到章首 40K chars."""
    if pos > 0:
        intro = text[:1000]  # 章首记号/约定上下文
        post = 6000 if narrow else _WIN_POST
        section = text[max(0, pos - _WIN_PRE) : pos + post]  # 定向窗口
        context = (
            f"Chapter {n} opening (notation/context):\n\n{intro}\n\nRelevant section:\n\n{section}"
        )
    else:
        # pos 未定位: 用章首 fallback(覆盖最密集的引入段落)
        context = f"Chapter {n} text (opening):\n\n{text[:_WIN_FALLBACK]}"
    r = await _call_with_retry(
        llm,
        messages=[
            {
                "role": "user",
                "content": f'{context}\n\nSynthesize ONE thorough KU for: "{name}" (type={typ}). '
                f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets (do not write 'not covered'). English then 中文.",
            }
        ],
        system=SYN_SYS.format(n=n),
        # ★2026-09-27 1100 → 3200: 双语("English then 中文")逐 facet 展开, 1100 不够写完
        #   英文半边就被上游截断(质检判退语高频"ends abruptly mid-word")。3200 取自
        #   chapter_synthesize_advmath.py:96 的实测结论(2200 仍会截断)。此前该值因
        #   _call_async 丢弃 max_tokens 而完全无效, 修通后此处才真正起作用。
        max_tokens=3200,
    )
    text_out = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
    # ★Grounded 协议(A1): 从合成窗口原文确定性提取证据句(零 LLM, 不依赖模型输出)
    from ku_schema import extract_evidence_quotes

    try:
        quotes = extract_evidence_quotes(section if pos > 0 else text[:_WIN_FALLBACK], name)
    except Exception:  # noqa: BLE001
        quotes = []
    return name, text_out, quotes, (section if pos > 0 else text[:_WIN_FALLBACK])


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    text = slice_chapter(SM.read_text(encoding="utf-8", errors="replace"), n)
    print(f"chapter {n}: {len(text)} chars", flush=True)
    points = await _plan(llm, text, n)
    print(f"planned {len(points)} knowledge points", flush=True)
    for p in points:
        print(f"  {p['name']}: pos={p.get('pos', 0)}", flush=True)
    sem = asyncio.Semaphore(8)

    async def s(p):
        async with sem:
            return await _synth(llm, text, n, p["name"], p.get("type", "concept"), p.get("pos", 0))

    kus = await asyncio.gather(*(s(p) for p in points))
    names = [k for k, *_ in kus]
    # ★防漏: 完整性校验
    comp = check_completeness(text, names)
    print(
        f"completeness: {comp['covered_terms']}/{comp['total_terms']} terms; "
        f"complete={comp['complete']} missing={comp['missing_bold_terms']}",
        flush=True,
    )
    # 补漏: 搜 pos 后再调 _synth
    if comp["missing_bold_terms"]:
        text_lo = text.lower()
        fill_pts = []
        for t in comp["missing_bold_terms"]:
            pos = _find_pos(text_lo, t)
            fill_pts.append(
                {"name": t.title(), "type": "concept", "pos": max(0, pos) if pos >= 0 else 0}
            )
        fill = await asyncio.gather(*(s(p) for p in fill_pts))
        kus = list(kus) + list(fill)
        print(f"backfilled {len(fill)} missing → total {len(kus)} KUs", flush=True)
    import os

    Path(os.getenv("PIPELINE_CKPT_DIR", "/tmp") + f"/ch{n}_synth.md").write_text(
        "\n\n".join(f"### {nm}\n{body}" for nm, body in kus), encoding="utf-8"
    )
    print(f"DONE: {len(kus)} thorough KUs (complete after backfill)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
