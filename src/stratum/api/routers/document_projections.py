"""Opt-in visual/translation/provenance API. Canonical substrates remain authoritative."""

from __future__ import annotations
import asyncio
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from stratum.common import jwt_auth
from stratum.config import (
    AII_ARTIFACT_PROVENANCE_ENABLED,
    AII_PDF_TRANSLATION_ENABLED,
    AII_VISUAL_RETRIEVAL_ENABLED,
    DATA_DIR,
)
from stratum.db import get_conn
from stratum.services.artifact_provenance import get_artifact
from stratum.services.visual_projection import persist_regions, render_source_regions
from stratum.services.visual_embedding import get_visual_embedding_provider
from stratum.services.source_storage import resolve_original_source
from stratum.services.translation_projection_writer import create_translation_projection
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(tags=["document-projections"])


def _source(user_id: str, source_id: str):
    with get_conn() as conn:
        return conn.execute(
            "SELECT id,source_path,file_hash FROM substrates WHERE id=? AND user_id=?",
            (source_id, hash_user_id(user_id)),
        ).fetchone()


@router.post("/api/v1/sources/{source_id}/visual-index")
async def visual_index(source_id: str, user_id: str = Depends(jwt_auth)):
    if not AII_VISUAL_RETRIEVAL_ENABLED:
        raise HTTPException(404, "visual retrieval is disabled")
    source = _source(user_id, source_id)
    if not source or not source[1]:
        raise HTTPException(404, "Source not found or has no file")

    def run():
        resolved_path = resolve_original_source(source_id, user_id)["path"]
        regions = render_source_regions(
            str(resolved_path), source[2] or hashlib.sha256(source[1].encode()).hexdigest()
        )
        return persist_regions(
            user_id, source_id, regions, embedding_provider=get_visual_embedding_provider()
        )

    count = await asyncio.to_thread(run)
    return {
        "source_id": source_id,
        "regions_indexed": count,
        "projection": "visual_region_projection",
    }


@router.get("/api/v1/sources/{source_id}/visual-regions")
async def visual_regions(source_id: str, user_id: str = Depends(jwt_auth)):
    if not AII_VISUAL_RETRIEVAL_ENABLED:
        raise HTTPException(404, "visual retrieval is disabled")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,source_id,fragment_id,page_number,region_index,bbox_json,tile_uri,tile_hash,render_hash,width,height,embedding_model,embedding_dim FROM visual_region_projection WHERE source_id=? AND user_id=? AND deleted_at IS NULL ORDER BY page_number,region_index",
            (source_id, hash_user_id(user_id)),
        ).fetchall()
    return {
        "source_id": source_id,
        "regions": [dict(r) if isinstance(r, dict) else r for r in rows],
    }


class TranslateRequest(BaseModel):
    target_language: str
    provider: str = "PDFMathTranslate"
    options: dict = {}


@router.post("/api/v1/sources/{source_id}/translate")
async def translate(source_id: str, body: TranslateRequest, user_id: str = Depends(jwt_auth)):
    if not AII_PDF_TRANSLATION_ENABLED:
        raise HTTPException(404, "PDF translation is disabled")
    source = _source(user_id, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    owner = hash_user_id(user_id)
    source_version = source[2] or ""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM translation_projection WHERE user_id=? AND source_id=? AND source_version=? AND target_language=? AND provider=?",
            (owner, source_id, source_version, body.target_language, body.provider),
        ).fetchone()
    if existing:
        return {"translation_id": existing[0], "status": "completed", "idempotent": True}
    from stratum.services.translation_provider import PDFMathTranslateProvider

    original = resolve_original_source(source_id, user_id)
    out = DATA_DIR / "translations" / owner / f"{source_id}-{body.target_language}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    result = await asyncio.to_thread(
        PDFMathTranslateProvider().translate_pdf,
        str(original["path"]),
        body.target_language,
        str(out),
        options=body.options,
    )
    persisted = create_translation_projection(
        user_id,
        source_id=source_id,
        source_version=source_version,
        target_language=body.target_language,
        provider=result.provider,
        model=result.model,
        translated_artifact_uri=result.artifact_uri,
        artifact_hash=result.artifact_hash,
    )
    return {
        "translation_id": persisted["id"],
        "status": "completed",
        "idempotent": persisted["status"] == "reused",
    }


@router.get("/api/v1/sources/{source_id}/translations")
async def translations(source_id: str, user_id: str = Depends(jwt_auth)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,source_id,target_language,provider,model,translated_artifact_uri,artifact_hash,alignment_version,status,created_at FROM translation_projection WHERE source_id=? AND user_id=? ORDER BY created_at DESC",
            (source_id, hash_user_id(user_id)),
        ).fetchall()
    return {
        "source_id": source_id,
        "translations": [dict(r) if isinstance(r, dict) else r for r in rows],
    }


@router.get("/api/v1/artifacts/{artifact_id}")
async def artifact(artifact_id: str, user_id: str = Depends(jwt_auth)):
    if not AII_ARTIFACT_PROVENANCE_ENABLED:
        raise HTTPException(404, "artifact provenance is disabled")
    value = get_artifact(user_id, artifact_id)
    if not value:
        raise HTTPException(404, "Artifact not found")
    return value


@router.get("/api/v1/sources/{source_id}/artifacts")
async def source_artifacts(source_id: str, user_id: str = Depends(jwt_auth)):
    if not AII_ARTIFACT_PROVENANCE_ENABLED:
        raise HTTPException(404, "artifact provenance is disabled")
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT a.* FROM derived_artifact a JOIN artifact_input i ON i.artifact_id=a.id WHERE a.user_id=? AND i.source_id=? ORDER BY a.created_at DESC",
            (hash_user_id(user_id), source_id),
        ).fetchall()
    return {
        "source_id": source_id,
        "artifacts": [dict(r) if isinstance(r, dict) else r for r in rows],
    }
