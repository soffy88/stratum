"""Display endpoints — read-only KU/Graph/KC/BU views for the frontend."""
import json
import uuid as _uuid
from collections import deque
from typing import Optional

from fastapi import APIRouter, Query
from oprim import vector_encode

from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response

router = APIRouter()


# ── helpers ────────────────────────────────────────────────────────────────

def _str(v) -> str | None:
    return str(v) if v is not None else None


def _jsonb(v):
    """asyncpg returns jsonb as str or dict depending on version; normalise to Python object."""
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


# ── KU list / detail ────────────────────────────────────────────────────────

@router.get("/ku/list")
async def ku_list(
    grade: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    substrate: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=200),
):
    """Paginated KU list (is_synthesis=false). Supports grade/type/substrate filters."""
    try:
        conditions = ["k.is_synthesis IS NOT TRUE"]
        params: list = []

        if grade:
            params.append(grade)
            conditions.append(f"k.grade = ${len(params)}")
        if type:
            params.append(type)
            conditions.append(f"k.knowledge_type = ${len(params)}")
        if substrate:
            params.append(substrate)
            conditions.append(f"k.substrate_id = ${len(params)}")

        where = " AND ".join(conditions)
        offset = (page - 1) * size
        params += [size, offset]
        limit_p = len(params) - 1
        offset_p = len(params)

        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                f"SELECT count(*) FROM aii.ku k WHERE {where}",
                *params[: len(params) - 2],
            )
            rows = await conn.fetch(
                f"""
                SELECT k.ku_id, left(k.natural_text, 300) AS natural_text,
                       k.knowledge_type, k.grade, k.substrate_id,
                       s.title, k.merge_count, k.created_at
                FROM aii.ku k
                LEFT JOIN aii.ingested_substrate s ON k.substrate_id = s.substrate_id
                WHERE {where}
                ORDER BY k.created_at DESC
                LIMIT ${limit_p} OFFSET ${offset_p}
                """,
                *params,
            )

        items = [
            {
                "ku_id": _str(r["ku_id"]),
                "natural_text": r["natural_text"],
                "knowledge_type": r["knowledge_type"],
                "grade": r["grade"],
                "substrate_id": r["substrate_id"],
                "title": r["title"],
                "merge_count": r["merge_count"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return success_response({"total": total, "page": page, "size": size, "items": items})
    except Exception as e:
        return error_response("KU_LIST_ERROR", str(e))


@router.get("/ku/{ku_id}")
async def ku_detail(ku_id: str):
    """Full KU detail: all fields + sources + connected edges."""
    try:
        uid = _uuid.UUID(ku_id)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ku_id, natural_text, knowledge_type, grade, source,
                       verified, is_quarantined, valid_from, valid_until,
                       provenance, created_at, updated_at, substrate_id,
                       sources, merge_count, synthesis_meta, is_synthesis,
                       symbolic_form
                FROM aii.ku WHERE ku_id = $1
                """,
                uid,
            )
            if not row:
                return error_response("NOT_FOUND", f"KU {ku_id} not found")

            edge_rows = await conn.fetch(
                """
                SELECT src_id::text, dst_id::text, relation_type, grade, extraction_method, evidence
                FROM aii.edge
                WHERE src_id = $1 OR dst_id = $1
                LIMIT 100
                """,
                uid,
            )

        edges = [
            {
                "src_id": r["src_id"],
                "dst_id": r["dst_id"],
                "relation_type": r["relation_type"],
                "grade": r["grade"],
                "extraction_method": r["extraction_method"],
                "evidence": _jsonb(r["evidence"]),
            }
            for r in edge_rows
        ]

        ku = dict(row)
        ku["ku_id"] = _str(ku["ku_id"])
        ku["sources"] = _jsonb(ku.get("sources"))
        ku["synthesis_meta"] = _jsonb(ku.get("synthesis_meta"))
        ku["provenance"] = _jsonb(ku.get("provenance"))
        ku["symbolic_form"] = _jsonb(ku.get("symbolic_form"))
        for ts in ("valid_from", "valid_until", "created_at", "updated_at"):
            if ku.get(ts):
                ku[ts] = ku[ts].isoformat()
        ku["edges"] = edges

        return success_response(ku)
    except ValueError:
        return error_response("INVALID_ID", "ku_id must be a valid UUID")
    except Exception as e:
        return error_response("KU_DETAIL_ERROR", str(e))


# ── Graph ────────────────────────────────────────────────────────────────────

@router.get("/graph/subgraph")
async def graph_subgraph(
    ku_id: str = Query(...),
    hops: int = Query(2, ge=1, le=4),
    limit: int = Query(50, ge=1, le=200),
):
    """BFS subgraph starting from ku_id. Returns nodes + edges within hops, capped at limit nodes."""
    try:
        start = _uuid.UUID(ku_id)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            # BFS over edge table
            visited: set[str] = {ku_id}
            frontier: list[str] = [ku_id]
            all_edges: list[dict] = []

            for _ in range(hops):
                if not frontier or len(visited) >= limit:
                    break
                uids = [_uuid.UUID(x) for x in frontier]
                edge_rows = await conn.fetch(
                    """
                    SELECT src_id::text, dst_id::text, relation_type, grade, extraction_method
                    FROM aii.edge
                    WHERE src_id = ANY($1::uuid[]) OR dst_id = ANY($1::uuid[])
                    """,
                    uids,
                )
                new_frontier: list[str] = []
                seen_edges: set[tuple] = set()
                for r in edge_rows:
                    s, d = r["src_id"], r["dst_id"]
                    key = (s, d, r["relation_type"])
                    if key not in seen_edges:
                        seen_edges.add(key)
                        all_edges.append({
                            "src": s, "dst": d,
                            "relation_type": r["relation_type"],
                            "grade": r["grade"],
                            "extraction_method": r["extraction_method"],
                        })
                    for nid in (s, d):
                        if nid not in visited and len(visited) < limit:
                            visited.add(nid)
                            new_frontier.append(nid)
                frontier = new_frontier

            # Fetch node data
            all_uids = [_uuid.UUID(x) for x in visited]
            node_rows = await conn.fetch(
                """
                SELECT ku_id::text, left(natural_text, 120) AS natural_text, grade, knowledge_type
                FROM aii.ku WHERE ku_id = ANY($1::uuid[])
                """,
                all_uids,
            )

        nodes = [
            {
                "ku_id": r["ku_id"],
                "natural_text": r["natural_text"],
                "grade": r["grade"],
                "knowledge_type": r["knowledge_type"],
            }
            for r in node_rows
        ]
        return success_response({"nodes": nodes, "edges": all_edges})
    except ValueError:
        return error_response("INVALID_ID", "ku_id must be a valid UUID")
    except Exception as e:
        return error_response("SUBGRAPH_ERROR", str(e))


@router.get("/graph/search")
async def graph_search(q: str = Query(..., min_length=1)):
    """Vector search for KUs. Returns matching KUs sorted by similarity."""
    try:
        qv = vector_encode(texts=[q], provider="default")[0]
        results = await backend.search_ku_by_vector([float(x) for x in qv], limit=20)
        items = [
            {
                "ku_id": str(r["ku_id"]),
                "natural_text": r.get("natural_text"),
                "knowledge_type": r.get("knowledge_type"),
                "grade": r.get("grade"),
                "score": round(1.0 - r.get("distance", 1.0), 4),
            }
            for r in results
        ]
        return success_response(items)
    except Exception as e:
        return error_response("SEARCH_ERROR", str(e))


# ── KC (Community Overview / synthesis) ──────────────────────────────────────

@router.get("/kc/list")
async def kc_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """List all KC (community overview, knowledge_type='synthesis')."""
    try:
        offset = (page - 1) * size
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM aii.ku WHERE knowledge_type = 'synthesis' AND is_synthesis = true"
            )
            rows = await conn.fetch(
                """
                SELECT ku_id, left(natural_text, 300) AS natural_text, grade,
                       synthesis_meta->>'community_label' AS community_label,
                       (synthesis_meta->>'community_size')::int AS community_size,
                       created_at
                FROM aii.ku
                WHERE knowledge_type = 'synthesis' AND is_synthesis = true
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                size, offset,
            )

        items = [
            {
                "ku_id": _str(r["ku_id"]),
                "natural_text": r["natural_text"],
                "grade": r["grade"],
                "community_label": r["community_label"],
                "community_size": r["community_size"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return success_response({"total": total, "page": page, "size": size, "items": items})
    except Exception as e:
        return error_response("KC_LIST_ERROR", str(e))


@router.get("/kc/{ku_id}")
async def kc_detail(ku_id: str):
    """KC detail: full synthesis_meta including source_ku_ids."""
    try:
        uid = _uuid.UUID(ku_id)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ku_id, natural_text, grade, synthesis_meta, created_at
                FROM aii.ku WHERE ku_id = $1 AND knowledge_type = 'synthesis' AND is_synthesis = true
                """,
                uid,
            )
        if not row:
            return error_response("NOT_FOUND", f"KC {ku_id} not found")

        meta = _jsonb(row["synthesis_meta"]) or {}
        return success_response({
            "ku_id": _str(row["ku_id"]),
            "natural_text": row["natural_text"],
            "grade": row["grade"],
            "community_label": meta.get("community_label"),
            "community_size": meta.get("community_size"),
            "source_ku_ids": meta.get("source_ku_ids", []),
            "synthesis_note": meta.get("synthesis_note"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })
    except ValueError:
        return error_response("INVALID_ID", "ku_id must be a valid UUID")
    except Exception as e:
        return error_response("KC_DETAIL_ERROR", str(e))


# ── BU (Book Understanding) ───────────────────────────────────────────────────

@router.get("/bu/list")
async def bu_list(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """List all BU (book understanding entries)."""
    try:
        offset = (page - 1) * size
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM aii.ku WHERE knowledge_type = 'book_understanding' AND is_synthesis = true"
            )
            rows = await conn.fetch(
                """
                SELECT k.ku_id, left(k.natural_text, 300) AS natural_text, k.grade,
                       k.synthesis_meta->>'book_substrate_id' AS book_substrate_id,
                       k.synthesis_meta->>'doc_type' AS doc_type,
                       s.title, k.created_at
                FROM aii.ku k
                LEFT JOIN aii.ingested_substrate s
                  ON s.substrate_id = k.synthesis_meta->>'book_substrate_id'
                WHERE k.knowledge_type = 'book_understanding' AND k.is_synthesis = true
                ORDER BY k.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                size, offset,
            )

        items = [
            {
                "ku_id": _str(r["ku_id"]),
                "natural_text": r["natural_text"],
                "grade": r["grade"],
                "book_substrate_id": r["book_substrate_id"],
                "doc_type": r["doc_type"],
                "title": r["title"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
        return success_response({"total": total, "page": page, "size": size, "items": items})
    except Exception as e:
        return error_response("BU_LIST_ERROR", str(e))


@router.get("/bu/{ku_id}")
async def bu_detail(ku_id: str):
    """Full BU detail: synthesis_meta with main_claims, argument_structure, key_concept_ku_ids."""
    try:
        uid = _uuid.UUID(ku_id)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT k.ku_id, k.natural_text, k.grade, k.synthesis_meta, k.created_at,
                       s.title
                FROM aii.ku k
                LEFT JOIN aii.ingested_substrate s
                  ON s.substrate_id = k.synthesis_meta->>'book_substrate_id'
                WHERE k.ku_id = $1
                  AND k.knowledge_type = 'book_understanding'
                  AND k.is_synthesis = true
                """,
                uid,
            )
        if not row:
            return error_response("NOT_FOUND", f"BU {ku_id} not found")

        meta = _jsonb(row["synthesis_meta"]) or {}
        return success_response({
            "ku_id": _str(row["ku_id"]),
            "natural_text": row["natural_text"],
            "grade": row["grade"],
            "title": row["title"],
            "book_substrate_id": meta.get("book_substrate_id"),
            "doc_type": meta.get("doc_type"),
            "structure": meta.get("structure"),
            "main_claims": meta.get("main_claims", []),
            "argument_structure": meta.get("argument_structure", []),
            "key_concept_ku_ids": meta.get("key_concept_ku_ids", []),
            "synthesis_note": meta.get("synthesis_note"),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        })
    except ValueError:
        return error_response("INVALID_ID", "ku_id must be a valid UUID")
    except Exception as e:
        return error_response("BU_DETAIL_ERROR", str(e))
