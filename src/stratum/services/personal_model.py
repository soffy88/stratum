"""Shared ownership and persistence helpers for the Personal Model.

The canonical PersonalState/Belief/ContextLink tables live in ``stratum`` so
the JWT-authenticated service layer can enforce user isolation.  The older
``cx.learning_*`` tables remain a separate, single-tenant compatibility
surface until their external database is migrated.
"""

from __future__ import annotations

import json
from typing import Any

from stratum.common import generate_ulid
from stratum.utils.user_id_hash import hash_user_id

OBJECT_TYPES = frozenset({"claim", "evidence", "concept", "substrate", "note", "highlight"})

# These are deliberately explicit: object_type is user input and must never be
# interpolated into SQL without first passing this allowlist.
_OBJECT_OWNERS = {
    "claim": ("knowledge_claims", "raw", True),
    "evidence": ("evidence", "raw_or_hash", False),
    "concept": ("concepts", "raw", True),
    "substrate": ("substrates", "raw_or_hash", False),
    "note": ("notes_sl", "raw", True),
    "highlight": ("highlights", "hash", False),
}


def assert_supported_object_type(object_type: str) -> None:
    if object_type not in OBJECT_TYPES:
        allowed = ", ".join(sorted(OBJECT_TYPES))
        raise ValueError(f"object_type must be one of: {allowed}")


def owned_object_exists(conn: Any, user_id: str, object_type: str, object_id: str) -> bool:
    """Check ownership of a cross-table object without introducing cross-DB FKs."""
    assert_supported_object_type(object_type)
    table, owner_mode, has_deleted_at = _OBJECT_OWNERS[object_type]
    if owner_mode == "raw":
        owner_sql = "user_id=?"
        params: tuple[Any, ...] = (object_id, user_id)
    elif owner_mode == "hash":
        owner_sql = "user_id=?"
        params = (object_id, hash_user_id(user_id))
    else:
        owner_sql = "user_id IN (?, ?)"
        params = (object_id, user_id, hash_user_id(user_id))
    deleted_sql = " AND deleted_at IS NULL" if has_deleted_at else ""
    row = conn.execute(
        f"SELECT id FROM stratum.{table} WHERE id=? AND {owner_sql}{deleted_sql} LIMIT 1",
        params,
    ).fetchone()
    return bool(row)


def upsert_personal_state(
    conn: Any,
    user_id: str,
    *,
    object_type: str,
    object_id: str,
    mastery: float,
    interest: float,
    certainty: float,
    relevance: float,
    source: str,
    source_event_id: str | None,
) -> str:
    """Upsert state and return its stable id.

    The database unique key (user, object type, object id) makes repeated
    Reader actions idempotent while retaining the latest explicit state.
    """
    assert_supported_object_type(object_type)
    conn.execute(
        "INSERT INTO stratum.personal_states "
        "(id, user_id, object_type, object_id, mastery, interest, certainty, relevance, "
        "source, source_event_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NOW(), NOW()) "
        "ON CONFLICT (user_id, object_type, object_id) DO UPDATE SET "
        "mastery=EXCLUDED.mastery, interest=EXCLUDED.interest, "
        "certainty=EXCLUDED.certainty, relevance=EXCLUDED.relevance, "
        "source=EXCLUDED.source, source_event_id=EXCLUDED.source_event_id, "
        "deleted_at=NULL, updated_at=NOW()",
        (
            _state_id(user_id, object_type, object_id),
            user_id,
            object_type,
            object_id,
            mastery,
            interest,
            certainty,
            relevance,
            source,
            source_event_id,
        ),
    )
    row = conn.execute(
        "SELECT id FROM stratum.personal_states WHERE user_id=? AND object_type=? AND object_id=?",
        (user_id, object_type, object_id),
    ).fetchone()
    if not row:
        raise RuntimeError("personal state upsert did not return an id")
    return str(row[0])


def personal_signals(user_id: str) -> dict[tuple[str, str], dict[str, float]]:
    """Load bounded ranking signals for one user.

    Missing migration 022 is treated as an empty personalization layer so
    retrieval remains backwards-compatible during rolling deployment.
    """
    from stratum.db import get_conn

    try:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT object_type, object_id, relevance, interest, certainty "
                "FROM stratum.personal_states WHERE user_id=? AND deleted_at IS NULL",
                (user_id,),
            ).fetchall()
            evidence_rows = []
            try:
                evidence_rows = conn.execute(
                    "SELECT e.substrate_id, MAX(ps.relevance), MAX(ps.interest), "
                    "MAX(ps.certainty) FROM stratum.personal_states ps "
                    "JOIN stratum.evidence e ON e.id=ps.object_id "
                    "WHERE ps.user_id=? AND ps.object_type='evidence' "
                    "AND ps.deleted_at IS NULL AND e.user_id IN (?, ?) "
                    "GROUP BY e.substrate_id",
                    (user_id, user_id, hash_user_id(user_id)),
                ).fetchall()
            except Exception:
                # Migration 020 may lag behind 022 during a rolling deploy.
                pass
    except Exception:
        return {}
    signals = {
        (row[0], row[1]): {
            "relevance": float(row[2] or 0.0),
            "interest": float(row[3] or 0.0),
            "certainty": float(row[4] or 0.0),
        }
        for row in rows
    }
    for row in evidence_rows:
        key = ("substrate", row[0])
        existing = signals.get(key, {})
        signals[key] = {
            field: max(existing.get(field, 0.0), float(value or 0.0))
            for field, value in zip(("relevance", "interest", "certainty"), row[1:])
        }
    return signals


def personalized_score(
    base_score: float,
    *,
    relevance: float = 0.0,
    interest: float = 0.0,
    certainty: float = 0.0,
) -> float:
    """Apply a small, explainable boost without overwhelming textual relevance."""
    signal = (
        0.60 * max(0.0, min(1.0, relevance))
        + 0.25 * max(0.0, min(1.0, interest))
        + 0.15 * max(0.0, min(1.0, certainty))
    )
    return round(min(1.0, max(0.0, base_score) + 0.15 * signal), 8)


def record_learning_event(
    user_id: str,
    *,
    object_type: str,
    object_id: str,
    event_type: str,
    result: dict[str, Any] | None = None,
    source: str = "api",
) -> str | None:
    """Append an auditable learning event; return None during old-schema rollout."""
    from stratum.db import get_conn

    event_id = generate_ulid()
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO stratum.learning_events "
                "(id, user_id, object_type, object_id, event_type, result, source, "
                "occurred_at, created_at) VALUES (?, ?, ?, ?, ?, ?::jsonb, ?, NOW(), NOW())",
                (
                    event_id,
                    user_id,
                    object_type,
                    object_id,
                    event_type,
                    json.dumps(result or {}, ensure_ascii=False),
                    source,
                ),
            )
    except Exception:
        return None
    return event_id


def _state_id(user_id: str, object_type: str, object_id: str) -> str:
    # The unique key is authoritative for retries; generated IDs keep the
    # canonical object identifier in the repository-wide ULID convention.
    return generate_ulid()
