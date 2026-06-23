"""P3 级联删除 API — DELETE /api/source/{source_id} 和 DELETE /api/ku/{ku_id}.

命门:
  - dry_run 默认 True — 只报告影响范围,不真删
  - 真删需显式传 ?dry_run=false
  - 只 AII_API_KEY 可调用(STRATUM_API_KEY 是只读 key,不能删)
  - 共享 KU(多来源支撑)由 cascade_delete 自动保留
"""
from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Header, Path, Query

from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response

router = APIRouter()


def _require_admin_key(x_api_key: str = Header(..., alias="X-API-Key")) -> None:
    """FastAPI dependency: only AII_API_KEY (admin) may perform delete operations."""
    main_key = os.getenv("AII_API_KEY", "")
    if not main_key:
        raise HTTPException(status_code=500, detail="AII_API_KEY not configured")
    if not secrets.compare_digest(x_api_key, main_key):
        raise HTTPException(status_code=403, detail="Admin key required for delete operations")


@router.delete("/source/{source_id}", dependencies=[Depends(_require_admin_key)])
async def delete_source(
    source_id: str = Path(..., description="substrate_id to cascade-delete"),
    dry_run: bool = Query(True, description="默认 True(只报告); 传 false 才真删"),
):
    """Cascade-delete a source (substrate) and all KUs exclusively supported by it.

    dry_run=true (default): report only, nothing deleted.
    dry_run=false: execute deletion (admin key required).
    Shared KUs (supported by multiple sources) are always preserved.
    """
    try:
        from oskill.cascade_delete import cascade_delete
    except ImportError:
        try:
            from oskill._cascade_delete import cascade_delete
        except ImportError:
            return error_response("NOT_IMPLEMENTED", "cascade_delete element not available")

    try:
        result = await cascade_delete(
            source_id=source_id,
            db_conn=backend,
            dry_run=dry_run,
        )
        return success_response({
            "source_id": source_id,
            "dry_run": result.dry_run,
            "deleted_ku_count": len(result.deleted_ku_ids),
            "preserved_ku_count": len(result.preserved_ku_ids),
            "dangling_deps_cleared": result.dangling_deps_cleared,
            "deleted_ku_ids": result.deleted_ku_ids,
            "preserved_ku_ids": result.preserved_ku_ids,
        })
    except Exception as e:
        return error_response("CASCADE_DELETE_ERROR", str(e))


@router.delete("/ku/{ku_id}", dependencies=[Depends(_require_admin_key)])
async def delete_ku(
    ku_id: str = Path(..., description="ku_id (UUID) to delete"),
    dry_run: bool = Query(True, description="默认 True(只报告); 传 false 才真删"),
):
    """Delete a single KU and all its dependents (edges, state history, concept count).

    dry_run=true (default): report dangling deps count, nothing deleted.
    dry_run=false: execute deletion.
    """
    try:
        dep_count = await backend.get_dangling_deps_count(ku_id)
        if not dry_run:
            await backend.delete_ku(ku_id)
        return success_response({
            "ku_id": ku_id,
            "dry_run": dry_run,
            "dangling_deps_cleared": dep_count,
            "deleted": not dry_run,
        })
    except Exception as e:
        return error_response("DELETE_KU_ERROR", str(e))
