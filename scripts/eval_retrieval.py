#!/usr/bin/env python3
"""Retrieval eval harness — measure recall@k / MRR@k against a golden set.

This is the missing "ruler": without it, every retrieval change (rerank,
expansion, chunking, embedding swap) is a blind bet. Run it before and after a
change to know whether quality actually moved.

Golden set format (JSON list):
    [
      {"query": "什么是注意力机制", "relevant_substrate_ids": ["01ABC...", "01DEF..."]},
      ...
    ]
Build it from real questions you care about + the substrate ids that *should*
surface. 30-50 entries is enough to detect meaningful regressions.

Usage:
    export STRATUM_EVAL_TOKEN=<jwt>            # or pass --token
    python3 scripts/eval_retrieval.py --golden scripts/eval_golden_set.example.json
    python3 scripts/eval_retrieval.py --golden my_set.json --rerank
    python3 scripts/eval_retrieval.py --golden my_set.json --rerank --expand --top-k 10

Compare two runs (e.g. baseline vs --rerank) by eyeballing the printed metrics.
Exit code is non-zero if the golden set is empty or all queries error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request


def _post_search(base_url: str, token: str, query: str, top_k: int,
                 rerank: bool, expand: bool, timeout: float) -> list[str]:
    """Return ordered list of result substrate ids for a query."""
    body = json.dumps({
        "query": query,
        "top_k": top_k,
        "rerank": rerank,
        "expand": expand,
    }).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/v1/search",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode())
    return [r["id"] for r in data.get("results", [])]


def _metrics(ranked_ids: list[str], relevant: set[str], k: int) -> tuple[float, float]:
    """Return (recall@k, reciprocal_rank@k) for one query."""
    if not relevant:
        return 0.0, 0.0
    top = ranked_ids[:k]
    hits = sum(1 for i in top if i in relevant)
    recall = hits / len(relevant)
    rr = 0.0
    for rank, i in enumerate(top, start=1):
        if i in relevant:
            rr = 1.0 / rank
            break
    return recall, rr


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--golden", required=True, help="path to golden set JSON")
    ap.add_argument("--base-url", default=os.environ.get("STRATUM_EVAL_BASE_URL",
                    "https://stratum.kanpan.co"))
    ap.add_argument("--token", default=os.environ.get("STRATUM_EVAL_TOKEN", ""))
    ap.add_argument("--top-k", type=int, default=10)
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--expand", action="store_true")
    ap.add_argument("--timeout", type=float, default=60.0)
    args = ap.parse_args()

    if not args.token:
        print("ERROR: provide --token or set STRATUM_EVAL_TOKEN", file=sys.stderr)
        return 2

    with open(args.golden, encoding="utf-8") as f:
        golden = json.load(f)
    if not golden:
        print("ERROR: golden set is empty", file=sys.stderr)
        return 2

    k = args.top_k
    recalls: list[float] = []
    rrs: list[float] = []
    errors = 0
    t0 = time.time()

    print(f"Eval: {len(golden)} queries | top_k={k} | "
          f"rerank={args.rerank} expand={args.expand} | {args.base_url}")
    print("-" * 72)
    for item in golden:
        q = item["query"]
        relevant = set(item.get("relevant_substrate_ids", []))
        try:
            ranked = _post_search(args.base_url, args.token, q, k,
                                  args.rerank, args.expand, args.timeout)
        except (urllib.error.URLError, KeyError, ValueError) as e:
            errors += 1
            print(f"  [ERR] {q[:40]!r}: {e}")
            continue
        recall, rr = _metrics(ranked, relevant, k)
        recalls.append(recall)
        rrs.append(rr)
        print(f"  recall@{k}={recall:.2f}  rr={rr:.2f}  {q[:44]}")

    print("-" * 72)
    n = len(recalls)
    if n == 0:
        print("All queries errored.", file=sys.stderr)
        return 1
    print(f"queries scored : {n}/{len(golden)}  (errors: {errors})")
    print(f"recall@{k}      : {sum(recalls)/n:.3f}")
    print(f"MRR@{k}         : {sum(rrs)/n:.3f}")
    print(f"elapsed        : {time.time()-t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
