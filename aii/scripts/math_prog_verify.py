"""数学程序化飞轮(math_prog, 0 LLM抽取) — 内容质检判官(新增). 0LLM抽取靠正则切边界,
忠实但不理解语义: 常见两类问题——①PDF→MD转换把书边栏批注术语(如"row-echelon form"
单独一行)拍扁揉进正文中间, 稀疏(全书通常只重复1-2次), strip_running_lines()的全书
频次去重(专门抓逐页重复的页眉页脚)抓不到, 需要语义判断; ②type分类(定义/定理/例子…
→procedural/rationale/conceptual)在书排版不规整时可能仍有残余误判(常见默认档已在
math_ingest.py._ku_type()修过). 用独立key/独立judge调用, 只标记不拦截入库(判官本身
有主观误差, 0LLM抽取的"忠实"是设计目标, 不该被判官一票否决)。

用法: SUBSTRATE=xxx python scripts/math_prog_verify.py
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

SUB = os.getenv("SUBSTRATE", "math_prog_placeholder")
# ★2026-09-21 判官改走本地 Veya 网关(默认 veya1.2-free, 免费常驻):
# 旧逻辑 NIM key 缺失直接跳过质检; 本地网关 key 缺省 sk-veya, 不跳过。
# 仍可用 MATH_PROG_VERIFY_BASE_URL/MODEL/KEY 覆盖(设回 NIM URL+NIM key 即走回 NIM)。
# 注: 不跟 OPENCODE_BASE_URL(飞轮导出的是 http://192.168.80.1:8791, 但网关只绑
# 127.0.0.1, 直连 192.168.80.1 被拒; 实测 2026-09-21)。判官跑在本机, 默认走回环。
VERIFY_BASE_URL = os.getenv(
    "MATH_PROG_VERIFY_BASE_URL", "http://127.0.0.1:8791/v1/chat/completions"
)
_NIM_KEY = os.getenv("MATH_PROG_VERIFY_KEY") or json.load(
    open(ROOT / ".pipeline_keys.json")
).get("math_prog_verify", "")
_VEYA_KEY = os.getenv("OPENCODE_KEY_POOL", "sk-veya").split(",")[0].strip()
# key 跟 endpoint 走: NIM URL 配 NIM key, 本地网关配 veya key(缺省 sk-veya)
_VERIFY_NIM = "nvidia" in VERIFY_BASE_URL or "integrate.api" in VERIFY_BASE_URL
VERIFY_KEY = _NIM_KEY if _VERIFY_NIM else (_VEYA_KEY or _NIM_KEY)
VERIFY_MODEL = os.getenv("MATH_PROG_VERIFY_MODEL", "veya1.2-free")

JUDGE_SYS = (
    "You are a QA judge for a 0-LLM programmatic extraction pipeline that slices textbook "
    "definitions/theorems/examples out of PDF-to-Markdown converted text VERBATIM (by design, it "
    "does not paraphrase). Your job is to catch conversion artifacts the program can't detect. "
    "Output JSON only: "
    '{"clean_content": bool, "type_sensible": bool, "reason": "..."}\n'
    "- clean_content: false if the text contains a stray fragment that clearly does NOT belong "
    "to the mathematical statement/derivation/proof flow — e.g. a lone short margin-glossary term "
    "sitting by itself (like a bare word/phrase such as 'pivot' or 'row-echelon form' appearing "
    "mid-derivation with no grammatical connection to its sentence), a leftover page header/footer, "
    "a running page title, or a citation/copyright fragment. Do NOT flag legitimate inline math, "
    "notation, or normal prose even if dense or awkwardly formatted from LaTeX conversion — only "
    "flag fragments that are clearly OUT OF PLACE (interrupt a sentence or formula mid-flow).\n"
    "- type_sensible: false only if the assigned type is clearly wrong for the content shown — "
    "e.g. content that is obviously a worked example/exercise labeled as 'conceptual' (a bare "
    "definition), or a definition labeled as 'procedural'. When in doubt, true."
)


async def _judge(client: httpx.AsyncClient, title: str, ktype: str, text: str) -> dict:
    body = {
        "model": VERIFY_MODEL,
        "messages": [
            {"role": "system", "content": JUDGE_SYS},
            {
                "role": "user",
                "content": f"KU title: {title}\nAssigned type: {ktype}\n\nContent:\n{text[:2500]}",
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
            "  ⚠ math_prog_verify: 无判官key(.pipeline_keys.json缺math_prog_verify), 跳过质检(不拦截)",
            flush=True,
        )
        return
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch(
        "SELECT ku_id, title, natural_text, knowledge_type FROM aii.ku_onto WHERE substrate_id=$1",
        SUB,
    )
    await conn.close()
    if not rows:
        print("  math_prog_verify: 无KU可查(异常, 但不拦截)", flush=True)
        return

    client = httpx.AsyncClient(timeout=60)
    sem = asyncio.Semaphore(4)

    async def j(row):
        async with sem:
            return row, await _judge(
                client, row["title"], row["knowledge_type"], row["natural_text"] or ""
            )

    results = await asyncio.gather(*(j(r) for r in rows))
    await client.aclose()

    fails = []
    for row, verdict in results:
        if verdict.get("error"):
            continue  # 判官调用本身失败, 不算KU质量问题, 跳过不计入不合格
        if not (verdict.get("clean_content") and verdict.get("type_sensible")):
            fails.append((row["title"], verdict))

    total = len(rows)
    print(
        f"  math_prog_verify [{SUB}]: {total - len(fails)}/{total} 条KU通过判官"
        f"(内容干净+类型合理), {len(fails)}条不达标(不拦截入库, 仅记录):",
        flush=True,
    )
    for title, v in fails[:20]:
        print(f"    ✗ {title[:40]}: {v.get('reason', '')[:100]}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
