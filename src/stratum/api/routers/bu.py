"""BU2 API — Book Understanding v2 endpoints.

Thin adapter over BU2Query service. Reads from book_understandings_v2 (authority).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from stratum.common import jwt_auth
from stratum.db import query, read

router = APIRouter(prefix="/api/v1/bu", tags=["bu"])


class BuListItem(BaseModel):
    id: str
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
        items.append(BuListItem(
            id=r['id'],
            substrate_id=r['substrate_id'],
            book_title=r['book_title'] or r['book_id'],
            summary=f"Coverage: {r['coverage_score']:.0%}, Verification: {r['verification_score']:.0%}",
            grade="verified" if r['verification_score'] > 0.7 else "unverified",
            main_claim_count=0,
            version=r['version'],
            status=r['status'],
            created_at=str(r['created_at']),
        ))
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
    bu_id = r['id']
    substrate_id = r['substrate_id']

    # Get chapter summaries using actual schema
    ch_rows = query(
        """
        SELECT cu.chapter_id, cu.chapter_question, cu.primary_role,
               array_length(cu.concepts_introduced_refs, 1) as concepts_count,
               array_length(cu.arguments_refs, 1) as args_count,
               array_length(cu.evidence_program_json->'entries', 1) as ev_count
        FROM stratum.chapter_understandings cu
        WHERE cu.run_id = %(run_id)s
        ORDER BY cu.chapter_id
        """,
        {"run_id": run_id},
    )
    chapters = [
        ChapterSummary(
            chapter_id=c['chapter_id'],
            chapter_question=c['chapter_question'],
            primary_role=c['primary_role'],
            concepts_introduced=c['concepts_count'] or 0,
            arguments_count=c['args_count'] or 0,
            evidence_count=c['ev_count'] or 0,
            quality_score=0.5,
        )
        for c in ch_rows
    ]

    return BuDetailResponse(
        id=bu_id,
        substrate_id=substrate_id,
        run_id=run_id,
        book_title=r['book_title'] or r['book_id'],
        version=r['version'],
        status=r['status'],
        grade="verified" if r['verification_score'] > 0.7 else "unverified",
        summary=f"Coverage: {r['coverage_score']:.0%}, Verification: {r['verification_score']:.0%}",
        main_claim_count=0,
        coverage_score=r['coverage_score'] or 0.0,
        verification_score=r['verification_score'] or 0.0,
        chapters=chapters,
        created_at=str(r['created_at']),
        updated_at=str(r['updated_at']),
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
               array_length(cu.evidence_program_json->'entries', 1) as ev_count
        FROM stratum.chapter_understandings cu
        WHERE cu.run_id = %(run_id)s
        ORDER BY cu.chapter_id
        """,
        {"run_id": run_id},
    )
    return [
        ChapterSummary(
            chapter_id=c['chapter_id'],
            chapter_question=c['chapter_question'],
            primary_role=c['primary_role'],
            concepts_introduced=c['concepts_count'] or 0,
            arguments_count=c['args_count'] or 0,
            evidence_count=c['ev_count'] or 0,
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
               cu.promises_to_future, cu.created_at
        FROM stratum.chapter_understandings cu
        WHERE cu.run_id = %(run_id)s AND cu.chapter_id = %(chapter_id)s
        """,
        {"run_id": run_id, "chapter_id": chapter_id},
    )
    if not row:
        raise HTTPException(404, "Chapter not found")

    r = row[0]
    return {
        "chapter_id": r['chapter_id'],
        "chapter_question": r['chapter_question'],
        "chapter_goal": r['chapter_goal'],
        "chapter_thesis": r['chapter_thesis'],
        "primary_role": r['primary_role'],
        "secondary_roles": r['secondary_roles_json'] or [],
        "concepts_introduced": r['concepts_introduced_refs'] or [],
        "concepts_redefined": r['concepts_redefined_refs'] or [],
        "major_ku_refs": r['major_ku_refs'] or [],
        "supporting_ku_refs": r['supporting_ku_refs'] or [],
        "arguments_refs": r['arguments_refs'] or [],
        "mechanisms_refs": r['mechanisms_refs'] or [],
        "evidence_program": r['evidence_program_json'] or {},
        "assumptions": r['assumptions_json'] or [],
        "qualifications": r['qualifications_json'] or [],
        "dependencies_on_prior": r['dependencies_on_prior'] or [],
        "promises_to_future": r['promises_to_future'] or [],
        "created_at": str(r['created_at']),
    }


@router.get("/{run_id}/synthesis")
async def get_synthesis(run_id: str, user_id: str = Depends(jwt_auth)):
    """Get P13 book synthesis."""
    bu_row = query(
        """
        SELECT bu.id, bu.substrate_id FROM stratum.book_understandings_v2 bu
        JOIN stratum.substrates s ON s.id = bu.substrate_id
        WHERE bu.run_id = %(run_id)s AND s.user_id IN (%(uid)s, %(huid)s)
        """,
        {"run_id": run_id, "uid": user_id, "huid": user_id},
    )
    if not bu_row:
        raise HTTPException(404, "Book Understanding not found")
    r = bu_row[0]
    bu_id = r['id']
    substrate_id = r['substrate_id']

    # Read from book_syntheses (created by P13)
    synth = read("book_syntheses", run_id)
    if not synth:
        raise HTTPException(404, "Synthesis not found")

    # Ensure ownership
    if str(synth.get("book_id")) != substrate_id:
        raise HTTPException(404, "Synthesis not found for this book")

    return synth