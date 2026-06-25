"""Resumable bounded onto-ingest: steps 1-3 only (extract -> persist -> normalize).

Deliberately SKIPS step 4 (cross-chunk, uncapped O(N^2)) and step 5 (KC).
All-flash. Namespaced by substrate_id. Resumable via checkpoint + idempotent persist.

Why batched (not one monolithic ontology_extract call):
  - a full book is ~hundreds of chunks / hours sequential -> a mid-run crash loses everything.
  - batch = ~batch_chars of prose -> extract concurrently, persist+checkpoint per batch.
  - tradeoff: outline context is per-batch (chapter-ish), not whole-book. Acceptable for resumability.

ID namespacing: persist prefixes '{substrate}::{id}', and each ontology_extract call restarts
chunk idx at 0 (ku_c0_0). To avoid cross-batch collision we offset chunk idx by batch*10000,
keeping the 'ku_cN_' format that cross_chunk_link's regex depends on.

Usage:
  .venv/bin/python scripts/run_first3.py <substrate_id> <md_path> <title> <subject> [batch_chars] [concurrency]
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

import asyncpg
from aii.api._provider import register_providers
from aii.storage.pg_backend import PgBackend
from aii.service import onto_prompts as P
from aii.service import onto_vocab as V
from aii.service.onto_persist import persist_ontology_result
from aii.service.concept_onto_ops import vectorize_and_normalize
from obase import ProviderRegistry

SCRATCH = Path("/tmp/claude-1000/-home-soffy-projects-AII/"
               "bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad")
SCRATCH.mkdir(parents=True, exist_ok=True)

_CID = re.compile(r'^ku_c(\d+)_(.+)$')


def strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            return text[text.find("\n", end + 1) + 1:]
    return text


def split_batches(text: str, batch_chars: int) -> list[str]:
    paras = [p for p in text.split("\n\n") if p.strip()]
    batches, buf, blen = [], [], 0
    for p in paras:
        if blen + len(p) > batch_chars and buf:
            batches.append("\n\n".join(buf))
            buf, blen = [], 0
        buf.append(p)
        blen += len(p)
    if buf:
        batches.append("\n\n".join(buf))
    return batches


def reoffset_ids(result, batch_idx: int):
    """Rewrite ku_c{X}_{Y} -> ku_c{batch*10000+X}_{Y} on KUs and edge endpoints."""
    off = batch_idx * 10000
    idmap = {}
    for ku in result.ku_candidates or []:
        old = ku.get("id") or ""
        m = _CID.match(old)
        if m:
            new = f"ku_c{int(m.group(1)) + off}_{m.group(2)}"
            idmap[old] = new
            ku["id"] = new
    for e in result.edge_candidates or []:
        if e.get("source") in idmap:
            e["source"] = idmap[e["source"]]
        if e.get("target") in idmap:
            e["target"] = idmap[e["target"]]


async def main():
    substrate_id = sys.argv[1]
    md_path = Path(sys.argv[2])
    title = sys.argv[3]
    subject = sys.argv[4]
    batch_chars = int(sys.argv[5]) if len(sys.argv) > 5 else 50000
    concurrency = int(sys.argv[6]) if len(sys.argv) > 6 else 5
    doc_type = "textbook"

    register_providers()
    backend = PgBackend()
    backend.dsn = os.getenv("DATABASE_URL")
    llm = ProviderRegistry.get().llm("default")  # flash
    from oskill import ontology_extract

    text = strip_frontmatter(md_path.read_text(encoding="utf-8"))
    batches = split_batches(text, batch_chars)

    ckpt_path = SCRATCH / f"ckpt_{substrate_id}.json"
    ckpt = json.loads(ckpt_path.read_text()) if ckpt_path.exists() else {"done": []}
    done = set(ckpt["done"])
    print(f"[{substrate_id}] {len(batches)} batches, {len(done)} already done, "
          f"batch_chars={batch_chars}, concurrency={concurrency}", flush=True)

    trail = Path("/tmp/onto_trails"); trail.mkdir(parents=True, exist_ok=True)
    sem = asyncio.Semaphore(concurrency)
    persist_lock = asyncio.Lock()
    fails = []

    async def do_batch(bi: int, btext: str):
        async with sem:
            try:
                result = await ontology_extract(
                    source_text=btext, llm=llm, doc_type=doc_type, source_credibility="high",
                    pass1_chunk_tmpl=P.PASS1_CHUNK_TMPL, pass1_chunk_system=P.PASS1_CHUNK_SYSTEM,
                    pass1_outline_tmpl=P.PASS1_OUTLINE_TMPL, pass1_outline_system=P.PASS1_OUTLINE_SYSTEM,
                    pass2_chunk_tmpl=P.PASS2_CHUNK_TMPL, pass2_system=P.PASS2_SYSTEM,
                    valid_knowledge_types=V.VALID_KNOWLEDGE_TYPES,
                    valid_sub_types=V.VALID_SUB_TYPES,
                    valid_relation_types=V.VALID_RELATION_TYPES,
                )
                reoffset_ids(result, bi)
            except Exception as e:
                fails.append((bi, f"extract: {e}"))
                print(f"  batch {bi} EXTRACT FAIL: {e}", flush=True)
                return
            async with persist_lock:  # serialize DB writes (concept upsert races)
                try:
                    ps = await persist_ontology_result(
                        dsn=backend.dsn, substrate_id=substrate_id, result=result,
                        trail_dir=trail, backend=backend)
                    done.add(bi)
                    ckpt_path.write_text(json.dumps({"done": sorted(done)}))
                    print(f"  batch {bi}: +{ps.get('registered',0)} KU "
                          f"(rej {ps.get('rejected',0)}) [{len(done)}/{len(batches)}]", flush=True)
                except Exception as e:
                    fails.append((bi, f"persist: {e}"))
                    print(f"  batch {bi} PERSIST FAIL: {e}", flush=True)

    await asyncio.gather(*(do_batch(bi, bt) for bi, bt in enumerate(batches) if bi not in done))

    # Step 3: normalize concepts over the whole substrate (vector union-find, 0 LLM)
    norm = {}
    if not fails:
        conn = await asyncpg.connect(backend.dsn)
        try:
            from pgvector.asyncpg import register_vector
            await register_vector(conn)
            norm = await vectorize_and_normalize(
                conn, substrate_id=substrate_id, discipline=(subject or "general"), threshold=0.90)
        finally:
            await conn.close()

    # final KU count
    conn = await asyncpg.connect(backend.dsn)
    n = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", substrate_id)
    nz = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1 AND natural_text_zh IS NOT NULL "
        "AND natural_text_zh<>''", substrate_id)
    await conn.close()
    print(f"\nDONE {substrate_id}: KU={n} zh={nz} normalize={norm} fails={len(fails)}", flush=True)
    if fails:
        print("FAILS (rerun to retry):", fails[:20], flush=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
