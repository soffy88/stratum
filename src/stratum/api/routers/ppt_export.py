"""Book → editable PPT export API (luobo-ppt engine).

    GET  /api/v1/ppt/styles                       the 14 style presets
    GET  /api/v1/ppt/books/{substrate_id}/chapters chapters a deck can be built from
    POST /api/v1/ppt/exports                      start a job (202)
    GET  /api/v1/ppt/exports                      the caller's jobs (optionally per book)
    GET  /api/v1/ppt/exports/{job_id}             status, progress, QA summary
    GET  /api/v1/ppt/exports/{job_id}/download    the .pptx
    GET  /api/v1/ppt/exports/{job_id}/previews/{n} preview PNG of slide n

Ownership follows the /search IDOR fix: the book must belong to the caller (raw
or hashed owner id) before anything is read, and every job read filters on the
hashed owner id, so a foreign id is indistinguishable from an unknown one (404).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from stratum.common import jwt_auth
from stratum.services.ppt_export import jobs
from stratum.services.ppt_export.deck_builder import DEFAULT_PAGES, MAX_PAGES, MIN_PAGES
from stratum.services.ppt_export.styles import DEFAULT_STYLE, list_styles, style_ids

router = APIRouter(prefix="/api/v1/ppt", tags=["ppt-export"])


class ExportRequest(BaseModel):
    substrate_id: str | None = Field(None, max_length=64)
    run_id: str | None = Field(None, max_length=64)
    chapter_id: str | None = Field(None, max_length=32)
    style: str = DEFAULT_STYLE
    pages: int = Field(DEFAULT_PAGES, ge=MIN_PAGES, le=MAX_PAGES)
    audience: str = Field("", max_length=40)
    notes: bool = True


def _public(job: dict[str, Any]) -> dict[str, Any]:
    jid = job["id"]
    done = job.get("status") == "succeeded"
    return {
        "job_id": jid,
        "substrate_id": job.get("substrate_id"),
        "run_id": job.get("run_id"),
        "chapter_id": job.get("chapter_id"),
        "style": job.get("style"),
        "pages": job.get("pages"),
        "status": job.get("status"),
        "stage": job.get("stage"),
        "progress": job.get("progress") or 0,
        "title": job.get("title"),
        "language": job.get("language"),
        "slide_count": job.get("slide_count"),
        "file_size": job.get("file_size"),
        "qa": job.get("qa_json") or {},
        "error": job.get("error"),
        "created_at": str(job.get("created_at") or ""),
        "finished_at": str(job.get("finished_at") or "") or None,
        "download_url": f"/api/v1/ppt/exports/{jid}/download" if done else None,
        "preview_urls": [
            f"/api/v1/ppt/exports/{jid}/previews/{i}"
            for i in range(1, int(job.get("preview_count") or 0) + 1)
        ]
        if done
        else [],
    }


def _owned_job(user_id: str, job_id: str) -> dict[str, Any]:
    job = jobs.get_job(user_id, job_id)
    if not job:
        raise HTTPException(404, "export not found")
    return job


def _safe_file(job: dict[str, Any], path: Path) -> Path:
    """Only serve files inside this job's own directory."""
    root = jobs.job_dir(job["user_id"], job["id"]).resolve()
    resolved = path.resolve()
    if root not in resolved.parents or not resolved.is_file():
        raise HTTPException(404, "file not found")
    return resolved


@router.get("/styles")
async def styles() -> dict[str, Any]:
    return {
        "styles": list_styles(),
        "default": DEFAULT_STYLE,
        "pages": {"min": MIN_PAGES, "max": MAX_PAGES, "default": DEFAULT_PAGES},
    }


@router.get("/books/{substrate_id}/chapters")
async def book_chapters(substrate_id: str, user_id: str = Depends(jwt_auth)) -> dict[str, Any]:
    if not jobs.owned_substrate(user_id, substrate_id):
        raise HTTPException(404, "book not found")
    from stratum.services.ppt_export.material import MaterialUnavailable, load_material

    try:
        material = await asyncio.to_thread(load_material, substrate_id)
    except MaterialUnavailable as exc:
        return {"substrate_id": substrate_id, "ready": False, "reason": str(exc), "chapters": []}
    return {
        "substrate_id": substrate_id,
        "title": material.title,
        "ready": bool(material.usable_chapters()),
        "run_id": material.run_id,
        "bu_status": material.bu_status,
        "language": material.language,
        "chapters": [
            {"chapter_id": c.chapter_id, "title": c.display_title(), "question": c.question}
            for c in material.usable_chapters()
        ],
    }


@router.post("/exports", status_code=202)
async def create_export(
    req: ExportRequest,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(jwt_auth),
) -> dict[str, Any]:
    if req.style not in style_ids():
        raise HTTPException(422, f"unknown style {req.style!r}")
    if req.substrate_id:
        book = jobs.owned_substrate(user_id, req.substrate_id)
        if book and req.run_id:
            run_book = jobs.owned_run(user_id, req.run_id)
            if not run_book or run_book["id"] != book["id"]:
                book = None
    elif req.run_id:
        book = jobs.owned_run(user_id, req.run_id)
    else:
        raise HTTPException(422, "substrate_id or run_id is required")
    if not book:
        raise HTTPException(404, "book not found")
    job = jobs.create_job(
        user_id,
        book["id"],
        style=req.style,
        pages=req.pages,
        chapter_id=req.chapter_id or None,
        run_id=req.run_id or None,
        options={"audience": req.audience.strip(), "notes": req.notes},
    )
    background_tasks.add_task(jobs.run_job, job["id"], jobs.owner_of(user_id))
    return _public(job)


@router.get("/exports")
async def list_exports(
    user_id: str = Depends(jwt_auth),
    substrate_id: str | None = Query(None, max_length=64),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    return {"exports": [_public(j) for j in jobs.list_jobs(user_id, substrate_id, limit)]}


@router.get("/exports/{job_id}")
async def get_export(job_id: str, user_id: str = Depends(jwt_auth)) -> dict[str, Any]:
    return _public(_owned_job(user_id, job_id))


@router.get("/exports/{job_id}/download")
async def download_export(job_id: str, user_id: str = Depends(jwt_auth)) -> FileResponse:
    job = _owned_job(user_id, job_id)
    if job.get("status") != "succeeded" or not job.get("file_path"):
        raise HTTPException(409, "export is not ready")
    path = _safe_file(job, Path(job["file_path"]))
    name = (job.get("title") or "deck").replace("/", "-").replace("\\", "-")[:60]
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{name}.pptx",
    )


@router.get("/exports/{job_id}/previews/{n}")
async def preview(job_id: str, n: int, user_id: str = Depends(jwt_auth)) -> FileResponse:
    job = _owned_job(user_id, job_id)
    if job.get("status") != "succeeded" or not (1 <= n <= int(job.get("preview_count") or 0)):
        raise HTTPException(404, "preview not found")
    path = jobs.job_dir(job["user_id"], job["id"]) / "previews" / f"slide-{n:02d}.png"
    return FileResponse(_safe_file(job, path), media_type="image/png")
