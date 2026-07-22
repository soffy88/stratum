"""quality.py — 存量质保扫描 API (Stratum Layer 4, §20).

POST /api/v1/admin/quality-audit   触发全库扫描，写 pq/quality_reason
GET  /api/v1/admin/quality-report  返回当前 pq 分布 + quarantine/fragment 清单
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends

from stratum.common import jwt_auth
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(prefix="/api/v1/admin", tags=["quality"])
log = logging.getLogger(__name__)

# 全库扫描状态（进程级）
_audit_state: dict = {"running": False, "done": 0, "total": 0, "errors": 0}


def _run_full_audit() -> dict:
    """同步扫描全库，逐条过 quality gate。在 to_thread 里运行。"""
    from stratum.lib.quality.ingest_quality_gate import run_quality_gate

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM substrates WHERE parse_quality NOT IN"
            " ('duplicate', 'bundle', 'bundle_child') OR parse_quality IS NULL"
        ).fetchall()

    ids = [r[0] for r in rows]
    _audit_state.update({"running": True, "done": 0, "total": len(ids), "errors": 0})
    log.info("quality_audit: starting, %d substrates", len(ids))

    results: dict[str, list[str]] = {
        "ok": [],
        "quarantine": [],
        "fragment": [],
        "scanned": [],
        "empty": [],
        "garbled": [],
        "other": [],
    }

    for sid in ids:
        try:
            r = run_quality_gate(sid)
            pq = r.get("pq") or "other"
            results.setdefault(pq, []).append(sid)
        except Exception as exc:
            log.warning("quality_audit: error on %s: %s", sid[:12], exc)
            _audit_state["errors"] += 1
        _audit_state["done"] += 1

    _audit_state["running"] = False
    log.info(
        "quality_audit: done — ok=%d quarantine=%d fragment=%d scanned=%d errors=%d",
        len(results["ok"]),
        len(results.get("quarantine", [])),
        len(results.get("fragment", [])),
        len(results.get("scanned", [])),
        _audit_state["errors"],
    )
    return results


@router.post("/quality-audit")
async def trigger_quality_audit(
    background_tasks: BackgroundTasks,
    _user: str = Depends(jwt_auth),
):
    """后台触发全库 pq 回填扫描（幂等：重跑会覆盖上次结果）."""
    if _audit_state["running"]:
        return {"status": "already_running", **_audit_state}
    background_tasks.add_task(asyncio.to_thread, _run_full_audit)
    return {"status": "started", "message": "扫描已在后台启动，GET /quality-report 查看进度"}


@router.get("/quality-audit/status")
async def audit_status(_user: str = Depends(jwt_auth)):
    return _audit_state


@router.get("/quality-report")
async def quality_report(_user: str = Depends(jwt_auth)):
    """返回当前 pq 分布 + quarantine/fragment 详情."""
    with get_conn() as conn:
        pq_rows = conn.execute(
            "SELECT COALESCE(parse_quality, 'None') AS pq, COUNT(*) AS cnt"
            " FROM substrates GROUP BY parse_quality ORDER BY cnt DESC"
        ).fetchall()

        quarantine_rows = conn.execute(
            "SELECT id, title, quality_reason FROM substrates"
            " WHERE parse_quality = 'quarantine' ORDER BY updated_at DESC"
        ).fetchall()

        fragment_rows = conn.execute(
            "SELECT id, title FROM substrates"
            " WHERE parse_quality = 'fragment' ORDER BY updated_at DESC"
        ).fetchall()

    return {
        "pq_distribution": {pq: cnt for pq, cnt in pq_rows},
        "quarantine": [{"id": r[0], "title": r[1], "reason": r[2]} for r in quarantine_rows],
        "fragment": [{"id": r[0], "title": r[1]} for r in fragment_rows],
    }


@router.get("/aii-needs-status")
async def aii_needs_status(_user: str = Depends(jwt_auth)):
    """查 aii_processed_needs 历史记录 + 当前 needs.json。"""
    import json as _json
    from pathlib import Path

    with get_conn() as conn:
        try:
            rows = conn.execute(
                "SELECT need_hash, topic, source_type, ingested_count, processed_at"
                " FROM aii_processed_needs ORDER BY processed_at DESC"
            ).fetchall()
            processed = [
                {
                    "hash": r[0],
                    "topic": r[1],
                    "source_type": r[2],
                    "ingested": r[3],
                    "at": str(r[4]),
                }
                for r in rows
            ]
        except Exception as exc:
            processed = [{"error": str(exc)}]

    needs_path = Path("/data/shared/aii-to-stratum/needs.json")
    try:
        current_needs = _json.loads(needs_path.read_text())
    except Exception as exc:
        current_needs = {"error": str(exc)}

    return {"aii_processed_needs": processed, "current_needs": current_needs}


@router.post("/aii-tick")
async def trigger_aii_tick(
    background_tasks: BackgroundTasks,
    _user: str = Depends(jwt_auth),
):
    """手动触发一次 aii_feedback _tick()（调试用）。"""

    async def _do_tick():
        from stratum.services.aii_feedback_service import _tick

        try:
            await _tick()
            log.info("aii_tick: manual tick completed")
        except Exception:
            log.exception("aii_tick: manual tick failed")

    background_tasks.add_task(_do_tick)
    return {"status": "started", "message": "aii_feedback _tick() 已在后台触发"}


@router.post("/md-export-one")
async def export_one_substrate(
    body: dict,
    background_tasks: BackgroundTasks,
    _user: str = Depends(jwt_auth),
):
    """触发单个 substrate 的 md_export（写 AII 共享目录）。body: {substrate_id: "..."}"""
    sid = body.get("substrate_id", "")
    if not sid:
        from fastapi import HTTPException

        raise HTTPException(400, "substrate_id required")

    async def _do_export():
        from stratum.services.md_export_service import export_one

        try:
            # 手动API触发的重导出=人明确要求, 绕过 exported_at 防重
            result = await asyncio.to_thread(lambda: export_one(sid, force=True))
            log.info("md_export_one: %s → %s", sid[:12], result)
        except Exception:
            log.exception("md_export_one: failed for %s", sid[:12])

    background_tasks.add_task(_do_export)
    return {"status": "started", "substrate_id": sid}


def _owns_substrate(conn, substrate_id: str, user_id: str) -> bool:
    """These /admin/* routes have no real admin-role check (none exists in the
    schema) — they were reachable by any authenticated user against ANY other
    user's substrates. substrates.user_id is stored either hashed
    (hash_user_id) or raw depending on ingestion path (same backward-compat
    duality substrates.py's list endpoint already accounts for), so check both."""
    row = conn.execute(
        "SELECT 1 FROM substrates WHERE id = ? AND (user_id = ? OR user_id = ?)",
        (substrate_id, hash_user_id(user_id), user_id),
    ).fetchone()
    return row is not None


@router.patch("/derivative-content")
async def patch_derivative_content(
    payload: dict,
    user: str = Depends(jwt_auth),
):
    """Overwrite derivative.content for a specific substrate+kind (admin use).

    Body: {"substrate_id": "...", "kind": "markdown", "content": "..."}
    Used by scripts (e.g. fix_werner_fffd.py) to write fixed content while
    the server holds the DuckDB write lock.
    """
    from fastapi import HTTPException

    sid = payload.get("substrate_id")
    kind = payload.get("kind", "markdown")
    content = payload.get("content")
    if not sid or not content:
        raise HTTPException(status_code=400, detail="substrate_id and content required")

    with get_conn() as conn:
        if not _owns_substrate(conn, sid, user):
            raise HTTPException(status_code=404, detail="substrate not found")
        rows = conn.execute(
            "UPDATE derivative SET content = ? WHERE substrate_id = ? AND kind = ?",
            (content, sid, kind),
        ).rowcount
    log.info("patch_derivative_content: updated %d row(s) for %s kind=%s", rows, sid[:12], kind)
    return {"updated": rows, "substrate_id": sid, "kind": kind}


@router.delete("/substrates/{substrate_id}")
async def delete_substrate(
    substrate_id: str,
    user: str = Depends(jwt_auth),
):
    """Hard-delete a substrate and its derivatives (admin use).

    Used by scripts/cleanup_library.py for bulk dedup cleanup.
    """
    from fastapi import HTTPException

    with get_conn() as conn:
        if not _owns_substrate(conn, substrate_id, user):
            raise HTTPException(status_code=404, detail="substrate not found")
        d_rows = conn.execute(
            "DELETE FROM derivative WHERE substrate_id = ?", (substrate_id,)
        ).rowcount
        s_rows = conn.execute("DELETE FROM substrates WHERE id = ?", (substrate_id,)).rowcount
    log.info(
        "delete_substrate: %s — substrates=%d derivatives=%d", substrate_id[:12], s_rows, d_rows
    )
    return {
        "deleted_substrates": s_rows,
        "deleted_derivatives": d_rows,
        "substrate_id": substrate_id,
    }


@router.patch("/substrates/bulk-title")
async def bulk_patch_title(
    payload: dict,
    user: str = Depends(jwt_auth),
):
    """Bulk-update substrate titles (only for substrates the caller owns —
    unowned ids in the batch are skipped, not silently applied).

    Body: {"updates": [{"id": "...", "title": "..."}, ...]}
    Used by scripts/cleanup_library.py for z-lib tag stripping.
    """
    from fastapi import HTTPException

    updates = payload.get("updates", [])
    if not updates:
        raise HTTPException(status_code=400, detail="updates list required")

    count = 0
    skipped = 0
    with get_conn() as conn:
        for item in updates:
            sid = item.get("id")
            title = item.get("title")
            if not sid or not title:
                continue
            if not _owns_substrate(conn, sid, user):
                skipped += 1
                continue
            conn.execute("UPDATE substrates SET title = ? WHERE id = ?", (title, sid))
            count += 1
    log.info("bulk_patch_title: updated %d titles, skipped %d not-owned", count, skipped)
    return {"updated": count, "skipped_not_owned": skipped}
