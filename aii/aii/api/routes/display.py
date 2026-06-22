"""Display endpoints — read-only KU/Graph/KC/BU views, fully aligned to AII-FRONTEND-DISPLAY-001."""
import json
import os
import uuid as _uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Body, Query
from oprim import vector_encode

from aii.api._dependencies import backend
from aii.api._envelope import success_response, error_response

router = APIRouter()

_SHARED_DIR = Path(os.getenv("FLYWHEEL_SHARED_DIR", "/home/soffy/shared/stratum-to-aii"))


# ── helpers ────────────────────────────────────────────────────────────────

def _str(v) -> str | None:
    return str(v) if v is not None else None


def _jsonb(v):
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
    merged_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    size: int = Query(0),           # legacy alias
):
    """Paginated KU list. Contract: AII-FRONTEND-DISPLAY-001 视图2."""
    try:
        effective_size = page_size if page_size != 20 or size == 0 else size
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
        if merged_only:
            conditions.append("k.merge_count > 1")

        where = " AND ".join(conditions)
        offset = (page - 1) * effective_size
        filter_params = params[:]
        params += [effective_size, offset]
        limit_p = len(params) - 1
        offset_p = len(params)

        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                f"SELECT count(*) FROM aii.ku k WHERE {where}", *filter_params
            )
            rows = await conn.fetch(
                f"""
                SELECT k.ku_id, left(k.natural_text, 300) AS natural_text,
                       k.knowledge_type, k.grade, k.substrate_id,
                       s.title AS substrate_title, s.subject AS subject,
                       k.merge_count, k.created_at
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
                "id": _str(r["ku_id"]),
                "natural_text": r["natural_text"],
                "knowledge_type": r["knowledge_type"],
                "grade": r["grade"],
                "substrate_id": r["substrate_id"],
                "substrate_title": r["substrate_title"],
                "subject": r["subject"],
                "merge_count": r["merge_count"],
                "defeater_count": 0,
            }
            for r in rows
        ]
        return success_response({
            "total": total,
            "page": page,
            "page_size": effective_size,
            "items": items,
        })
    except Exception as e:
        return error_response("KU_LIST_ERROR", str(e))


@router.get("/ku/{ku_id}")
async def ku_detail(ku_id: str):
    """KU detail: all fields + sources + edges with target text."""
    try:
        uid = _uuid.UUID(ku_id)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT k.ku_id, k.natural_text, k.knowledge_type, k.grade,
                       k.substrate_id, s.title AS substrate_title,
                       k.merge_count, k.sources, k.is_synthesis, k.created_at
                FROM aii.ku k
                LEFT JOIN aii.ingested_substrate s ON k.substrate_id = s.substrate_id
                WHERE k.ku_id = $1
                """,
                uid,
            )
            if not row:
                return error_response("NOT_FOUND", f"KU {ku_id} not found")

            # Fetch edges with other end's text
            edge_rows = await conn.fetch(
                """
                SELECT e.src_id::text, e.dst_id::text, e.relation_type,
                       e.grade, e.extraction_method,
                       CASE WHEN e.src_id = $1 THEN e.dst_id ELSE e.src_id END AS target_ku_id,
                       kt.natural_text AS target_text
                FROM aii.edge e
                JOIN aii.ku kt ON kt.ku_id =
                     CASE WHEN e.src_id = $1 THEN e.dst_id ELSE e.src_id END
                WHERE e.src_id = $1 OR e.dst_id = $1
                LIMIT 100
                """,
                uid,
            )

        raw_sources = _jsonb(row["sources"]) or []
        sources = [
            {
                "substrate_id": s.get("substrate_id", ""),
                "substrate_title": s.get("substrate_id", ""),
                "text": s.get("natural_text", ""),
            }
            for s in (raw_sources if isinstance(raw_sources, list) else [])
        ]

        edges = [
            {
                "target_id": _str(r["target_ku_id"]),
                "target_text": (r["target_text"] or "")[:120],
                "relation_type": r["relation_type"],
                "extraction_method": r["extraction_method"] or "llm",
                "grade": r["grade"],
            }
            for r in edge_rows
        ]

        return success_response({
            "id": _str(row["ku_id"]),
            "natural_text": row["natural_text"],
            "knowledge_type": row["knowledge_type"],
            "grade": row["grade"],
            "substrate_id": row["substrate_id"],
            "substrate_title": row["substrate_title"],
            "merge_count": row["merge_count"],
            "defeater_count": 0,
            "sources": sources,
            "defeaters": [],
            "edges": edges,
        })
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
    """BFS subgraph. Contract: GraphNode{id,label,grade,knowledge_type,degree} + GraphEdge{id,source,target,...}"""
    try:
        start = _uuid.UUID(ku_id)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            visited: set[str] = {ku_id}
            frontier: list[str] = [ku_id]
            all_edges: list[dict] = []
            seen_edge_keys: set[tuple] = set()

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
                for r in edge_rows:
                    s, d = r["src_id"], r["dst_id"]
                    key = (s, d, r["relation_type"])
                    if key not in seen_edge_keys:
                        seen_edge_keys.add(key)
                        all_edges.append({
                            "id": f"{s[:8]}-{d[:8]}-{r['relation_type']}",
                            "source": s,
                            "target": d,
                            "relation_type": r["relation_type"],
                            "grade": r["grade"],
                            "extraction_method": r["extraction_method"] or "llm",
                        })
                    for nid in (s, d):
                        if nid not in visited and len(visited) < limit:
                            visited.add(nid)
                            new_frontier.append(nid)
                frontier = new_frontier

            # Degree map
            degree: dict[str, int] = {}
            for e in all_edges:
                degree[e["source"]] = degree.get(e["source"], 0) + 1
                degree[e["target"]] = degree.get(e["target"], 0) + 1

            all_uids = [_uuid.UUID(x) for x in visited]
            node_rows = await conn.fetch(
                """
                SELECT ku_id::text, left(natural_text, 120) AS label, grade, knowledge_type
                FROM aii.ku WHERE ku_id = ANY($1::uuid[])
                """,
                all_uids,
            )

        nodes = [
            {
                "id": r["ku_id"],
                "label": r["label"],
                "grade": r["grade"],
                "knowledge_type": r["knowledge_type"],
                "degree": degree.get(r["ku_id"], 0),
            }
            for r in node_rows
        ]
        return success_response({
            "nodes": nodes,
            "edges": all_edges,
            "center_id": ku_id,
            "truncated": len(visited) >= limit,
        })
    except ValueError:
        return error_response("INVALID_ID", "ku_id must be a valid UUID")
    except Exception as e:
        return error_response("SUBGRAPH_ERROR", str(e))


@router.get("/graph/search")
async def graph_search(q: str = Query(..., min_length=1), limit: int = Query(20, ge=1, le=50)):
    """Vector search. Returns {matches:[{id,label,grade}]}."""
    try:
        qv = vector_encode(texts=[q], provider="default")[0]
        results = await backend.search_ku_by_vector([float(x) for x in qv], limit=limit)
        matches = [
            {
                "id": str(r["ku_id"]),
                "label": (r.get("natural_text") or "")[:120],
                "grade": r.get("grade"),
            }
            for r in results
        ]
        return success_response({"matches": matches})
    except Exception as e:
        return error_response("SEARCH_ERROR", str(e))


# ── KC (Community Overview / synthesis) ──────────────────────────────────────

@router.get("/kc/list")
async def kc_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        offset = (page - 1) * page_size
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM aii.ku WHERE knowledge_type = 'synthesis' AND is_synthesis = true"
            )
            rows = await conn.fetch(
                """
                SELECT ku_id, left(natural_text, 300) AS natural_text, grade,
                       synthesis_meta->>'community_label' AS community_label,
                       (synthesis_meta->>'community_size')::int AS community_size
                FROM aii.ku
                WHERE knowledge_type = 'synthesis' AND is_synthesis = true
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                page_size, offset,
            )

        items = [
            {
                "id": _str(r["ku_id"]),
                "community_label": r["community_label"] or "",
                "summary": r["natural_text"],
                "grade": r["grade"],
                "community_size": r["community_size"] or 0,
            }
            for r in rows
        ]
        return success_response({"total": total, "page": page, "page_size": page_size, "items": items})
    except Exception as e:
        return error_response("KC_LIST_ERROR", str(e))


@router.get("/kc/{ku_id}")
async def kc_detail(ku_id: str):
    try:
        uid = _uuid.UUID(ku_id)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ku_id, natural_text, grade, synthesis_meta
                FROM aii.ku WHERE ku_id = $1 AND knowledge_type = 'synthesis' AND is_synthesis = true
                """,
                uid,
            )
            if not row:
                return error_response("NOT_FOUND", f"KC {ku_id} not found")

            meta = _jsonb(row["synthesis_meta"]) or {}
            source_ids = meta.get("source_ku_ids", [])

            # Fetch up to 20 member KU details
            member_rows = []
            if source_ids:
                valid_uids = []
                for sid in source_ids[:20]:
                    try:
                        valid_uids.append(_uuid.UUID(str(sid)))
                    except Exception:
                        pass
                if valid_uids:
                    member_rows = await conn.fetch(
                        "SELECT ku_id::text, left(natural_text,120) AS natural_text, grade "
                        "FROM aii.ku WHERE ku_id = ANY($1::uuid[])",
                        valid_uids,
                    )

        members = [
            {"id": r["ku_id"], "natural_text": r["natural_text"], "grade": r["grade"]}
            for r in member_rows
        ]
        return success_response({
            "id": _str(row["ku_id"]),
            "community_label": meta.get("community_label", ""),
            "summary": row["natural_text"],
            "grade": row["grade"],
            "community_size": meta.get("community_size", 0),
            "source_ku_ids": source_ids,
            "members": members,
        })
    except ValueError:
        return error_response("INVALID_ID", "ku_id must be a valid UUID")
    except Exception as e:
        return error_response("KC_DETAIL_ERROR", str(e))


# ── BU (Book Understanding) ───────────────────────────────────────────────────

@router.get("/bu/list")
async def bu_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    try:
        offset = (page - 1) * page_size
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                "SELECT count(*) FROM aii.ku WHERE knowledge_type = 'book_understanding' AND is_synthesis = true"
            )
            rows = await conn.fetch(
                """
                SELECT k.ku_id, left(k.natural_text, 300) AS natural_text, k.grade,
                       k.synthesis_meta->>'book_substrate_id' AS substrate_id,
                       k.synthesis_meta->>'doc_type' AS doc_type,
                       s.title AS book_title, s.subject AS subject,
                       jsonb_array_length(COALESCE(k.synthesis_meta->'main_claims', '[]'::jsonb)) AS claim_count
                FROM aii.ku k
                LEFT JOIN aii.ingested_substrate s
                  ON s.substrate_id = k.synthesis_meta->>'book_substrate_id'
                WHERE k.knowledge_type = 'book_understanding' AND k.is_synthesis = true
                ORDER BY k.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                page_size, offset,
            )

        items = [
            {
                "id": _str(r["ku_id"]),
                "substrate_id": r["substrate_id"] or "",
                "book_title": r["book_title"] or "",
                "summary": r["natural_text"],
                "grade": r["grade"],
                "subject": r["subject"],
                "main_claim_count": r["claim_count"] or 0,
            }
            for r in rows
        ]
        return success_response({"total": total, "page": page, "page_size": page_size, "items": items})
    except Exception as e:
        return error_response("BU_LIST_ERROR", str(e))


@router.get("/bu/{ku_id}")
async def bu_detail(ku_id: str):
    try:
        uid = _uuid.UUID(ku_id)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT k.ku_id, k.natural_text, k.grade, k.synthesis_meta,
                       s.title AS book_title
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

        # main_claims: add synthetic id
        raw_claims = meta.get("main_claims") or []
        main_claims = [
            {
                "id": f"claim-{i}",
                "text": c.get("claim", ""),
                "stance_marker": c.get("stance_marker", ""),
                "claim_grade": c.get("claim_grade", "unverified"),
            }
            for i, c in enumerate(raw_claims)
        ]

        # argument_structure: add synthetic ids
        raw_args = meta.get("argument_structure") or []
        argument_structure = [
            {
                "id": f"arg-{i}",
                "thesis": a.get("point", ""),
                "thesis_grade": "unverified",
                "evidence": [
                    {"text": e.get("text", ""), "grade": e.get("grade", "unverified")}
                    for e in (a.get("evidence") or [])
                ],
            }
            for i, a in enumerate(raw_args)
        ]

        # key_concepts: resolve ku_ids to labels (up to 10)
        key_ku_ids = meta.get("key_concept_ku_ids") or []
        key_concepts = []
        if key_ku_ids:
            pool2 = await backend._ensure_pool()
            async with pool2.acquire() as conn2:
                valid_uids = []
                for kid in key_ku_ids[:10]:
                    try:
                        valid_uids.append(_uuid.UUID(str(kid)))
                    except Exception:
                        pass
                if valid_uids:
                    kc_rows = await conn2.fetch(
                        "SELECT ku_id::text, left(natural_text,60) AS label, grade "
                        "FROM aii.ku WHERE ku_id = ANY($1::uuid[])",
                        valid_uids,
                    )
                    key_concepts = [
                        {"ku_id": r["ku_id"], "label": r["label"], "grade": r["grade"]}
                        for r in kc_rows
                    ]

        # structure: raw string from meta (frontend handles as opaque)
        structure_raw = meta.get("structure") or ""

        return success_response({
            "id": _str(row["ku_id"]),
            "substrate_id": meta.get("book_substrate_id", ""),
            "book_title": row["book_title"] or "",
            "summary": row["natural_text"],
            "grade": row["grade"],
            "main_claim_count": len(main_claims),
            "main_claims": main_claims,
            "argument_structure": argument_structure,
            "structure": structure_raw,
            "key_concepts": key_concepts,
        })
    except ValueError:
        return error_response("INVALID_ID", "ku_id must be a valid UUID")
    except Exception as e:
        return error_response("BU_DETAIL_ERROR", str(e))


# ── Concept (KU零件索引, 不带grade, 不当知识网) ────────────────────────────────

@router.get("/concepts")
async def concept_list(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    min_ku_count: int = Query(1, ge=0),
    q: Optional[str] = Query(None),
):
    """List concepts sorted by ku_count DESC.
    Concepts are KU索引 only — no grade, no epistemic status.
    """
    try:
        offset = (page - 1) * page_size
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            conditions = ["ku_count >= $1"]
            params: list = [min_ku_count]
            if q:
                params.append(f"%{q.lower()}%")
                conditions.append(f"name LIKE ${len(params)}")
            where = " AND ".join(conditions)
            total = await conn.fetchval(
                f"SELECT count(*) FROM aii.concept WHERE {where}", *params
            )
            params += [page_size, offset]
            rows = await conn.fetch(
                f"""
                SELECT concept_id::text, name, ku_count, created_at
                FROM aii.concept
                WHERE {where}
                ORDER BY ku_count DESC, name
                LIMIT ${len(params)-1} OFFSET ${len(params)}
                """,
                *params,
            )
        items = [
            {"id": r["concept_id"], "name": r["name"], "ku_count": r["ku_count"]}
            for r in rows
        ]
        return success_response({
            "total": total, "page": page, "page_size": page_size, "items": items,
        })
    except Exception as e:
        return error_response("CONCEPT_LIST_ERROR", str(e))


@router.get("/concepts/{name}/kus")
async def concept_kus(
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """KUs that involve this concept (by exact name, case-insensitive)."""
    try:
        offset = (page - 1) * page_size
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            c_row = await conn.fetchrow(
                "SELECT concept_id, ku_count FROM aii.concept WHERE name = $1",
                name.strip().lower(),
            )
            if not c_row:
                return error_response("NOT_FOUND", f"Concept '{name}' not found")

            total = c_row["ku_count"]
            rows = await conn.fetch(
                """
                SELECT k.ku_id::text, left(k.natural_text, 200) AS natural_text,
                       k.knowledge_type, k.grade, k.substrate_id
                FROM aii.ku_concept kc
                JOIN aii.ku k ON k.ku_id = kc.ku_id
                WHERE kc.concept_id = $1
                  AND k.is_quarantined = FALSE
                ORDER BY k.created_at DESC
                LIMIT $2 OFFSET $3
                """,
                c_row["concept_id"], page_size, offset,
            )
        items = [
            {
                "id": r["ku_id"],
                "natural_text": r["natural_text"],
                "knowledge_type": r["knowledge_type"],
                "grade": r["grade"],
                "substrate_id": r["substrate_id"],
            }
            for r in rows
        ]
        return success_response({
            "concept": name.strip().lower(),
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        })
    except Exception as e:
        return error_response("CONCEPT_KUS_ERROR", str(e))


# ── Stratum 反向共享端点 (只读) ─────────────────────────────────────────────────

_VALID_RELATION_TYPES = {
    "special_case_of", "prerequisite_of", "basis_of", "references", "contradicts",
}

@router.get("/graph/edges")
async def graph_edges(
    relation_type: Optional[str] = Query(None),
    grade: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=2000),
):
    """Paginated full edge export for Stratum reverse-sharing.

    精简返回 — 不含 evidence 大字段。Stratum 要的是网结构。
    """
    try:
        offset = (page - 1) * page_size
        conditions = ["relation_type IS NOT NULL", "relation_type != ''"]
        params: list = []

        if relation_type:
            params.append(relation_type)
            conditions.append(f"relation_type = ${len(params)}")
        if grade:
            params.append(grade)
            conditions.append(f"grade = ${len(params)}")

        where = " AND ".join(conditions)
        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            total = await conn.fetchval(
                f"SELECT count(*) FROM aii.edge WHERE {where}", *params
            )
            count_params = params[:]
            params += [page_size, offset]
            rows = await conn.fetch(
                f"""
                SELECT src_id::text, dst_id::text, relation_type, grade, extraction_method
                FROM aii.edge
                WHERE {where}
                ORDER BY src_id, relation_type
                LIMIT ${len(params) - 1} OFFSET ${len(params)}
                """,
                *params,
            )
        items = [
            {
                "src_id": r["src_id"],
                "dst_id": r["dst_id"],
                "relation_type": r["relation_type"],
                "grade": r["grade"],
                "extraction_method": r["extraction_method"] or "llm",
            }
            for r in rows
        ]
        return success_response({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": items,
        })
    except Exception as e:
        return error_response("GRAPH_EDGES_ERROR", str(e))


@router.post("/ku/batch")
async def ku_batch(
    ids: list[str] = Body(..., embed=True, max_length=200),
):
    """Batch KU lookup by ID list (≤200). Returns grade/type/concepts per KU.

    Stratum 用于回查 AII 对某批 KU 的标注(grade/knowledge_type/concepts)。
    """
    try:
        if not ids:
            return success_response({"items": []})
        if len(ids) > 200:
            return error_response("TOO_MANY_IDS", "ids list exceeds 200 limit")

        valid_uuids: list[_uuid.UUID] = []
        invalid: list[str] = []
        for raw in ids:
            try:
                valid_uuids.append(_uuid.UUID(str(raw)))
            except ValueError:
                invalid.append(raw)

        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            ku_rows = await conn.fetch(
                """
                SELECT ku_id::text, left(natural_text, 200) AS natural_text,
                       grade, knowledge_type, is_synthesis, substrate_id
                FROM aii.ku
                WHERE ku_id = ANY($1::uuid[])
                  AND is_quarantined = FALSE
                """,
                valid_uuids,
            )

            # Batch fetch concepts for all returned KUs
            if ku_rows:
                ku_uuids = [_uuid.UUID(r["ku_id"]) for r in ku_rows]
                concept_rows = await conn.fetch(
                    """
                    SELECT kc.ku_id::text, c.name
                    FROM aii.ku_concept kc
                    JOIN aii.concept c USING (concept_id)
                    WHERE kc.ku_id = ANY($1::uuid[])
                    ORDER BY kc.ku_id, c.name
                    """,
                    ku_uuids,
                )
            else:
                concept_rows = []

        # Group concepts by ku_id
        ku_concepts: dict[str, list[str]] = {}
        for cr in concept_rows:
            ku_concepts.setdefault(cr["ku_id"], []).append(cr["name"])

        items = [
            {
                "id": r["ku_id"],
                "natural_text": r["natural_text"],
                "grade": r["grade"],
                "knowledge_type": r["knowledge_type"],
                "is_synthesis": bool(r["is_synthesis"]),
                "substrate_id": r["substrate_id"],
                "concepts": ku_concepts.get(r["ku_id"], []),
            }
            for r in ku_rows
        ]
        result: dict = {"items": items}
        if invalid:
            result["invalid_ids"] = invalid
        return success_response(result)
    except Exception as e:
        return error_response("KU_BATCH_ERROR", str(e))


# ── KU 溯源 (P-G3 source_trace) ────────────────────────────────────────────

@router.get("/ku/{ku_id}/trace")
async def ku_trace(ku_id: str):
    """KU source provenance: which substrate(s) this KU was extracted from.

    Uses source_trace (oprim P-G3) via sources JSONB adapter.
    Falls back to substrate_id column for historical KUs with empty sources.
    """
    try:
        uid = _uuid.UUID(ku_id)
    except ValueError:
        return error_response("INVALID_UUID", f"invalid ku_id: {ku_id}")

    try:
        from oprim._source_trace import source_trace

        pool = await backend._ensure_pool()
        async with pool.acquire() as conn:
            ku_row = await conn.fetchrow(
                "SELECT ku_id, natural_text, substrate_id, sources FROM aii.ku WHERE ku_id = $1",
                uid,
            )
            if not ku_row:
                return error_response("NOT_FOUND", f"KU {ku_id} not found")

            # Fetch substrate titles for all source_ids
            raw_sources = _jsonb(ku_row["sources"]) or []
            source_ids: list[str] = [s["substrate_id"] for s in raw_sources if s.get("substrate_id")]
            if not source_ids and ku_row["substrate_id"]:
                source_ids = [str(ku_row["substrate_id"])]

            substrate_rows = await conn.fetch(
                "SELECT substrate_id, title, medium FROM aii.ingested_substrate WHERE substrate_id = ANY($1)",
                source_ids,
            ) if source_ids else []

        substrate_map = {str(r["substrate_id"]): {"title": r["title"], "medium": r["medium"]} for r in substrate_rows}

        # Adapter: feeds source_trace (P-G3) from sources JSONB
        class _SourcesAdapter:
            async def fetch(self, _sql: str, _ku_id: str) -> list[dict]:
                result = []
                for i, s in enumerate(raw_sources):
                    result.append({
                        "source_id": s.get("substrate_id", ""),
                        "page": s.get("page"),
                        "chunk_idx": i,
                        "text_snippet": (s.get("natural_text") or "")[:200],
                    })
                if not result and ku_row["substrate_id"]:
                    result.append({
                        "source_id": str(ku_row["substrate_id"]),
                        "page": None,
                        "chunk_idx": 0,
                        "text_snippet": "",
                    })
                return result

        trace_result = await source_trace(ku_id=ku_id, db_conn=_SourcesAdapter())

        positions_with_titles = [
            {
                **pos,
                "substrate_title": substrate_map.get(pos["source_id"], {}).get("title"),
                "medium": substrate_map.get(pos["source_id"], {}).get("medium"),
            }
            for pos in trace_result.source_positions
        ]

        return success_response({
            "ku_id": ku_id,
            "source_ids": trace_result.source_ids,
            "trace_depth": trace_result.trace_depth,
            "positions": positions_with_titles,
        })
    except Exception as e:
        return error_response("TRACE_ERROR", str(e))
