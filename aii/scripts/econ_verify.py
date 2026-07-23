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

import asyncio, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
import asyncpg
import httpx

SUB = os.getenv("SUBSTRATE", "econ_placeholder")
VERIFY_KEY = os.getenv("ECON_VERIFY_KEY") or json.load(open(ROOT / ".pipeline_keys.json")).get(
    "econ_verify", ""
)
VERIFY_MODEL = os.getenv("ECON_VERIFY_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")

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
    "inline; that is this pipeline's normal faithful style."
)


async def _judge(client: httpx.AsyncClient, title: str, ktype: str, en: str, zh: str) -> dict:
    body = {
        "model": VERIFY_MODEL,
        "messages": [
            {"role": "system", "content": JUDGE_SYS},
            {
                "role": "user",
                "content": f"KU title: {title}\nAssigned type: {ktype}\n\n"
                f"English:\n{en[:2000]}\n\n中文:\n{zh[:2000]}",
            },
        ],
        "max_tokens": 250,
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
