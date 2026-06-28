"""arXiv subscription watcher.

Pipeline per subscription:
  oprim.arxiv_search → diff vs processed_ids → download PDF (oprim.http_download_file) →
  process_inbox_substrate(medium_hint=pdf) → md_export → mark_processed
"""
from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from stratum.db import get_conn
from stratum.services.arxiv_subscription_store import ArxivSubscriptionStore

log = logging.getLogger(__name__)

ARXIV_CHECK_INTERVAL = 6 * 3600  # 6小时


# ── Ingest one paper ──────────────────────────────────────────────────────────

async def _ingest_paper(paper, user_id_hash: str, sub_id: str) -> str | None:
    """Download PDF and ingest via process_inbox_substrate. Returns substrate_id or None."""
    from omodul.process_inbox_substrate import process_inbox_substrate, InboxConfig, InboxInput
    from oprim import http_download_file
    import hashlib

    with tempfile.TemporaryDirectory(prefix="arxiv_ingest_") as tmpdir:
        pdf_path = Path(tmpdir) / f"{paper.arxiv_id.replace('/', '_')}.pdf"
        ok = await asyncio.to_thread(
            http_download_file,
            paper.pdf_url,
            str(pdf_path),
            rate_limit_sleep=3.0,
            timeout=60,
        )
        if not ok:
            log.warning("arxiv_ingest: PDF download failed for %s", paper.arxiv_id)
            return None

        with open(pdf_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        config = InboxConfig(
            file_path=pdf_path,
            file_checksum=checksum,
            user_id_hash=user_id_hash,
            medium_hint="pdf",
            auto_classify=True,
            llm_provider="qwen3_dashscope",
            llm_model="qwen-plus",
        )
        try:
            result = await asyncio.to_thread(
                process_inbox_substrate,
                config=config,
                input_data=InboxInput(),
                output_dir=pdf_path.parent,
            )
        except Exception as exc:
            log.error("arxiv_ingest: process_inbox_substrate failed arxiv=%s: %s", paper.arxiv_id, exc)
            return None

        if result.get("status") == "failed":
            return None

        findings = result.get("findings")
        sid_raw = getattr(findings, "substrate_id", None) if findings else None
        if not sid_raw:
            return None

        import re
        m = re.search(r"[0-9A-Z]{26}", str(sid_raw))
        if not m:
            return None
        sid = m.group(0)

        # Patch title + arxiv metadata into substrates
        import json
        try:
            with get_conn() as conn:
                row = conn.execute("SELECT meta_json FROM substrates WHERE id=?", (sid,)).fetchone()
                meta = json.loads(row[0] or "{}") if row else {}
                meta["arxiv_id"] = paper.arxiv_id
                meta["arxiv_url"] = f"https://arxiv.org/abs/{paper.arxiv_id}"
                meta["authors"] = paper.authors[:5]
                meta["published"] = paper.published
                meta["medium"] = "pdf"
                conn.execute(
                    "UPDATE substrates SET meta_json=?, title=? WHERE id=?",
                    (json.dumps(meta, ensure_ascii=False), paper.title, sid),
                )
        except Exception as exc:
            log.warning("arxiv_ingest: meta patch failed sid=%s: %s", sid, exc)

        # Quality gate then export
        try:
            from stratum.lib.quality.ingest_quality_gate import run_quality_gate
            run_quality_gate(sid)
        except Exception as exc:
            log.warning("arxiv_ingest: quality gate failed sid=%s: %s", sid, exc)
        try:
            from stratum.services.md_export_service import export_one
            export_one(sid)
        except Exception as exc:
            log.warning("arxiv_ingest: md_export failed sid=%s: %s", sid, exc)

        return sid


# ── Per-subscription scan ─────────────────────────────────────────────────────

async def _check_one_subscription(sub_id: str, user_id_hash: str, sub_cfg: dict):
    categories = sub_cfg.get("categories") or []
    keywords = sub_cfg.get("keywords")
    author = sub_cfg.get("author")
    after_date = sub_cfg.get("after_date")
    max_results = sub_cfg.get("max_results") or 10

    with get_conn() as conn:
        conn.execute(
            "UPDATE arxiv_subscriptions SET scan_status='scanning', current_paper='' WHERE id=?",
            (sub_id,),
        )

    store = ArxivSubscriptionStore(sub_id)
    processed_ids = store.get_processed_ids()

    try:
        from oprim import arxiv_search
        papers = await asyncio.to_thread(
            arxiv_search,
            categories=categories,
            keywords=keywords,
            author=author,
            after_date=after_date,
            max_results=max_results,
            rate_limit_sleep=1.0,
        )
    except Exception as exc:
        log.error("arxiv_watcher: fetch failed sub=%s: %s", sub_id, exc)
        with get_conn() as conn:
            conn.execute(
                "UPDATE arxiv_subscriptions SET scan_status='error', current_paper=? WHERE id=?",
                (str(exc)[:300], sub_id),
            )
        return

    new_papers = [p for p in papers if p.arxiv_id not in processed_ids]
    log.info("arxiv_watcher: sub=%s found=%d new=%d", sub_id, len(papers), len(new_papers))

    with get_conn() as conn:
        row = conn.execute(
            "SELECT found_count, ingested_count FROM arxiv_subscriptions WHERE id=?", (sub_id,)
        ).fetchone()
        existing_found = row[0] if row else 0
        existing_ingested = row[1] if row else 0
        conn.execute(
            "UPDATE arxiv_subscriptions SET found_count=? WHERE id=?",
            (existing_found + len(new_papers), sub_id),
        )

    ingested = 0
    for paper in new_papers:
        try:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE arxiv_subscriptions SET current_paper=? WHERE id=?",
                    (paper.title[:200], sub_id),
                )
            sid = await _ingest_paper(paper, user_id_hash, sub_id)
            if sid:
                store.mark_processed(paper.arxiv_id)
                ingested += 1
                with get_conn() as conn:
                    conn.execute(
                        "UPDATE arxiv_subscriptions SET ingested_count=? WHERE id=?",
                        (existing_ingested + ingested, sub_id),
                    )
        except Exception as exc:
            log.error("arxiv_watcher: ingest failed arxiv=%s: %s", paper.arxiv_id, exc)

    with get_conn() as conn:
        conn.execute(
            "UPDATE arxiv_subscriptions SET scan_status='completed', last_check=NOW(), "
            "current_paper='', ingested_count=? WHERE id=?",
            (existing_ingested + ingested, sub_id),
        )
    log.info("arxiv_watcher: sub=%s ingested=%d", sub_id, ingested)


async def _run_first_check(sub_id: str, user_id_hash: str, sub_cfg: dict):
    try:
        await _check_one_subscription(sub_id, user_id_hash, sub_cfg)
    except Exception:
        log.exception("arxiv first scan failed sub_id=%s", sub_id)


async def arxiv_watcher_loop():
    await asyncio.sleep(90)  # 启动延迟
    while True:
        try:
            with get_conn() as conn:
                subs = conn.execute(
                    "SELECT id, user_id, name, categories_json, keywords, author, "
                    "after_date, max_results FROM arxiv_subscriptions WHERE status='active'"
                ).fetchall()
            import json
            for row in subs:
                sub_id, user_id_hash = row[0], row[1]
                sub_cfg = {
                    "name": row[2],
                    "categories": json.loads(row[3] or "[]"),
                    "keywords": row[4],
                    "author": row[5],
                    "after_date": row[6],
                    "max_results": row[7] or 10,
                }
                await _check_one_subscription(sub_id, user_id_hash, sub_cfg)
        except Exception as exc:
            log.error("arxiv_watcher_loop error: %s", exc)
        await asyncio.sleep(ARXIV_CHECK_INTERVAL)
