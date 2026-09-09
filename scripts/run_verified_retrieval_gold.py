"""Evaluate verified gold through the KnowledgeView product contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

import psycopg2

from stratum.services.knowledge_view import KnowledgeViewRequest, search_knowledge_view
from stratum.services.retrieval_engine import _get_bge

DB = dict(host="127.0.0.1", port=5435, user="aii", password="aii_safe_pass", dbname="aii_kg")
HASHED_OWNER = "56d6bc01edc35765"
RAW_OWNER = "soffy88@gmail.com"


def _runtime_user(value: str) -> str:
    return RAW_OWNER if value == HASHED_OWNER else value


def _load_state() -> tuple[dict[str, tuple], dict[str, str], dict[str, bool]]:
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT id, user_id, title, COALESCE(file_hash,'') FROM stratum.substrates")
    sources = {row[0]: row for row in cur.fetchall()}
    cur.execute(
        """
        SELECT s.id, count(c.id), count(c.id) FILTER (WHERE c.anchor_json ? 'start_pos')
        FROM stratum.substrates s
        LEFT JOIN stratum.substrate_chunk c ON c.substrate_id=s.id
        GROUP BY s.id
        """
    )
    chunks = {row[0]: f"{row[1]}:{row[2]}" for row in cur.fetchall()}
    cur.execute(
        """SELECT s.id,
                  bool_or(sl.embedding IS NOT NULL
                          AND sl.model_used = 'BAAI/bge-m3'
                          AND vector_dims(sl.embedding) = 1024)
           FROM stratum.substrates s
           LEFT JOIN stratum.substrate_layers sl
             ON sl.substrate_id = s.id AND sl.layer = 'L0'
           GROUP BY s.id"""
    )
    index_state = {row[0]: bool(row[1]) for row in cur.fetchall()}
    cur.close()
    conn.close()
    return sources, chunks, index_state


def _dedupe(results: list[dict]) -> list[dict]:
    output = []
    seen = set()
    for result in results:
        sid = result.get("substrate_id") or result.get("id")
        if not sid or sid in seen:
            continue
        seen.add(sid)
        output.append(result)
    return output


def _ndcg(ranked: list[str], expected: set[str], k: int = 10) -> float:
    dcg = 0.0
    for index, sid in enumerate(ranked[:k], 1):
        if sid in expected:
            dcg += 1.0 / math.log2(index + 1)
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, min(len(expected), k) + 1))
    return dcg / ideal if ideal else 0.0


def _citation_valid(result: dict) -> bool:
    sid = result.get("substrate_id")
    provenance = result.get("provenance") or {}
    deep_link = result.get("deep_link") or ""
    return bool(
        sid
        and provenance.get("substrate_id") == sid
        and deep_link.startswith(f"stratum://substrate/{sid}")
        and result.get("snippet")
    )


def _anchor_valid(result: dict) -> bool:
    start, end = result.get("char_start"), result.get("char_end")
    return (
        result.get("anchor_status") in {"ok", "exact", "normalized", "approx"}
        and isinstance(start, int)
        and isinstance(end, int)
        and 0 <= start <= end
    )


def _failure(
    record: dict,
    ranked: list[str],
    sources: dict,
    index_state: dict[str, bool],
) -> str | None:
    expected = set(record.get("expected_source_ids", []))
    if expected & set(ranked):
        return None
    if not expected or any(sid not in sources for sid in expected):
        return "bad gold"
    if any(not index_state.get(sid, False) for sid in expected):
        return "missing index"
    query = record.get("query", "").lower()
    title_or_text = query[:80]
    if title_or_text and any(title_or_text in (sources[sid][2] or "").lower() for sid in expected):
        return "lexical miss"
    if ranked:
        returned_text = " ".join(str(sid) for sid in ranked)
        if returned_text:
            return "ranking failure"
    return "embedding miss"


def run(gold_path: Path, output: Path, limit: int | None) -> int:
    gold = [item for item in json.loads(gold_path.read_text(encoding="utf-8")) if item.get("review_status") == "verified"]
    if limit:
        gold = gold[:limit]
    sources, _chunks, index_state = _load_state()
    isolation_leaks = 0
    citation_total = citation_ok = 0
    anchor_total = anchor_ok = 0
    per_query = []
    failure_categories = Counter()
    wrong_source_results = 0
    result_slots = 0

    for index, record in enumerate(gold, 1):
        user_id = _runtime_user(record.get("user_id", RAW_OWNER))
        response = search_knowledge_view(
            KnowledgeViewRequest(
                query=record["query"],
                top_k=10,
                scopes=["lexical", "dense"],
                user_id=user_id,
            )
        )
        results = _dedupe(response.get("results", []))
        ranked = [result.get("substrate_id") or result.get("id") for result in results]
        expected = set(record.get("expected_source_ids", []))
        allowed = {user_id, hashlib.sha256(user_id.encode()).hexdigest()[:16]}
        for result in results:
            sid = result.get("substrate_id") or result.get("id")
            owner = sources.get(sid, (None, None))[1] if sid in sources else None
            if owner not in allowed:
                isolation_leaks += 1
            citation_total += 1
            citation_ok += int(_citation_valid(result))
            anchor_total += 1
            anchor_ok += int(_anchor_valid(result))
        result_slots += len(results)
        wrong_source_results += sum(sid not in expected for sid in ranked)
        hit_positions = [position for position, sid in enumerate(ranked, 1) if sid in expected]
        failure = _failure(record, ranked, sources, index_state)
        if failure:
            failure_categories[failure] += 1
        per_query.append(
            {
                "query_id": record["query_id"],
                "gold_type": record["gold_type"],
                "ranked_source_ids": ranked,
                "expected_source_ids": sorted(expected),
                "hit_rank": min(hit_positions) if hit_positions else None,
                "recall_at_1": bool(hit_positions and hit_positions[0] <= 1),
                "recall_at_5": bool(hit_positions and hit_positions[0] <= 5),
                "recall_at_10": bool(hit_positions and hit_positions[0] <= 10),
                "mrr": 1.0 / min(hit_positions) if hit_positions else 0.0,
                "ndcg_at_10": _ndcg(ranked, expected),
                "failure_category": failure,
                "result_count": len(results),
            }
        )
        if index % 10 == 0:
            print(f"evaluated={index}/{len(gold)}", flush=True)

    count = len(per_query) or 1
    metrics = {
        "N": len(per_query),
        "Recall@1": sum(item["recall_at_1"] for item in per_query) / count,
        "Recall@5": sum(item["recall_at_5"] for item in per_query) / count,
        "Recall@10": sum(item["recall_at_10"] for item in per_query) / count,
        "MRR": sum(item["mrr"] for item in per_query) / count,
        "nDCG@10": sum(item["ndcg_at_10"] for item in per_query) / count,
        "citation_validity": citation_ok / citation_total if citation_total else 0.0,
        "anchor_validity": anchor_ok / anchor_total if anchor_total else 0.0,
        "isolation_leaks": isolation_leaks,
        "wrong_source_results": wrong_source_results,
        "wrong_source_rate": wrong_source_results / result_slots if result_slots else 0.0,
        "failure_categories": dict(failure_categories.most_common()),
        "query_model": _get_bge().model_name,
        "index_model": "BAAI/bge-m3",
        "dim": _get_bge().native_dim,
        "retrieval_entrypoint": "stratum.services.knowledge_view.search_knowledge_view",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"metrics": metrics, "per_query": per_query}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    raise SystemExit(run(args.gold, args.output, args.limit))
