"""Cross-chapter/cross-book semantic dedup (P2⑨) — importable core, shared by
scripts/dedup_semantic.py (manual CLI) and the periodic loop below.

Was CLI-only with zero automated callers — this covers a real blind spot in
dedup_within_book.py (title-based, misses same-fact-different-wording dupes
across chapters/books) but only closed when someone remembered to run it by
hand. Safety boundary (unchanged from the original script): same-book SAME
pairs are safe to auto-merge (one KU, same book, same claim — pick the longer
text, redirect edges, delete the other). Cross-book SAME pairs are NEVER
auto-merged — different books "duplicating" a fact is often each book's own
independent coverage, not a real duplicate; those are logged for human review.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re

import asyncpg
from obase import ProviderRegistry

from aii.api._provider import register_providers
from aii.storage.pg_backend import PgBackend

logger = logging.getLogger(__name__)

JUDGE_SYS = (
    "You decide if two knowledge statements assert THE SAME core knowledge (duplicate). "
    "Output valid JSON only. verdict ∈ {SAME, DIFFERENT}. "
    "SAME only if they teach the same fact/concept with the same substance (wording may differ)."
)

DEDUP_SEMANTIC_ENABLED = os.getenv("DEDUP_SEMANTIC_ENABLED", "true").lower() not in {
    "false",
    "0",
    "no",
}
DEDUP_SEMANTIC_INTERVAL_SECONDS = int(os.getenv("DEDUP_SEMANTIC_INTERVAL_SECONDS", str(6 * 3600)))
DEDUP_SEMANTIC_SIM_THRESHOLD = float(os.getenv("DEDUP_SEMANTIC_SIM_THRESHOLD", "0.86"))
DEDUP_SEMANTIC_MAX_PAIRS = int(os.getenv("DEDUP_SEMANTIC_MAX_PAIRS", "80"))


async def _pairs(conn, sim: float, limit: int) -> list[dict]:
    rows = await conn.fetch(
        """
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
        """,
        sim,
    )
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for r in rows:
        key = tuple(sorted([r["a_id"], r["b_id"]]))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(r))
    return out[:limit]


async def run_dedup_semantic(*, sim: float, max_pairs: int, apply: bool) -> dict:
    """Find + judge candidate pairs; auto-merge same-book SAME pairs iff apply=True.
    Cross-book SAME pairs are always report-only. Returns a summary dict."""
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    be = PgBackend()
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        cands = await _pairs(conn, sim, max_pairs)

        sem = asyncio.Semaphore(4)

        async def judge(p):
            async with sem:
                try:
                    r = await llm(
                        messages=[
                            {
                                "role": "user",
                                "content": (
                                    f"A: {(p['a_tx'] or '')[:550]}\n\nB: {(p['b_tx'] or '')[:550]}\n\n"
                                    'JSON: {"verdict":"SAME|DIFFERENT"}'
                                ),
                            }
                        ],
                        system=JUDGE_SYS,
                        max_tokens=40,
                    )
                    t = "".join(
                        b.get("text", "") for b in r.get("content", []) if b.get("type") == "text"
                    )
                    m = re.search(r"\{.*\}", t, re.DOTALL)
                    return (
                        {**p, "verdict": (json.loads(m.group(0)).get("verdict") or "").upper()}
                        if m
                        else None
                    )
                except Exception:
                    return None

        judged = [j for j in await asyncio.gather(*(judge(p) for p in cands)) if j]
        sames = [j for j in judged if j["verdict"] == "SAME"]
        same_book = [j for j in sames if j["a_sub"] == j["b_sub"]]
        cross_book = [j for j in sames if j["a_sub"] != j["b_sub"]]

        merged = 0
        for p in same_book:
            keep, drop = (
                (p["a_id"], p["b_id"]) if p["a_len"] >= p["b_len"] else (p["b_id"], p["a_id"])
            )
            logger.info(
                "dedup_semantic same_book_dup sim=%.2f keep=%s drop=%s apply=%s",
                p["sim"],
                keep,
                drop,
                apply,
            )
            if apply:
                await conn.execute("UPDATE aii.edge_onto SET src_id=$1 WHERE src_id=$2", keep, drop)
                await conn.execute("UPDATE aii.edge_onto SET dst_id=$1 WHERE dst_id=$2", keep, drop)
                await be.delete_ku(drop)
                merged += 1

        for p in cross_book:
            # Never auto-merged — logged so a human can review and decide
            # same_as-edge vs leave-as-is. No table exists for a review queue;
            # structured logs are the review surface until one does.
            logger.info(
                "dedup_semantic cross_book_candidate sim=%.2f ku_a=%s ku_b=%s needs_human_review=true",
                p["sim"],
                p["a_id"],
                p["b_id"],
            )

        return {
            "candidates": len(cands),
            "same_verdicts": len(sames),
            "same_book_merged": merged,
            "cross_book_reported": len(cross_book),
            "applied": apply,
        }
    finally:
        await conn.close()


async def dedup_semantic_loop() -> None:
    """Periodic loop — started via asyncio.create_task() in app.py's lifespan,
    same pattern as background_flywheel.flywheel_loop."""
    if not DEDUP_SEMANTIC_ENABLED:
        logger.warning("dedup_semantic_loop disabled (DEDUP_SEMANTIC_ENABLED=false)")
        return
    await asyncio.sleep(120)  # let the app finish starting up first
    while True:
        try:
            summary = await run_dedup_semantic(
                sim=DEDUP_SEMANTIC_SIM_THRESHOLD, max_pairs=DEDUP_SEMANTIC_MAX_PAIRS, apply=True
            )
            logger.info("dedup_semantic_loop tick complete %s", summary)
        except Exception:
            logger.exception("dedup_semantic_loop tick failed")
        await asyncio.sleep(DEDUP_SEMANTIC_INTERVAL_SECONDS)
