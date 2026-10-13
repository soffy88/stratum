#!/usr/bin/env python3
"""EmbeddingGemma2 (768-d) backfill for the B仓 (aii_refined) and C仓 (aii_context) stores.

Companion of scripts/eg2_backfill.py (A仓 / aii_kg).  Run it AFTER the aii_kg
backfill has finished, because B仓 singletons reuse the A仓 vector exactly like
aii/scripts/dedup/orchestrate.py does:

* rf.refined_ku: a singleton (one contribution whose raw_ku_id exists in
  aii.ku_onto) copies aii.ku_onto.embedding_768; a merged cluster is embedded
  from ``integrate.embed_text(contributions)`` (concatenated fragments).
* rf.refined_concept: ``f"{name} {name_zh}".strip()`` (same text m0.py encodes).
* cx.decision_case: situation or title; cx.methodology: description or name;
  cx.lesson_pattern: lesson or pattern text (same fields context_compiler uses).

Same guarantees as eg2_backfill.py: only the new ``embedding_768`` columns are
written, per-batch commits, md5 ledger per database for resume/catch-up, and
infinite capped-backoff retry while the embedding service is away.

DSNs: AII_EG2_DSN (aii_kg), AII_EG2_REFINED_DSN (aii_refined),
AII_EG2_CONTEXT_DSN (aii_context).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eg2_backfill import BATCH, _on_term, _vec, embed  # noqa: E402
import eg2_backfill as _bf  # noqa: E402

EMBED_TEXT_MAX = 4000  # integrate.embed_text default


def embed_text(contributions) -> str:
    if isinstance(contributions, str):
        contributions = json.loads(contributions)
    t = " ".join((c.get("fragment_text") or "").strip() for c in contributions or []).strip()
    return t[:EMBED_TEXT_MAX]


async def _ledger(conn, tbl):
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS public.eg2_backfill_ledger (tbl TEXT NOT NULL, pk TEXT NOT NULL,"
        " text_md5 TEXT NOT NULL, updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (tbl, pk))"
    )
    return {
        r["pk"]: r["text_md5"]
        for r in await conn.fetch(
            "SELECT pk, text_md5 FROM public.eg2_backfill_ledger WHERE tbl=$1", tbl
        )
    }


async def _write(conn, rel, pkcol, tbl, items):
    """items: list of (pk, md5, vector)"""
    async with conn.transaction():
        for pk, md5, v in items:
            await conn.execute(
                f"UPDATE {rel} SET embedding_768 = $1::vector WHERE {pkcol} = $2", _vec(v), pk
            )
            await conn.execute(
                "INSERT INTO public.eg2_backfill_ledger(tbl, pk, text_md5) VALUES ($1,$2,$3) "
                "ON CONFLICT (tbl, pk) DO UPDATE SET text_md5 = EXCLUDED.text_md5, updated_at = now()",
                tbl,
                pk,
                md5,
            )


async def embed_rows(conn, tbl, rel, pkcol, rows, dry):
    """rows: list of (pk, text). Embeds rows whose text md5 is not in the ledger."""
    ledger = await _ledger(conn, tbl)
    have = {
        str(r["pk"])
        for r in await conn.fetch(
            f"SELECT {pkcol}::text AS pk FROM {rel} WHERE embedding_768 IS NOT NULL"
        )
    }
    todo = []
    for pk, text in rows:
        text = (text or "").strip()
        if not text:
            continue
        md5 = hashlib.md5(text.encode()).hexdigest()
        if ledger.get(str(pk)) == md5 and str(pk) in have:
            continue
        todo.append((pk, text, md5))
    print(f"[{tbl}] rows={len(rows)} todo={len(todo)}", flush=True)
    if dry:
        return {"table": tbl, "rows": len(rows), "todo": len(todo), "written": 0}
    t0, done, last = time.time(), 0, 0.0
    for i in range(0, len(todo), BATCH):
        if _bf._stop:
            break
        chunk = todo[i : i + BATCH]
        vecs = await asyncio.to_thread(embed, [c[1] for c in chunk])
        await _write(conn, rel, pkcol, tbl, [(pk, md5, v) for (pk, _, md5), v in zip(chunk, vecs)])
        done += len(chunk)
        if time.time() - last > 60 or done == len(todo):
            last = time.time()
            rate = done / max(time.time() - t0, 1e-6)
            print(
                f"[{tbl}] {done}/{len(todo)} {rate:.2f}/s eta {(len(todo) - done) / rate / 60:.0f} min",
                flush=True,
            )
    return {
        "table": tbl,
        "rows": len(rows),
        "todo": len(todo),
        "written": done,
        "seconds": round(time.time() - t0, 1),
    }


async def refined(kg, rf, dry):
    out = []
    rows = await rf.fetch(
        "SELECT ku_id, contributions FROM rf.refined_ku WHERE embedding IS NOT NULL ORDER BY ku_id"
    )
    singles, merged = {}, []
    for r in rows:
        c = r["contributions"]
        c = json.loads(c) if isinstance(c, str) else (c or [])
        if len(c) == 1 and c[0].get("raw_ku_id"):
            singles[r["ku_id"]] = c[0]["raw_ku_id"]
        else:
            merged.append((r["ku_id"], embed_text(c)))
    # singletons: copy A仓 vector (same as orchestrate.py's reuse path)
    a = {}
    raw_ids = list(set(singles.values()))
    for i in range(0, len(raw_ids), 5000):
        for r in await kg.fetch(
            "SELECT ku_id, embedding_768::text AS v FROM aii.ku_onto WHERE ku_id = ANY($1::text[]) "
            "AND embedding_768 IS NOT NULL",
            raw_ids[i : i + 5000],
        ):
            a[r["ku_id"]] = r["v"]
    missing = [(k, v) for k, v in singles.items() if v not in a]
    print(
        f"[refined_ku] singletons={len(singles)} copyable={len(singles) - len(missing)} "
        f"merged={len(merged)} singleton-without-A-vector={len(missing)}",
        flush=True,
    )
    copied = 0
    if not dry:
        ledger = await _ledger(rf, "refined_ku")
        batch = []
        for ku, raw in singles.items():
            if raw not in a:
                continue
            md5 = "copy:" + hashlib.md5(a[raw].encode()).hexdigest()
            if ledger.get(ku) == md5:
                continue
            batch.append((ku, md5, a[raw]))
            if len(batch) >= 500:
                await _write_text(rf, batch)
                copied += len(batch)
                batch = []
        if batch:
            await _write_text(rf, batch)
            copied += len(batch)
    out.append({"table": "refined_ku(copy)", "copied": copied})
    # merged clusters + singletons whose A row has no vector: embed the fragments
    contrib = {r["ku_id"]: r["contributions"] for r in rows}
    extra = [(k, embed_text(contrib[k])) for k, _ in missing]
    out.append(await embed_rows(rf, "refined_ku", "rf.refined_ku", "ku_id", merged + extra, dry))
    crow = await rf.fetch(
        "SELECT concept_id, name, name_zh FROM rf.refined_concept WHERE embedding IS NOT NULL ORDER BY 1"
    )
    out.append(
        await embed_rows(
            rf,
            "refined_concept",
            "rf.refined_concept",
            "concept_id",
            [(r["concept_id"], f"{r['name'] or ''} {r['name_zh'] or ''}".strip()) for r in crow],
            dry,
        )
    )
    return out


async def _write_text(conn, items):
    async with conn.transaction():
        for pk, md5, vtext in items:
            await conn.execute(
                "UPDATE rf.refined_ku SET embedding_768 = $1::vector WHERE ku_id = $2", vtext, pk
            )
            await conn.execute(
                "INSERT INTO public.eg2_backfill_ledger(tbl, pk, text_md5) VALUES ($1,$2,$3) "
                "ON CONFLICT (tbl, pk) DO UPDATE SET text_md5 = EXCLUDED.text_md5, updated_at = now()",
                "refined_ku",
                pk,
                md5,
            )


async def context(cx, dry):
    out = []
    specs = [
        ("decision_case", "cx.decision_case", "case_id", "coalesce(nullif(situation, ''), title)"),
        ("methodology", "cx.methodology", "method_id", "coalesce(nullif(description, ''), name)"),
    ]
    for tbl, rel, pk, expr in specs:
        if await cx.fetchval("SELECT to_regclass($1)", rel) is None:
            continue
        rows = await cx.fetch(
            f"SELECT {pk} AS pk, {expr} AS t FROM {rel} WHERE embedding IS NOT NULL ORDER BY 1"
        )
        out.append(await embed_rows(cx, tbl, rel, pk, [(r["pk"], r["t"]) for r in rows], dry))
    n = (
        await cx.fetchval("SELECT count(*) FROM cx.lesson_pattern WHERE embedding IS NOT NULL")
        if await cx.fetchval("SELECT to_regclass('cx.lesson_pattern')")
        else 0
    )
    if n:
        print(
            f"WARNING: cx.lesson_pattern has {n} vectors; text convention not wired — embed manually",
            flush=True,
        )
    return out


async def main():
    import asyncpg
    import signal

    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", choices=["refined", "context"], default=None)
    ap.add_argument("--report", default=os.getenv("EG2_BACKFILL_REFINED_REPORT", ""))
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)
    t0, res = time.time(), []
    if a.only in (None, "refined"):
        kg = await asyncpg.connect(_bf._dsn())
        rf = await asyncpg.connect(os.environ["AII_EG2_REFINED_DSN"])
        res += await refined(kg, rf, a.dry_run)
        await kg.close()
        await rf.close()
    if a.only in (None, "context") and not _bf._stop:
        cx = await asyncpg.connect(os.environ["AII_EG2_CONTEXT_DSN"])
        res += await context(cx, a.dry_run)
        await cx.close()
    summary = {"seconds": round(time.time() - t0, 1), "stopped": _bf._stop, "results": res}
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if a.report:
        Path(a.report).write_text(json.dumps(summary, ensure_ascii=False, indent=1))
    if _bf._stop:
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main())
