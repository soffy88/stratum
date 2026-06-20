"""scan_ocr router — 扫描版 PDF OCR 触发 API（Stratum Layer 4）。

POST /api/v1/documents/{id}/ocr  → 单本 OCR（后台任务）
POST /api/v1/admin/ocr-batch     → 批量 OCR（后台任务）
GET  /api/v1/admin/ocr-candidates → 查看待 OCR 候选列表
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from stratum.api.deps import get_current_user
from stratum.db import get_conn

log = logging.getLogger(__name__)

router = APIRouter(tags=["scan-ocr"])


def _run_ocr_one(substrate_id: str, force: bool) -> None:
    from stratum.services.scan_ocr_service import ocr_one
    try:
        result = ocr_one(substrate_id, force=force)
        log.info("scan_ocr background done: %s", result)
    except Exception as exc:
        log.error("scan_ocr background failed %s: %s", substrate_id[:12], exc, exc_info=True)


def _run_ocr_batch(user_id: str | None, force: bool, max_books: int) -> None:
    from stratum.services.scan_ocr_service import ocr_batch
    try:
        result = ocr_batch(user_id=user_id, force=force, max_books=max_books)
        log.info("scan_ocr batch done: ok=%s err=%s skip=%s", result["ok"], result["error"], result["skipped"])
    except Exception as exc:
        log.error("scan_ocr batch failed: %s", exc, exc_info=True)


@router.post("/api/v1/documents/{substrate_id}/ocr")
async def trigger_ocr_one(
    substrate_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(False, description="Force re-OCR even if already ocr_ok"),
    user=Depends(get_current_user),
):
    """触发单本扫描书 OCR（异步后台）。"""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, parse_quality, mime FROM substrates WHERE id=?",
            (substrate_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="substrate not found")

    sid, title, pq, mime = row
    if not force and pq == "ocr_ok":
        return {"status": "skipped", "reason": "already ocr_ok", "substrate_id": sid}

    if mime and "pdf" not in (mime or "").lower():
        raise HTTPException(status_code=422, detail=f"OCR only supported for PDF, got mime={mime}")

    background_tasks.add_task(_run_ocr_one, sid, force)
    return {
        "status": "queued",
        "substrate_id": sid,
        "title": title,
        "parse_quality": pq,
        "message": "OCR started in background. Check logs for progress.",
    }


@router.post("/api/v1/admin/ocr-batch")
async def trigger_ocr_batch(
    background_tasks: BackgroundTasks,
    force: bool = Query(False),
    max_books: int = Query(50, ge=1, le=200),
    user=Depends(get_current_user),
):
    """批量 OCR 所有 scanned/empty/garbled substrates（异步后台）。"""
    from stratum.services.scan_ocr_service import _OCR_TARGET_PQ

    pq_filter = list(_OCR_TARGET_PQ)
    if force:
        pq_filter.append("ocr_ok")

    placeholders = ", ".join("?" * len(pq_filter))
    with get_conn() as conn:
        count_row = conn.execute(
            f"SELECT COUNT(*) FROM substrates WHERE parse_quality IN ({placeholders}) AND mime LIKE '%pdf%'",
            pq_filter,
        ).fetchone()
    candidate_count = count_row[0] if count_row else 0

    background_tasks.add_task(_run_ocr_batch, None, force, max_books)
    return {
        "status": "queued",
        "candidate_count": candidate_count,
        "max_books": max_books,
        "message": "Batch OCR started in background. Check logs for progress.",
    }


@router.get("/api/v1/admin/ocr-candidates")
async def list_ocr_candidates(
    user=Depends(get_current_user),
):
    """列出所有待 OCR 候选（dry-run 视图）。"""
    from stratum.services.scan_ocr_service import ocr_batch
    result = ocr_batch(dry_run=True)
    return result
