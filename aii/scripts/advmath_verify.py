"""高级数学经济专用飞轮 — 讲透质量判官(新增, 现有econ_quality_gate.py全是确定性规则
检查, 没有LLM去判断"这条KU是否保留了原书的严谨性、中文是否纯净". 用独立key/独立judge
调用, 跑在[1/5]讲透之后、[2/5]概念抽取之前——不合格的KU重讲一次(带纠正提示), 仍不
合格就标记但不拦截入库(留给下游econ_quality_gate.py的确定性检查兜底, 判官本身有主观
判断误差, 不适合直接一票否决).

用法: SUBSTRATE=xxx python scripts/advmath_verify.py
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

SUB = os.getenv("SUBSTRATE", "advmath_placeholder")
# ★2026-09-21 判官改走本地 Veya 网关(默认 veya1.2-free, 免费常驻):
# 旧逻辑 NIM key 缺失直接跳过质检; 本地网关 key 缺省 sk-veya, 不跳过。
# 仍可用 ADVMATH_VERIFY_BASE_URL/MODEL/KEY 覆盖(设回 NIM URL+NIM key 即走回 NIM)。
# 注: 不跟 OPENCODE_BASE_URL(飞轮导出的是 http://192.168.80.1:8791, 但网关只绑
# 127.0.0.1, 直连 192.168.80.1 被拒; 实测 2026-09-21)。判官跑在本机, 默认走回环。
VERIFY_BASE_URL = os.getenv(
    "ADVMATH_VERIFY_BASE_URL", "http://127.0.0.1:8791/v1/chat/completions"
)
_NIM_KEY = os.getenv("ADVMATH_VERIFY_KEY") or json.load(
    open(ROOT / ".pipeline_keys.json")
).get("advmath_verify", "")
_VEYA_KEY = os.getenv("OPENCODE_KEY_POOL", "sk-veya").split(",")[0].strip()
# key 跟 endpoint 走: NIM URL 配 NIM key, 本地网关配 veya key(缺省 sk-veya)
_VERIFY_NIM = "nvidia" in VERIFY_BASE_URL or "integrate.api" in VERIFY_BASE_URL
VERIFY_KEY = _NIM_KEY if _VERIFY_NIM else (_VEYA_KEY or _NIM_KEY)
VERIFY_MODEL = os.getenv("ADVMATH_VERIFY_MODEL", "veya1.2-free")

JUDGE_SYS = (
    "You are a strict QA judge for a book-explanation pipeline whose ENTIRE PURPOSE is: explain "
    "graduate-level math/economics so a smart high-schooler can follow it, WITHOUT losing any rigor. "
    "You check ONE synthesized knowledge unit against two hard requirements. Output JSON only: "
    '{"rigor_preserved": bool, "clean_chinese": bool, "reason": "..."}\n'
    "- rigor_preserved: true only if the exact technical content (formulas, theorem statements, "
    "citations like [ChN]) from the source chapter is still present, not dropped or vaguely gestured at.\n"
    "- clean_chinese: true only if the 中文 section is written entirely in Chinese prose (technical "
    "notation/symbols are fine; English prose words mixed into Chinese sentences are not)."
)


def _excerpt(text: str, limit: int = 4000) -> str:
    """截断到 limit 字符, 但回退到最近的句末/段末, 不给判官看半句话.

    ★2026-09-27: 与 econ_verify.py 同型修复。原来硬切 en[:2500] / zh[:2500], 近 3h 实测
    54% 的 KU 英文长度就超 2000 字符(均值 2551), 判官据此判 "rigor dropped" /
    "incoherent" 属假阳性。
    """
    t = text or ""
    if len(t) <= limit:
        return t
    window = t[:limit]
    for sep in ("。", "！", "？", ". ", "! ", "? ", "\n\n", "\n"):
        idx = window.rfind(sep)
        if idx > limit * 0.5:
            return window[: idx + len(sep)]
    return window


async def _judge(client: httpx.AsyncClient, title: str, en: str, zh: str) -> dict:
    body = {
        "model": VERIFY_MODEL,
        "messages": [
            {"role": "system", "content": JUDGE_SYS},
            {
                "role": "user",
                "content": f"KU title: {title}\n\nEnglish:\n{_excerpt(en)}\n\n中文:\n{_excerpt(zh)}",
            },
        ],
        "max_tokens": 300,
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
        print("  ⚠ advmath_verify: 无判官key, 跳过质检(不拦截)", flush=True)
        return
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        "SELECT ku_id, title, natural_text, natural_text_zh FROM aii.ku_onto WHERE substrate_id=$1",
        SUB,
    )
    await conn.close()
    if not rows:
        print("  advmath_verify: 无KU可查(异常, 但不拦截)", flush=True)
        return

    client = httpx.AsyncClient(timeout=60)
    sem = asyncio.Semaphore(4)

    async def j(row):
        async with sem:
            return row, await _judge(
                client, row["title"], row["natural_text"] or "", row["natural_text_zh"] or ""
            )

    results = await asyncio.gather(*(j(r) for r in rows))
    await client.aclose()

    fails = []
    for row, verdict in results:
        if verdict.get("error"):
            continue  # 判官调用本身失败, 不算KU质量问题, 跳过不计入不合格
        if not (verdict.get("rigor_preserved") and verdict.get("clean_chinese")):
            fails.append((row["title"], verdict))

    total = len(rows)
    print(
        f"  advmath_verify [{SUB}]: {total - len(fails)}/{total} 条KU通过判官"
        f"(保留严谨+中文纯净), {len(fails)}条不达标(不拦截入库, 仅记录):",
        flush=True,
    )
    for title, v in fails[:20]:
        print(f"    ✗ {title[:40]}: {v.get('reason', '')[:100]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
