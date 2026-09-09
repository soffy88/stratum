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
from stratum.services.retrieval_engine import (
    _claim_provenance_search,
    _get_bge,
    _rrf_merge_channels,
    _text_search_chunks,
    _text_search_layers,
    _title_metadata_search,
    _vector_search_chunks,
    _vector_search_layers,
)
from stratum.services.mix_retrieval import _kg_entity_expansion

DB = dict(host="127.0.0.1", port=5435, user="aii", password="aii_safe_pass", dbname="aii_kg")
HASHED_OWNER = "56d6bc01edc35765"
RAW_OWNER = "soffy88@gmail.com"


def _runtime_user(value: str) -> str:
    return RAW_OWNER if value == HASHED_OWNER else value


def _load_state() -> tuple[dict[str, tuple], dict[str, str], dict[str, bool], dict[str, str]]:
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
    cur.execute("SELECT id, COALESCE(text, '') FROM stratum.substrate_chunk")
    chunk_texts = {row[0]: row[1] for row in cur.fetchall()}
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
    return sources, chunks, index_state, chunk_texts


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


def _fragment_ranked(results: list[dict], limit: int = 10) -> list[str]:
    """Return unique canonical fragment IDs while preserving result order."""
    output: list[str] = []
    seen: set[str] = set()
    for result in results:
        fragment_id = result.get("fragment_id")
        if not fragment_id or fragment_id in seen:
            continue
        seen.add(fragment_id)
        output.append(fragment_id)
        if len(output) >= limit:
            break
    return output


def _source_ranked(results: list[dict], limit: int = 10) -> list[str]:
    return [
        result.get("substrate_id") or result.get("id")
        for result in _dedupe(results)[:limit]
        if result.get("substrate_id") or result.get("id")
    ]


def _metric_for_ranked(per_query: list[dict], key: str) -> dict[str, float | int]:
    """Calculate Recall@k/MRR for either source or fragment ranked IDs."""
    expected_key = "expected_fragment_ids" if key == "fragment_ranked" else "expected_source_ids"
    eligible = [item for item in per_query if item.get(expected_key)]
    denominator = len(eligible)
    if not denominator:
        return {"N": 0, "Recall@1": 0.0, "Recall@5": 0.0, "Recall@10": 0.0, "MRR": 0.0}
    reciprocal = []
    hits = {1: 0, 5: 0, 10: 0}
    for item in eligible:
        ranked = item[key]
        expected = set(item["expected_fragment_ids"] if key == "fragment_ranked" else item["expected_source_ids"])
        positions = [pos for pos, value in enumerate(ranked, 1) if value in expected]
        rank = min(positions) if positions else None
        reciprocal.append(1.0 / rank if rank else 0.0)
        for cutoff in hits:
            hits[cutoff] += int(rank is not None and rank <= cutoff)
    return {
        "N": denominator,
        "Recall@1": hits[1] / denominator,
        "Recall@5": hits[5] / denominator,
        "Recall@10": hits[10] / denominator,
        "MRR": sum(reciprocal) / denominator,
    }


def _channel_row(results: list[dict], limit: int = 10) -> dict[str, object]:
    return {
        "top10": _source_ranked(results, limit),
        "scores": [
            {
                "id": result.get("substrate_id") or result.get("id"),
                "fragment_id": result.get("fragment_id"),
                "score": result.get("score"),
            }
            for result in results[:limit]
        ],
    }


def _owner_visible(results: list[dict], sources: dict[str, tuple], user_id: str) -> list[dict]:
    """Apply the same owner check to diagnostic-only channels as KnowledgeView."""
    allowed = {user_id, hashlib.sha256(user_id.encode()).hexdigest()[:16]}
    return [
        result
        for result in results
        if (sources.get(result.get("substrate_id"), (None, None))[1] in allowed)
    ]


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
    # Batch immutable BGE-M3 query vectors once; each query still traverses
    # the formal KnowledgeView product contract below.
    query_embeddings = _get_bge().embed([record["query"] for record in gold], dim=1024)
    sources, _chunks, index_state, chunk_texts = _load_state()
    isolation_leaks = 0
    citation_total = citation_ok = 0
    anchor_total = anchor_ok = 0
    per_query = []
    failure_categories = Counter()
    wrong_source_results = 0
    result_slots = 0

    for index, (record, query_embedding) in enumerate(zip(gold, query_embeddings), 1):
        user_id = _runtime_user(record.get("user_id", RAW_OWNER))
        response = search_knowledge_view(
            KnowledgeViewRequest(
                query=record["query"],
                top_k=10,
                scopes=["lexical", "dense"],
                user_id=user_id,
                query_embedding=query_embedding,
            )
        )
        raw_results = response.get("results", [])
        results = _dedupe(raw_results)
        ranked = _source_ranked(raw_results)
        fragment_ranked = _fragment_ranked(raw_results)
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

        # These channel runs are diagnostics on the same canonical corpus and
        # query vector. The product metric above remains the formal
        # KnowledgeView path; this block identifies whether a miss belongs to
        # dense, lexical, graph, or fusion behavior.
        dense_l0 = _vector_search_layers(query_embedding, "L0", top_k=50, user_id=user_id)
        dense_chunk = _vector_search_chunks(query_embedding, top_k=50, user_id=user_id)
        lexical_l0 = _text_search_layers(record["query"], "L0", top_k=50, user_id=user_id)
        lexical_chunk = _text_search_chunks(record["query"], top_k=50, user_id=user_id)
        claim = _claim_provenance_search(record["query"], top_k=50, user_id=user_id)
        title = _title_metadata_search(record["query"], top_k=50, user_id=user_id)
        try:
            graph = _owner_visible(
                _kg_entity_expansion(record["query"], top_k=50), sources, user_id
            )
        except Exception:
            graph = []
        channel_lists = {
            "dense_l0": dense_l0,
            "dense_chunk": dense_chunk,
            "lexical_l0": lexical_l0,
            "lexical_chunk": lexical_chunk,
            "claim": claim,
            "title": title,
            "graph": graph,
            "dense_only": _rrf_merge_channels(
                {"dense_l0": dense_l0, "dense_chunk": dense_chunk},
                top_k=50,
                protect_exact=False,
            ),
            "lexical_only": _rrf_merge_channels(
                {"lexical_l0": lexical_l0, "lexical_chunk": lexical_chunk},
                top_k=50,
                protect_exact=False,
            ),
            "rrf_dense_lexical": _rrf_merge_channels(
                {
                    "dense_l0": dense_l0,
                    "dense_chunk": dense_chunk,
                    "lexical_l0": lexical_l0,
                    "lexical_chunk": lexical_chunk,
                },
                top_k=50,
                protect_exact=False,
            ),
        }
        channel_metrics = {}
        for channel_name, channel_results in channel_lists.items():
            channel_ranked = _source_ranked(channel_results)
            channel_hits = [
                position for position, sid in enumerate(channel_ranked, 1) if sid in expected
            ]
            channel_metrics[channel_name] = {
                "top10": channel_ranked,
                "scores": _channel_row(channel_results)["scores"],
                "hit_at_10": bool(channel_hits),
            }
        per_query.append(
            {
                "query_id": record["query_id"],
                "gold_type": record["gold_type"],
                "ranked_source_ids": ranked,
                "ranked_fragment_ids": fragment_ranked,
                "expected_source_ids": sorted(expected),
                "expected_fragment_ids": sorted(record.get("expected_fragment_ids", [])),
                "expected_fragment_text": [
                    chunk_texts.get(fragment_id, "")
                    for fragment_id in record.get("expected_fragment_ids", [])
                ],
                "hit_rank": min(hit_positions) if hit_positions else None,
                "recall_at_1": bool(hit_positions and hit_positions[0] <= 1),
                "recall_at_5": bool(hit_positions and hit_positions[0] <= 5),
                "recall_at_10": bool(hit_positions and hit_positions[0] <= 10),
                "mrr": 1.0 / min(hit_positions) if hit_positions else 0.0,
                "ndcg_at_10": _ndcg(ranked, expected),
                "failure_category": failure,
                "result_count": len(results),
                "filters_applied": {
                    "user_id": user_id,
                    "scopes": ["lexical", "dense"],
                    "namespace": "global",
                },
                "returned_results": [
                    {
                        "substrate_id": result.get("substrate_id") or result.get("id"),
                        "fragment_id": result.get("fragment_id"),
                        "score": result.get("score"),
                    }
                    for result in raw_results[:10]
                ],
                "channel_metrics": channel_metrics,
            }
        )
        if index % 10 == 0:
            print(f"evaluated={index}/{len(gold)}", flush=True)

    count = len(per_query) or 1
    source_items = [
        {
            "source_ranked": item["ranked_source_ids"],
            "expected_source_ids": item["expected_source_ids"],
            "expected_fragment_ids": [],
        }
        for item in per_query
    ]
    fragment_items = [
        {
            "fragment_ranked": item["ranked_fragment_ids"],
            "expected_source_ids": [],
            "expected_fragment_ids": item["expected_fragment_ids"],
        }
        for item in per_query
    ]
    source_metrics = _metric_for_ranked(source_items, "source_ranked")
    fragment_metrics = _metric_for_ranked(fragment_items, "fragment_ranked")

    channel_benchmarks = {}
    for channel_name in (
        "dense_l0",
        "lexical_l0",
        "graph",
        "dense_only",
        "lexical_only",
        "rrf_dense_lexical",
    ):
        channel_items = [
            {
                "source_ranked": item["channel_metrics"][channel_name]["top10"],
                "expected_source_ids": item["expected_source_ids"],
                "expected_fragment_ids": [],
            }
            for item in per_query
        ]
        channel_benchmarks[channel_name] = _metric_for_ranked(channel_items, "source_ranked")
    channel_benchmarks["current_fusion"] = source_metrics

    metrics = {
        "N": len(per_query),
        "Recall@1": source_metrics["Recall@1"],
        "Recall@5": source_metrics["Recall@5"],
        "Recall@10": source_metrics["Recall@10"],
        "MRR": source_metrics["MRR"],
        "nDCG@10": sum(item["ndcg_at_10"] for item in per_query) / count,
        "Source Recall@1": source_metrics["Recall@1"],
        "Source Recall@5": source_metrics["Recall@5"],
        "Source Recall@10": source_metrics["Recall@10"],
        "Fragment N": fragment_metrics["N"],
        "Fragment Recall@1": fragment_metrics["Recall@1"],
        "Fragment Recall@5": fragment_metrics["Recall@5"],
        "Fragment Recall@10": fragment_metrics["Recall@10"],
        "Fragment MRR": fragment_metrics["MRR"],
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
        "channel_benchmarks": channel_benchmarks,
        "channel_definitions": {
            "dense_l0": "BGE-M3 over substrate_layers.L0",
            "lexical_l0": "Unicode/CJK lexical over substrate_layers.L0",
            "graph": "owner-filtered graph entity expansion diagnostic",
            "dense_only": "unprotected RRF of dense_l0+dense_chunk",
            "lexical_only": "unprotected RRF of lexical_l0+lexical_chunk",
            "rrf_dense_lexical": "unprotected RRF of dense and lexical canonical channels",
            "current_fusion": "formal KnowledgeView response with exact-match protection",
        },
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
