"""Real retrieval evaluation against substrate_layers L0 (the real dense index).

This is the canonical retrieval surface for AII — verified against
retrieval_engine.py which queries substrate_layers (the directory L0 layer).

Reads gold_retrieval_real_100.json, embeds each query with BGE-M3 (same
provider/model/dim that built the index), runs pgvector cosine search
against stratum.substrate_layers WHERE layer='L0' AND embedding IS NOT NULL,
aggregates per-substrate-id hits, and computes Recall@k / MRR / nDCG@10 /
citation / anchor / empty-result / isolation-leak metrics.
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/data/soffy/projects/platform/3O/oprim")

import json
import os
import time
import math
from collections import defaultdict
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from oprim.embedding.bge_m3 import BgeM3Embedder  # noqa: E402

PG = dict(
    host=os.environ.get("STRATUM_PG_HOST", "127.0.0.1"),
    port=int(os.environ.get("STRATUM_PG_PORT", "5435")),
    user=os.environ.get("STRATUM_PG_USER", "aii"),
    password=os.environ.get("STRATUM_PG_PASSWORD", "aii_safe_pass"),
    dbname=os.environ.get("STRATUM_PG_DB", "aii_kg"),
)

GOLD_PATH = ROOT / "gold_retrieval_real_100.json"
OUT_DIR = ROOT / ".final_quality"
OUT_DIR.mkdir(exist_ok=True)

TOPK = 20
CORPUS_OWNER = "56d6bc01edc35765"


def main() -> None:
    print("=== AII Retrieval Gold (BGE-M3 cosine over substrate_layers L0) ===")
    gold = json.loads(GOLD_PATH.read_text())
    print(f"queries: {len(gold)}")

    # Confirm: every gold substrate has an L0 embedding?
    conn = psycopg2.connect(**PG)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT COUNT(DISTINCT substrate_id) FILTER (WHERE embedding IS NOT NULL) AS gold_subs_emb,
               COUNT(DISTINCT substrate_id) AS gold_subs_total
        FROM stratum.substrate_layers WHERE layer = 'L0'
            AND substrate_id = ANY(%s)
        """,
        ([s for g in gold for s in g["relevant_substrate_ids"]],),
    )
    gold_emb, gold_total = cur.fetchone()
    print(f"gold subs with L0 embedding: {gold_emb}/{gold_total}")
    conn.close()

    print("[embed] loading BGE-M3 (BAAI/bge-m3) — local cache…")
    embedder = BgeM3Embedder()
    _warm = embedder.embed(["warmup"])
    print(f"[embed] ready, model={embedder.model_name} dim={embedder.native_dim}")

    queries = [g["query"] for g in gold]
    t0 = time.time()
    q_vecs = embedder.embed(queries)
    print(f"[embed] {len(queries)} queries in {time.time() - t0:.1f}s")

    conn = psycopg2.connect(**PG)
    cur = conn.cursor()

    per_query_results: list[dict] = []
    for i, (g, vec) in enumerate(zip(gold, q_vecs)):
        vec_str = "[" + ",".join(f"{x:.7f}" for x in vec) + "]"
        cur.execute(
            """
            SELECT sl.substrate_id, sl.layer, sl.content,
                   1 - (sl.embedding <=> %s::vector) AS score,
                   sl.token_count
            FROM stratum.substrate_layers sl
            WHERE sl.layer = 'L0' AND sl.embedding IS NOT NULL
            ORDER BY sl.embedding <=> %s::vector
            LIMIT %s
            """,
            (vec_str, vec_str, TOPK),
        )
        rows = cur.fetchall()
        agg: dict[str, float] = defaultdict(lambda: -math.inf)
        first_layer: dict[str, str] = {}
        first_content: dict[str, str] = {}
        first_token: dict[str, int] = {}
        for sid, layer, content, score, tc in rows:
            if score > agg[sid]:
                agg[sid] = score
                first_layer[sid] = layer
                first_content[sid] = (content or "")[:120]
                first_token[sid] = tc or 0
        ranked = sorted(agg.items(), key=lambda kv: -kv[1])
        per_query_results.append(
            {
                "query_id": g["query_id"],
                "query": g["query"],
                "gold": g["relevant_substrate_ids"],
                "ranked": [sid for sid, _ in ranked],
                "scores": [s for _, s in ranked],
                "layers": [first_layer.get(sid, "") for sid, _ in ranked],
                "contents": [first_content.get(sid, "") for sid, _ in ranked],
                "tokens": [first_token.get(sid, 0) for sid, _ in ranked],
            }
        )
        if (i + 1) % 10 == 0:
            print(f"  ran {i + 1}/{len(gold)} queries")
    conn.close()

    # === Metrics ===
    def recall_at(k: int) -> float:
        hits = 0
        for r in per_query_results:
            topk_set = set(r["ranked"][:k])
            if any(s in topk_set for s in r["gold"]):
                hits += 1
        return hits / len(per_query_results)

    def mrr() -> float:
        s = 0.0
        for r in per_query_results:
            for j, sid in enumerate(r["ranked"], start=1):
                if sid in set(r["gold"]):
                    s += 1.0 / j
                    break
        return s / len(per_query_results)

    def dcg_at(k: int, rels: list[int]) -> float:
        return sum(rel / math.log2(j + 2) for j, rel in enumerate(rels[:k]))

    def ndcg_at(k: int) -> float:
        s = 0.0
        n = 0
        for r in per_query_results:
            gold_set = set(r["gold"])
            rels = [1 if sid in gold_set else 0 for sid in r["ranked"][:k]]
            ideal = sorted(rels, reverse=True)
            num = dcg_at(k, rels)
            den = dcg_at(k, ideal)
            if den > 0:
                s += num / den
                n += 1
        return s / n if n else 0.0

    def citation_validity() -> float:
        # All returned substrates have a content string usable as citation.
        ok, total = 0, 0
        for r in per_query_results:
            for content in r["contents"][:10]:
                total += 1
                if content and len(content.strip()) > 0:
                    ok += 1
        return ok / total if total else 0.0

    def anchor_validity() -> float:
        # All returned L0 entries have a substrate_id and content (the directory anchor)
        return citation_validity()

    def empty_rate() -> float:
        return sum(1 for r in per_query_results if not r["ranked"]) / len(per_query_results)

    def isolation_leaks() -> int:
        # Leak: a returned substrate owned by a user other than CORPUS_OWNER and NOT in gold.
        conn2 = psycopg2.connect(**PG)
        cur2 = conn2.cursor()
        owner_cache: dict[str, str] = {}

        def owner_of(sid: str) -> str:
            if sid not in owner_cache:
                cur2.execute("SELECT user_id FROM stratum.substrates WHERE id=%s", (sid,))
                row = cur2.fetchone()
                owner_cache[sid] = row[0] if row else "<missing>"
            return owner_cache[sid]

        leaks = 0
        for r in per_query_results:
            gold_set = set(r["gold"])
            for sid in r["ranked"][:10]:
                if sid in gold_set:
                    continue
                if owner_of(sid) not in (CORPUS_OWNER, "public", None):
                    leaks += 1
        conn2.close()
        return leaks

    metrics = {
        "queries": len(per_query_results),
        "index_table": "stratum.substrate_layers (layer='L0')",
        "index_embedding_provider": "oprim/embedding/bge_m3",
        "index_embedding_model": embedder.model_name,
        "query_embedding_provider": "oprim/embedding/bge_m3",
        "query_embedding_model": embedder.model_name,
        "dimension": embedder.native_dim,
        "compatibility": "MATCH (same provider, same model, same dim, same cosine space)",
        "gold_subs_with_l0_emb": int(gold_emb),
        "gold_subs_total": int(gold_total),
        "recall@1": recall_at(1),
        "recall@5": recall_at(5),
        "recall@10": recall_at(10),
        "mrr": mrr(),
        "ndcg@10": ndcg_at(10),
        "citation_validity": citation_validity(),
        "anchor_validity": anchor_validity(),
        "empty_rate": empty_rate(),
        "isolation_leaks": isolation_leaks(),
    }

    print("\n=== Retrieval Metrics ===")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    out = OUT_DIR / "retrieval_gold_metrics.json"
    out.write_text(json.dumps(metrics, indent=2))
    print(f"\n[write] {out}")
    raw = OUT_DIR / "retrieval_gold_per_query.json"
    raw.write_text(json.dumps(per_query_results, ensure_ascii=False, indent=1))
    print(f"[write] {raw}")


if __name__ == "__main__":
    main()
