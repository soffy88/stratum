#!/usr/bin/env python3
"""Apply or roll back an approved legacy Concept/Relation merge report.

This is a guarded deployment command.  It refuses to invent canonical IDs or
relation endpoints.  An approved report must carry:

* concept: ``target_id`` + ``user_id``;
* relation: ``target_id`` + ``user_id`` + ``source_concept_id`` +
  ``target_concept_id``.

Without ``--apply --confirm-apply`` the command only validates and summarizes.
Rollback deletes only relations inserted by this batch; concepts are marked
``rollback_blocked`` because the canonical concept table has no source-owner
column and a shared concept may have acquired new references after import.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


TARGET_TABLES = {"stratum.concepts", "stratum.concept_relations"}


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
        required = (
            "id",
            "batch_id",
            "source_kind",
            "source_table",
            "source_id",
            "candidate_group_id",
            "target_table",
            "payload_hash",
            "payload_json",
        )
        for key in required:
            if key not in candidate:
                errors.append(f"{prefix} missing {key}")
        if candidate.get("id") in seen:
            errors.append(f"{prefix} duplicate id")
        seen.add(candidate.get("id"))
        if candidate.get("target_table") not in TARGET_TABLES:
            errors.append(f"{prefix} unsupported target_table")
        if candidate.get("batch_id") != report.get("batch_id"):
            errors.append(f"{prefix} batch_id mismatch")
        payload = candidate.get("payload_json")
        if not isinstance(payload, dict):
            errors.append(f"{prefix} payload_json must be an object")
        elif candidate.get("payload_hash") != _payload_hash(payload):
            errors.append(f"{prefix} payload_hash mismatch")
        if candidate.get("review_status") == "approved":
            if not candidate.get("target_id") or not candidate.get("user_id"):
                errors.append(f"{prefix} approved candidate missing target_id/user_id")
            if candidate.get("source_kind") == "relation" and (
                not payload.get("source_concept_id") or not payload.get("target_concept_id")
            ):
                errors.append(f"{prefix} approved relation missing canonical endpoints")
    return errors


def _owner_matches(cur, user_id: str, concept_id: str) -> bool:
    cur.execute("SELECT user_id FROM stratum.concepts WHERE id=%s", (concept_id,))
    row = cur.fetchone()
    if not row:
        return False
    owner = row[0]
    return owner in {user_id, hashlib.sha256(user_id.encode()).hexdigest()[:16]}


def _ledger_insert(cur, candidate: dict[str, Any]) -> str:
    cur.execute(
        """
        INSERT INTO stratum.legacy_knowledge_merge_ledger
          (id,batch_id,source_kind,source_table,source_id,candidate_group_id,
           target_table,target_id,user_id,status,payload_hash,payload_json,reason)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)
        ON CONFLICT (batch_id,source_kind,source_table,source_id) DO NOTHING
        """,
        (
            candidate["id"],
            candidate["batch_id"],
            candidate["source_kind"],
            candidate["source_table"],
            candidate["source_id"],
            candidate["candidate_group_id"],
            candidate["target_table"],
            candidate.get("target_id"),
            candidate.get("user_id"),
            "approved" if candidate.get("review_status") == "approved" else "candidate",
            candidate["payload_hash"],
            json.dumps(candidate["payload_json"], ensure_ascii=False),
            candidate.get("reason"),
        ),
    )
    cur.execute(
        "SELECT status FROM stratum.legacy_knowledge_merge_ledger WHERE id=%s", (candidate["id"],)
    )
    row = cur.fetchone()
    return str(row[0]) if row else "candidate"


def _update_ledger(cur, candidate_id: str, status: str, reason: str) -> None:
    cur.execute(
        "UPDATE stratum.legacy_knowledge_merge_ledger SET status=%s,reason=%s,updated_at=NOW() WHERE id=%s",
        (status, reason, candidate_id),
    )


def _apply_concept(cur, candidate: dict[str, Any]) -> str:
    payload = candidate["payload_json"]
    target_id = str(candidate["target_id"])
    user_id = str(candidate["user_id"])
    cur.execute("SELECT user_id FROM stratum.concepts WHERE id=%s", (target_id,))
    existing = cur.fetchone()
    if existing:
        if not _owner_matches(cur, user_id, target_id):
            return "blocked"
        return "skipped_conflict"
    cur.execute(
        """
        INSERT INTO stratum.concepts
          (id,user_id,name,type,aliases,substrate_refs,related_concept_ids,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
        ON CONFLICT (id) DO NOTHING
        """,
        (
            target_id,
            user_id,
            payload["canonical_name"],
            payload.get("type") or "concept",
            payload.get("aliases") or [],
            [],
            [],
        ),
    )
    return "applied"


def _apply_relation(cur, candidate: dict[str, Any]) -> str:
    payload = candidate["payload_json"]
    user_id = str(candidate["user_id"])
    source_id = str(payload["source_concept_id"])
    target_id = str(payload["target_concept_id"])
    if (
        source_id == target_id
        or not _owner_matches(cur, user_id, source_id)
        or not _owner_matches(cur, user_id, target_id)
    ):
        return "blocked"
    cur.execute(
        """
        INSERT INTO stratum.concept_relations
          (id,user_id,source_concept_id,target_concept_id,relation_type,confidence,
           rationale,evidence_ids,created_at,updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
        ON CONFLICT (user_id,source_concept_id,target_concept_id,relation_type) DO NOTHING
        RETURNING id
        """,
        (
            str(candidate["target_id"]),
            user_id,
            source_id,
            target_id,
            payload["relation_type"],
            0.5,
            payload.get("rationale"),
            [],
        ),
    )
    return "applied" if cur.fetchone() else "skipped_conflict"


def apply_report(conn, report: dict[str, Any]) -> dict[str, int]:
    errors = validate_report(report)
    if errors:
        raise ValueError("invalid merge report: " + "; ".join(errors[:5]))
    stats = {"applied": 0, "skipped_conflict": 0, "blocked": 0, "already_done": 0}
    with conn:
        with conn.cursor() as cur:
            for candidate in report["candidates"]:
                current = _ledger_insert(cur, candidate)
                if current in {"applied", "skipped_conflict"}:
                    stats["already_done"] += 1
                    continue
                if candidate.get("review_status") != "approved":
                    _update_ledger(cur, candidate["id"], "blocked", "approval manifest required")
                    stats["blocked"] += 1
                    continue
                result = (
                    _apply_concept(cur, candidate)
                    if candidate["source_kind"] == "concept"
                    else _apply_relation(cur, candidate)
                )
                status = "applied" if result == "applied" else result
                _update_ledger(cur, candidate["id"], status, status)
                stats[status] += 1
    return stats


def rollback_batch(conn, batch_id: str) -> dict[str, int]:
    stats = {"rolled_back": 0, "rollback_blocked": 0, "concepts_retained": 0}
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id,source_kind,target_table,target_id FROM stratum.legacy_knowledge_merge_ledger "
                "WHERE batch_id=%s AND status='applied' ORDER BY created_at DESC",
                (batch_id,),
            )
            for ledger_id, source_kind, target_table, target_id in cur.fetchall():
                if source_kind == "concept":
                    _update_ledger(
                        cur,
                        ledger_id,
                        "rollback_blocked",
                        "concept retained; shared references unknown",
                    )
                    stats["concepts_retained"] += 1
                    continue
                cur.execute(
                    "DELETE FROM stratum.concept_relations WHERE id=%s "
                    "AND created_at=updated_at RETURNING id",
                    (target_id,),
                )
                deleted = cur.fetchone() is not None
                status = "rolled_back" if deleted else "rollback_blocked"
                _update_ledger(
                    cur,
                    ledger_id,
                    status,
                    "relation removed" if deleted else "relation changed/missing",
                )
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
        parser.error("invalid merge report: " + "; ".join(errors[:5]))
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
    if args.rollback_batch and args.rollback_batch != report.get("batch_id"):
        parser.error("--rollback-batch must match report batch_id")
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
