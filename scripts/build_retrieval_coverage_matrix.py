"""Audit verified retrieval gold against the canonical KnowledgeView projection.

This is intentionally a read-only audit.  It distinguishes canonical source
truth from the rebuildable L0 dense projection so a low recall score cannot be
misread as a ranking failure when the target is not indexed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import psycopg2


DB = dict(host="127.0.0.1", port=5435, user="aii", password="aii_safe_pass", dbname="aii_kg")
COMPATIBLE_MODEL = "BAAI/bge-m3"
COMPATIBLE_DIM = 1024


def _owner_ids(user_id: str) -> set[str]:
    return {user_id, hashlib.sha256(user_id.encode()).hexdigest()[:16]}


def build(gold_path: Path) -> dict:
    gold = [
        row
        for row in json.loads(gold_path.read_text(encoding="utf-8"))
        if row.get("review_status") == "verified"
    ]
    source_ids = sorted({sid for row in gold for sid in row.get("expected_source_ids", [])})
    fragment_ids = sorted({fid for row in gold for fid in row.get("expected_fragment_ids", [])})

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        """SELECT s.id, s.user_id, s.title, s.file_hash,
                  sl.id, sl.model_used, vector_dims(sl.embedding),
                  sl.embedding IS NOT NULL
           FROM stratum.substrates s
           LEFT JOIN stratum.substrate_layers sl
             ON sl.substrate_id = s.id AND sl.layer = 'L0'
           WHERE s.id = ANY(%s)""",
        (source_ids,),
    )
    sources = {row[0]: row for row in cur.fetchall()}
    cur.execute(
        """SELECT id, substrate_id, embedding IS NOT NULL, parser_version,
                  vector_dims(embedding)
           FROM stratum.substrate_chunk
           WHERE id = ANY(%s)""",
        (fragment_ids or ["__no_fragments__"],),
    )
    fragments = {row[0]: row for row in cur.fetchall()}

    matrix: list[dict] = []
    status_counts: Counter[str] = Counter()
    for row in gold:
        expected_sources = list(row.get("expected_source_ids", []))
        expected_fragments = list(row.get("expected_fragment_ids", []))
        source_items = []
        target_statuses = []
        for sid in expected_sources:
            source = sources.get(sid)
            if source is None:
                status = "SOURCE_MISSING"
                source_item = {
                    "source_id": sid,
                    "source_exists": False,
                    "fragment_exists": False,
                    "embedding_exists": False,
                    "embedding_model": None,
                    "embedding_dim": None,
                    "projection_exists": False,
                    "retrieval_scope_visible": False,
                    "user_scope_visible": False,
                    "index_status": status,
                }
            else:
                _, stored_user, title, file_hash, layer_id, model, dim, has_embedding = source
                user_scope_visible = stored_user in _owner_ids(row.get("user_id", ""))
                compatible = bool(has_embedding and model == COMPATIBLE_MODEL and dim == COMPATIBLE_DIM)
                expected_for_source = [
                    fragments.get(fid)
                    for fid in expected_fragments
                    if fragments.get(fid) is not None
                ]
                source_fragments = [
                    fragment
                    for fragment in expected_for_source
                    if fragment[1] == sid
                ]
                fragment_exists = not expected_fragments or (
                    len(source_fragments) == len(expected_fragments)
                )
                fragment_embedding_ok = all(
                    frag[2] and frag[4] == COMPATIBLE_DIM for frag in source_fragments
                ) if expected_fragments else True
                if not user_scope_visible:
                    status = "USER_SCOPE_MISMATCH"
                elif expected_fragments and not fragment_exists:
                    status = "FRAGMENT_MISSING"
                elif expected_fragments and not fragment_embedding_ok:
                    status = "EMBEDDING_MISSING"
                elif not layer_id:
                    status = "PROJECTION_MISSING"
                elif not compatible:
                    status = "EMBEDDING_MISSING"
                else:
                    status = "INDEXED"
                source_item = {
                    "source_id": sid,
                    "title": title,
                    "source_exists": True,
                    "fragment_exists": fragment_exists,
                    "embedding_exists": bool(has_embedding),
                    "embedding_model": model,
                    "embedding_dim": dim,
                    "projection_exists": bool(layer_id),
                    "retrieval_scope_visible": bool(user_scope_visible and compatible),
                    "user_scope_visible": user_scope_visible,
                    "index_status": status,
                }
            source_items.append(source_item)
            target_statuses.append(status)

        # A record is indexed only when every expected canonical target is
        # visible to its KnowledgeView owner.  This preserves the prior
        # per-query missing-index denominator of 100.
        record_status = "INDEXED" if target_statuses and all(
            value == "INDEXED" for value in target_statuses
        ) else next((value for value in target_statuses if value != "INDEXED"), "OTHER")
        status_counts[record_status] += 1
        matrix.append(
            {
                "query_id": row["query_id"],
                "expected_source_ids": expected_sources,
                "expected_fragment_ids": expected_fragments,
                "source_items": source_items,
                "index_status": record_status,
            }
        )

    cur.execute(
        """SELECT count(*) FILTER (WHERE sl.embedding IS NOT NULL),
                  count(*),
                  count(*) FILTER (WHERE sl.embedding IS NULL),
                  count(*) FILTER (WHERE sl.embedding IS NOT NULL AND sl.model_used <> %s),
                  count(*) FILTER (WHERE sl.embedding IS NOT NULL AND vector_dims(sl.embedding) <> %s)
           FROM stratum.substrate_layers sl
           JOIN stratum.substrates s ON s.id = sl.substrate_id
           WHERE sl.layer = 'L0'""",
        (COMPATIBLE_MODEL, COMPATIBLE_DIM),
    )
    indexed, eligible, missing, wrong_model, wrong_dim = cur.fetchone()
    conn.close()
    return {
        "gold_verified": len(gold),
        "unique_expected_sources": len(source_ids),
        "record_status_counts": dict(status_counts),
        "corpus": {
            "eligible_l0_fragments": eligible,
            "indexed_l0_fragments": indexed - wrong_model - wrong_dim,
            "missing_embeddings": missing,
            "wrong_model": wrong_model,
            "wrong_dimension": wrong_dim,
            "compatible_coverage": (indexed - wrong_model - wrong_dim) / eligible if eligible else 0.0,
        },
        "matrix": matrix,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.gold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "matrix"}, ensure_ascii=False))
    for row in result["matrix"]:
        print(row["query_id"], row["index_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
