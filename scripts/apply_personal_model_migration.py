#!/usr/bin/env python3
"""Apply or roll back an approved Personal Model migration report.

The companion planner is deliberately read-only.  This command is the only
write path and requires explicit flags:

* no flags: validate the report and print a write plan;
* ``--apply --confirm-apply``: apply candidates in one PostgreSQL transaction;
* ``--rollback-batch BATCH --confirm-rollback``: remove untouched imported
  state/belief/context rows and mark the ledger; LearningEvents are retained
  because their database contract is append-only.

Before inserting PersonalState, Belief, ContextLink, or LearningEvent rows it
checks that the mapped target object exists and is owned by the mapped user.
An ownership failure is recorded as ``blocked`` in the import ledger rather
than bypassing the check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


TARGET_OBJECT_TABLES = {
    "claim": "knowledge_claims",
    "evidence": "evidence",
    "concept": "concepts",
    "substrate": "substrates",
    "note": "notes_sl",
    "highlight": "highlights",
}
TARGET_TABLES = {
    "stratum.personal_states",
    "stratum.beliefs",
    "stratum.context_links",
    "stratum.learning_events",
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _payload_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not report.get("batch_id"):
        errors.append("missing batch_id")
    candidates = report.get("candidates")
    if not isinstance(candidates, list):
        return ["candidates must be an array"]
    seen: set[str] = set()
    for index, candidate in enumerate(candidates):
        prefix = f"candidates[{index}]"
        for key in (
            "id",
            "batch_id",
            "source_database",
            "source_table",
            "source_id",
            "target_table",
            "payload_hash",
            "payload_json",
        ):
            if key not in candidate:
                errors.append(f"{prefix} missing {key}")
        if candidate.get("id") in seen:
            errors.append(f"{prefix} duplicate id")
        seen.add(candidate.get("id"))
        if candidate.get("target_table") not in TARGET_TABLES:
            errors.append(f"{prefix} unsupported target_table")
        payload = candidate.get("payload_json")
        if not isinstance(payload, dict):
            errors.append(f"{prefix} payload_json must be an object")
        elif candidate.get("payload_hash") != _payload_hash(payload):
            errors.append(f"{prefix} payload_hash mismatch")
        if payload.get("user_id") != candidate.get("user_id"):
            errors.append(f"{prefix} candidate/payload user_id mismatch")
        if candidate.get("target_id") != payload.get("id"):
            errors.append(f"{prefix} candidate/payload target_id mismatch")
        if candidate.get("batch_id") != report.get("batch_id"):
            errors.append(f"{prefix} batch_id mismatch")
    return errors


def _hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode()).hexdigest()[:16]


def _object_owner_matches(cur, user_id: str, object_type: str, object_id: str) -> bool:
    table = TARGET_OBJECT_TABLES.get(object_type)
    if not table:
        return False
    cur.execute(f"SELECT user_id FROM stratum.{table} WHERE id=%s LIMIT 1", (object_id,))
    row = cur.fetchone()
    if not row:
        return False
    owner = row[0]
    return owner in {user_id, _hash_user_id(user_id)}


def _reference_for(candidate: dict[str, Any]) -> tuple[str, str] | None:
    payload = candidate["payload_json"]
    table = candidate["target_table"]
    if table == "stratum.beliefs":
        return "claim", str(payload["claim_id"])
    if table in {"stratum.personal_states", "stratum.context_links", "stratum.learning_events"}:
        return str(payload["object_type"]), str(payload["object_id"])
    return None


def _ledger_insert(cur, candidate: dict[str, Any]) -> str:
    cur.execute(
        """
        INSERT INTO stratum.personal_model_import_ledger
          (id,batch_id,source_database,source_table,source_id,target_table,target_id,
           user_id,status,payload_hash,payload_json,reason)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'candidate',%s,%s::jsonb,%s)
        ON CONFLICT (batch_id,source_database,source_table,source_id,target_table)
        DO NOTHING
        """,
        (
            candidate["id"],
            candidate["batch_id"],
            candidate["source_database"],
            candidate["source_table"],
            candidate["source_id"],
            candidate["target_table"],
            candidate.get("target_id"),
            candidate.get("user_id"),
            candidate["payload_hash"],
            json.dumps(candidate["payload_json"], ensure_ascii=False),
            candidate.get("reason"),
        ),
    )
    cur.execute(
        "SELECT status FROM stratum.personal_model_import_ledger WHERE id=%s",
        (candidate["id"],),
    )
    row = cur.fetchone()
    return str(row[0]) if row else "candidate"


def _update_ledger(cur, candidate_id: str, status: str, reason: str) -> None:
    cur.execute(
        "UPDATE stratum.personal_model_import_ledger "
        "SET status=%s, reason=%s, updated_at=NOW() WHERE id=%s",
        (status, reason, candidate_id),
    )


def _insert_canonical(cur, candidate: dict[str, Any]) -> bool:
    payload = candidate["payload_json"]
    table = candidate["target_table"]
    if table == "stratum.personal_states":
        cur.execute(
            """
            INSERT INTO stratum.personal_states
              (id,user_id,object_type,object_id,mastery,interest,certainty,relevance,
               source,source_event_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id,object_type,object_id) DO NOTHING
            RETURNING id
            """,
            (
                payload["id"],
                payload["user_id"],
                payload["object_type"],
                payload["object_id"],
                payload["mastery"],
                payload["interest"],
                payload["certainty"],
                payload["relevance"],
                payload["source"],
                payload.get("source_event_id"),
            ),
        )
    elif table == "stratum.beliefs":
        cur.execute(
            """
            INSERT INTO stratum.beliefs
              (id,user_id,claim_id,stance,confidence,source,source_event_id,rationale)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id,claim_id) DO NOTHING
            RETURNING id
            """,
            (
                payload["id"],
                payload["user_id"],
                payload["claim_id"],
                payload["stance"],
                payload["confidence"],
                payload["source"],
                payload.get("source_event_id"),
                payload.get("rationale"),
            ),
        )
    elif table == "stratum.context_links":
        cur.execute(
            """
            INSERT INTO stratum.context_links
              (id,user_id,object_type,object_id,context_type,context_id,weight,source,
               source_event_id,rationale)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (user_id,object_type,object_id,context_type,context_id) DO NOTHING
            RETURNING id
            """,
            (
                payload["id"],
                payload["user_id"],
                payload["object_type"],
                payload["object_id"],
                payload["context_type"],
                payload["context_id"],
                payload["weight"],
                payload["source"],
                payload.get("source_event_id"),
                payload.get("rationale"),
            ),
        )
    else:
        cur.execute(
            """
            INSERT INTO stratum.learning_events
              (id,user_id,object_type,object_id,event_type,result,source,occurred_at)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            """,
            (
                payload["id"],
                payload["user_id"],
                payload["object_type"],
                payload["object_id"],
                payload["event_type"],
                json.dumps(payload.get("result", {}), ensure_ascii=False),
                payload["source"],
                payload.get("occurred_at"),
            ),
        )
    return cur.fetchone() is not None


def apply_report(conn, report: dict[str, Any]) -> dict[str, int]:
    errors = validate_report(report)
    if errors:
        raise ValueError("invalid migration report: " + "; ".join(errors[:5]))
    stats = {"applied": 0, "skipped_conflict": 0, "blocked": 0, "already_done": 0}
    with conn:
        with conn.cursor() as cur:
            for candidate in report["candidates"]:
                current_status = _ledger_insert(cur, candidate)
                if current_status in {"applied", "skipped_conflict"}:
                    stats["already_done"] += 1
                    continue
                reference = _reference_for(candidate)
                if reference and not _object_owner_matches(
                    cur, str(candidate["user_id"]), reference[0], reference[1]
                ):
                    _update_ledger(
                        cur, candidate["id"], "blocked", "target object missing or owner mismatch"
                    )
                    stats["blocked"] += 1
                    continue
                inserted = _insert_canonical(cur, candidate)
                status = "applied" if inserted else "skipped_conflict"
                _update_ledger(cur, candidate["id"], status, status)
                stats[status] += 1
    return stats


def rollback_batch(conn, batch_id: str) -> dict[str, int]:
    stats = {"rolled_back": 0, "rollback_blocked": 0, "events_retained": 0}
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,target_table,target_id FROM stratum.personal_model_import_ledger "
                "WHERE batch_id=%s AND status='applied' ORDER BY created_at DESC",
                (batch_id,),
            )
            rows = cur.fetchall()
            for ledger_id, target_table, target_id in rows:
                if target_table == "stratum.learning_events":
                    _update_ledger(
                        cur, ledger_id, "rolled_back", "event retained by append-only contract"
                    )
                    stats["events_retained"] += 1
                    continue
                if target_table not in TARGET_TABLES:
                    _update_ledger(cur, ledger_id, "rollback_blocked", "unsupported target table")
                    stats["rollback_blocked"] += 1
                    continue
                cur.execute(
                    f"DELETE FROM {target_table} "
                    "WHERE id=%s AND source='imported' AND created_at=updated_at "
                    "RETURNING id",
                    (target_id,),
                )
                deleted = cur.fetchone() is not None
                status = "rolled_back" if deleted else "rollback_blocked"
                reason = (
                    "imported row removed"
                    if deleted
                    else "row changed, missing, or conflict was not owned"
                )
                _update_ledger(cur, ledger_id, status, reason)
                stats[status] += 1
    return stats


def _connect(dsn: str | None):
    import psycopg2

    if dsn:
        return psycopg2.connect(dsn)
    return psycopg2.connect(
        host=os.getenv("STRATUM_PG_HOST", "127.0.0.1"),
        port=int(os.getenv("STRATUM_PG_PORT", "5435")),
        user=os.getenv("STRATUM_PG_USER", "aii"),
        password=os.getenv("STRATUM_PG_PASSWORD", ""),
        dbname=os.getenv("STRATUM_PG_DB", "aii_kg"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--dsn", default=os.getenv("STRATUM_DATABASE_DSN"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-apply", action="store_true")
    parser.add_argument("--rollback-batch")
    parser.add_argument("--confirm-rollback", action="store_true")
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    errors = validate_report(report)
    if errors:
        parser.error("invalid report: " + "; ".join(errors[:5]))
    if args.rollback_batch and args.rollback_batch != report.get("batch_id"):
        parser.error("--rollback-batch must match the report batch_id")
    if not args.apply and not args.rollback_batch:
        print(
            json.dumps(
                {"mode": "dry-run", "batch_id": report["batch_id"], **report["summary"]},
                ensure_ascii=False,
            )
        )
        return 0
    if args.apply and not args.confirm_apply:
        parser.error("--apply requires --confirm-apply")
    if args.rollback_batch and not args.confirm_rollback:
        parser.error("--rollback-batch requires --confirm-rollback")
    conn = _connect(args.dsn)
    try:
        result = (
            rollback_batch(conn, args.rollback_batch)
            if args.rollback_batch
            else apply_report(conn, report)
        )
    finally:
        conn.close()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
