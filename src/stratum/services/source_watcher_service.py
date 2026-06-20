"""Unified source watcher: arXiv / Gutenberg / OAPEN.

Pipeline per subscription:
  search (oprim) → diff vs processed_ids → download → process_inbox_substrate → md_export → mark_processed
"""
from __future__ import annotations

import asyncio
import json
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from stratum.db import get_conn
from stratum.services.source_subscription_store import SourceSubscriptionStore

log = logging.getLogger(__name__)

# Per-source scan intervals (seconds)
SCAN_INTERVALS = {
    "arxiv": 6 * 3600,
    "gutenberg": 30 * 86400,
    "oapen": 30 * 86400,
}
SOURCE_WATCHER_TICK = 3600  # check every hour which subscriptions are due


# ── Download + ingest one item ────────────────────────────────────────────────

async def _ingest_item(result, user_id_hash: str, sub_id: str) -> str | None:
    """Download file and ingest. Returns substrate_id or None."""
    from omodul.process_inbox_substrate import process_inbox_substrate, InboxConfig, InboxInput
    from oprim import http_download_file
    import hashlib
    import re

    medium_hint = result.file_type  # "pdf" | "epub" | "txt"

    with tempfile.TemporaryDirectory(prefix="srcwatch_") as tmpdir:
        ext = {"pdf": ".pdf", "epub": ".epub", "txt": ".txt"}.get(medium_hint, ".bin")
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", result.external_id)
        file_path = Path(tmpdir) / f"{safe_id}{ext}"

        ok = await asyncio.to_thread(
            http_download_file,
            result.download_url,
            str(file_path),
            rate_limit_sleep=2.0,
            timeout=90,
        )
        if not ok:
            log.warning("source_watcher: download failed ext_id=%s url=%s", result.external_id, result.download_url[:80])
            return None

        with open(file_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        config = InboxConfig(
            file_path=file_path,
            file_checksum=checksum,
            user_id_hash=user_id_hash,
            medium_hint=medium_hint,
            auto_classify=True,
            llm_provider="qwen3_dashscope",
            llm_model="qwen-plus",
        )
        try:
            res = await asyncio.to_thread(
                process_inbox_substrate,
                config=config,
                input_data=InboxInput(),
                output_dir=file_path.parent,
            )
        except Exception as exc:
            log.error("source_watcher: process_inbox failed ext_id=%s: %s", result.external_id, exc)
            return None

        if res.get("status") == "failed":
            return None

        findings = res.get("findings")
        sid_raw = getattr(findings, "substrate_id", None) if findings else None
        if not sid_raw:
            return None

        m = re.search(r"[0-9A-Z]{26}", str(sid_raw))
        if not m:
            return None
        sid = m.group(0)

        # Patch metadata
        try:
            with get_conn() as conn:
                row = conn.execute("SELECT meta_json FROM substrates WHERE id=?", (sid,)).fetchone()
                meta = json.loads(row[0] or "{}") if row else {}
                meta.update(result.metadata)
                meta["source_type"] = result.metadata.get("source_type", "unknown")
                meta["medium"] = medium_hint
                conn.execute(
                    "UPDATE substrates SET meta_json=?, title=? WHERE id=?",
                    (json.dumps(meta, ensure_ascii=False), result.title, sid),
                )
        except Exception as exc:
            log.warning("source_watcher: meta patch failed sid=%s: %s", sid, exc)

        try:
            from stratum.services.md_export_service import export_one
            export_one(sid)
        except Exception as exc:
            log.warning("source_watcher: md_export failed sid=%s: %s", sid, exc)

        return sid


# ── Per-subscription scan ─────────────────────────────────────────────────────

async def _check_one_subscription(sub_id: str, user_id_hash: str, source_type: str, query: dict, max_results: int):
    with get_conn() as conn:
        conn.execute(
            "UPDATE source_subscriptions SET scan_status='scanning', current_item='' WHERE id=?",
            (sub_id,),
        )

    store = SourceSubscriptionStore(sub_id)
    processed_ids = store.get_processed_ids()

    # Search
    try:
        if source_type == "arxiv":
            from oprim import arxiv_search
            items = await asyncio.to_thread(
                arxiv_search,
                categories=query.get("categories") or [],
                keywords=query.get("keywords"),
                author=query.get("author"),
                after_date=query.get("after_date"),
                max_results=max_results,
                rate_limit_sleep=3.0,
            )
            # Wrap ArxivPaper to SourceResult interface
            from oprim._media_types import SourceResult
            results = [
                SourceResult(
                    external_id=p.arxiv_id,
                    title=p.title,
                    download_url=p.pdf_url,
                    file_type="pdf",
                    metadata={
                        "arxiv_id": p.arxiv_id,
                        "arxiv_url": f"https://arxiv.org/abs/{p.arxiv_id}",
                        "authors": p.authors[:5],
                        "published": p.published,
                        "source_type": "arxiv",
                    },
                )
                for p in items
            ]
        elif source_type == "gutenberg":
            from oprim import gutenberg_search
            results = await asyncio.to_thread(
                gutenberg_search,
                topic=query.get("topic"),
                languages=query.get("languages") or ["en"],
                keywords=query.get("keywords"),
                author=query.get("author"),
                max_results=max_results,
                rate_limit_sleep=1.0,
            )
        elif source_type == "oapen":
            from oprim import oapen_search
            results = await asyncio.to_thread(
                oapen_search,
                query=query.get("query") or "",
                language=query.get("language"),
                max_results=max_results,
                rate_limit_sleep=2.0,
            )
        else:
            log.error("source_watcher: unknown source_type=%s", source_type)
            results = []
    except Exception as exc:
        log.error("source_watcher: search failed sub=%s type=%s: %s", sub_id, source_type, exc)
        with get_conn() as conn:
            conn.execute(
                "UPDATE source_subscriptions SET scan_status='error', current_item=? WHERE id=?",
                (str(exc)[:300], sub_id),
            )
        return

    new_items = [r for r in results if r.external_id not in processed_ids]
    log.info("source_watcher: sub=%s type=%s found=%d new=%d", sub_id, source_type, len(results), len(new_items))

    with get_conn() as conn:
        row = conn.execute(
            "SELECT found_count, ingested_count FROM source_subscriptions WHERE id=?", (sub_id,)
        ).fetchone()
        prev_found = row[0] if row else 0
        prev_ingested = row[1] if row else 0
        conn.execute(
            "UPDATE source_subscriptions SET found_count=? WHERE id=?",
            (prev_found + len(new_items), sub_id),
        )

    ingested = 0
    for item in new_items:
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE source_subscriptions SET current_item=? WHERE id=?",
                    (item.title[:200], sub_id),
                )
            sid = await _ingest_item(item, user_id_hash, sub_id)
            if sid:
                store.mark_processed(item.external_id)
                ingested += 1
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE source_subscriptions SET ingested_count=? WHERE id=?",
                        (prev_ingested + ingested, sub_id),
                    )
        except Exception as exc:
            log.error("source_watcher: ingest failed ext_id=%s: %s", item.external_id, exc)

    with get_conn() as conn:
        conn.execute(
            "UPDATE source_subscriptions SET scan_status='completed', last_check=NOW(), "
            "current_item='', ingested_count=? WHERE id=?",
            (prev_ingested + ingested, sub_id),
        )
    log.info("source_watcher: sub=%s ingested=%d", sub_id, ingested)


async def run_first_check(sub_id: str, user_id_hash: str, source_type: str, query: dict, max_results: int):
    try:
        await _check_one_subscription(sub_id, user_id_hash, source_type, query, max_results)
    except Exception:
        log.exception("source_watcher: first_check failed sub=%s", sub_id)


# ── Main watcher loop ─────────────────────────────────────────────────────────

async def source_watcher_loop():
    await asyncio.sleep(90)  # startup delay
    while True:
        try:
            with get_conn() as conn:
                subs = conn.execute(
                    "SELECT id, user_id, source_type, query_json, max_results, last_check "
                    "FROM source_subscriptions WHERE status='active'"
                ).fetchall()

            now = datetime.now(timezone.utc)
            for row in subs:
                sub_id, user_id_hash, source_type, query_json, max_results, last_check = row
                interval = SCAN_INTERVALS.get(source_type, 6 * 3600)
                if last_check is not None:
                    # last_check may be naive or aware
                    lc = last_check
                    if hasattr(lc, "tzinfo") and lc.tzinfo is None:
                        lc = lc.replace(tzinfo=timezone.utc)
                    elapsed = (now - lc).total_seconds()
                    if elapsed < interval:
                        continue
                query = json.loads(query_json or "{}")
                await _check_one_subscription(
                    sub_id, user_id_hash, source_type, query, max_results or 10
                )
        except Exception as exc:
            log.error("source_watcher_loop error: %s", exc)
        await asyncio.sleep(SOURCE_WATCHER_TICK)
