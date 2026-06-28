"""构建检索评测 golden set: 从已入库 KU 反向生成"自然问题→应命中KU".

方法(合成评测集, 业界标准): 抽样 KU → LLM 为该 KU 写一个学生会问的自然问题
(问题的答案正是这条知识) → (query, gold_ku_id) 即一条 golden.
分层抽样: 跨 substrate × knowledge_type, 避免偏向某书/某类.

用法: python3 scripts/eval/build_golden.py [N]   # 默认 60 条
  ECON_LLM_PROVIDER=ollama OLLAMA_MODEL=gemma4:e4b 用本地模型生成(离线/省钱)
输出: scripts/eval/golden.json
"""
import asyncio, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from aii.api._provider import register_providers
from obase import ProviderRegistry

OUT = ROOT / "scripts" / "eval" / "golden.json"
GEN_SYS = "You write one natural exam-style question a student would ask. Output the question only, no preamble."


async def _sample(conn, n: int) -> list[dict]:
    """分层抽样 n 条 KU: 每 (substrate, knowledge_type) 桶按比例取, 偏好内容充实的(zh 长)."""
    rows = await conn.fetch("""
        WITH ranked AS (
          SELECT ku_id, substrate_id, knowledge_type, title, natural_text, natural_text_zh,
                 row_number() OVER (PARTITION BY substrate_id, knowledge_type
                                    ORDER BY length(coalesce(natural_text_zh,'')) DESC) AS rn
          FROM aii.ku_onto
          WHERE natural_text IS NOT NULL
            AND length(coalesce(natural_text,'')) > 120
        )
        SELECT * FROM ranked WHERE rn <= 6 ORDER BY substrate_id, knowledge_type, rn
    """)
    # round-robin 跨桶取, 保证多样
    from collections import defaultdict
    buckets = defaultdict(list)
    for r in rows:
        buckets[(r["substrate_id"], r["knowledge_type"])].append(dict(r))
    out, keys = [], list(buckets)
    i = 0
    while len(out) < n and any(buckets[k] for k in keys):
        k = keys[i % len(keys)]
        if buckets[k]:
            out.append(buckets[k].pop(0))
        i += 1
    return out[:n]


async def _gen_q(llm, ku: dict) -> str | None:
    text = (ku.get("natural_text") or "")[:1200]
    title = ku.get("title") or ""
    r = await llm(messages=[{"role": "user", "content":
        f"Knowledge unit (title: {title}):\n{text}\n\n"
        f"Write ONE specific natural question whose answer is exactly this knowledge. "
        f"Do NOT mention 'the text'/'the chapter'. Make it standalone."}],
        system=GEN_SYS, max_tokens=120)
    q = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text").strip()
    q = re.sub(r'^(question|q)[:：]\s*', '', q, flags=re.I).strip().strip('"').split("\n")[0]
    return q if 8 < len(q) < 300 else None


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    kus = await _sample(conn, n)
    await conn.close()
    print(f"sampled {len(kus)} KUs across buckets", flush=True)
    sem = asyncio.Semaphore(3)  # 本地模型并发过高会 OOM/拒连; 降并发更稳
    async def one(ku):
        async with sem:
            q = None
            for attempt in range(3):  # 拒连/超时重试
                try:
                    q = await _gen_q(llm, ku)
                    break
                except Exception as e:
                    if attempt == 2:
                        print(f"  gen fail {ku['ku_id']}: {e}", flush=True)
                    await asyncio.sleep(1.5 * (attempt + 1))
            if not q:
                return None
            return {"query": q, "gold_ku_id": ku["ku_id"],
                    "substrate_id": ku["substrate_id"], "knowledge_type": ku["knowledge_type"],
                    "gold_title": ku.get("title")}
    golden = [g for g in await asyncio.gather(*(one(k) for k in kus)) if g]
    OUT.write_text(json.dumps(golden, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"DONE: {len(golden)} golden pairs → {OUT}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
