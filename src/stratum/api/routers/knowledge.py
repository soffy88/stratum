"""Canonical Knowledge API for claims, relations, and first-class Evidence."""

from __future__ import annotations

import json
import hashlib
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class ClaimCreate(BaseModel):
    statement: str = Field(..., min_length=1, max_length=20_000)
    status: str = Field("unverified", pattern="^(unverified|verified|contradicted|refuted)$")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    concept_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    evidence_relation: str = Field("supports", pattern="^(supports|contradicts|qualifies)$")


class ClaimUpdate(BaseModel):
    statement: str | None = Field(None, min_length=1, max_length=20_000)
    status: str | None = Field(None, pattern="^(unverified|verified|contradicted|refuted)$")
    confidence: float | None = Field(None, ge=0.0, le=1.0)


class EvidenceCreate(BaseModel):
    substrate_id: str = Field(..., min_length=1)
    quote: str = Field(..., min_length=1, max_length=100_000)
    source_highlight_id: str | None = None
    locator: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(1.0, ge=0.0, le=1.0)


class RelationCreate(BaseModel):
    source_concept_id: str
    target_concept_id: str
    relation_type: str = Field(..., min_length=1, max_length=80)
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    rationale: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_explanation(self) -> "RelationCreate":
        if not (self.rationale and self.rationale.strip()) and not self.evidence_ids:
            raise ValueError("relation requires rationale or at least one evidence_id")
        return self


def _json(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return value


def _quote_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _owned_concepts(conn: Any, user_id: str, concept_ids: list[str]) -> set[str]:
    if not concept_ids:
        return set()
    rows = conn.execute(
        "SELECT id FROM stratum.concepts WHERE user_id=? AND deleted_at IS NULL AND id = ANY(?)",
        (user_id, concept_ids),
    ).fetchall()
    return {r[0] for r in rows}


def _owned_evidence(conn: Any, user_id: str, evidence_ids: list[str]) -> set[str]:
    if not evidence_ids:
        return set()
    rows = conn.execute(
        "SELECT id FROM stratum.evidence WHERE user_id IN (?, ?) AND id = ANY(?)",
        (user_id, hash_user_id(user_id), evidence_ids),
    ).fetchall()
    return {r[0] for r in rows}


def _owned_substrate(conn: Any, user_id: str, substrate_id: str) -> bool:
    rows = conn.execute(
        "SELECT id FROM stratum.substrates WHERE id=? AND user_id IN (?, ?)",
        (substrate_id, user_id, hash_user_id(user_id)),
    ).fetchall()
    return bool(rows)


def _owned_highlight(conn: Any, user_id: str, highlight_id: str) -> tuple[Any, ...] | None:
    row = conn.execute(
        "SELECT id, substrate_id, text, user_id FROM stratum.highlights WHERE id=?",
        (highlight_id,),
    ).fetchone()
    if not row or row[3] not in {user_id, hash_user_id(user_id)}:
        return None
    return cast(tuple[Any, ...], row)


@router.post("/evidence", status_code=201)
async def create_evidence(body: EvidenceCreate, user_id: str = Depends(jwt_auth)) -> Any:
    """Create a portable Evidence object owned by the caller.

    Highlights remain a convenient UI write path, but agents and importers can
    now create Evidence directly as long as the substrate (and optional source
    highlight) belongs to the caller.
    """
    owner = hash_user_id(user_id)
    with get_conn() as conn:
        if not _owned_substrate(conn, user_id, body.substrate_id):
            raise HTTPException(404, "Substrate not found")
        if body.source_highlight_id:
            highlight = _owned_highlight(conn, user_id, body.source_highlight_id)
            if not highlight or highlight[1] != body.substrate_id:
                raise HTTPException(404, "Source highlight not found")
            evidence_id = body.source_highlight_id
        else:
            evidence_id = generate_ulid()
        now = now_utc()
        conn.execute(
            "INSERT INTO stratum.evidence "
            "(id, user_id, source_highlight_id, substrate_id, quote, quote_hash, "
            "locator_json, confidence, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (id) DO UPDATE SET quote=EXCLUDED.quote, "
            "quote_hash=EXCLUDED.quote_hash, locator_json=EXCLUDED.locator_json, "
            "confidence=EXCLUDED.confidence, updated_at=EXCLUDED.updated_at",
            (
                evidence_id,
                owner,
                body.source_highlight_id,
                body.substrate_id,
                body.quote.strip(),
                _quote_hash(body.quote),
                json.dumps(body.locator),
                body.confidence,
                now,
                now,
            ),
        )
    return {
        "id": evidence_id,
        "substrate_id": body.substrate_id,
        "source_highlight_id": body.source_highlight_id,
        "quote": body.quote.strip(),
        "quote_hash": _quote_hash(body.quote),
        "locator": body.locator,
        "confidence": body.confidence,
    }


@router.post("/claims", status_code=201)
async def create_claim(body: ClaimCreate, user_id: str = Depends(jwt_auth)) -> Any:
    """Create a claim and attach only Evidence owned by the caller."""
    with get_conn() as conn:
        owned_concepts = _owned_concepts(conn, user_id, body.concept_ids)
        if owned_concepts != set(body.concept_ids):
            raise HTTPException(404, "One or more concepts not found")
        owned_evidence = _owned_evidence(conn, user_id, body.evidence_ids)
        if owned_evidence != set(body.evidence_ids):
            raise HTTPException(404, "One or more evidence objects not found")

        claim_id = generate_ulid()
        now = now_utc()
        conn.execute(
            "INSERT INTO stratum.knowledge_claims "
            "(id, user_id, statement, status, confidence, concept_ids, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                claim_id,
                user_id,
                body.statement.strip(),
                body.status,
                body.confidence,
                body.concept_ids,
                now,
                now,
            ),
        )
        for evidence_id in body.evidence_ids:
            conn.execute(
                "INSERT INTO stratum.claim_evidence (claim_id, evidence_id, relation) "
                "VALUES (?,?,?) ON CONFLICT DO NOTHING",
                (claim_id, evidence_id, body.evidence_relation),
            )
    return {"id": claim_id, "status": body.status, "evidence_ids": body.evidence_ids}


@router.get("/claims/{claim_id}")
async def get_claim(claim_id: str, user_id: str = Depends(jwt_auth)) -> Any:
    """Return one caller-owned claim with its Evidence links."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, statement, status, confidence, concept_ids, created_at, updated_at "
            "FROM stratum.knowledge_claims "
            "WHERE id=? AND user_id=? AND deleted_at IS NULL",
            (claim_id, user_id),
        ).fetchone()
        if not row:
            raise HTTPException(404, "Claim not found")
        evidence = conn.execute(
            "SELECT evidence_id, relation FROM stratum.claim_evidence "
            "WHERE claim_id=? ORDER BY created_at",
            (claim_id,),
        ).fetchall()
    return {
        "id": row[0],
        "statement": row[1],
        "status": row[2],
        "confidence": float(row[3]),
        "concept_ids": row[4] or [],
        "evidence": [{"evidence_id": item[0], "relation": item[1]} for item in evidence],
        "created_at": str(row[5]),
        "updated_at": str(row[6]),
    }


@router.patch("/claims/{claim_id}")
async def update_claim(claim_id: str, body: ClaimUpdate, user_id: str = Depends(jwt_auth)) -> Any:
    changes = {key: value for key, value in body.model_dump().items() if value is not None}
    if not changes:
        raise HTTPException(400, "At least one claim field is required")
    changes["updated_at"] = now_utc()
    with get_conn() as conn:
        updated = conn.execute(
            "UPDATE stratum.knowledge_claims SET "
            "statement=COALESCE(?, statement), status=COALESCE(?, status), "
            "confidence=COALESCE(?, confidence), updated_at=? "
            "WHERE id=? AND user_id=? AND deleted_at IS NULL RETURNING id",
            (
                changes.get("statement"),
                changes.get("status"),
                changes.get("confidence"),
                changes["updated_at"],
                claim_id,
                user_id,
            ),
        ).fetchone()
    if not updated:
        raise HTTPException(404, "Claim not found")
    return {"id": claim_id, "status": "updated", **changes}


@router.get("/claims")
async def list_claims(
    status: str | None = Query(None),
    concept_id: str | None = Query(None),
    user_id: str = Depends(jwt_auth),
) -> Any:
    where = ["c.user_id = ?", "c.deleted_at IS NULL"]
    params: list[Any] = [user_id]
    if status:
        where.append("c.status = ?")
        params.append(status)
    if concept_id:
        where.append("? = ANY(c.concept_ids)")
        params.append(concept_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.id, c.statement, c.status, c.confidence, c.concept_ids, "
            "c.created_at, c.updated_at, "
            "COALESCE(json_agg(json_build_object('evidence_id', ce.evidence_id, "
            "'relation', ce.relation)) FILTER (WHERE ce.evidence_id IS NOT NULL), '[]') "
            "FROM stratum.knowledge_claims c "
            "LEFT JOIN stratum.claim_evidence ce ON ce.claim_id=c.id "
            f"WHERE {' AND '.join(where)} GROUP BY c.id ORDER BY c.updated_at DESC",
            tuple(params),
        ).fetchall()
    return [
        {
            "id": r[0],
            "statement": r[1],
            "status": r[2],
            "confidence": float(r[3]),
            "concept_ids": r[4] or [],
            "evidence": _json(r[7], []),
            "created_at": str(r[5]),
            "updated_at": str(r[6]),
        }
        for r in rows
    ]


@router.get("/relations")
async def list_relations(
    concept_id: str | None = Query(None),
    user_id: str = Depends(jwt_auth),
) -> Any:
    where = ["user_id=?"]
    params: list[Any] = [user_id]
    if concept_id:
        where.append("(source_concept_id=? OR target_concept_id=?)")
        params.extend([concept_id, concept_id])
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, source_concept_id, target_concept_id, relation_type, confidence, "
            "rationale, evidence_ids, created_at, updated_at "
            f"FROM stratum.concept_relations WHERE {' AND '.join(where)} "
            "ORDER BY updated_at DESC LIMIT 500",
            tuple(params),
        ).fetchall()
    return [
        {
            "id": row[0],
            "source_concept_id": row[1],
            "target_concept_id": row[2],
            "relation_type": row[3],
            "confidence": float(row[4]),
            "rationale": row[5],
            "evidence_ids": row[6] or [],
            "created_at": str(row[7]),
            "updated_at": str(row[8]),
        }
        for row in rows
    ]


@router.post("/relations", status_code=201)
async def create_relation(body: RelationCreate, user_id: str = Depends(jwt_auth)) -> Any:
    """Create an explainable Concept edge backed by optional Evidence IDs."""
    with get_conn() as conn:
        owned = _owned_concepts(conn, user_id, [body.source_concept_id, body.target_concept_id])
        if len(owned) != 2:
            raise HTTPException(404, "One or both concepts not found")
        owned_evidence = _owned_evidence(conn, user_id, body.evidence_ids)
        if owned_evidence != set(body.evidence_ids):
            raise HTTPException(404, "One or more evidence objects not found")
        relation_id = generate_ulid()
        now = now_utc()
        conn.execute(
            "INSERT INTO stratum.concept_relations "
            "(id, user_id, source_concept_id, target_concept_id, relation_type, "
            "confidence, rationale, evidence_ids, created_at, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT (user_id, source_concept_id, target_concept_id, relation_type) "
            "DO UPDATE SET confidence=EXCLUDED.confidence, rationale=EXCLUDED.rationale, "
            "evidence_ids=EXCLUDED.evidence_ids, updated_at=EXCLUDED.updated_at",
            (
                relation_id,
                user_id,
                body.source_concept_id,
                body.target_concept_id,
                body.relation_type,
                body.confidence,
                body.rationale,
                body.evidence_ids,
                now,
                now,
            ),
        )
        relation_id = conn.execute(
            "SELECT id FROM stratum.concept_relations "
            "WHERE user_id=? AND source_concept_id=? AND target_concept_id=? AND relation_type=?",
            (user_id, body.source_concept_id, body.target_concept_id, body.relation_type),
        ).fetchone()[0]
    return {"id": relation_id, **body.model_dump()}


@router.get("/concepts/{concept_id}/neighborhood")
async def concept_neighborhood(
    concept_id: str,
    depth: int = Query(1, ge=1, le=3),
    user_id: str = Depends(jwt_auth),
) -> Any:
    """Return a bounded, user-scoped relation neighborhood with rationale."""
    with get_conn() as conn:
        if not _owned_concepts(conn, user_id, [concept_id]):
            raise HTTPException(404, "Concept not found")
        rows = conn.execute(
            "SELECT id, source_concept_id, target_concept_id, relation_type, confidence, "
            "rationale, evidence_ids FROM stratum.concept_relations "
            "WHERE user_id=? ORDER BY confidence DESC LIMIT 5000",
            (user_id,),
        ).fetchall()
        selected: list[Any] = []
        frontier = {concept_id}
        seen_concepts = {concept_id}
        for _ in range(depth):
            next_frontier: set[str] = set()
            for row in rows:
                if row[1] not in frontier and row[2] not in frontier:
                    continue
                if row not in selected:
                    selected.append(row)
                neighbor = row[2] if row[1] in frontier else row[1]
                if neighbor not in seen_concepts:
                    seen_concepts.add(neighbor)
                    next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break
        ids = seen_concepts
        labels = {}
        if ids:
            concept_rows = conn.execute(
                "SELECT id, name FROM stratum.concepts WHERE user_id=? AND id = ANY(?)",
                (user_id, list(ids)),
            ).fetchall()
            labels = {row[0]: row[1] for row in concept_rows}
    return {
        "seed": {"id": concept_id, "name": labels.get(concept_id)},
        "edges": [
            {
                "id": row[0],
                "source": row[1],
                "source_name": labels.get(row[1]),
                "target": row[2],
                "target_name": labels.get(row[2]),
                "type": row[3],
                "confidence": float(row[4]),
                "rationale": row[5],
                "evidence_ids": row[6] or [],
            }
            for row in selected
        ],
    }


@router.get("/evidence")
async def list_evidence(
    substrate_id: str | None = Query(None),
    user_id: str = Depends(jwt_auth),
) -> Any:
    where = ["user_id IN (?, ?)"]
    params: list[Any] = [user_id, hash_user_id(user_id)]
    if substrate_id:
        where.append("substrate_id=?")
        params.append(substrate_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, source_highlight_id, substrate_id, quote, quote_hash, "
            "locator_json, confidence, created_at, updated_at "
            f"FROM stratum.evidence WHERE {' AND '.join(where)} "
            "ORDER BY created_at DESC LIMIT 100",
            tuple(params),
        ).fetchall()
    return [
        {
            "id": row[0],
            "source_highlight_id": row[1],
            "substrate_id": row[2],
            "quote": row[3],
            "quote_hash": row[4],
            "locator": _json(row[5], {}),
            "confidence": float(row[6]),
            "created_at": str(row[7]),
            "updated_at": str(row[8]),
        }
        for row in rows
    ]


@router.get("/evidence/{evidence_id}")
async def get_evidence(evidence_id: str, user_id: str = Depends(jwt_auth)) -> Any:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, source_highlight_id, substrate_id, quote, quote_hash, "
            "locator_json, confidence, created_at, updated_at "
            "FROM stratum.evidence WHERE id=? AND user_id IN (?, ?)",
            (evidence_id, user_id, hash_user_id(user_id)),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Evidence not found")
    return {
        "id": row[0],
        "source_highlight_id": row[1],
        "substrate_id": row[2],
        "quote": row[3],
        "quote_hash": row[4],
        "locator": _json(row[5], {}),
        "confidence": float(row[6]),
        "created_at": str(row[7]),
        "updated_at": str(row[8]),
    }
