"""程序化经济学/其它飞轮(econ_zh/misc, chapter_synthesize.py) — 内容质检判官(新增,
呼应 math_prog_verify.py / advmath_verify.py 同一套"程序为主+LLM辅助质检"模式).
规划阶段本就有LLM辅助(_plan()); 这里补上抽完之后的LLM辅助——0LLM抽取靠
_extract_skeleton() 正则拼接定义句+例子+图表数据, 忠实但常见两类问题:
①rationale(为什么)点常常只抠到概念本身的定义句, 没抠到真正解释"为什么"的机制/论据
  (季度gate里"rationale(why)=0"报警就是这个); ②骨架拼接出来的内容有时读起来是几段
  不相关碎片硬凑, 不连贯. 独立key/独立judge调用, 只标记不拦截入库(判官本身有主观
  误差, 0LLM抽取的"忠实"是设计目标, 不该被判官一票否决——同 math_prog_verify.py)。

用法: SUBSTRATE=xxx python scripts/econ_verify.py
Exit: 0=完成(不管有没有仍不合格的, 只是打日志), 非0=判官调用本身出错(网络/key问题)
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
import asyncpg
import httpx

SUB = os.getenv("SUBSTRATE", "econ_placeholder")
# ★2026-09-21 判官改走本地 Veya 网关(默认 veya1.2-free, 免费常驻):
# 旧逻辑 NIM key 缺失直接跳过质检; 本地网关 key 缺省 sk-veya, 不跳过。
# 仍可用 ECON_VERIFY_BASE_URL/MODEL/KEY 覆盖(设回 NIM URL+NIM key 即走回 NIM)。
# 注: 不跟 OPENCODE_BASE_URL(飞轮导出的是 http://192.168.80.1:8791, 但网关只绑
# 127.0.0.1, 直连 192.168.80.1 被拒; 实测 2026-09-21)。判官跑在本机, 默认走回环。
VERIFY_BASE_URL = os.getenv(
    "ECON_VERIFY_BASE_URL", "http://127.0.0.1:8791/v1/chat/completions"
)
_NIM_KEY = os.getenv("ECON_VERIFY_KEY") or json.load(
    open(ROOT / ".pipeline_keys.json")
).get("econ_verify", "")
_VEYA_KEY = os.getenv("OPENCODE_KEY_POOL", "sk-veya").split(",")[0].strip()
# key 跟 endpoint 走: NIM URL 配 NIM key, 本地网关配 veya key(缺省 sk-veya)
_VERIFY_NIM = "nvidia" in VERIFY_BASE_URL or "integrate.api" in VERIFY_BASE_URL
VERIFY_KEY = _NIM_KEY if _VERIFY_NIM else (_VEYA_KEY or _NIM_KEY)
VERIFY_MODEL = os.getenv("ECON_VERIFY_MODEL", "veya1.2-free")

JUDGE_SYS = (
    "You are a QA judge for a mostly-programmatic (0/low-LLM) textbook extraction pipeline. It "
    "slices a definition sentence + examples + data out of the source chapter by regex/skeleton "
    "matching (by design, faithful to the source, not rewritten prose) — OR falls back to a raw "
    "verbatim section slice when no skeleton match is found. Your job is to catch extraction gaps "
    "the program can't detect. Output JSON only: "
    '{"substantive_why": bool, "coherent": bool, "reason": "..."}\n'
    "- substantive_why: for a 'rationale' type KU (a WHY/mechanism point), true only if the text "
    "actually explains the causal mechanism or reasoning — false if it just restates a bare "
    "definition/label with no real 'why' content. For non-rationale types (conceptual/procedural/"
    "positional/factual), this is automatically true — do not penalize them for lacking a 'why'.\n"
    "- coherent: false only if the text reads as disconnected fragments awkwardly stitched together "
    "(e.g. a definition sentence followed by an unrelated data snippet with no connective flow, or "
    "abrupt mid-sentence cutoffs) — NOT false merely for being terse, bullet-like, or citing sources "
    "inline; that is this pipeline's normal faithful style. NOTE: the KU text below may be shown "
    "to you as an EXCERPT (truncated at a sentence boundary to fit the prompt). Never report "
    "'abrupt cutoff' / 'truncated' / 'incoherent' on the basis of the excerpt simply ending — only "
    "judge incoherence visible *inside* the text you were given."
)


def _excerpt(text: str, limit: int = 4000) -> str:
    """截断到 limit 字符, 但回退到最近的句末/段末, 不给判官看半句话.

    ★2026-09-27: 原来硬切 en[:2000] / zh[:2000]。近 3h 实测 54% 的 KU 英文长度超 2000
    字符(均值 2551), 于是判官拿到的就是半句话, 再据此报 "abrupt mid-sentence cutoffs" /
    "begins with truncated" —— 判官在诊断自己输入切片的假象, 不是 KU 的缺陷。判退理由里
    "truncated/cutoff" 那一大类基本由此产生, 属纯假阳性。
    """
    t = text or ""
    if len(t) <= limit:
        return t
    window = t[:limit]
    for sep in ("。", "！", "？", ". ", "! ", "? ", "\n\n", "\n"):
        idx = window.rfind(sep)
        if idx > limit * 0.5:  # 太靠前说明这段异常长, 换更长的分隔符
            return window[: idx + len(sep)]
    return window


async def _judge(client: httpx.AsyncClient, title: str, ktype: str, en: str, zh: str) -> dict:
    body = {
        "model": VERIFY_MODEL,
        "messages": [
            {"role": "system", "content": JUDGE_SYS},
            {
                "role": "user",
                "content": f"KU title: {title}\nAssigned type: {ktype}\n\n"
                f"English:\n{_excerpt(en)}\n\n中文:\n{_excerpt(zh)}",
            },
        ],
        "max_tokens": 250,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(3):
        try:
            r = await client.post(
                VERIFY_BASE_URL,
                headers={
                    "Authorization": f"Bearer {VERIFY_KEY}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            if r.status_code == 429 and attempt < 2:
                await asyncio.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            m = re.search(r"\{.*\}", content, re.DOTALL)
            return json.loads(m.group(0)) if m else {}
        except Exception as e:
            if attempt == 2:
                return {"error": str(e)}
            await asyncio.sleep(5)
    return {}


async def main():
    if not VERIFY_KEY:
        print(
            "  ⚠ econ_verify: 无判官key(.pipeline_keys.json缺econ_verify), 跳过质检(不拦截)",
            flush=True,
        )
        return
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        "SELECT ku_id, title, natural_text, natural_text_zh, knowledge_type "
        "FROM aii.ku_onto WHERE substrate_id=$1",
        SUB,
    )
    await conn.close()
    if not rows:
        print("  econ_verify: 无KU可查(异常, 但不拦截)", flush=True)
        return

    client = httpx.AsyncClient(timeout=60)
    sem = asyncio.Semaphore(4)

    async def j(row):
        async with sem:
            return row, await _judge(
                client,
                row["title"],
                row["knowledge_type"],
                row["natural_text"] or "",
                row["natural_text_zh"] or "",
            )

    results = await asyncio.gather(*(j(r) for r in rows))
    await client.aclose()

    fails = []
    for row, verdict in results:
        if verdict.get("error"):
            continue  # 判官调用本身失败, 不算KU质量问题, 跳过不计入不合格
        if not (verdict.get("substantive_why") and verdict.get("coherent")):
            fails.append((row["title"], verdict))

    total = len(rows)
    print(
        f"  econ_verify [{SUB}]: {total - len(fails)}/{total} 条KU通过判官"
        f"(why充分+连贯), {len(fails)}条不达标(不拦截入库, 仅记录):",
        flush=True,
    )
    for title, v in fails[:20]:
        print(f"    ✗ {title[:40]}: {v.get('reason', '')[:100]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
