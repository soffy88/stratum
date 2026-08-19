#!/usr/bin/env python3
"""Benchmark: retrieval accuracy — tiered retrieval vs flat search.

Measures:
  1. Recall@K: how many relevant results in top-K
  2. Token efficiency: L0 pre-filter vs full L2 loading
  3. Latency: directory-recursive vs flat vector search

Usage:
    python benchmark/retrieval_accuracy.py [--queries N]
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import httpx

_BASE = "http://localhost:9304"
_JWT = ""  # Set via env STRATUM_JWT_TOKEN

# Test queries with expected relevant substrates (manually curated)
TEST_QUERIES = [
    {"query": "linear algebra eigenvalue decomposition", "expected_keywords": ["eigenvalue", "matrix", "decomposition"]},
    {"query": "probability theory bayesian inference", "expected_keywords": ["bayesian", "probability", "posterior"]},
    {"query": "optimization gradient descent", "expected_keywords": ["gradient", "descent", "optimization"]},
    {"query": "game theory nash equilibrium", "expected_keywords": ["nash", "equilibrium", "game"]},
    {"query": "differential equation PDE", "expected_keywords": ["differential", "equation", "PDE"]},
]


def _headers():
    import os
    h = {"Content-Type": "application/json"}
    token = os.environ.get("STRATUM_JWT_TOKEN", _JWT)
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def benchmark_tiered_vs_flat(queries: list[dict]) -> dict:
    """Compare tiered retrieval (L0→L1→L2) vs flat L2-only search."""
    results = {"tiered": [], "flat": []}

    for q in queries:
        query = q["query"]
        keywords = q["expected_keywords"]

        # Tiered (L0 pre-filter → L1 → L2)
        t0 = time.time()
        resp = httpx.post(
            f"{_BASE}/api/v1/retrieve",
            headers=_headers(),
            json={"query": query, "max_depth": 3, "top_k": 10},
            timeout=60,
        )
        tiered_ms = int((time.time() - t0) * 1000)
        tiered_data = resp.json() if resp.status_code == 200 else {}

        # Flat (L2 only)
        t0 = time.time()
        resp2 = httpx.post(
            f"{_BASE}/api/v1/retrieve",
            headers=_headers(),
            json={"query": query, "layers": ["L2"], "top_k": 10},
            timeout=60,
        )
        flat_ms = int((time.time() - t0) * 1000)
        flat_data = resp2.json() if resp2.status_code == 200 else {}

        # Calculate keyword recall
        def _recall(data):
            contents = " ".join(
                r.get("content_preview", "") for r in data.get("results", [])
            ).lower()
            hits = sum(1 for kw in keywords if kw.lower() in contents)
            return hits / max(len(keywords), 1)

        tiered_recall = _recall(tiered_data)
        flat_recall = _recall(flat_data)

        # Token efficiency
        tiered_tokens = sum(r.get("token_count", 0) for r in tiered_data.get("results", []))
        flat_tokens = sum(r.get("token_count", 0) for r in flat_data.get("results", []))

        results["tiered"].append({
            "query": query, "recall": round(tiered_recall, 2),
            "latency_ms": tiered_ms, "tokens": tiered_tokens,
            "result_count": len(tiered_data.get("results", [])),
        })
        results["flat"].append({
            "query": query, "recall": round(flat_recall, 2),
            "latency_ms": flat_ms, "tokens": flat_tokens,
            "result_count": len(flat_data.get("results", [])),
        })

    return results


def main():
    print("=" * 60)
    print("Stratum Retrieval Benchmark")
    print("=" * 60)

    results = benchmark_tiered_vs_flat(TEST_QUERIES)

    print("\n## Tiered Retrieval (L0→L1→L2)")
    print(f"{'Query':<45} {'Recall':>8} {'ms':>8} {'Tokens':>8} {'Results':>8}")
    print("-" * 80)
    for r in results["tiered"]:
        print(f"{r['query']:<45} {r['recall']:>8.2f} {r['latency_ms']:>8} {r['tokens']:>8} {r['result_count']:>8}")

    avg_recall = sum(r["recall"] for r in results["tiered"]) / max(len(results["tiered"]), 1)
    avg_ms = sum(r["latency_ms"] for r in results["tiered"]) / max(len(results["tiered"]), 1)
    avg_tokens = sum(r["tokens"] for r in results["tiered"]) / max(len(results["tiered"]), 1)
    print(f"{'AVERAGE':<45} {avg_recall:>8.2f} {avg_ms:>8.0f} {avg_tokens:>8.0f}")

    print("\n## Flat Retrieval (L2 only)")
    print(f"{'Query':<45} {'Recall':>8} {'ms':>8} {'Tokens':>8} {'Results':>8}")
    print("-" * 80)
    for r in results["flat"]:
        print(f"{r['query']:<45} {r['recall']:>8.2f} {r['latency_ms']:>8} {r['tokens']:>8} {r['result_count']:>8}")

    avg_recall_f = sum(r["recall"] for r in results["flat"]) / max(len(results["flat"]), 1)
    avg_ms_f = sum(r["latency_ms"] for r in results["flat"]) / max(len(results["flat"]), 1)
    avg_tokens_f = sum(r["tokens"] for r in results["flat"]) / max(len(results["flat"]), 1)
    print(f"{'AVERAGE':<45} {avg_recall_f:>8.2f} {avg_ms_f:>8.0f} {avg_tokens_f:>8.0f}")

    # Token efficiency comparison
    if avg_tokens_f > 0:
        savings = (1 - avg_tokens / avg_tokens_f) * 100
        print(f"\n## Token Savings: {savings:.1f}% fewer tokens with tiered retrieval")


if __name__ == "__main__":
    main()
