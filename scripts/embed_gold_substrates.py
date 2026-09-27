"""Embed gold-relevant substrates' markdown derivative content into substrate_chunk.

This is the missing data-plane step: pg_reembed.py was run previously but only
covered 7 substrates (540 chunks). The 100-query retrieval gold references
88 unique substrate IDs; 82 of them have NO chunks in substrate_chunk,
so cosine search returns only the 7 already-embedded substrates.

This script embeds ONLY the gold-relevant substrates whose derivative
markdown content exists, using the same BGE-M3 + structural_chunk pipeline
as pg_reembed.py so the chunks are dimensionally and semantically compatible
with the existing dense index.

NOT an architecture change — same provider, same model, same dim, same parser.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD_PATH = ROOT / "gold_retrieval_real_100.json"

PG = dict(
    host=os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
    port=int(os.environ.get("STRATUM_PG_PORT", "5435")),
    user=os.environ.get("STRATUM_PG_USER", "aii"),
    password=os.environ.get("STRATUM_PG_PASSWORD", "***REMOVED***"),
    database=os.environ.get("STRATUM_PG_DB", "aii_kg"),
)
BATCH = int(os.environ.get("REEMBED_BATCH", "16"))
MIN_CHARS, MAX_CHARS = 500, 2000
FRAGMENT_VERSION = int(os.environ.get("STRATUM_FRAGMENT_VERSION", "1"))
PARSER_VERSION = os.environ.get("STRATUM_PARSER_VERSION", "structural_chunk-v1")


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

    gold = json.loads(GOLD_PATH.read_text())
    gold_subs = sorted({s for g in gold for s in g["relevant_substrate_ids"]})
    _log(f"gold queries: {len(gold)}, unique gold substrate ids: {len(gold_subs)}")

    done = {
        r["substrate_id"]
        for r in await conn.fetch("SELECT DISTINCT substrate_id FROM substrate_chunk")
    }
    _log(f"already embedded: {len(done)} substrates")

    rows = await conn.fetch(
        """
        SELECT s.id, (
            SELECT d.content FROM derivative d
            WHERE d.substrate_id = s.id AND d.kind='markdown' AND length(d.content) > 0
            ORDER BY length(d.content) DESC LIMIT 1
        ) AS content
        FROM substrates s
        WHERE s.id = ANY($1::text[])
        """,
        gold_subs,
    )
    targets = [(r["id"], r["content"]) for r in rows if r["content"] and r["id"] not in done]
    _log(f"targets to embed (gold subs with markdown content, not yet embedded): {len(targets)}")
    no_derivative = [r["id"] for r in rows if not r["content"]]
    _log(f"gold subs with NO derivative content (will skip): {len(no_derivative)}")

    total_chunks = 0
    for n, (sid, content) in enumerate(targets, 1):
        raw = structural_chunk(text=content, min_chars=MIN_CHARS, max_chars=MAX_CHARS) or []
        chunks = []
        for c in raw:
            if isinstance(c, dict):
                chunk_text = c.get("content", "")
                anchor = {
                    key: c[key]
                    for key in ("heading_path", "start_pos", "end_pos", "block_types")
                    if c.get(key) is not None
                }
            else:
                chunk_text = str(c)
                anchor = {}
            if chunk_text and chunk_text.strip():
                chunks.append((chunk_text, anchor))
        chunks = chunks or [(content[:MAX_CHARS], {"fallback": True})]

        recs = []
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            batch_text = [text for text, _ in batch]
            embs = vector_encode(texts=batch_text, provider="default")
            for j, ((text, anchor), emb) in enumerate(zip(batch, embs)):
                recs.append(
                    (
                        f"{sid}#{i + j}",
                        sid,
                        i + j,
                        text,
                        list(emb),
                        FRAGMENT_VERSION,
                        json.dumps(anchor, ensure_ascii=False),
                        PARSER_VERSION,
                    )
                )
        await conn.executemany(
            "INSERT INTO substrate_chunk "
            "(id, substrate_id, chunk_idx, text, embedding, version, anchor_json, parser_version) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8) ON CONFLICT (id) DO NOTHING",
            recs,
        )
        total_chunks += len(recs)
        _log(
            f"  {n}/{len(targets)} {sid[:18]} · {len(recs)} chunks · {(time.time() - t0) / 60:.1f}min"
        )

    _log("HNSW index already exists or being rebuilt…")
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_substrate_chunk_vec "
        "ON substrate_chunk USING hnsw (embedding vector_cosine_ops)"
    )
    cnt = await conn.fetchval("SELECT count(*) FROM substrate_chunk")
    _log(f"DONE — substrate_chunk total rows now: {cnt}, new chunks added: {total_chunks}")
    _log(f"runtime: {(time.time() - t0) / 60:.1f}min")
    await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
