#!/usr/bin/env python3
"""Backfill EmbeddingGemma2 (768-d) vectors next to the legacy BGE-M3 columns.

Resumable, idempotent and safe to run while the legacy writers are live:

* only the new ``*_768`` columns are written; the legacy ``embedding`` /
  ``vector`` columns (and the tenant-projection trigger that watches them) are
  never touched;
* ``public.eg2_backfill_ledger`` records the md5 of the exact text each vector
  was computed from, so a re-run skips unchanged rows and re-embeds rows whose
  text changed or that were inserted after the previous pass (catch-up mode);
* every batch is committed on its own, so a crash or SIGTERM loses at most one
  batch, and the next run continues where the ledger stops;
* the embedding service may go away (laptop asleep, GPU restart): requests are
  retried forever with capped exponential backoff, nothing is skipped.

Text convention (validated by the AII retrieval A/B, MRR@10 0.971 sub1000 /
0.948 full3000): document = ``{title}\\n{body}`` (body Chinese first), encoded
with the server's ``Document`` prompt (``embeddinggemma-2-document``, which the
server expands to ``title: none | text: ...``).

Usage (run detached, e.g. as a transient systemd user unit):
    python scripts/eg2_backfill.py [--tables ku_onto,concept_onto] [--dry-run]
    python scripts/eg2_backfill.py --catch-up      # final pass before cutover
    python scripts/eg2_backfill.py --post-cutover  # after 089: fill rows whose (now 768-d)
                                                   # `embedding` is NULL but whose frozen
                                                   # `*_bge1024` vector exists
DSN: $AII_EG2_DSN, else $DATABASE_URL, else DATABASE_URL in aii/aii/.env.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import signal
import sys
import time
import urllib.request
from pathlib import Path

EMBED_BASE = os.getenv("AII_EMBED_BASE_URL", "http://100.68.226.13:8790/v1").rstrip("/")
DOC_MODEL = os.getenv("AII_EMBED_DOC_MODEL", "embeddinggemma-2-document")
DIM = int(os.getenv("AII_EMBED_DIM", "768"))
BATCH = min(int(os.getenv("EG2_BACKFILL_BATCH", "4")), 4)  # laptop GPU is shared: never above 4
MAX_CHARS = int(os.getenv("EG2_BACKFILL_MAX_CHARS", "1800"))
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # bypass http_proxy

# name -> (relation, pk expression, new column, legacy column, title sql, body sql)
# ``where`` keeps parity with the legacy column: every row that has a BGE vector
# gets an EG2 vector, nothing more.
TABLES: dict[str, dict] = {
    "ku_onto": dict(
        rel="aii.ku_onto",
        pk="ku_id",
        new="embedding_768",
        old="embedding",
        title="coalesce(title, '')",
        body="coalesce(nullif(btrim(natural_text_zh), ''), natural_text, '')",
    ),
    "concept_onto": dict(
        rel="aii.concept_onto",
        pk="concept_id::text",
        new="vector_768",
        old="vector",
        title="''",
        body="coalesce(name, '')",
    ),
    "invariant": dict(
        rel="aii.invariant",
        pk="id::text",
        new="vector_768",
        old="vector",
        title="''",
        body="coalesce(statement, '')",
    ),
    "kc_onto": dict(
        rel="aii.kc_onto",
        pk="kc_id::text",
        new="embedding_768",
        old="embedding",
        title="coalesce(community_label, '')",
        body="coalesce(nullif(btrim(summary), ''), summary_en, '')",
    ),
    "bu_onto": dict(
        rel="aii.bu_onto",
        pk="bu_id::text",
        new="embedding_768",
        old="embedding",
        title="''",
        # same retrieval text persist_bu.py builds: overview + problem + use_when + do_not_use_when
        body=(
            "concat_ws('。', nullif(overview_oneline, ''), nullif(problem_statement, ''),"
            " (SELECT string_agg(x, '。') FROM jsonb_array_elements_text("
            "   CASE WHEN jsonb_typeof(agent_skill->'use_when') = 'array' THEN agent_skill->'use_when' ELSE '[]'::jsonb END) x),"
            " (SELECT string_agg(x, '。') FROM jsonb_array_elements_text("
            "   CASE WHEN jsonb_typeof(agent_skill->'do_not_use_when') = 'array' THEN agent_skill->'do_not_use_when' ELSE '[]'::jsonb END) x))"
        ),
    ),
    "substrate_layers": dict(
        rel="stratum.substrate_layers",
        pk="id",
        new="embedding_768",
        old="embedding",
        title="''",
        body="coalesce(content, '')",
    ),
    "substrate_chunk": dict(
        rel="stratum.substrate_chunk",
        pk="id",
        new="embedding_768",
        old="embedding",
        title="''",
        body="coalesce(text, '')",
    ),
    "ku_layers": dict(
        rel="stratum.ku_layers",
        pk="id",
        new="embedding_768",
        old="embedding",
        title="''",
        body="coalesce(content, '')",
    ),
}
ORDER = [
    "ku_onto",
    "concept_onto",
    "invariant",
    "kc_onto",
    "bu_onto",
    "substrate_layers",
    "substrate_chunk",
    "ku_layers",
]

_stop = False


def _on_term(*_):
    global _stop
    _stop = True
    print("signal received: finishing current batch then exiting", flush=True)


def _dsn() -> str:
    for k in ("AII_EG2_DSN", "DATABASE_URL"):
        if os.getenv(k):
            return os.environ[k]
    env = Path(__file__).resolve().parents[1] / "aii" / "aii" / ".env"
    for line in env.read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("no DSN: set AII_EG2_DSN")


def doc_text(title: str, body: str) -> str:
    title, body = (title or "").strip(), (body or "").strip()
    text = f"{title}\n{body}" if title and body else (title or body)
    return text[:MAX_CHARS]


def _embed_once(texts: list[str]) -> list[list[float]]:
    req = urllib.request.Request(
        f"{EMBED_BASE}/embeddings",
        data=json.dumps({"model": DOC_MODEL, "input": texts, "dimensions": DIM}).encode(),
        headers={"content-type": "application/json"},
    )
    data = json.loads(_OPENER.open(req, timeout=300).read())["data"]
    vecs = [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
    if len(vecs) != len(texts) or any(len(v) != DIM for v in vecs):
        raise RuntimeError(f"bad response shape: {len(vecs)} vecs for {len(texts)} texts")
    return vecs


def embed(texts: list[str]) -> list[list[float]]:
    delay, attempt = 5.0, 0
    while True:
        try:
            return _embed_once(texts)
        except Exception as e:  # service down / restarting / OOM: wait, never skip
            attempt += 1
            if _stop:
                raise
            # a single over-long batch that keeps failing: fall back to one-by-one
            if attempt >= 3 and len(texts) > 1:
                print(
                    f"  batch of {len(texts)} failed {attempt}x ({e!r:.120}); retrying singly",
                    flush=True,
                )
                out = []
                for t in texts:
                    out.extend(embed([t]))
                return out
            print(f"  embed failed (attempt {attempt}): {e!r:.160}; sleep {delay:.0f}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 120.0)


def _vec(v: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + "]"


async def backfill_table(conn, name: str, catch_up: bool, dry: bool, post: bool = False) -> dict:
    t = dict(TABLES[name])
    if post:  # after the 089 rename: live column is 768-d, legacy is *_bge1024
        t["new"], t["old"] = t["old"], t["old"] + "_bge1024"
        has_old = await conn.fetchval(
            "SELECT count(*) FROM information_schema.columns WHERE table_schema||'.'||table_name=$1 "
            "AND column_name=$2",
            t["rel"],
            t["old"],
        )
        if not has_old:
            return {"table": name, "skipped": "no legacy column"}
    if await conn.fetchval("SELECT to_regclass($1)", t["rel"]) is None:
        return {"table": name, "skipped": "missing"}
    sel = (
        f"SELECT {t['pk']} AS pk, {t['title']} AS title, {t['body']} AS body FROM {t['rel']} "
        f"WHERE {t['old']} IS NOT NULL ORDER BY 1"
    )
    rows = await conn.fetch(sel)
    ledger = {
        r["pk"]: r["text_md5"]
        for r in await conn.fetch(
            "SELECT pk, text_md5 FROM public.eg2_backfill_ledger WHERE tbl=$1", name
        )
    }
    have = {
        r["pk"]
        for r in await conn.fetch(
            f"SELECT {t['pk']} AS pk FROM {t['rel']} WHERE {t['new']} IS NOT NULL"
        )
    }
    todo = []
    for r in rows:
        text = doc_text(r["title"], r["body"])
        if not text:
            continue
        md5 = hashlib.md5(text.encode()).hexdigest()
        if post and r["pk"] in have:
            continue  # post-cutover: only rows the live writers left without a vector
        if ledger.get(r["pk"]) == md5 and r["pk"] in have:
            continue
        todo.append((r["pk"], text, md5))
    print(
        f"[{name}] rows with legacy vector={len(rows)} done={len(rows) - len(todo)} todo={len(todo)}"
        f"{' (catch-up)' if catch_up else ''}",
        flush=True,
    )
    if dry or not todo:
        return {"table": name, "rows": len(rows), "todo": len(todo), "written": 0}
    upd = f"UPDATE {t['rel']} SET {t['new']} = $1::vector WHERE {t['pk']} = $2"
    t0, done, last = time.time(), 0, 0.0
    for i in range(0, len(todo), BATCH):
        if _stop:
            break
        chunk = todo[i : i + BATCH]
        vecs = await asyncio.to_thread(embed, [c[1] for c in chunk])
        async with conn.transaction():
            for (pk, _, md5), v in zip(chunk, vecs):
                await conn.execute(upd, _vec(v), pk)
                await conn.execute(
                    "INSERT INTO public.eg2_backfill_ledger(tbl, pk, text_md5) VALUES ($1,$2,$3) "
                    "ON CONFLICT (tbl, pk) DO UPDATE SET text_md5 = EXCLUDED.text_md5, updated_at = now()",
                    name,
                    pk,
                    md5,
                )
        done += len(chunk)
        if time.time() - last > 60 or done == len(todo):
            last = time.time()
            rate = done / max(time.time() - t0, 1e-6)
            eta = (len(todo) - done) / rate if rate else 0
            print(f"[{name}] {done}/{len(todo)} {rate:.2f}/s eta {eta / 60:.0f} min", flush=True)
    return {
        "table": name,
        "rows": len(rows),
        "todo": len(todo),
        "written": done,
        "seconds": round(time.time() - t0, 1),
    }


async def copy_tenant_projection(conn, dry: bool, post: bool = False) -> dict:
    """tenant_ann_vectors is an exact copy of substrate_chunk / substrate_layers vectors."""
    if await conn.fetchval("SELECT to_regclass('stratum.tenant_ann_vectors')") is None:
        return {"table": "tenant_ann_vectors", "skipped": "missing"}
    if dry:
        return {"table": "tenant_ann_vectors", "dry": True}
    if post:  # after 089 the projection column is `embedding` (768-d) on both sides
        a = await conn.execute(
            "UPDATE stratum.tenant_ann_vectors t SET embedding = c.embedding "
            "FROM stratum.substrate_chunk c WHERE t.source_kind = 'chunk' AND c.id = t.source_id "
            "AND t.embedding IS NULL AND c.embedding IS NOT NULL"
        )
        b = await conn.execute(
            "UPDATE stratum.tenant_ann_vectors t SET embedding = l.embedding "
            "FROM stratum.substrate_layers l WHERE t.source_kind = 'layer' AND l.id = t.source_id "
            "AND t.embedding IS NULL AND l.embedding IS NOT NULL"
        )
        print(f"[tenant_ann_vectors] post-cutover chunk {a} / layer {b}", flush=True)
        return {"table": "tenant_ann_vectors", "chunk": a, "layer": b}
    a = await conn.execute(
        "UPDATE stratum.tenant_ann_vectors t SET embedding_768 = c.embedding_768 "
        "FROM stratum.substrate_chunk c WHERE t.source_kind = 'chunk' AND c.id = t.source_id "
        "AND t.embedding_768 IS DISTINCT FROM c.embedding_768"
    )
    b = await conn.execute(
        "UPDATE stratum.tenant_ann_vectors t SET embedding_768 = l.embedding_768 "
        "FROM stratum.substrate_layers l WHERE t.source_kind = 'layer' AND l.id = t.source_id "
        "AND t.embedding_768 IS DISTINCT FROM l.embedding_768"
    )
    print(f"[tenant_ann_vectors] chunk {a} / layer {b}", flush=True)
    return {"table": "tenant_ann_vectors", "chunk": a, "layer": b}


async def main() -> None:
    import asyncpg

    ap = argparse.ArgumentParser()
    ap.add_argument("--tables", default=",".join(ORDER))
    ap.add_argument("--catch-up", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--post-cutover", action="store_true")
    ap.add_argument("--report", default=os.getenv("EG2_BACKFILL_REPORT", ""))
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    conn = await asyncpg.connect(_dsn())
    t0, results = time.time(), []
    print(
        f"eg2 backfill start base={EMBED_BASE} model={DOC_MODEL} dim={DIM} batch={BATCH}",
        flush=True,
    )
    for name in [n for n in a.tables.split(",") if n]:
        if name == "tenant_ann_vectors":
            continue
        if _stop:
            break
        results.append(await backfill_table(conn, name, a.catch_up, a.dry_run, a.post_cutover))
    if not _stop:
        results.append(await copy_tenant_projection(conn, a.dry_run, a.post_cutover))
    await conn.close()
    summary = {"seconds": round(time.time() - t0, 1), "stopped": _stop, "results": results}
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if a.report:
        Path(a.report).write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    if _stop:
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())
