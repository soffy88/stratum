"""实证章内建边 v2: 评分排序(共现tier当分数)+机制因果验证, 对照 ch3 全LLM判的643边.
结论: 评分排序(只判strong+medium)解over-link且省79% LLM; Hearst抽层级已证失败(见hearst_experiment);
机制explains 44%无因果信号=幻觉, 须因果验证."""
import asyncio, os, re
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / "aii" / ".env", override=True)
import asyncpg
from aii.service.cooccurrence import compute_cooccurrence
SUB = "microecon_en_ch3"


async def main():
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    from pgvector.asyncpg import register_vector
    await register_vector(c)
    cooc = await compute_cooccurrence(c, substrate_id=SUB, sim_threshold=0.80)
    rows = await c.fetch(f"""
      SELECT e.relation_type rel, co.strength, ka.natural_text sa, kb.natural_text sb
      FROM aii.edge_onto e
      JOIN aii.ku_onto ka ON e.src_id=ka.ku_id JOIN aii.ku_onto kb ON e.dst_id=kb.ku_id
      LEFT JOIN aii.ku_cooccurrence co ON co.substrate_id='{SUB}'
        AND co.ku_a=LEAST(e.src_id,e.dst_id) AND co.ku_b=GREATEST(e.src_id,e.dst_id)
      WHERE e.substrate_id='{SUB}'""")
    n = len(rows)
    sm = sum(1 for r in rows if r["strength"] in ("strong", "medium"))
    causal = re.compile(r'\b(because|therefore|thus|hence|leads? to|causes?|results? in|due to|signals?)\b', re.I)
    expl = [r for r in rows if r["rel"] == "explains"]
    val = sum(1 for r in expl if causal.search((r["sa"] or "") + " " + (r["sb"] or "")))
    print(f"candidates(cooc tiers): {cooc['by_strength']} total={cooc['total']}")
    print(f"edges by tier: {dict(Counter(r['strength'] or 'none' for r in rows))}")
    print(f"A all-LLM: {n} edges, {n/101:.1f}/KU, 1177 judges")
    print(f"B score-rank(strong+medium): ~{sm} edges, {sm/101:.1f}/KU, 242 judges (-79%)")
    print(f"explains causal-validated: {val}/{len(expl)} ({100*val/max(len(expl),1):.0f}%), {len(expl)-val} likely hallucinated")
    await c.close()


if __name__ == "__main__":
    asyncio.run(main())
