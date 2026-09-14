#!/usr/bin/env python3
"""Benchmark the PostgreSQL-native lexical retrieval contract.

This is a synthetic capacity benchmark: it reports latency percentiles and
index behaviour without touching canonical Stratum tables.  It is not the
human-reviewed quality gold qualification. Example::

    STRATUM_BENCHMARK_DSN=postgresql://... \
      python scripts/benchmark_lexical_retrieval.py

Use ``--sizes 10000 100000 1000000`` for the release qualification matrix.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg2
from psycopg2.extras import execute_values


def _query(conn, table: str, query: str, top_k: int = 10) -> list[str]:
    terms = [term for term in query.casefold().split() if len(term) > 1]
    patterns = [f"%{term}%" for term in terms]
    score_sql = " + ".join("CASE WHEN text ILIKE %s THEN 1 ELSE 0 END" for _ in terms)
    where_sql = " OR ".join("text ILIKE %s" for _ in terms)
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT id FROM {table}
                WHERE ({where_sql})
                ORDER BY ({score_sql}) DESC, id
                LIMIT %s""",
            (*patterns, *patterns, top_k),
        )
        return [row[0] for row in cur.fetchall()]


def _metrics(ranked: list[str], expected: str, k: int = 10) -> tuple[float, float, float, float]:
    top = ranked[:k]
    if expected not in top:
        return 0.0, 0.0, 0.0, 0.0
    rank = top.index(expected) + 1
    ndcg = 1.0 / math.log2(rank + 1)  # single-label nDCG@10
    return float(rank <= 5), 1.0, 1.0 / rank, ndcg


def run_size(dsn: str, size: int, concurrency: int, queries: int) -> dict[str, object]:
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    table = f"p2_lexical_benchmark_{uuid.uuid4().hex}"
    ingest_start = time.perf_counter()
    with admin.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cur.execute(f"DROP TABLE IF EXISTS {table}")
        cur.execute(f"CREATE TABLE {table} (id text PRIMARY KEY, text text NOT NULL)")
        rows = [
            (
                f"fragment-{i:07d}",
                f"synthetic fragment {i} unique-token-{i:07d} benchmark corpus",
            )
            for i in range(size)
        ]
        execute_values(cur, f"INSERT INTO {table} (id, text) VALUES %s", rows, page_size=5000)
    ingestion_ms = (time.perf_counter() - ingest_start) * 1000
    index_start = time.perf_counter()
    with admin.cursor() as cur:
        cur.execute(f"CREATE INDEX {table}_trgm ON {table} USING gin (text gin_trgm_ops)")
        cur.execute(f"ANALYZE {table}")
    index_build_ms = (time.perf_counter() - index_start) * 1000

    expected = f"fragment-{size - 1:07d}"
    query = f"unique-token-{size - 1:07d}"

    def one(_: int) -> tuple[float, tuple[float, float, float]]:
        conn = psycopg2.connect(dsn)
        try:
            start = time.perf_counter()
            ranked = _query(conn, table, query)
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed, _metrics(ranked, expected)
        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        samples = list(pool.map(one, range(queries)))
    latencies = sorted(sample[0] for sample in samples)
    p95_index = min(len(latencies) - 1, int(len(latencies) * 0.95))
    metric_rows = [sample[1] for sample in samples]
    with admin.cursor() as cur:
        cur.execute(
            "SELECT pg_size_pretty(pg_table_size(%s)), pg_size_pretty(pg_indexes_size(%s)), "
            "pg_database_size(current_database())",
            (table, table),
        )
        table_size, index_size, database_size = cur.fetchone()
        cur.execute(f"DROP TABLE IF EXISTS {table}")
    admin.close()
    return {
        "fragments": size,
        "concurrency": concurrency,
        "queries": queries,
        "dataset": "SYNTHETIC_CAPACITY_DATA",
        "ingestion_ms": round(ingestion_ms, 3),
        "index_build_ms": round(index_build_ms, 3),
        "table_size": table_size,
        "index_size": index_size,
        "database_size": database_size,
        "p50_ms": round(statistics.median(latencies), 3),
        "p95_ms": round(latencies[p95_index], 3),
        "recall_at_5": round(statistics.mean(row[0] for row in metric_rows), 4),
        "recall_at_10": round(statistics.mean(row[1] for row in metric_rows), 4),
        "mrr": round(statistics.mean(row[2] for row in metric_rows), 4),
        "ndcg_at_10": round(statistics.mean(row[3] for row in metric_rows), 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("STRATUM_BENCHMARK_DSN"))
    parser.add_argument("--sizes", nargs="+", type=int, default=[10_000, 100_000, 1_000_000])
    parser.add_argument("--concurrency", type=int, default=16)
    parser.add_argument("--queries", type=int, default=100)
    parser.add_argument("--output", type=argparse.FileType("w"), help="write machine-readable JSON")
    args = parser.parse_args()
    if not args.dsn:
        parser.error("--dsn or STRATUM_BENCHMARK_DSN is required")
    print("size,concurrency,queries,p50_ms,p95_ms,recall_at_5,recall_at_10,mrr,ndcg_at_10")
    results = []
    for size in args.sizes:
        result = run_size(args.dsn, size, args.concurrency, args.queries)
        results.append(result)
        print(
            ",".join(
                str(result[key])
                for key in (
                    "fragments",
                    "concurrency",
                    "queries",
                    "p50_ms",
                    "p95_ms",
                    "recall_at_5",
                    "recall_at_10",
                    "mrr",
                    "ndcg_at_10",
                )
            )
        )
    if args.output:
        json.dump({"synthetic": True, "results": results}, args.output, indent=2)
        args.output.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
