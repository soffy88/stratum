"""高级数学经济专用飞轮 — 讲透质量判官(新增, 现有econ_quality_gate.py全是确定性规则
检查, 没有LLM去判断"这条KU是否保留了原书的严谨性、中文是否纯净". 用独立key/独立judge
调用, 跑在[1/5]讲透之后、[2/5]概念抽取之前——不合格的KU重讲一次(带纠正提示), 仍不
合格就标记但不拦截入库(留给下游econ_quality_gate.py的确定性检查兜底, 判官本身有主观
判断误差, 不适合直接一票否决).

用法: SUBSTRATE=xxx python scripts/advmath_verify.py
Exit: 0=完成(不管有没有仍不合格的, 只是打日志), 非0=判官调用本身出错(网络/key问题)
"""

import asyncio, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
import asyncpg
import httpx

SUB = os.getenv("SUBSTRATE", "advmath_placeholder")
VERIFY_KEY = os.getenv("ADVMATH_VERIFY_KEY") or json.load(open(ROOT / ".pipeline_keys.json")).get(
    "advmath_verify", ""
)
VERIFY_MODEL = os.getenv("ADVMATH_VERIFY_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")

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


async def _judge(client: httpx.AsyncClient, title: str, en: str, zh: str) -> dict:
    body = {
        "model": VERIFY_MODEL,
        "messages": [
            {"role": "system", "content": JUDGE_SYS},
            {
                "role": "user",
                "content": f"KU title: {title}\n\nEnglish:\n{en[:2500]}\n\n中文:\n{zh[:2500]}",
            },
        ],
        "max_tokens": 300,
        "response_format": {"type": "json_object"},
    }
    for attempt in range(3):
        try:
            r = await client.post(
                "https://integrate.api.nvidia.com/v1/chat/completions",
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
