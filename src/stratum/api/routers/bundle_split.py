"""bundle_split router — EPUB 套装拆分 API（Stratum Layer 4）。

POST /api/v1/documents/{id}/split       → 拆分单个 EPUB 套装
POST /api/v1/admin/bundle-split-batch   → 批量拆分
POST /api/v1/admin/hash-backfill        → 回填 file_hash=NULL
POST /api/v1/admin/dedup-by-hash        → 同 SHA256 去重
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from stratum.api.deps import get_current_user
from stratum.db import get_conn

log = logging.getLogger(__name__)

router = APIRouter(tags=["bundle-split"])


@router.post("/api/v1/documents/{substrate_id}/split")
async def trigger_split_one(
    substrate_id: str,
    background_tasks: BackgroundTasks,
    force: bool = Query(False),
    user=Depends(get_current_user),
):
    """拆分单个 EPUB 套装（同步执行，结果直接返回）。"""
    from stratum.services.bundle_split_service import split_one
    result = split_one(substrate_id, force=force)
    if result["status"] == "not_found":
        raise HTTPException(status_code=404, detail="substrate not found")
    return result


@router.post("/api/v1/admin/bundle-split-batch")
async def trigger_split_batch(
    background_tasks: BackgroundTasks,
    force: bool = Query(False),
    user=Depends(get_current_user),
):
    """批量拆分所有检测到的 EPUB 套装（后台任务）。"""
    def _run():
        from stratum.services.bundle_split_service import split_batch
        result = split_batch(force=force)
        log.info("bundle_split batch done: %s", result)

    background_tasks.add_task(_run)
    return {"status": "queued", "message": "Bundle split batch started in background"}


@router.post("/api/v1/admin/hash-backfill")
async def trigger_hash_backfill(
    user=Depends(get_current_user),
):
    """回填所有 file_hash=NULL 的 EPUB substrates（同步）。"""
    from stratum.services.bundle_split_service import fix_hash_batch
    result = fix_hash_batch(only_null=True)
    return result


@router.post("/api/v1/admin/dedup-by-hash")
async def trigger_dedup(
    title_like: str = Query(..., description="LIKE pattern, e.g. '%投资者与市场%'"),
    user=Depends(get_current_user),
):
    """找同 title + 同 SHA256 的重复，保留最旧，其余标 duplicate。"""
    from stratum.services.bundle_split_service import deduplicate_same_hash, fix_file_hash
    import hashlib
    from pathlib import Path

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, source_path, file_hash FROM substrates WHERE title LIKE ?",
            (title_like,)
        ).fetchall()

    if not rows:
        return {"status": "not_found", "title_like": title_like}

    # 确保所有都有 hash
    for sid, sp, fh in rows:
        if not fh and sp and Path(sp).exists():
            fix_file_hash(sid)

    # 重新读 hash
    with get_conn() as conn:
        rows2 = conn.execute(
            "SELECT id, file_hash FROM substrates WHERE title LIKE ?",
            (title_like,)
        ).fetchall()

    by_hash: dict[str, list[str]] = {}
    for sid, fh in rows2:
        if fh:
            by_hash.setdefault(fh, []).append(sid)

    results = []
    for fh, ids in by_hash.items():
        if len(ids) > 1:
            res = deduplicate_same_hash(ids)
            results.append({**res, "file_hash": fh[:16]})

    return {"status": "done", "groups": len(results), "results": results}
