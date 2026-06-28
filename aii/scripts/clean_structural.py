"""清存量结构噪声 KU(目录/索引/标题/表格/书本元话语)+级联清关联. 纯规则, 不动正文.

用 is_structural_noise 判 → 删 ku_onto + 级联 edge_onto / ku_concept_onto / ku_cooccurrence.
Usage: .venv/bin/python scripts/clean_structural.py <substrate_id> [--dry]
"""
import asyncio, os, sys
from collections import Counter
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from aii.service.structural_gate import is_structural_noise


async def main():
    sub = sys.argv[1]
    dry = "--dry" in sys.argv
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    rows = await conn.fetch("SELECT ku_id, natural_text FROM aii.ku_onto WHERE substrate_id=$1", sub)
    noise = [(r["ku_id"], r["natural_text"], is_structural_noise(r["natural_text"])) for r in rows]
    noise = [n for n in noise if n[2]]
    ids = [n[0] for n in noise]
    print(f"{sub}: total={len(rows)} flagged={len(ids)} ({100*len(ids)/max(len(rows),1):.1f}%) "
          f"by={dict(Counter(n[2] for n in noise))}", flush=True)
    if dry:
        print("DRY — no delete."); await conn.close(); return
    async with conn.transaction():
        e = await conn.execute(
            "DELETE FROM aii.edge_onto WHERE substrate_id=$1 AND (src_id = ANY($2) OR dst_id = ANY($2))", sub, ids)
        kc = await conn.execute("DELETE FROM aii.ku_concept_onto WHERE ku_id = ANY($1)", ids)
        co = await conn.execute(
            "DELETE FROM aii.ku_cooccurrence WHERE substrate_id=$1 AND (ku_a = ANY($2) OR ku_b = ANY($2))", sub, ids)
        k = await conn.execute("DELETE FROM aii.ku_onto WHERE ku_id = ANY($1)", ids)
    remaining = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", sub)
    print(f"deleted: ku_onto={k} edge_onto={e} ku_concept_onto={kc} ku_cooccurrence={co}", flush=True)
    print(f"remaining KU={remaining}", flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
