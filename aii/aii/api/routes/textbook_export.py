"""textbook_export — GET /api/textbook/{textbook_id}/export

契约 JSON 结构:
  {
    "textbook": {id, subject, grade, edition, book_name, ku_count},
    "clusters": [{id, name, chapter, order, ku_count}],
    "units": [{
      id, name, description, school_grade, difficulty, exam_frequency,
      question_types, ku_type, mastery_levels,
      curriculum_standard, standard_code,
      prerequisites: [ku_id, ...]   ← prerequisite_of 入边的 src_id
    }],
    "curriculum_coverage": {
      total_ku_count,
      ku_with_standard: int,
      covered_standards: [standard_code, ...]
    }
  }
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from aii.api._dependencies import backend

router = APIRouter()


class TextbookIngestRequest(BaseModel):
    md_path: str
    provider: str = "default"


@router.post("/textbook/ingest")
async def trigger_textbook_ingest(
    req: TextbookIngestRequest, background_tasks: BackgroundTasks
) -> JSONResponse:
    """Trigger textbook ingest for a local MD file (runs inside the server process)."""
    from aii.service.textbook_ingest import ingest_one_textbook

    md_path = Path(req.md_path)
    if not md_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {req.md_path}")

    # Run ingest as a background task so the HTTP response returns immediately
    result_holder: dict = {}

    async def _run():
        try:
            result = await ingest_one_textbook(md_path, backend=backend, provider=req.provider)
            result_holder.update(result)
        except Exception as exc:
            result_holder["error"] = str(exc)

    # For synchronous validation we want the result — run directly with timeout
    try:
        result = await asyncio.wait_for(
            ingest_one_textbook(md_path, backend=backend, provider=req.provider),
            timeout=600,
        )
    except asyncio.TimeoutError:
        return JSONResponse({"status": "timeout", "md_path": req.md_path}, status_code=202)
    except Exception as exc:
        return JSONResponse({"status": "error", "error": str(exc)}, status_code=500)

    return JSONResponse(result)


@router.get("/textbook/{textbook_id}/export")
async def export_textbook(textbook_id: str) -> JSONResponse:
    """Export a textbook's KUs and structure as a contract JSON."""
    pool = await backend._ensure_pool()

    async with pool.acquire() as conn:
        # ── 1. substrate 元数据 ─────────────────────────────────────────────
        sub = await conn.fetchrow(
            "SELECT title, subject, ku_count FROM aii.ingested_substrate WHERE substrate_id = $1",
            textbook_id,
        )
        if not sub:
            raise HTTPException(
                status_code=404,
                detail=f"Textbook '{textbook_id}' not found in ingested_substrate",
            )

        # ── 2. 教材 KU 全量 (含 provenance) ───────────────────────────────
        ku_rows = await conn.fetch(
            """
            SELECT ku_id::text, natural_text, knowledge_type, grade,
                   provenance, symbolic_form
            FROM aii.ku
            WHERE provenance->>'textbook_id' = $1
              AND is_quarantined = FALSE
            ORDER BY (provenance->>'order')::int NULLS LAST, created_at
            """,
            textbook_id,
        )

        if not ku_rows:
            return JSONResponse({
                "textbook": {
                    "id": textbook_id,
                    "book_name": sub["title"] or "",
                    "subject": sub["subject"] or "",
                    "ku_count": 0,
                },
                "clusters": [],
                "units": [],
                "curriculum_coverage": {
                    "total_ku_count": 0,
                    "ku_with_standard": 0,
                    "covered_standards": [],
                },
            })

        ku_ids_uuid = [UUID(r["ku_id"]) for r in ku_rows]

        # ── 3. prerequisite_of 入边 ──────────────────────────────────────
        prereq_rows = await conn.fetch(
            """
            SELECT src_id::text, dst_id::text
            FROM aii.edge
            WHERE relation_type = 'prerequisite_of'
              AND dst_id = ANY($1)
            """,
            ku_ids_uuid,
        )
        prereqs_map: dict[str, list[str]] = {}
        for r in prereq_rows:
            prereqs_map.setdefault(r["dst_id"], []).append(r["src_id"])

        # ── 4. 组装 units ────────────────────────────────────────────────
        cluster_ku_counts: dict[str, int] = {}
        cluster_meta: dict[str, dict] = {}
        units: list[dict] = []

        for r in ku_rows:
            prov: dict = {}
            if r["provenance"]:
                try:
                    prov = json.loads(r["provenance"]) if isinstance(r["provenance"], str) else dict(r["provenance"])
                except Exception:
                    pass

            cid = prov.get("cluster_id", "")
            if cid and cid not in cluster_meta:
                cluster_meta[cid] = {
                    "id": cid,
                    "name": prov.get("chapter", cid),
                    "chapter": prov.get("chapter", ""),
                    "order": len(cluster_meta) + 1,
                }
            if cid:
                cluster_ku_counts[cid] = cluster_ku_counts.get(cid, 0) + 1

            ku_id = r["ku_id"]
            units.append({
                "id": ku_id,
                "name": r["natural_text"][:80] if r["natural_text"] else "",
                "description": r["natural_text"] or "",
                "knowledge_type": r["knowledge_type"] or "",
                "grade": r["grade"] or "unverified",
                "school_grade": prov.get("school_grade", ""),
                "difficulty": prov.get("difficulty", ""),
                "exam_frequency": prov.get("exam_frequency", ""),
                "question_types": prov.get("question_types", []),
                "ku_type": prov.get("ku_type", ""),
                "mastery_levels": prov.get("mastery_levels", []),
                "curriculum_standard": prov.get("curriculum_standard", ""),
                "standard_code": prov.get("standard_code", ""),
                "chapter": prov.get("chapter", ""),
                "section": prov.get("section", ""),
                "cluster_id": cid,
                "prerequisites": prereqs_map.get(ku_id, []),
                "symbolic_form": r["symbolic_form"],
            })

        # ── 5. 组装 clusters ─────────────────────────────────────────────
        clusters = [
            {**meta, "ku_count": cluster_ku_counts.get(meta["id"], 0)}
            for meta in sorted(cluster_meta.values(), key=lambda x: x["order"])
        ]

        # ── 6. 课标覆盖度 ────────────────────────────────────────────────
        covered = [
            u["standard_code"]
            for u in units
            if u.get("standard_code")
        ]
        coverage = {
            "total_ku_count": len(units),
            "ku_with_standard": len(covered),
            "covered_standards": list(dict.fromkeys(covered)),
        }

        # ── 7. 教材元数据 ────────────────────────────────────────────────
        first_prov: dict = {}
        if units:
            first_prov = {
                k: units[0].get(k, "")
                for k in ("school_grade",)
            }

        textbook_out = {
            "id": textbook_id,
            "book_name": sub["title"] or "",
            "subject": sub["subject"] or "",
            "grade": first_prov.get("school_grade", ""),
            "ku_count": len(units),
        }

    return JSONResponse({
        "textbook": textbook_out,
        "clusters": clusters,
        "units": units,
        "curriculum_coverage": coverage,
    })
