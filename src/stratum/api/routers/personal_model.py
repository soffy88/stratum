"""Multi-user PersonalState, Belief, ContextLink, and LearningEvent API."""

from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator

from stratum.common import generate_ulid, jwt_auth, now_utc
from stratum.db import get_conn
from stratum.services.personal_model import (
    OBJECT_TYPES,
    owned_object_exists,
    record_learning_event,
    upsert_personal_state,
)

router = APIRouter(prefix="/api/v1/personal-model", tags=["personal-model"])

ObjectType = Literal["claim", "evidence", "concept", "substrate", "note", "highlight"]
SourceType = Literal["explicit", "inferred", "imported"]


class PersonalStateUpsert(BaseModel):
    object_type: ObjectType
    object_id: str = Field(..., min_length=1, max_length=200)
    mastery: float = Field(0.0, ge=0.0, le=1.0)
    interest: float = Field(0.0, ge=0.0, le=1.0)
    certainty: float = Field(0.0, ge=0.0, le=1.0)
    relevance: float = Field(0.0, ge=0.0, le=1.0)
    source: SourceType = "explicit"
    source_event_id: str | None = Field(None, max_length=200)

    @model_validator(mode="after")
    def inferred_state_needs_provenance(self) -> "PersonalStateUpsert":
        if self.source == "inferred" and not self.source_event_id:
            raise ValueError("inferred personal state requires source_event_id")
        return self


class BeliefUpsert(BaseModel):
    claim_id: str = Field(..., min_length=1, max_length=200)
    stance: Literal["agree", "disagree", "uncertain", "conditional"]
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    source: Literal["user", "inferred", "imported"] = "user"
    source_event_id: str | None = Field(None, max_length=200)
    rationale: str | None = Field(None, max_length=20_000)

    @model_validator(mode="after")
    def inferred_belief_needs_provenance(self) -> "BeliefUpsert":
        if self.source == "inferred" and not self.source_event_id:
            raise ValueError("inferred belief requires source_event_id")
        return self


class ContextLinkUpsert(BaseModel):
    object_type: ObjectType
    object_id: str = Field(..., min_length=1, max_length=200)
    context_type: Literal["project", "goal", "tag", "area"]
    context_id: str = Field(..., min_length=1, max_length=200)
    weight: float = Field(1.0, ge=0.0, le=1.0)
    source: SourceType = "explicit"
    source_event_id: str | None = Field(None, max_length=200)
    rationale: str | None = Field(None, max_length=20_000)

    @model_validator(mode="after")
    def inferred_link_needs_provenance(self) -> "ContextLinkUpsert":
        if self.source == "inferred" and not self.source_event_id:
            raise ValueError("inferred context link requires source_event_id")
        return self


def _assert_object_type(object_type: str) -> None:
    # Keep this explicit check even though Pydantic validates the normal HTTP
    # path; it protects helper calls and future importers.
    if object_type not in OBJECT_TYPES:
        raise HTTPException(422, "Unsupported object_type")


def _require_owned_object(conn, user_id: str, object_type: str, object_id: str) -> None:
    _assert_object_type(object_type)
    if not owned_object_exists(conn, user_id, object_type, object_id):
        raise HTTPException(404, "Referenced object not found")


@router.put("/states", status_code=200)
async def upsert_state(body: PersonalStateUpsert, user_id: str = Depends(jwt_auth)):
    with get_conn() as conn:
        _require_owned_object(conn, user_id, body.object_type, body.object_id)
        state_id = upsert_personal_state(
            conn,
            user_id,
            object_type=body.object_type,
            object_id=body.object_id,
            mastery=body.mastery,
            interest=body.interest,
            certainty=body.certainty,
            relevance=body.relevance,
            source=body.source,
            source_event_id=body.source_event_id,
        )
    _record_model_event(
        user_id,
        object_type=body.object_type,
        object_id=body.object_id,
        event_type="personal_state_updated",
        result=body.model_dump(),
    )
    return {"id": state_id, **body.model_dump()}


@router.get("/states")
async def list_states(
    object_type: ObjectType | None = Query(None),
    object_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(jwt_auth),
):
    where = ["user_id=?", "deleted_at IS NULL"]
    params: list[object] = [user_id]
    if object_type:
        where.append("object_type=?")
        params.append(object_type)
    if object_id:
        where.append("object_id=?")
        params.append(object_id)
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, object_type, object_id, mastery, interest, certainty, relevance, "
            "source, source_event_id, created_at, updated_at "
            f"FROM stratum.personal_states WHERE {' AND '.join(where)} "
            "ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [_state_row(row) for row in rows]


@router.get("/events")
async def list_learning_events(
    event_type: str | None = Query(None, min_length=1, max_length=100),
    object_type: str | None = Query(None, min_length=1, max_length=100),
    object_id: str | None = Query(None, min_length=1, max_length=200),
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(jwt_auth),
):
    """Read the user's append-only learning ledger; writes stay service-owned."""
    where = ["user_id=?"]
    params: list[object] = [user_id]
    for field, value in (
        ("event_type", event_type),
        ("object_type", object_type),
        ("object_id", object_id),
    ):
        if value:
            where.append(f"{field}=?")
            params.append(value)
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, object_type, object_id, event_type, result, source, "
            "occurred_at, created_at FROM stratum.learning_events "
            f"WHERE {' AND '.join(where)} ORDER BY occurred_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [_event_row(row) for row in rows]


@router.delete("/states/{state_id}", status_code=204)
async def delete_state(state_id: str, user_id: str = Depends(jwt_auth)):
    with get_conn() as conn:
        row = conn.execute(
            "UPDATE stratum.personal_states SET deleted_at=?, updated_at=? "
            "WHERE id=? AND user_id=? AND deleted_at IS NULL RETURNING id",
            (now_utc(), now_utc(), state_id, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Personal state not found")
    _record_model_event(
        user_id,
        object_type="state",
        object_id=state_id,
        event_type="personal_state_deleted",
        result={},
    )


@router.put("/beliefs", status_code=200)
async def upsert_belief(body: BeliefUpsert, user_id: str = Depends(jwt_auth)):
    with get_conn() as conn:
        _require_owned_object(conn, user_id, "claim", body.claim_id)
        belief_id = generate_ulid()
        conn.execute(
            "INSERT INTO stratum.beliefs "
            "(id, user_id, claim_id, stance, confidence, source, source_event_id, rationale, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW()) "
            "ON CONFLICT (user_id, claim_id) DO UPDATE SET stance=EXCLUDED.stance, "
            "confidence=EXCLUDED.confidence, source=EXCLUDED.source, "
            "source_event_id=EXCLUDED.source_event_id, rationale=EXCLUDED.rationale, "
            "deleted_at=NULL, updated_at=NOW()",
            (
                belief_id,
                user_id,
                body.claim_id,
                body.stance,
                body.confidence,
                body.source,
                body.source_event_id,
                body.rationale,
            ),
        )
        row = conn.execute(
            "SELECT id FROM stratum.beliefs WHERE user_id=? AND claim_id=?",
            (user_id, body.claim_id),
        ).fetchone()
    _record_model_event(
        user_id,
        object_type="claim",
        object_id=body.claim_id,
        event_type="belief_updated",
        result=body.model_dump(),
    )
    return {"id": row[0] if row else belief_id, **body.model_dump()}


@router.get("/beliefs")
async def list_beliefs(
    claim_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(jwt_auth),
):
    where = ["user_id=?", "deleted_at IS NULL"]
    params: list[object] = [user_id]
    if claim_id:
        where.append("claim_id=?")
        params.append(claim_id)
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, claim_id, stance, confidence, source, source_event_id, rationale, "
            "created_at, updated_at "
            f"FROM stratum.beliefs WHERE {' AND '.join(where)} "
            "ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [
        {
            "id": row[0],
            "claim_id": row[1],
            "stance": row[2],
            "confidence": float(row[3]),
            "source": row[4],
            "source_event_id": row[5],
            "rationale": row[6],
            "created_at": str(row[7]),
            "updated_at": str(row[8]),
        }
        for row in rows
    ]


@router.put("/context-links", status_code=200)
async def upsert_context_link(body: ContextLinkUpsert, user_id: str = Depends(jwt_auth)):
    with get_conn() as conn:
        _require_owned_object(conn, user_id, body.object_type, body.object_id)
        link_id = generate_ulid()
        conn.execute(
            "INSERT INTO stratum.context_links "
            "(id, user_id, object_type, object_id, context_type, context_id, weight, source, "
            "source_event_id, rationale, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW()) "
            "ON CONFLICT (user_id, object_type, object_id, context_type, context_id) "
            "DO UPDATE SET weight=EXCLUDED.weight, source=EXCLUDED.source, "
            "source_event_id=EXCLUDED.source_event_id, rationale=EXCLUDED.rationale, "
            "deleted_at=NULL, updated_at=NOW()",
            (
                link_id,
                user_id,
                body.object_type,
                body.object_id,
                body.context_type,
                body.context_id,
                body.weight,
                body.source,
                body.source_event_id,
                body.rationale,
            ),
        )
        row = conn.execute(
            "SELECT id FROM stratum.context_links WHERE user_id=? AND object_type=? "
            "AND object_id=? AND context_type=? AND context_id=?",
            (user_id, body.object_type, body.object_id, body.context_type, body.context_id),
        ).fetchone()
    _record_model_event(
        user_id,
        object_type=body.object_type,
        object_id=body.object_id,
        event_type="context_link_updated",
        result=body.model_dump(),
    )
    return {"id": row[0] if row else link_id, **body.model_dump()}


@router.get("/context-links")
async def list_context_links(
    object_type: ObjectType | None = Query(None),
    object_id: str | None = Query(None),
    context_type: str | None = Query(None),
    context_id: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user_id: str = Depends(jwt_auth),
):
    where = ["user_id=?", "deleted_at IS NULL"]
    params: list[object] = [user_id]
    for field, value in (
        ("object_type", object_type),
        ("object_id", object_id),
        ("context_type", context_type),
        ("context_id", context_id),
    ):
        if value:
            where.append(f"{field}=?")
            params.append(value)
    params.append(limit)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, object_type, object_id, context_type, context_id, weight, source, "
            "source_event_id, rationale, created_at, updated_at "
            f"FROM stratum.context_links WHERE {' AND '.join(where)} "
            "ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    return [
        {
            "id": row[0],
            "object_type": row[1],
            "object_id": row[2],
            "context_type": row[3],
            "context_id": row[4],
            "weight": float(row[5]),
            "source": row[6],
            "source_event_id": row[7],
            "rationale": row[8],
            "created_at": str(row[9]),
            "updated_at": str(row[10]),
        }
        for row in rows
    ]


@router.delete("/context-links/{link_id}", status_code=204)
async def delete_context_link(link_id: str, user_id: str = Depends(jwt_auth)):
    with get_conn() as conn:
        row = conn.execute(
            "UPDATE stratum.context_links SET deleted_at=?, updated_at=? "
            "WHERE id=? AND user_id=? AND deleted_at IS NULL RETURNING id",
            (now_utc(), now_utc(), link_id, user_id),
        ).fetchone()
    if not row:
        raise HTTPException(404, "Context link not found")
    _record_model_event(
        user_id,
        object_type="context_link",
        object_id=link_id,
        event_type="context_link_deleted",
        result={},
    )


def _state_row(row):
    return {
        "id": row[0],
        "object_type": row[1],
        "object_id": row[2],
        "mastery": float(row[3]),
        "interest": float(row[4]),
        "certainty": float(row[5]),
        "relevance": float(row[6]),
        "source": row[7],
        "source_event_id": row[8],
        "created_at": str(row[9]),
        "updated_at": str(row[10]),
    }


def _record_model_event(
    user_id: str,
    *,
    object_type: str,
    object_id: str,
    event_type: str,
    result: dict,
) -> None:
    """Keep the model API available during a rolling 023 migration."""
    try:
        record_learning_event(
            user_id,
            object_type=object_type,
            object_id=object_id,
            event_type=event_type,
            result=result,
            source="personal-model",
        )
    except Exception:
        # The primary Personal Model mutation has already committed; the
        # additive ledger must not turn it into a 5xx on old deployments.
        pass


def _event_row(row):
    result = row[4]
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = {}
    return {
        "id": row[0],
        "object_type": row[1],
        "object_id": row[2],
        "event_type": row[3],
        "result": result or {},
        "source": row[5],
        "occurred_at": str(row[6]),
        "created_at": str(row[7]),
    }
