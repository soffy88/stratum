"""跨章/跨书语义去重(P2⑨): 向量近邻配对 → LLM 判 SAME → 报告/安全合并.

补 dedup_kus.py(只查同章标题)的盲区: 跨章(同书)、跨书的语义重复.
判定: LLM SAME/DIFFERENT(只关心是否同一断言).
动作分级(命门: 跨书"重复"常是不同书各自覆盖, 不可乱删):
  - 同书跨章 SAME → 可安全合并(--apply): 保留内容更长者, 另一条的边重指向, 删除.
  - 跨书 SAME → 仅报告(人工决定是否归并/建 same_as 边), 不自动删.

用法: python3 scripts/dedup_semantic.py [--sim 0.86] [--max 80] [--apply]
"""
import asyncio, os, re, json, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from aii.api._provider import register_providers
from obase import ProviderRegistry
from aii.storage.pg_backend import PgBackend

JUDGE_SYS = ("You decide if two knowledge statements assert THE SAME core knowledge (duplicate). "
             "Output valid JSON only. verdict ∈ {SAME, DIFFERENT}. "
             "SAME only if they teach the same fact/concept with the same substance (wording may differ).")


async def _pairs(conn, sim, limit):
    rows = await conn.fetch("""
        SELECT a.ku_id a_id, a.substrate_id a_sub, length(a.natural_text) a_len, a.natural_text a_tx,
               n.ku_id b_id, n.substrate_id b_sub, length(n.natural_text) b_len, n.natural_text b_tx,
               1 - (a.embedding <=> n.embedding) sim
        FROM aii.ku_onto a
        CROSS JOIN LATERAL (
            SELECT ku_id, substrate_id, natural_text, embedding FROM aii.ku_onto b
            WHERE b.ku_id <> a.ku_id AND b.embedding IS NOT NULL
            ORDER BY b.embedding <=> a.embedding LIMIT 4
        ) n
        WHERE a.embedding IS NOT NULL AND 1 - (a.embedding <=> n.embedding) >= $1
        ORDER BY sim DESC
    """, sim)
    seen, out = set(), []
    for r in rows:
        key = tuple(sorted([r["a_id"], r["b_id"]]))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(r))
    return out[:limit]


async def main():
    sim = float(sys.argv[sys.argv.index("--sim") + 1]) if "--sim" in sys.argv else 0.86
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 80
    apply = "--apply" in sys.argv
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    be = PgBackend()
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    cands = await _pairs(conn, sim, mx)
    print(f"{len(cands)} candidate pairs (sim≥{sim}, judging…)", flush=True)

    sem = asyncio.Semaphore(4)
    async def judge(p):
        async with sem:
            try:
                r = await llm(messages=[{"role": "user", "content":
                    f"A: {(p['a_tx'] or '')[:550]}\n\nB: {(p['b_tx'] or '')[:550]}\n\n"
                    f'JSON: {{"verdict":"SAME|DIFFERENT"}}'}], system=JUDGE_SYS, max_tokens=40)
                t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
                m = re.search(r"\{.*\}", t, re.DOTALL)
                return {**p, "verdict": (json.loads(m.group(0)).get("verdict") or "").upper()} if m else None
            except Exception:
                return None

    judged = [j for j in await asyncio.gather(*(judge(p) for p in cands)) if j]
    sames = [j for j in judged if j["verdict"] == "SAME"]
    same_book = [j for j in sames if j["a_sub"] == j["b_sub"]]
    cross_book = [j for j in sames if j["a_sub"] != j["b_sub"]]
    print(f"SAME={len(sames)} (同书跨章={len(same_book)} 可合并, 跨书={len(cross_book)} 仅报告)")

    merged = 0
    for p in same_book:
        keep, drop = (p["a_id"], p["b_id"]) if p["a_len"] >= p["b_len"] else (p["b_id"], p["a_id"])
        print(f"  同书dup sim={p['sim']:.2f} keep {keep[-22:]}  drop {drop[-22:]}")
        if apply:
            # 重指向被删 KU 的边到保留 KU, 再删
            await conn.execute("UPDATE aii.edge_onto SET src_id=$1 WHERE src_id=$2", keep, drop)
            await conn.execute("UPDATE aii.edge_onto SET dst_id=$1 WHERE dst_id=$2", keep, drop)
            await be.delete_ku(drop)
            merged += 1
    for p in cross_book:
        print(f"  跨书dup sim={p['sim']:.2f} {p['a_id'][-22:]} ↔ {p['b_id'][-22:]} (人工: 归并或建 same_as)")
    print(f"\nDONE: {len(sames)} dups; merged {merged} same-book" + ("" if apply else " (dry-run)"), flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
