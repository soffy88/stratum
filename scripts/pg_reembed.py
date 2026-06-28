#!/usr/bin/env python3
"""P1.4: re-embed Stratum substrate content with BGE-M3 → stratum.substrate_chunk (pgvector).

Aligns Stratum's vectors with AII (BGE-M3 1024-dim) so the two can be cross-searched
in one PostgreSQL. Replaces the LanceDB(Qwen3) index. Long CPU batch — resumable.

MUST run in AII's venv (has sentence-transformers + oprim BGE-M3 + asyncpg + pgvector;
the stratum-sl image does NOT). The model is cached at ~/.cache/huggingface and loaded
ONCE at startup.

    export STRATUM_PG_PASSWORD=$(docker exec aii-postgres printenv POSTGRES_PASSWORD)
    HF_HUB_OFFLINE=1 /home/soffy/projects/AII/.venv/bin/python scripts/pg_reembed.py

Resumable: substrates already present in substrate_chunk are skipped. Re-run any time.
After all rows are embedded it builds the HNSW index.
"""
import asyncio
import os
import sys
import time

PG = dict(
    host=os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
    port=int(os.environ.get("STRATUM_PG_PORT", "5435")),
    user=os.environ.get("STRATUM_PG_USER", "aii"),
    password=os.environ.get("STRATUM_PG_PASSWORD", ""),
    database=os.environ.get("STRATUM_PG_DB", "aii_kg"),
)
BATCH = int(os.environ.get("REEMBED_BATCH", "32"))
MIN_CHARS, MAX_CHARS = 500, 2000


def _log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def main() -> int:
    import asyncpg
    from pgvector.asyncpg import register_vector
    from obase import ProviderRegistry
    from oprim.embedding.bge_m3 import BgeM3Embedder
    from oprim import structural_chunk, vector_encode

    t0 = time.time()
    _log("loading BGE-M3 …")
    ProviderRegistry.register("embedding", "default", BgeM3Embedder().embed)
    vector_encode(texts=["warmup"], provider="default")  # trigger load
    _log(f"BGE-M3 ready ({time.time() - t0:.0f}s)")

    conn = await asyncpg.connect(server_settings={"search_path": "stratum"}, **PG)
    await register_vector(conn)

    done = {r["substrate_id"] for r in
            await conn.fetch("SELECT DISTINCT substrate_id FROM substrate_chunk")}
    rows = await conn.fetch(
        "SELECT s.id, ("
        "  SELECT d.content FROM derivative d "
        "  WHERE d.substrate_id = s.id AND d.kind='markdown' AND length(d.content) > 0 "
        "  ORDER BY length(d.content) DESC LIMIT 1) AS content "
        "FROM substrates s")
    targets = [(r["id"], r["content"]) for r in rows if r["content"] and r["id"] not in done]
    _log(f"substrates: {len(rows)} total, {len(done)} done, {len(targets)} to embed")

    total_chunks = 0
    for n, (sid, content) in enumerate(targets, 1):
        raw = structural_chunk(text=content, min_chars=MIN_CHARS, max_chars=MAX_CHARS) or []
        chunks = [c.get("content", "") if isinstance(c, dict) else str(c) for c in raw]
        chunks = [c for c in chunks if c.strip()] or [content[:MAX_CHARS]]
        recs = []
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i:i + BATCH]
            embs = vector_encode(texts=batch, provider="default")
            for j, (text, emb) in enumerate(zip(batch, embs)):
                recs.append((f"{sid}#{i + j}", sid, i + j, text, list(emb)))
        # one substrate = one transaction (resumable at substrate granularity)
        await conn.executemany(
            "INSERT INTO substrate_chunk (id, substrate_id, chunk_idx, text, embedding) "
            "VALUES ($1,$2,$3,$4,$5) ON CONFLICT (id) DO NOTHING", recs)
        total_chunks += len(recs)
        if n % 10 == 0 or n == len(targets):
            _log(f"  {n}/{len(targets)} substrates · {total_chunks} chunks · "
                 f"{(time.time()-t0)/60:.1f}min")

    _log("building HNSW index (cosine) …")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_substrate_chunk_vec "
        "ON substrate_chunk USING hnsw (embedding vector_cosine_ops)")
    cnt = await conn.fetchval("SELECT count(*) FROM substrate_chunk")
    _log(f"DONE — {cnt} chunks embedded, {(time.time()-t0)/60:.1f}min total")
    await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
