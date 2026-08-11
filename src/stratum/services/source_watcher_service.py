"""Unified source watcher: arXiv / Gutenberg / OAPEN / WeChat / Twitter.

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
    "openstax": 30 * 86400,
    "mit_ocw": 30 * 86400,
    "wechat": 6 * 3600,   # 微信: 每 6h (手动 URL 列表)
    "twitter": 3 * 3600,  # Twitter: 每 3h (用户名/关键词)
}
SOURCE_WATCHER_TICK = 3600  # check every hour which subscriptions are due


# ── Download + ingest one item ────────────────────────────────────────────────


async def _ingest_item(result, user_id_hash: str, sub_id: str) -> str | None:
    """Download file and ingest (parse runs in an isolated subprocess). Returns substrate_id or None."""
    from oprim import http_download_file
    from stratum.services.inbox_isolation import is_quarantined, record_attempt, run_isolated
    import hashlib
    import re

    source_type = (result.metadata or {}).get("source_type", "unknown")

    # ★2026-07-10 自动隔离台账(取代硬编码 _POISON_EXTERNAL_IDS): 反复崩溃/挂死解析器的条目
    #   会被自动记账并在阈值后隔离, 不再靠人肉维护毒丸ID表, 也不会崩溃-重启循环。
    if is_quarantined(result.external_id):
        log.warning("source_watcher: SKIP quarantined ext_id=%s", result.external_id)
        return None

    file_type = result.file_type  # "pdf" | "epub" | "txt" | "html"
    # 书源的下载物是"书"不是"论文": medium 直接沿用 file_type 时, md_export 的
    # pdf→paper 映射会把 PDF 教材打成 doc_type:paper, aii 侧 classify 一律扔低质堆
    # (2026-07-11 实测 openstax《Principles of Finance 2e》如此报废, 历史 gutenberg
    # PDF 同理)。arxiv 论文仍走 file_type(pdf→paper 正确)。
    medium_hint = (
        "book" if source_type in ("gutenberg", "oapen", "openstax", "mit_ocw") else
        "webpage" if source_type in ("wechat", "twitter") else file_type
    )

    # ★2026-08-07: web sources (wechat/twitter) already have content via enhanced fetcher
    # 直接写入 HTML 文件, 跳过 binary download
    is_web_source = source_type in ("wechat", "twitter")
    content_preview = (result.metadata or {}).get("content_preview", "")

    with tempfile.TemporaryDirectory(prefix="srcwatch_") as tmpdir:
        ext = {"pdf": ".pdf", "epub": ".epub", "txt": ".txt", "html": ".html"}.get(file_type, ".bin")
        safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", result.external_id)
        file_path = Path(tmpdir) / f"{safe_id}{ext}"

        # Web source: 直接写入 HTML 内容 (已通过 enhanced fetcher 抓取)
        if is_web_source and content_preview:
            file_path.write_text(
                f"<html><body>{content_preview}</body></html>", encoding="utf-8")
            ok = True
        else:
            ok = await asyncio.to_thread(
                http_download_file,
                result.download_url,
                str(file_path),
                rate_limit_sleep=2.0,
                timeout=90,
            )
        if not ok:
            log.warning(
                "source_watcher: download failed ext_id=%s url=%s",
                result.external_id,
                result.download_url[:80],
            )
            # download failure is transient/infra (see oprim http_download_file retry);
            # log as infra_fail so it never consumes the item's quarantine budget.
            record_attempt(result.external_id, source_type, "infra_fail", "download failed")
            return None

        with open(file_path, "rb") as f:
            checksum = hashlib.sha256(f.read()).hexdigest()

        # If the same file was already ingested, return the existing sid so
        # mark_processed is called and the retry loop stops.
        try:
            with get_conn() as conn:
                dup = conn.execute(
                    "SELECT id FROM substrates WHERE user_id=? AND file_hash=? LIMIT 1",
                    (user_id_hash, checksum),
                ).fetchone()
            if dup:
                log.info(
                    "source_watcher: already ingested ext_id=%s sid=%s", result.external_id, dup[0]
                )
                return dup[0]
        except Exception:
            pass  # if DB is unavailable, let the isolated run handle it

        # ── isolated parse+ingest: a native crash/hang can't kill the service ──
        timeout = 600.0 if source_type == "arxiv" else 1800.0
        job = {
            "file_path": str(file_path),
            "file_checksum": checksum,
            "user_id_hash": user_id_hash,
            "medium_hint": medium_hint,
            "output_dir": str(file_path.parent),
            "llm_provider": "qwen3_dashscope",
            "llm_model": "qwen-plus",
        }
        iso = await asyncio.to_thread(run_isolated, job, timeout)
        quarantined = record_attempt(
            result.external_id, source_type, iso["outcome"], iso.get("error")
        )
        if iso["outcome"] != "completed":
            log.warning(
                "source_watcher: ext_id=%s outcome=%s%s (%s)",
                result.external_id,
                iso["outcome"],
                " → QUARANTINED" if quarantined else "",
                (iso.get("error") or "")[:120],
            )
            return None

        sid_raw = iso.get("substrate_id")
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
            from stratum.lib.quality.ingest_quality_gate import run_quality_gate

            run_quality_gate(sid)
        except Exception as exc:
            log.warning("source_watcher: quality gate failed sid=%s: %s", sid, exc)
        try:
            from stratum.services.md_export_service import export_one

            # export_one 内部用 asyncio.run(); 此处身处事件循环, 必须丢到线程执行
            # (否则 RuntimeError: asyncio.run() cannot be called from a running event loop)
            await asyncio.to_thread(export_one, sid)
        except Exception as exc:
            log.warning("source_watcher: md_export failed sid=%s: %s", sid, exc)

        # Phase 1: Generate L0/L1 layers for substrate
        try:
            from stratum.services.layer_generator import generate_substrate_layers
            with get_conn() as _c:
                _row = _c.execute(
                    "SELECT title FROM substrates WHERE id=?", (sid,)
                ).fetchone()
            _title = _row[0] if _row else None
            generate_substrate_layers(sid, title=_title, content=None)
        except Exception as exc:
            log.warning("source_watcher: layer generation failed sid=%s: %s", sid, exc)

        # Phase 2: Register in directory tree (incremental update)
        try:
            from stratum.services.directory_builder import register_substrate
            with get_conn() as _c:
                _row = _c.execute(
                    "SELECT title, COALESCE(meta_json->>'discipline', '') FROM substrates WHERE id=?",
                    (sid,),
                ).fetchone()
            if _row:
                _title = _row[0] or sid[:16]
                _disc = _row[1] or None
                _l0 = None
                with get_conn() as _c2:
                    _l0_row = _c2.execute(
                        "SELECT content FROM substrate_layers WHERE substrate_id=? AND layer='L0'",
                        (sid,),
                    ).fetchone()
                    if _l0_row:
                        _l0 = _l0_row[0]
                register_substrate(sid, _title, _disc, _l0)
        except Exception as exc:
            log.warning("source_watcher: directory registration failed sid=%s: %s", sid, exc)

        return sid


# ── Per-subscription scan ─────────────────────────────────────────────────────


async def _check_one_subscription(
    sub_id: str, user_id_hash: str, source_type: str, query: dict, max_results: int
):
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
            from stratum.services.oapen_direct_search import oapen_direct_search

            results = await asyncio.to_thread(
                oapen_direct_search,
                query=query.get("query") or "",
                language=query.get("language"),
                max_results=max_results,
                rate_limit_sleep=2.0,
            )
        elif source_type == "openstax":
            from stratum.services.openstax_search import openstax_search

            results = await asyncio.to_thread(
                openstax_search,
                subjects=query.get("subjects"),
                keywords=query.get("keywords"),
                max_results=max_results,
                max_pdf_mb=float(query.get("max_pdf_mb", 0.0)),
                rate_limit_sleep=1.0,
            )
        elif source_type == "mit_ocw":
            from stratum.services.mit_ocw_search import mit_ocw_search

            results = await asyncio.to_thread(
                mit_ocw_search,
                departments=query.get("departments"),
                keywords=query.get("keywords"),
                max_courses=query.get("max_courses", 20),
                max_pdfs_per_course=query.get("max_pdfs_per_course", 8),
                rate_limit_sleep=1.5,
            )
        elif source_type == "wechat":
            from stratum.services.web_source_handlers import wechat_fetch_articles

            results = await wechat_fetch_articles(
                urls=query.get("urls") or [],
                keyword=query.get("keyword"),
                max_results=max_results,
            )
        elif source_type == "twitter":
            from stratum.services.web_source_handlers import twitter_fetch_threads

            results = await twitter_fetch_threads(
                usernames=query.get("usernames") or [],
                keyword=query.get("keyword"),
                max_results=max_results,
                urls=query.get("urls") or [],
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
    log.info(
        "source_watcher: sub=%s type=%s found=%d new=%d",
        sub_id,
        source_type,
        len(results),
        len(new_items),
    )

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


async def run_first_check(
    sub_id: str, user_id_hash: str, source_type: str, query: dict, max_results: int
):
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
