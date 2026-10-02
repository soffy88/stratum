#!/usr/bin/env python3
"""Plan a human-reviewed merge of legacy Concept/Relation stores.

The planner only groups exact normalized keys.  It never fuzzy-merges names,
never chooses a canonical ID, and never writes a legacy or canonical table.
Input is a reviewed JSON snapshot with this shape::

    {
      "concepts": [
        {"source_table": "aii.concept_onto", "source_id": "12",
         "name": "Marginal Cost", "type": "concept", "domain": "economics"}
      ],
      "relations": [
        {"source_table": "aii.edge_onto", "source_id": "9",
         "source_ref": "aii.concept_onto:12", "target_ref": "rf.refined_concept:44",
         "relation_type": "prerequisite_of"}
      ]
    }

Optional approvals use ``concept_groups`` and ``relation_groups`` keyed by the
reported group ID.  A group is only approved when the manifest explicitly says
``{"decision":"merge", "target_id":"...", "user_id":"..."}``.  All other
groups remain ``needs_manual_review``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def normalize_label(value: Any) -> str:
    """Normalize spelling/whitespace only; punctuation is a separator, not deleted."""
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    # Punctuation is a word separator; programming/math symbols stay visible
    # so names such as C and C++ never collapse into one merge key.
    chars = [" " if unicodedata.category(char).startswith("P") else char for char in text]
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


def _hash(value: Any) -> str:
    body = json.dumps(_jsonable(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode()).hexdigest()


def _group_id(prefix: str, key: tuple[str, ...]) -> str:
    return f"{prefix}_{_hash(key)[:16]}"


def _ref(source_table: Any, source_id: Any) -> str:
    return f"{source_table}:{source_id}"


def _approval(approvals: dict[str, Any], section: str, group_id: str) -> dict[str, Any] | None:
    value = approvals.get(section, {}).get(group_id)
    return value if isinstance(value, dict) else None


def _review_status(approval: dict[str, Any] | None) -> str:
    if (
        approval
        and approval.get("decision") == "merge"
        and approval.get("target_id")
        and approval.get("user_id")
    ):
        return "approved"
    if approval and approval.get("decision") in {"keep_separate", "reject"}:
        return str(approval["decision"])
    return "needs_manual_review"


def _ledger_candidate(
    *,
    batch_id: str,
    source_kind: str,
    row: dict[str, Any],
    group_id: str,
    target_table: str,
    payload: dict[str, Any],
    approval: dict[str, Any] | None,
) -> dict[str, Any]:
    source_table = str(row.get("source_table", ""))
    source_id = str(row.get("source_id", ""))
    payload = _jsonable(payload)
    review_status = _review_status(approval)
    if source_kind == "relation" and review_status == "approved":
        if not approval.get("source_concept_id") or not approval.get("target_concept_id"):
            review_status = "needs_manual_review"
            payload["approval_error"] = "relation approval must include both canonical endpoint IDs"
        else:
            payload["source_concept_id"] = str(approval["source_concept_id"])
            payload["target_concept_id"] = str(approval["target_concept_id"])
    if source_kind == "concept" and review_status == "approved":
        payload["canonical_id"] = str(approval["target_id"])
        payload["canonical_user_id"] = str(approval["user_id"])
    payload_hash = _hash(payload)
    candidate_id = (
        f"merge_{_hash((batch_id, source_kind, source_table, source_id, payload_hash))[:24]}"
    )
    target_id = approval.get("target_id") if review_status == "approved" else None
    user_id = approval.get("user_id") if review_status == "approved" else None
    return {
        "id": candidate_id,
        "batch_id": batch_id,
        "source_kind": source_kind,
        "source_table": source_table,
        "source_id": source_id,
        "candidate_group_id": group_id,
        "target_table": target_table,
        "target_id": target_id,
        "user_id": user_id,
        "status": "approved" if review_status == "approved" else "candidate",
        "review_status": review_status,
        "payload_hash": payload_hash,
        "payload_json": payload,
        "reason": (
            "explicit human approval manifest"
            if review_status == "approved"
            else "exact normalized candidate; human review required"
        ),
    }


def build_plan(
    snapshot: dict[str, Any], batch_id: str, approvals: dict[str, Any] | None = None
) -> dict[str, Any]:
    approvals = approvals or {}
    blocked: list[dict[str, Any]] = []
    concepts = snapshot.get("concepts", [])
    relations = snapshot.get("relations", [])
    if not isinstance(concepts, list) or not isinstance(relations, list):
        raise ValueError("snapshot concepts and relations must be arrays")

    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    ref_to_group: dict[str, str] = {}
    for row in concepts:
        if not isinstance(row, dict):
            blocked.append({"source_kind": "concept", "reason": "row_must_be_object"})
            continue
        source_table = row.get("source_table")
        source_id = row.get("source_id")
        name = normalize_label(row.get("name"))
        if not source_table or source_id in (None, "") or not name:
            blocked.append(
                {
                    "source_kind": "concept",
                    "source_table": source_table,
                    "source_id": str(source_id or ""),
                    "reason": "missing_source_identity_or_name",
                }
            )
            continue
        scope = normalize_label(row.get("user_id")) or "__global__"
        key = (
            name,
            normalize_label(row.get("type")) or "concept",
            normalize_label(row.get("domain")),
            scope,
        )
        groups[key].append(row)

    concept_groups: list[dict[str, Any]] = []
    group_rows: dict[str, list[dict[str, Any]]] = {}
    for key, rows in sorted(groups.items()):
        group_id = _group_id("cg", key)
        group_rows[group_id] = rows
        for row in rows:
            ref_to_group[_ref(row.get("source_table"), row.get("source_id"))] = group_id
        field_values = {
            field: sorted({normalize_label(row.get(field)) for row in rows if row.get(field)})
            for field in ("type", "domain")
        }
        conflicts = {field: values for field, values in field_values.items() if len(values) > 1}
        approval = _approval(approvals, "concept_groups", group_id)
        concept_groups.append(
            {
                "group_id": group_id,
                "normalized_key": key,
                "member_count": len(rows),
                "members": [_ref(row.get("source_table"), row.get("source_id")) for row in rows],
                "field_conflicts": conflicts,
                "review_status": _review_status(approval),
            }
        )

    candidates: list[dict[str, Any]] = []
    for group in concept_groups:
        group_id = group["group_id"]
        approval = _approval(approvals, "concept_groups", group_id)
        for row in group_rows[group_id]:
            candidates.append(
                _ledger_candidate(
                    batch_id=batch_id,
                    source_kind="concept",
                    row=row,
                    group_id=group_id,
                    target_table="stratum.concepts",
                    payload={
                        "canonical_name": normalize_label(row.get("name")),
                        "type": normalize_label(row.get("type")) or "concept",
                        "domain": normalize_label(row.get("domain")),
                        "aliases": row.get("aliases") or [],
                        "group_members": group["members"],
                    },
                    approval=approval,
                )
            )

    relation_groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in relations:
        if not isinstance(row, dict):
            blocked.append({"source_kind": "relation", "reason": "row_must_be_object"})
            continue
        source_ref = str(row.get("source_ref", ""))
        target_ref = str(row.get("target_ref", ""))
        src_group = ref_to_group.get(source_ref)
        dst_group = ref_to_group.get(target_ref)
        if not src_group or not dst_group:
            blocked.append(
                {
                    "source_kind": "relation",
                    "source_table": row.get("source_table"),
                    "source_id": str(row.get("source_id", "")),
                    "reason": "relation_endpoint_not_in_concept_snapshot",
                    "source_ref": source_ref,
                    "target_ref": target_ref,
                }
            )
            continue
        relation_type = normalize_label(row.get("relation_type"))
        if not relation_type or not row.get("source_table") or row.get("source_id") in (None, ""):
            blocked.append(
                {
                    "source_kind": "relation",
                    "source_id": str(row.get("source_id", "")),
                    "reason": "missing_relation_identity_or_type",
                }
            )
            continue
        scope = normalize_label(row.get("user_id")) or "__global__"
        relation_groups[(src_group, relation_type, dst_group, scope)].append(row)

    relation_group_rows: dict[str, list[dict[str, Any]]] = {}
    relation_group_reports: list[dict[str, Any]] = []
    for key, rows in sorted(relation_groups.items()):
        group_id = _group_id("rg", key)
        relation_group_rows[group_id] = rows
        approval = _approval(approvals, "relation_groups", group_id)
        relation_group_reports.append(
            {
                "group_id": group_id,
                "normalized_key": key,
                "member_count": len(rows),
                "members": [_ref(row.get("source_table"), row.get("source_id")) for row in rows],
                "review_status": _review_status(approval),
            }
        )
        for row in rows:
            candidates.append(
                _ledger_candidate(
                    batch_id=batch_id,
                    source_kind="relation",
                    row=row,
                    group_id=group_id,
                    target_table="stratum.concept_relations",
                    payload={
                        "source_group_id": key[0],
                        "relation_type": key[1],
                        "target_group_id": key[2],
                        "relation_scope": key[3],
                        "rationale": row.get("description") or row.get("evidence"),
                    },
                    approval=approval,
                )
            )

    has_review = any(
        item["review_status"] == "needs_manual_review"
        for item in concept_groups + relation_group_reports
    )
    report = {
        "batch_id": batch_id,
        "status": "blocked"
        if blocked
        else ("ready_for_apply" if not has_review else "needs_manual_review"),
        "summary": {
            "concept_groups": len(concept_groups),
            "relation_groups": len(relation_group_reports),
            "candidates": len(candidates),
            "blocked": len(blocked),
            "needs_manual_review": sum(
                c["review_status"] == "needs_manual_review" for c in candidates
            ),
            "approved": sum(c["review_status"] == "approved" for c in candidates),
        },
        "concept_groups": concept_groups,
        "relation_groups": relation_group_reports,
        "candidates": candidates,
        "blocked": blocked,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--approvals", type=Path)
    parser.add_argument("--batch-id", default=None)
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    approvals = json.loads(args.approvals.read_text(encoding="utf-8")) if args.approvals else {}
    batch_id = args.batch_id or datetime.now(timezone.utc).strftime(
        "legacy-knowledge-%Y%m%dT%H%M%SZ"
    )
    report = build_plan(snapshot, batch_id, approvals)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report["blocked"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
