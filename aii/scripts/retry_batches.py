"""Retry specific batch indices (fixed persist) + run normalize. Does NOT touch other batches.

Usage: .venv/bin/python scripts/retry_batches.py <substrate_id> <md_path> <subject> <i1,i2,...>
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

sys.path.insert(0, str(ROOT / "scripts"))
from run_first3 import strip_frontmatter, split_batches, reoffset_ids, SCRATCH

import asyncpg
from aii.api._provider import register_providers
from aii.storage.pg_backend import PgBackend
from aii.service import onto_prompts as P
from aii.service import onto_vocab as V
from aii.service.onto_persist import persist_ontology_result
from aii.service.concept_onto_ops import vectorize_and_normalize
from obase import ProviderRegistry


async def main():
    substrate_id, md_path, subject, idxs = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    targets = [int(x) for x in idxs.split(",")]
    register_providers()
    backend = PgBackend(); backend.dsn = os.getenv("DATABASE_URL")
    llm = ProviderRegistry.get().llm("default")
    from oskill import ontology_extract

    text = strip_frontmatter(md_path.read_text(encoding="utf-8"))
    batches = split_batches(text, 50000)
    trail = Path("/tmp/onto_trails"); trail.mkdir(parents=True, exist_ok=True)
    ckpt_path = SCRATCH / f"ckpt_{substrate_id}.json"
    ckpt = json.loads(ckpt_path.read_text()); done = set(ckpt["done"])

    for bi in targets:
        result = await ontology_extract(
            source_text=batches[bi], llm=llm, doc_type="textbook", source_credibility="high",
            pass1_chunk_tmpl=P.PASS1_CHUNK_TMPL, pass1_chunk_system=P.PASS1_CHUNK_SYSTEM,
            pass1_outline_tmpl=P.PASS1_OUTLINE_TMPL, pass1_outline_system=P.PASS1_OUTLINE_SYSTEM,
            pass2_chunk_tmpl=P.PASS2_CHUNK_TMPL, pass2_system=P.PASS2_SYSTEM,
            valid_knowledge_types=V.VALID_KNOWLEDGE_TYPES, valid_sub_types=V.VALID_SUB_TYPES,
            valid_relation_types=V.VALID_RELATION_TYPES,
        )
        reoffset_ids(result, bi)
        ps = await persist_ontology_result(
            dsn=backend.dsn, substrate_id=substrate_id, result=result, trail_dir=trail, backend=backend)
        done.add(bi)
        ckpt_path.write_text(json.dumps({"done": sorted(done)}))
        print(f"  retry batch {bi}: +{ps.get('registered',0)} KU (rej {ps.get('rejected',0)})", flush=True)

    conn = await asyncpg.connect(backend.dsn)
    from pgvector.asyncpg import register_vector
    await register_vector(conn)
    norm = await vectorize_and_normalize(
        conn, llm, substrate_id=substrate_id, discipline=(subject or "general"))
    n = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", substrate_id)
    await conn.close()
    print(f"DONE retry+normalize: KU={n} normalize={norm}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
