"""Highlight CRUD — highlights are exported as W3C-style Evidence objects."""

import hashlib
import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from stratum.common import generate_ulid, jwt_auth
from stratum.db import get_conn
from stratum.utils.user_id_hash import hash_user_id

router = APIRouter(prefix="/api/v1/highlights", tags=["highlights"])
log = logging.getLogger(__name__)


class HighlightCreate(BaseModel):
    substrate_id: str
    color: str = "yellow"
    text: str
    note: Optional[str] = None
    location_json: dict[str, Any] = Field(default_factory=dict)  # legacy locator
    locator: Optional[dict[str, Any]] = None  # W3C Target/Selector-compatible
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


def _quote_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _w3c_locator(
    substrate_id: str, text: str, location: dict[str, Any], supplied: dict[str, Any] | None
) -> dict[str, Any]:
    """Build a small W3C Web Annotation Target using standard selectors.

    ``location_json`` remains a lossless compatibility field for PDF/EPUB
    renderers.  Text quote/position selectors are portable to other annotation
    clients; renderer-specific rectangles/CFIs stay in the legacy field.
    """
    if supplied:
        return supplied
    selectors: list[dict[str, Any]] = [
        {"type": "TextQuoteSelector", "exact": text},
    ]
    start, end = location.get("start"), location.get("end")
    if isinstance(start, int) and isinstance(end, int) and end >= start:
        selectors.append({"type": "TextPositionSelector", "start": start, "end": end})
    return {"source": f"substrate://{substrate_id}", "selector": selectors}


@router.post("", status_code=201)
async def create_highlight(body: HighlightCreate, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    hid = generate_ulid()
    with get_conn() as conn:
        substrate = conn.execute(
            "SELECT id FROM substrates WHERE id=? AND user_id IN (?, ?)",
            (body.substrate_id, user_id, uh),
        ).fetchone()
        if not substrate:
            raise HTTPException(404, "Substrate not found")
        conn.execute(
            "INSERT INTO highlights "
            "(id, user_id, substrate_id, color, text, note, location_json, confidence, quote_hash, locator_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                hid,
                uh,
                body.substrate_id,
                body.color,
                body.text,
                body.note,
                json.dumps(body.location_json),
                body.confidence,
                _quote_hash(body.text),
                json.dumps(
                    _w3c_locator(body.substrate_id, body.text, body.location_json, body.locator)
                ),
            ),
        )
        try:
            locator_json = json.dumps(
                _w3c_locator(body.substrate_id, body.text, body.location_json, body.locator)
            )
            conn.execute(
                "INSERT INTO stratum.evidence "
                "(id, user_id, source_highlight_id, substrate_id, quote, quote_hash, "
                "locator_json, confidence, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,NOW(),NOW()) "
                "ON CONFLICT (id) DO UPDATE SET quote=EXCLUDED.quote, "
                "quote_hash=EXCLUDED.quote_hash, locator_json=EXCLUDED.locator_json, "
                "confidence=EXCLUDED.confidence, updated_at=NOW()",
                (
                    hid,
                    uh,
                    hid,
                    body.substrate_id,
                    body.text,
                    _quote_hash(body.text),
                    locator_json,
                    body.confidence,
                ),
            )
        except Exception:
            # Keep older installations usable before migration 020 is applied.
            pass
        try:
            from stratum.services.personal_model import upsert_personal_state

            # A user highlight is the first explicit Reader action that feeds
            # the Personal Model: the evidence is relevant to this user.
            upsert_personal_state(
                conn,
                user_id,
                object_type="evidence",
                object_id=hid,
                mastery=0.0,
                interest=0.0,
                certainty=1.0,
                relevance=1.0,
                source="explicit",
                source_event_id=hid,
            )
        except Exception as exc:
            # Migration 022 is deployment-gated; preserve highlight writes on
            # older installations while making the missing bridge observable.
            log.warning("personal state bridge unavailable for highlight %s: %s", hid, exc)
        try:
            from stratum.services.personal_model import record_learning_event

            record_learning_event(
                user_id,
                object_type="evidence",
                object_id=hid,
                event_type="highlight_created",
                result={"substrate_id": body.substrate_id, "confidence": body.confidence},
                source="reader",
            )
        except Exception as exc:
            log.warning("learning event bridge unavailable for highlight %s: %s", hid, exc)
        row = conn.execute(
            "SELECT id, color, text, note, substrate_id, location_json, confidence, quote_hash, "
            "locator_json, created_at "
            "FROM highlights WHERE id=?",
            (hid,),
        ).fetchone()
    if not row:
        raise HTTPException(500, "Failed to create highlight")
    from stratum.changefeed import emit_event

    await emit_event(
        uh, "highlight_create", {"highlight_id": hid, "substrate_id": body.substrate_id}
    )
    return {
        "id": row[0],
        "color": row[1],
        "text": row[2],
        "note": row[3],
        "substrate_id": row[4],
        "location_json": json.loads(row[5] or "{}"),
        "confidence": float(row[6] if row[6] is not None else 1.0),
        "quote_hash": row[7],
        "locator": json.loads(row[8] or "{}"),
        "created_at": str(row[9]),
    }


@router.get("")
async def list_highlights(substrate_id: Optional[str] = None, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        if substrate_id:
            rows = conn.execute(
                """
                SELECT h.id, h.color, h.text, h.note, h.substrate_id, s.title, h.location_json,
                       h.confidence, h.quote_hash, h.locator_json, h.created_at
                FROM highlights h
                LEFT JOIN substrates s ON h.substrate_id = s.id
                WHERE h.user_id = ? AND h.substrate_id = ?
                ORDER BY h.created_at DESC
                """,
                (uh, substrate_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT h.id, h.color, h.text, h.note, h.substrate_id, s.title, h.location_json,
                       h.confidence, h.quote_hash, h.locator_json, h.created_at
                FROM highlights h
                LEFT JOIN substrates s ON h.substrate_id = s.id
                WHERE h.user_id = ?
                ORDER BY h.created_at DESC
                """,
                (uh,),
            ).fetchall()
    return [
        {
            "id": r[0],
            "color": r[1],
            "text": r[2],
            "note": r[3],
            "substrate_id": r[4],
            "substrate_title": r[5],
            "location_json": json.loads(r[6] or "{}"),
            "confidence": float(r[7] if r[7] is not None else 1.0),
            "quote_hash": r[8],
            "locator": json.loads(r[9] or "{}"),
            "created_at": str(r[10]),
        }
        for r in rows
    ]


@router.patch("/{highlight_id}")
async def update_highlight(highlight_id: str, body: dict, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        h = conn.execute("SELECT user_id FROM highlights WHERE id=?", (highlight_id,)).fetchone()
        if not h or h[0] != uh:
            raise HTTPException(404, "Highlight not found")
        updates = {k: v for k, v in body.items() if k in ("color", "note")}
        if updates:
            sets = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE highlights SET {sets} WHERE id=?", (*updates.values(), highlight_id)
            )
    return {"ok": True}


@router.delete("/{highlight_id}", status_code=204)
async def delete_highlight(highlight_id: str, user_id: str = Depends(jwt_auth)):
    uh = hash_user_id(user_id)
    with get_conn() as conn:
        h = conn.execute("SELECT user_id FROM highlights WHERE id=?", (highlight_id,)).fetchone()
        if not h or h[0] != uh:
            raise HTTPException(404, "Highlight not found")
        conn.execute("DELETE FROM highlights WHERE id=?", (highlight_id,))
        try:
            conn.execute(
                "DELETE FROM stratum.evidence WHERE source_highlight_id=?",
                (highlight_id,),
            )
            conn.execute(
                "UPDATE stratum.personal_states SET deleted_at=NOW(), updated_at=NOW() "
                "WHERE user_id=? AND object_type='evidence' AND object_id=?",
                (user_id, highlight_id),
            )
        except Exception:
            # Older installations may not have migrations 020/022 yet.
            pass
    from stratum.changefeed import emit_event

    await emit_event(uh, "highlight_delete", {"highlight_id": highlight_id})
