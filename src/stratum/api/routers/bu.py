"""BU2 API — Book Understanding v2 endpoints.

Thin adapter over BU2Query service. Reads from book_understandings_v2 (authority).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from stratum.common import jwt_auth
from stratum.db import query

router = APIRouter(prefix="/api/v1/bu", tags=["bu"])


def _j(v, default=None):
    """jsonb may arrive as text (double-encoded); decode it."""
    import json as _json

    for _ in range(2):
        if isinstance(v, str):
            try:
                v = _json.loads(v)
            except ValueError:
                break
    return default if v is None else v


class BuListItem(BaseModel):
    id: str
    run_id: str
    substrate_id: str
    book_title: str
    summary: str
    grade: str
    main_claim_count: int
    version: int
    status: str
    created_at: str


class ChapterSummary(BaseModel):
    chapter_id: str
    chapter_question: str | None = None
    primary_role: str | None = None
    concepts_introduced: int = 0
    arguments_count: int = 0
    evidence_count: int = 0
    quality_score: float = 0.0


class BuDetailResponse(BaseModel):
    id: str
    substrate_id: str
    run_id: str
    book_title: str
    version: int
    status: str
    grade: str
    summary: str
    main_claim_count: int
    coverage_score: float
    verification_score: float
    chapters: list[ChapterSummary]
    created_at: str
    updated_at: str


@router.get("", response_model=list[BuListItem])
async def list_bu(
    user_id: str = Depends(jwt_auth),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
):
    """List Book Understandings for the current user."""
    rows = query(
        """
        SELECT bu.id, bu.run_id, bu.substrate_id, bu.book_id, bu.version, bu.status,
               bu.coverage_score, bu.verification_score, bu.created_at, bu.updated_at,
               s.title as book_title
        FROM stratum.book_understandings_v2 bu
        JOIN stratum.substrates s ON s.id = bu.substrate_id
        WHERE s.user_id IN (%(uid)s, %(huid)s)
          AND (%(status)s IS NULL OR bu.status = %(status)s)
        ORDER BY bu.updated_at DESC
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        {"uid": user_id, "huid": user_id, "status": status, "limit": limit, "offset": offset},
    )

    items = []
    for r in rows:
        items.append(
            BuListItem(
                id=r["id"],
                run_id=r["run_id"],
                substrate_id=r["substrate_id"],
                book_title=r["book_title"] or r["book_id"],
                summary=f"Coverage: {r['coverage_score']:.0%}, Verification: {r['verification_score']:.0%}",
                grade="verified" if r["verification_score"] > 0.7 else "unverified",
                main_claim_count=0,
                version=r["version"],
                status=r["status"],
                created_at=str(r["created_at"]),
            )
        )
    return items


@router.get("/{run_id}", response_model=BuDetailResponse)
async def get_bu(run_id: str, user_id: str = Depends(jwt_auth)):
    """Get full Book Understanding by run_id."""
    bu_row = query(
        """
        SELECT bu.id, bu.run_id, bu.substrate_id, bu.book_id, bu.version, bu.status,
               bu.coverage_score, bu.verification_score, bu.created_at, bu.updated_at,
               s.title as book_title
        FROM stratum.book_understandings_v2 bu
        JOIN stratum.substrates s ON s.id = bu.substrate_id
        WHERE bu.run_id = %(run_id)s
          AND s.user_id IN (%(uid)s, %(huid)s)
        ORDER BY bu.version DESC
        LIMIT 1
        """,
        {"run_id": run_id, "uid": user_id, "huid": user_id},
    )
    if not bu_row:
        raise HTTPException(404, "Book Understanding not found")

    r = bu_row[0]
    bu_id = r["id"]
    substrate_id = r["substrate_id"]

    # Get chapter summaries using actual schema
    ch_rows = query(
        """
        SELECT cu.chapter_id, cu.chapter_question, cu.primary_role,
               array_length(cu.concepts_introduced_refs, 1) as concepts_count,
               array_length(cu.arguments_refs, 1) as args_count,
               CASE jsonb_typeof(cu.evidence_program_json)
                 WHEN 'array' THEN jsonb_array_length(cu.evidence_program_json)
                 WHEN 'object' THEN CASE WHEN jsonb_typeof(cu.evidence_program_json->'entries') = 'array'
                                         THEN jsonb_array_length(cu.evidence_program_json->'entries') END
               END as ev_count
        FROM stratum.chapter_understandings cu
        WHERE cu.run_id = %(run_id)s
        ORDER BY cu.chapter_id
        """,
        {"run_id": run_id},
    )
    chapters = [
        ChapterSummary(
            chapter_id=c["chapter_id"],
            chapter_question=c["chapter_question"],
            primary_role=c["primary_role"],
            concepts_introduced=c["concepts_count"] or 0,
            arguments_count=c["args_count"] or 0,
            evidence_count=c["ev_count"] or 0,
            quality_score=0.5,
        )
        for c in ch_rows
    ]

    return BuDetailResponse(
        id=bu_id,
        substrate_id=substrate_id,
        run_id=run_id,
        book_title=r["book_title"] or r["book_id"],
        version=r["version"],
        status=r["status"],
        grade="verified" if r["verification_score"] > 0.7 else "unverified",
        summary=f"Coverage: {r['coverage_score']:.0%}, Verification: {r['verification_score']:.0%}",
        main_claim_count=0,
        coverage_score=r["coverage_score"] or 0.0,
        verification_score=r["verification_score"] or 0.0,
        chapters=chapters,
        created_at=str(r["created_at"]),
        updated_at=str(r["updated_at"]),
    )


@router.get("/{run_id}/chapters", response_model=list[ChapterSummary])
async def list_chapters(run_id: str, user_id: str = Depends(jwt_auth)):
    """List chapter understandings for a BU."""
    bu_row = query(
        """
        SELECT bu.id FROM stratum.book_understandings_v2 bu
        JOIN stratum.substrates s ON s.id = bu.substrate_id
        WHERE bu.run_id = %(run_id)s AND s.user_id IN (%(uid)s, %(huid)s)
        """,
        {"run_id": run_id, "uid": user_id, "huid": user_id},
    )
    if not bu_row:
        raise HTTPException(404, "Book Understanding not found")

    ch_rows = query(
        """
        SELECT cu.chapter_id, cu.chapter_question, cu.primary_role,
               array_length(cu.concepts_introduced_refs, 1) as concepts_count,
               array_length(cu.arguments_refs, 1) as args_count,
               CASE jsonb_typeof(cu.evidence_program_json)
                 WHEN 'array' THEN jsonb_array_length(cu.evidence_program_json)
                 WHEN 'object' THEN CASE WHEN jsonb_typeof(cu.evidence_program_json->'entries') = 'array'
                                         THEN jsonb_array_length(cu.evidence_program_json->'entries') END
               END as ev_count
        FROM stratum.chapter_understandings cu
        WHERE cu.run_id = %(run_id)s
        ORDER BY cu.chapter_id
        """,
        {"run_id": run_id},
    )
    return [
        ChapterSummary(
            chapter_id=c["chapter_id"],
            chapter_question=c["chapter_question"],
            primary_role=c["primary_role"],
            concepts_introduced=c["concepts_count"] or 0,
            arguments_count=c["args_count"] or 0,
            evidence_count=c["ev_count"] or 0,
            quality_score=0.5,
        )
        for c in ch_rows
    ]


@router.get("/{run_id}/chapters/{chapter_id}")
async def get_chapter(run_id: str, chapter_id: str, user_id: str = Depends(jwt_auth)):
    """Get chapter understanding detail."""
    bu_row = query(
        """
        SELECT bu.id FROM stratum.book_understandings_v2 bu
        JOIN stratum.substrates s ON s.id = bu.substrate_id
        WHERE bu.run_id = %(run_id)s AND s.user_id IN (%(uid)s, %(huid)s)
        """,
        {"run_id": run_id, "uid": user_id, "huid": user_id},
    )
    if not bu_row:
        raise HTTPException(404, "Book Understanding not found")

    row = query(
        """
        SELECT cu.chapter_id, cu.chapter_question, cu.chapter_goal, cu.chapter_thesis,
               cu.primary_role, cu.secondary_roles_json, cu.concepts_introduced_refs,
               cu.concepts_redefined_refs, cu.major_ku_refs, cu.supporting_ku_refs,
               cu.arguments_refs, cu.mechanisms_refs, cu.evidence_program_json,
               cu.assumptions_json, cu.qualifications_json, cu.dependencies_on_prior,
               cu.promises_to_future, cu.evidence_strengths, cu.concept_definitions, cu.created_at
        FROM stratum.chapter_understandings cu
        WHERE cu.run_id = %(run_id)s AND cu.chapter_id = %(chapter_id)s
        """,
        {"run_id": run_id, "chapter_id": chapter_id},
    )
    if not row:
        raise HTTPException(404, "Chapter not found")

    r = row[0]
    return {
        "chapter_id": r["chapter_id"],
        "chapter_question": r["chapter_question"],
        "chapter_goal": r["chapter_goal"],
        "chapter_thesis": r["chapter_thesis"],
        "primary_role": r["primary_role"],
        "secondary_roles": _j(r["secondary_roles_json"], []),
        "concepts_introduced": r["concepts_introduced_refs"] or [],
        "concepts_redefined": r["concepts_redefined_refs"] or [],
        "major_ku_refs": r["major_ku_refs"] or [],
        "supporting_ku_refs": r["supporting_ku_refs"] or [],
        "arguments_refs": r["arguments_refs"] or [],
        "mechanisms_refs": r["mechanisms_refs"] or [],
        "evidence_program": _j(r["evidence_program_json"], []),
        "claims": _claims_from_program(_j(r["evidence_program_json"], [])),
        "evidence_strengths": _j(r.get("evidence_strengths"), {}),
        "concept_definitions": _j(r.get("concept_definitions"), []),
        "assumptions": _j(r["assumptions_json"], []),
        "qualifications": _j(r["qualifications_json"], []),
        "dependencies_on_prior": _j(r["dependencies_on_prior"], []),
        "promises_to_future": _j(r["promises_to_future"], []),
        "created_at": str(r["created_at"]),
    }


@router.get("/{run_id}/synthesis")
async def get_synthesis(run_id: str, user_id: str = Depends(jwt_auth)):
    """Get P13 book synthesis."""
    bu_row = query(
        """
        SELECT bu.id, bu.substrate_id, bu.book_id FROM stratum.book_understandings_v2 bu
        JOIN stratum.substrates s ON s.id = bu.substrate_id
        WHERE bu.run_id = %(run_id)s AND s.user_id IN (%(uid)s, %(huid)s)
        """,
        {"run_id": run_id, "uid": user_id, "huid": user_id},
    )
    if not bu_row:
        raise HTTPException(404, "Book Understanding not found")
    r = bu_row[0]
    substrate_id = r["substrate_id"]

    # Read from book_syntheses (created by P13)
    synth_rows = query(
        "SELECT * FROM stratum.book_syntheses WHERE run_id = %(run_id)s "
        "ORDER BY created_at DESC LIMIT 1",
        {"run_id": run_id},
    )
    synth = synth_rows[0] if synth_rows else None
    if not synth:
        raise HTTPException(404, "Synthesis not found")

    # Ensure ownership
    if synth.get("book_id") and str(synth.get("book_id")) not in (
        substrate_id,
        str(r.get("book_id") or ""),
    ):
        raise HTTPException(404, "Synthesis not found for this book")

    return {k: (str(v) if k == "created_at" else v) for k, v in synth.items()}


# ── BU2 artifacts (PR #23): quality gates, evidence, arguments, graphs ──────


def _owned_bu(run_id: str, user_id: str) -> dict:
    rows = query(
        """
        SELECT bu.id, bu.substrate_id, bu.book_id, bu.reasoning_graph_id,
               bu.argument_graph_id
        FROM stratum.book_understandings_v2 bu
        JOIN stratum.substrates s ON s.id = bu.substrate_id
        WHERE bu.run_id = %(run_id)s AND s.user_id IN (%(uid)s, %(huid)s)
        ORDER BY bu.version DESC
        LIMIT 1
        """,
        {"run_id": run_id, "uid": user_id, "huid": user_id},
    )
    if not rows:
        raise HTTPException(404, "Book Understanding not found")
    return rows[0]


def _claims_from_program(program) -> list[dict]:
    """Normalise evidence_program_json into claim rows with is_supported."""
    entries = program
    if isinstance(program, dict):
        entries = program.get("entries") or []
    if not isinstance(entries, list):
        return []
    out = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        supported = e.get("is_supported")
        out.append(
            {
                "claim": e.get("claim_ref") or e.get("claim") or "",
                "is_supported": supported if isinstance(supported, bool) else None,
                "evidence_refs": e.get("evidence_refs") or [],
                "presented_as": "SOURCE" if supported is not False else "MODEL_INFERENCE",
            }
        )
    return out


@router.get("/{run_id}/quality-gates")
async def get_quality_gates(run_id: str, user_id: str = Depends(jwt_auth)):
    """H1–H7 hard gates and the six-dimension score for a run."""
    _owned_bu(run_id, user_id)
    rows = query(
        """
        SELECT gate_number, gate_name, status, score, detail, evidence, checked_at
        FROM stratum.bu2_p13_quality_gates
        WHERE run_id = %(run_id)s
        ORDER BY gate_number
        LIMIT 50
        """,
        {"run_id": run_id},
    )
    gates = []
    six = None
    for g in rows:
        item = {
            "gate_number": g["gate_number"],
            "gate_name": g["gate_name"],
            "status": g["status"],
            "score": g["score"],
            "detail": g["detail"],
            "evidence": _j(g["evidence"]),
            "checked_at": str(g["checked_at"]),
        }
        if g["gate_name"] == "six_dimension_score":
            six = item
        else:
            gates.append(item)
    return {
        "run_id": run_id,
        "all_passed": bool(gates) and all(g["status"] == "PASS" for g in gates),
        "hard_gates": gates,
        "six_dimension": six,
    }


@router.get("/{run_id}/evidence")
async def list_evidence(
    run_id: str,
    user_id: str = Depends(jwt_auth),
    chapter_id: str | None = Query(None),
    kind: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Persisted evidence artifacts: quote, locator, strength, verified."""
    _owned_bu(run_id, user_id)
    params = {"run_id": run_id, "ch": chapter_id, "kind": kind, "limit": limit, "offset": offset}
    total = query(
        """
        SELECT count(*) AS n FROM stratum.bu2_evidence_artifact
        WHERE run_id = %(run_id)s
          AND (%(ch)s::text IS NULL OR chapter_id = %(ch)s)
          AND (%(kind)s::text IS NULL OR kind = %(kind)s)
        """,
        params,
    )
    rows = query(
        """
        SELECT id, chapter_id, kind, locator, quote, strength, verified
        FROM stratum.bu2_evidence_artifact
        WHERE run_id = %(run_id)s
          AND (%(ch)s::text IS NULL OR chapter_id = %(ch)s)
          AND (%(kind)s::text IS NULL OR kind = %(kind)s)
        ORDER BY chapter_id, id
        LIMIT %(limit)s OFFSET %(offset)s
        """,
        params,
    )
    return {"total": total[0]["n"] if total else 0, "items": rows}


@router.get("/{run_id}/arguments")
async def list_arguments(
    run_id: str,
    user_id: str = Depends(jwt_auth),
    chapter_id: str | None = Query(None),
):
    """Reconstructed arguments: premises → inference steps → conclusion."""
    _owned_bu(run_id, user_id)
    ch_rows = query(
        """
        SELECT chapter_id, arguments_refs FROM stratum.chapter_understandings
        WHERE run_id = %(run_id)s AND (%(ch)s::text IS NULL OR chapter_id = %(ch)s)
        LIMIT 500
        """,
        {"run_id": run_id, "ch": chapter_id},
    )
    chapter_of: dict[str, str] = {}
    for c in ch_rows:
        for ref in c["arguments_refs"] or []:
            chapter_of[ref] = c["chapter_id"]
    if not chapter_of:
        return {"total": 0, "items": []}
    rows = query(
        """
        SELECT id, question, premises_json, warrants_json, inference_steps_json,
               qualifiers_json, conclusion, evidence_refs, confidence
        FROM stratum.arguments
        WHERE run_id = %(run_id)s AND id = ANY(%(ids)s)
        ORDER BY id
        LIMIT 1000
        """,
        {"run_id": run_id, "ids": list(chapter_of)},
    )
    ev_ids = sorted({e for r in rows for e in (r["evidence_refs"] or [])})
    ev = {}
    if ev_ids:
        for e in query(
            """
            SELECT id, locator, quote, strength, verified
            FROM stratum.bu2_evidence_artifact
            WHERE run_id = %(run_id)s AND id = ANY(%(ids)s)
            LIMIT 5000
            """,
            {"run_id": run_id, "ids": ev_ids},
        ):
            ev[e["id"]] = e
    items = []
    for r in rows:
        refs = r["evidence_refs"] or []
        evidence = [ev[x] for x in refs if x in ev]
        verified = [e["verified"] for e in evidence if e["verified"] is not None]
        concl = _j(r["conclusion"])
        if isinstance(concl, list):
            concl = " ".join(str(x) for x in concl)
        items.append(
            {
                "id": r["id"],
                "chapter_id": chapter_of.get(r["id"]),
                "claim": r["question"],
                "premises": _j(r["premises_json"], []),
                "warrants": _j(r["warrants_json"], []),
                "inference_steps": _j(r["inference_steps_json"], []),
                "qualifiers": _j(r["qualifiers_json"], []),
                "conclusion": concl,
                "confidence": r["confidence"],
                "evidence": evidence,
                "is_supported": (all(verified) if verified else None),
            }
        )
    items.sort(key=lambda a: (a["chapter_id"] or "", a["id"]))
    return {"total": len(items), "items": items}


@router.get("/{run_id}/graph")
async def get_graph(
    run_id: str,
    user_id: str = Depends(jwt_auth),
    kind: str = Query("reasoning", pattern="^(reasoning|argument)$"),
    chapter_id: str | None = Query(None),
    limit: int = Query(2000, ge=1, le=5000),
):
    """Reasoning graph or argument graph nodes and edges."""
    bu = _owned_bu(run_id, user_id)
    graph_id = bu["reasoning_graph_id"] if kind == "reasoning" else bu["argument_graph_id"]
    if not graph_id:
        raise HTTPException(404, f"No {kind} graph for this run")
    node_t, edge_t = (
        ("reasoning_node", "reasoning_edge")
        if kind == "reasoning"
        else ("argument_node", "argument_edge")
    )
    nodes = query(
        f"""
        SELECT id, node_type, label, chapter_id, confidence
        FROM stratum.{node_t}
        WHERE graph_id = %(g)s AND (%(ch)s::text IS NULL OR chapter_id = %(ch)s)
        ORDER BY chapter_id, id
        LIMIT %(limit)s
        """,
        {"g": graph_id, "ch": chapter_id, "limit": limit},
    )
    ids = [n["id"] for n in nodes]
    edges = query(
        f"""
        SELECT id, source_node_id, target_node_id, relation_type, reason, confidence
        FROM stratum.{edge_t}
        WHERE graph_id = %(g)s AND source_node_id = ANY(%(ids)s)
          AND target_node_id = ANY(%(ids)s)
        LIMIT %(limit)s
        """,
        {"g": graph_id, "ids": ids, "limit": limit * 3},
    )
    totals = query(
        f"""
        SELECT (SELECT count(*) FROM stratum.{node_t} WHERE graph_id = %(g)s) AS nodes,
               (SELECT count(*) FROM stratum.{edge_t} WHERE graph_id = %(g)s) AS edges
        """,
        {"g": graph_id},
    )
    return {
        "kind": kind,
        "graph_id": graph_id,
        "total_nodes": totals[0]["nodes"] if totals else len(nodes),
        "total_edges": totals[0]["edges"] if totals else len(edges),
        "nodes": nodes,
        "edges": edges,
    }


@router.get("/{run_id}/concept-evolution")
async def get_concept_evolution(
    run_id: str,
    user_id: str = Depends(jwt_auth),
    limit: int = Query(200, ge=1, le=2000),
    offset: int = Query(0, ge=0),
):
    """How concepts are introduced and redefined across chapters."""
    _owned_bu(run_id, user_id)
    rows = query(
        """
        SELECT concept_evolution_json FROM stratum.book_understandings_v2
        WHERE run_id = %(run_id)s ORDER BY version DESC LIMIT 1
        """,
        {"run_id": run_id},
    )
    data = _j(rows[0]["concept_evolution_json"]) if rows else None
    items = data if isinstance(data, list) else []
    return {"total": len(items), "items": items[offset : offset + limit]}
