#!/usr/bin/env python3
"""Build a reviewed, dry-run plan for legacy C/B assets → Stratum Personal Model.

This command never guesses a user or a canonical object.  It accepts an
explicit mapping manifest and produces JSON candidates plus parameterized SQL
statements.  The SQL is intentionally not executed by this tool; deployment
can review the report, run the 026 ledger migration, then apply the approved
statements in a controlled transaction.

Manifest shape (all keys are stringified source IDs)::

    {
      "profile_users": {"12": "user-id"},
      "learning_progress": {
        "55": {"user_id": "user-id", "object_type": "concept", "object_id": "..."}
      },
      "positional_beliefs": {
        "legacy-ku-1": {"user_id": "user-id", "claim_id": "claim-id", "stance": "agree"}
      },
      "decision_context_links": {
        "7": {"user_id": "user-id", "object_type": "claim", "object_id": "...",
              "context_type": "project", "context_id": "project-id"}
      }
    }

Use ``--input`` with a reviewed JSON snapshot for offline planning, or omit it
to read ``aii_context`` and the legacy refined database read-only.  ``--emit-sql``
adds executable parameterized statements to the JSON report; it still performs
no write.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


OBJECT_TYPES = {"claim", "evidence", "concept", "substrate", "note", "highlight"}
STANCE_TYPES = {"agree", "disagree", "uncertain", "conditional"}
CONTEXT_TYPES = {"project", "goal", "tag", "area"}
MANIFEST_KEYS = {
    "profile_users",
    "learning_progress",
    "positional_beliefs",
    "decision_context_links",
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def _hash_payload(payload: dict[str, Any]) -> str:
    body = json.dumps(_jsonable(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def _stable_id(prefix: str, source_table: str, source_id: str, payload_hash: str) -> str:
    key = f"{prefix}|{source_table}|{source_id}|{payload_hash}"
    return f"import_{hashlib.sha256(key.encode()).hexdigest()[:24]}"


def _blocked(source_table: str, source_id: Any, reason: str, detail: Any = None) -> dict[str, Any]:
    result = {
        "source_table": source_table,
        "source_id": str(source_id),
        "status": "blocked",
        "reason": reason,
    }
    if detail is not None:
        result["detail"] = _jsonable(detail)
    return result


def _candidate(
    *,
    batch_id: str,
    source_database: str,
    source_table: str,
    source_id: Any,
    target_table: str,
    user_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    payload = _jsonable(payload)
    payload_hash = _hash_payload(payload)
    target_id = str(payload.get("id")) if payload.get("id") else None
    ledger_id = _stable_id("ledger", f"{batch_id}:{source_table}", str(source_id), payload_hash)
    return {
        "id": ledger_id,
        "batch_id": batch_id,
        "source_database": source_database,
        "source_table": source_table,
        "source_id": str(source_id),
        "target_table": target_table,
        "target_id": target_id,
        "user_id": user_id,
        "status": "candidate",
        "payload_hash": payload_hash,
        "payload_json": payload,
        "reason": "explicit mapping manifest; review before apply",
    }


def _validate_manifest(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    unknown = sorted(set(manifest) - MANIFEST_KEYS)
    if unknown:
        errors.append({"reason": "unknown_manifest_keys", "detail": unknown})
    for key in MANIFEST_KEYS:
        if key in manifest and not isinstance(manifest[key], dict):
            errors.append({"reason": "manifest_section_must_be_object", "section": key})
    return errors


def _user_for_profile(profile_users: dict[str, Any], profile_id: Any) -> str | None:
    value = profile_users.get(str(profile_id))
    return str(value) if value not in (None, "") else None


def _bounded(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _progress_candidates(
    *, batch_id: str, snapshot: dict[str, list[dict[str, Any]]], manifest: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    profile_users = manifest.get("profile_users", {})
    progress_map = manifest.get("learning_progress", {})

    for row in snapshot.get("learning_progress", []):
        point_id = str(row.get("point_id", ""))
        profile_user = _user_for_profile(profile_users, row.get("profile_id"))
        mapping = progress_map.get(point_id)
        if not profile_user:
            blocked.append(
                _blocked("cx.learning_progress", point_id, "missing_profile_user_mapping")
            )
            continue
        if not isinstance(mapping, dict):
            blocked.append(
                _blocked("cx.learning_progress", point_id, "missing_canonical_object_mapping")
            )
            continue
        user_id = str(mapping.get("user_id") or profile_user)
        if user_id != profile_user:
            blocked.append(
                _blocked(
                    "cx.learning_progress",
                    point_id,
                    "profile_user_mapping_conflict",
                    {"profile_user": profile_user, "point_user": user_id},
                )
            )
            continue
        object_type = mapping.get("object_type")
        object_id = mapping.get("object_id")
        if object_type not in OBJECT_TYPES or not object_id:
            blocked.append(
                _blocked("cx.learning_progress", point_id, "invalid_canonical_object_mapping")
            )
            continue
        state_payload = {
            "id": _stable_id("state", "cx.learning_progress", point_id, point_id),
            "user_id": user_id,
            "object_type": object_type,
            "object_id": str(object_id),
            "mastery": _bounded(
                row.get("mastery_score")
                if row.get("mastery_score") is not None
                else (1.0 if row.get("grade") == "verified" else 0.0),
                0.0,
            ),
            "interest": 0.0,
            "certainty": 1.0 if row.get("grade") == "verified" else 0.5,
            "relevance": 0.0,
            "source": "imported",
            "source_event_id": None,
        }
        state = _candidate(
            batch_id=batch_id,
            source_database="aii_context",
            source_table="cx.learning_progress",
            source_id=point_id,
            target_table="stratum.personal_states",
            user_id=user_id,
            payload=state_payload,
        )
        candidates.append(state)

        attempts = _json_value(row.get("attempts"), [])
        if not isinstance(attempts, list):
            blocked.append(_blocked("cx.learning_progress", point_id, "attempts_is_not_json_array"))
            continue
        for index, attempt in enumerate(attempts):
            result = attempt if isinstance(attempt, dict) else {"value": attempt}
            event_payload = {
                "id": _stable_id("event", "cx.learning_progress", f"{point_id}:{index}", point_id),
                "user_id": user_id,
                "object_type": object_type,
                "object_id": str(object_id),
                "event_type": "legacy_learning_attempt",
                "result": result,
                "source": "legacy-cx",
                "occurred_at": result.get("occurred_at")
                or result.get("timestamp")
                or row.get("last_tested_at")
                or row.get("created_at"),
            }
            candidates.append(
                _candidate(
                    batch_id=batch_id,
                    source_database="aii_context",
                    source_table="cx.learning_progress.attempts",
                    source_id=f"{point_id}:{index}",
                    target_table="stratum.learning_events",
                    user_id=user_id,
                    payload=event_payload,
                )
            )
    return candidates, blocked


def build_plan(
    snapshot: dict[str, list[dict[str, Any]]], manifest: dict[str, Any], batch_id: str
) -> dict[str, Any]:
    """Build a deterministic plan from exported rows and explicit mappings."""
    blocked = _validate_manifest(manifest)
    candidates, progress_blocked = _progress_candidates(
        batch_id=batch_id, snapshot=snapshot, manifest=manifest
    )
    blocked.extend(progress_blocked)

    belief_map = manifest.get("positional_beliefs", {})
    for row in snapshot.get("positional_knowledge_units", []):
        ku_id = str(row.get("ku_id", ""))
        mapping = belief_map.get(ku_id)
        if not isinstance(mapping, dict):
            blocked.append(_blocked("aii.ku_onto", ku_id, "missing_belief_mapping"))
            continue
        confidence = _bounded(mapping.get("confidence", 0.5), -1.0)
        if (
            mapping.get("stance") not in STANCE_TYPES
            or not mapping.get("claim_id")
            or not mapping.get("user_id")
            or confidence < 0
        ):
            blocked.append(_blocked("aii.ku_onto", ku_id, "invalid_belief_mapping"))
            continue
        payload = {
            "id": _stable_id("belief", "aii.ku_onto", ku_id, ku_id),
            "user_id": str(mapping["user_id"]),
            "claim_id": str(mapping["claim_id"]),
            "stance": mapping["stance"],
            "confidence": confidence,
            "source": "imported",
            "source_event_id": None,
            "rationale": row.get("natural_text") or row.get("natural_text_zh"),
        }
        candidates.append(
            _candidate(
                batch_id=batch_id,
                source_database="aii_refined",
                source_table="aii.ku_onto",
                source_id=ku_id,
                target_table="stratum.beliefs",
                user_id=str(mapping["user_id"]),
                payload=payload,
            )
        )

    link_map = manifest.get("decision_context_links", {})
    for row in snapshot.get("decision_cases", []):
        case_id = str(row.get("case_id", ""))
        mapping = link_map.get(case_id)
        if not isinstance(mapping, dict):
            blocked.append(_blocked("cx.decision_case", case_id, "missing_context_link_mapping"))
            continue
        weight = _bounded(mapping.get("weight", 1.0), -1.0)
        if (
            mapping.get("object_type") not in OBJECT_TYPES
            or mapping.get("context_type") not in CONTEXT_TYPES
            or not mapping.get("object_id")
            or not mapping.get("context_id")
            or not mapping.get("user_id")
            or weight < 0
        ):
            blocked.append(_blocked("cx.decision_case", case_id, "invalid_context_link_mapping"))
            continue
        payload = {
            "id": _stable_id("link", "cx.decision_case", case_id, case_id),
            "user_id": str(mapping["user_id"]),
            "object_type": mapping["object_type"],
            "object_id": str(mapping["object_id"]),
            "context_type": mapping["context_type"],
            "context_id": str(mapping["context_id"]),
            "weight": weight,
            "source": "imported",
            "source_event_id": None,
            "rationale": row.get("lesson") or row.get("reuse_conditions"),
        }
        candidates.append(
            _candidate(
                batch_id=batch_id,
                source_database="aii_context",
                source_table="cx.decision_case",
                source_id=case_id,
                target_table="stratum.context_links",
                user_id=str(mapping["user_id"]),
                payload=payload,
            )
        )

    for row in snapshot.get("learning_stuck", []):
        blocked.append(
            _blocked(
                "cx.learning_stuck",
                row.get("stuck_id", ""),
                "no_canonical_personal_model_object_mapping",
            )
        )

    report = {
        "batch_id": batch_id,
        "status": "blocked" if blocked else "ready_for_review",
        "summary": {
            "candidates": len(candidates),
            "blocked": len(blocked),
            "personal_states": sum(
                c["target_table"] == "stratum.personal_states" for c in candidates
            ),
            "beliefs": sum(c["target_table"] == "stratum.beliefs" for c in candidates),
            "context_links": sum(c["target_table"] == "stratum.context_links" for c in candidates),
            "learning_events": sum(
                c["target_table"] == "stratum.learning_events" for c in candidates
            ),
        },
        "candidates": candidates,
        "blocked": blocked,
    }
    return report


def parameterized_sql(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return one ledger statement and one canonical insert as SQL + params."""
    payload = candidate["payload_json"]
    ledger_params = dict(candidate)
    ledger_params["payload_json"] = json.dumps(payload, ensure_ascii=False)
    canonical_params = dict(payload)
    for key in ("result",):
        if isinstance(canonical_params.get(key), (dict, list)):
            canonical_params[key] = json.dumps(canonical_params[key], ensure_ascii=False)
    ledger_sql = (
        "INSERT INTO stratum.personal_model_import_ledger "
        "(id,batch_id,source_database,source_table,source_id,target_table,target_id,user_id,status,payload_hash,payload_json,reason) "
        "VALUES (%(id)s,%(batch_id)s,%(source_database)s,%(source_table)s,%(source_id)s,%(target_table)s,%(target_id)s,%(user_id)s,%(status)s,%(payload_hash)s,%(payload_json)s::jsonb,%(reason)s) "
        "ON CONFLICT (batch_id,source_database,source_table,source_id,target_table) DO NOTHING"
    )
    table = candidate["target_table"]
    if table == "stratum.personal_states":
        canonical_sql = (
            "INSERT INTO stratum.personal_states "
            "(id,user_id,object_type,object_id,mastery,interest,certainty,relevance,source,source_event_id) "
            "VALUES (%(id)s,%(user_id)s,%(object_type)s,%(object_id)s,%(mastery)s,%(interest)s,%(certainty)s,%(relevance)s,%(source)s,%(source_event_id)s) "
            "ON CONFLICT (user_id,object_type,object_id) DO NOTHING"
        )
    elif table == "stratum.beliefs":
        canonical_sql = (
            "INSERT INTO stratum.beliefs "
            "(id,user_id,claim_id,stance,confidence,source,source_event_id,rationale) "
            "VALUES (%(id)s,%(user_id)s,%(claim_id)s,%(stance)s,%(confidence)s,%(source)s,%(source_event_id)s,%(rationale)s) "
            "ON CONFLICT (user_id,claim_id) DO NOTHING"
        )
    elif table == "stratum.context_links":
        canonical_sql = (
            "INSERT INTO stratum.context_links "
            "(id,user_id,object_type,object_id,context_type,context_id,weight,source,source_event_id,rationale) "
            "VALUES (%(id)s,%(user_id)s,%(object_type)s,%(object_id)s,%(context_type)s,%(context_id)s,%(weight)s,%(source)s,%(source_event_id)s,%(rationale)s) "
            "ON CONFLICT (user_id,object_type,object_id,context_type,context_id) DO NOTHING"
        )
    elif table == "stratum.learning_events":
        canonical_sql = (
            "INSERT INTO stratum.learning_events "
            "(id,user_id,object_type,object_id,event_type,result,source,occurred_at) "
            "VALUES (%(id)s,%(user_id)s,%(object_type)s,%(object_id)s,%(event_type)s,%(result)s::jsonb,%(source)s,%(occurred_at)s) "
            "ON CONFLICT (id) DO NOTHING"
        )
    else:  # pragma: no cover - candidates are built from a closed target allowlist
        raise ValueError(f"unsupported target table: {table}")
    return {
        "ledger": {"sql": ledger_sql, "params": ledger_params},
        "canonical": {"sql": canonical_sql, "params": canonical_params},
    }


def _load_snapshot(path: Path) -> dict[str, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("snapshot must be a JSON object")
    return {
        str(key): [dict(row) for row in value]
        for key, value in data.items()
        if isinstance(value, list)
    }


def _connect(dsn: str):
    import psycopg2
    from psycopg2.extras import RealDictCursor

    return psycopg2.connect(dsn, cursor_factory=RealDictCursor)


def _rows(conn, query: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(query)
        return [dict(row) for row in cur.fetchall()]


def _load_live_snapshot(context_dsn: str, refined_dsn: str) -> dict[str, list[dict[str, Any]]]:
    context = _connect(context_dsn)
    try:
        snapshot = {
            "learning_profiles": _rows(context, "SELECT * FROM cx.learning_profile"),
            "learning_progress": _rows(context, "SELECT * FROM cx.learning_progress"),
            "learning_stuck": _rows(context, "SELECT * FROM cx.learning_stuck"),
            "decision_cases": _rows(context, "SELECT * FROM cx.decision_case"),
        }
    finally:
        context.close()
    refined = _connect(refined_dsn)
    try:
        try:
            snapshot["positional_knowledge_units"] = _rows(
                refined,
                "SELECT * FROM aii.ku_onto WHERE knowledge_type = 'positional'",
            )
        except Exception:
            snapshot["positional_knowledge_units"] = _rows(
                refined,
                "SELECT * FROM rf.refined_ku WHERE ku_type = 'positional'",
            )
    finally:
        refined.close()
    return snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--input", type=Path, help="Reviewed JSON snapshot; omit to read source DBs"
    )
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--emit-sql", action="store_true")
    parser.add_argument(
        "--context-dsn",
        default=os.getenv("AII_CONTEXT_DATABASE_DSN")
        or os.getenv(
            "CONTEXT_DATABASE_URL", "postgresql://aii:***REMOVED***@localhost:5436/aii_context"
        ),
    )
    parser.add_argument(
        "--refined-dsn",
        default=os.getenv(
            "REFINED_DATABASE_URL", "postgresql://aii:***REMOVED***@localhost:5436/aii_refined"
        ),
    )
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        parser.error("manifest must be a JSON object")
    if args.input:
        snapshot = _load_snapshot(args.input)
    else:
        snapshot = _load_live_snapshot(args.context_dsn, args.refined_dsn)
    batch_id = args.batch_id or datetime.now(timezone.utc).strftime(
        "cx-personal-model-%Y%m%dT%H%M%SZ"
    )
    report = build_plan(snapshot, manifest, batch_id)
    if args.emit_sql:
        report["parameterized_sql"] = [
            parameterized_sql(candidate) for candidate in report["candidates"]
        ]
    print(json.dumps(_jsonable(report), ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
