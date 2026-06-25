"""Measure cross-chunk candidate pairs at 0.80 (NO LLM) — turns the 40x guess into a number.

Calls gen_candidates() (shared-concept + 0.80 cosine, cross-block, no existing edge) and reports
how many pairs WOULD be sent to the flash judge in step 4. Also breaks down by source.
"""
import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

import asyncpg
from aii.service.cross_chunk_link import gen_candidates


async def main():
    substrate_id = sys.argv[1]
    dsn = os.getenv("DATABASE_URL")
    conn = await asyncpg.connect(dsn)
    from pgvector.asyncpg import register_vector
    await register_vector(conn)

    ku = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", substrate_id)
    print(f"substrate={substrate_id} KU={ku}", flush=True)

    for thr in (0.80, 0.85, 0.88, 0.90):
        cands = await gen_candidates(conn, substrate_id=substrate_id, sem_threshold=thr)
        print(f"  sem_threshold={thr}: candidate_pairs={len(cands)}", flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
