#!/usr/bin/env python3
"""Disposable capacity probe for the production retrieval boundaries.

The corpus is synthetic and isolated in a disposable PostgreSQL database.  It
uses the production layer-vector SQL, the production lexical SQL, the actual
RRF fusion function, and the KnowledgeView final wrapper.  Chunk/claim tables
are present but empty because this probe targets the canonical layer corpus;
that limitation is retained in the output instead of being hidden.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psycopg2

from stratum.services.knowledge_view import KnowledgeViewRequest, search_knowledge_view
from stratum.services.retrieval_engine import (
    _rrf_merge_channels,
    _text_search_layers,
    _vector_search_layers,
)

USER = "p2-benchmark-user"
DIM = 1024
SIZES = (10_000, 100_000, 1_000_000)
MODES = ("vector", "hybrid", "final")
CONCURRENCY_LEVELS = (1, 4, 8, 16, 32)
CONCURRENT_REQUESTS = 10
P99_MIN_SAMPLES = 100
DSN = ""


def _connect():
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    with conn.cursor() as cur:
        # Keep a pathological capacity run bounded.  A timeout is recorded as
        # a failed request by the harness, never converted into a result.
        cur.execute("SET statement_timeout = '120s'")
        cur.execute("SET work_mem = '4MB'")
        cur.execute("SET ivfflat.probes = 1")
    return conn


def _reset_schema(size: int) -> None:
    conn = _connect()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS stratum CASCADE")
        cur.execute("CREATE SCHEMA stratum")
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        cur.execute(
            """CREATE UNLOGGED TABLE stratum.substrates (
                id text PRIMARY KEY,
                user_id text NOT NULL,
                title text,
                source_path text
            )"""
        )
        cur.execute(
            """CREATE UNLOGGED TABLE stratum.substrate_layers (
                substrate_id text NOT NULL,
                layer text NOT NULL,
                content text NOT NULL,
                token_count integer NOT NULL,
                embedding vector(1024)
            )"""
        )
        cur.execute(
            """CREATE UNLOGGED TABLE stratum.substrate_chunk (
                id text PRIMARY KEY,
                substrate_id text NOT NULL,
                text text NOT NULL,
                chunk_idx integer NOT NULL,
                embedding vector(1024)
            )"""
        )
        cur.execute(
            """CREATE TABLE stratum.context_directory (
                id text PRIMARY KEY,
                uri text,
                parent_id text,
                ref_id text,
                node_type text,
                l0_content text
            )"""
        )
        cur.execute(
            """CREATE TABLE stratum.retrieval_trajectories (
                id text PRIMARY KEY,
                user_id text,
                query text,
                query_embedding real[],
                results jsonb,
                trajectory jsonb,
                total_ms integer,
                result_count integer,
                created_at timestamptz DEFAULT now()
            )"""
        )
        cur.execute(
            "CREATE TABLE stratum.knowledge_claims (id text, user_id text, statement text, deleted_at timestamptz)"
        )
        cur.execute("CREATE TABLE stratum.claim_evidence (claim_id text, evidence_id text)")
        cur.execute(
            "CREATE TABLE stratum.evidence (id text, substrate_id text, quote text, user_id text)"
        )
        cur.execute(
            """INSERT INTO stratum.substrates (id, user_id, title, source_path)
               SELECT 'source-' || i, %s,
                      'synthetic fragment ' || i || ' unique-token-' || lpad(i::text, 7, '0'),
                      '/synthetic/source-' || i
               FROM generate_series(0, %s) AS g(i)""",
            (USER, size - 1),
        )
        seed_end = min(size, 100_000)
        cur.execute(
            """INSERT INTO stratum.substrate_layers
               (substrate_id, layer, content, token_count, embedding)
               SELECT 'source-' || i, 'L0',
                      'synthetic fragment ' || i || ' unique-token-' || lpad(i::text, 7, '0') || ' benchmark corpus',
                      10,
                      array_fill((0.01 + ((i %% 100)::real / 10000)), ARRAY[1024])::vector(1024)
               FROM generate_series(0, %s) AS g(i)""",
            (seed_end - 1,),
        )
        cur.execute(
            "CREATE INDEX p2_vector_idx ON stratum.substrate_layers USING ivfflat (embedding vector_cosine_ops) WITH (lists=100)"
        )
        if size > seed_end:
            cur.execute(
                """INSERT INTO stratum.substrate_layers
                   (substrate_id, layer, content, token_count, embedding)
                   SELECT 'source-' || i, 'L0',
                          'synthetic fragment ' || i || ' unique-token-' || lpad(i::text, 7, '0') || ' benchmark corpus',
                          10,
                          array_fill((0.01 + ((i %% 100)::real / 10000)), ARRAY[1024])::vector(1024)
                   FROM generate_series(%s, %s) AS g(i)""",
                (seed_end, size - 1),
            )
        # Materialise one canonical text fragment per synthetic source so the
        # final KnowledgeView run exercises the production fragment lexical
        # channel as well as the layer channels.  Fragment vectors remain NULL
        # deliberately: the canonical vector index under qualification is the
        # layer index; this is stated in the output rather than hidden.
        cur.execute(
            """INSERT INTO stratum.substrate_chunk
               (id, substrate_id, text, chunk_idx, embedding)
               SELECT 'source-' || i || '#0', 'source-' || i,
                      'synthetic fragment ' || i || ' unique-token-' || lpad(i::text, 7, '0') || ' benchmark corpus',
                      0, NULL
               FROM generate_series(0, %s) AS g(i)""",
            (size - 1,),
        )
        cur.execute(
            "CREATE INDEX p2_chunk_trgm ON stratum.substrate_chunk USING gin (text gin_trgm_ops)"
        )
        cur.execute(
            "CREATE INDEX p2_layer_trgm ON stratum.substrate_layers USING gin (content gin_trgm_ops)"
        )
        cur.execute(
            "CREATE INDEX p2_title_trgm ON stratum.substrates USING gin (title gin_trgm_ops)"
        )
        cur.execute("ANALYZE stratum.substrates")
        cur.execute("ANALYZE stratum.substrate_layers")
    conn.close()


def _query(size: int) -> str:
    return f"unique-token-{size - 1:07d}"


def _vector() -> list[float]:
    return [0.01] * DIM


def _run_mode(mode: str, size: int) -> list[float]:
    query = _query(size)
    vector = _vector()

    def call() -> None:
        if mode == "vector":
            result = _vector_search_layers(vector, "L0", top_k=10, user_id=USER)
            if not result:
                raise RuntimeError("vector query returned no rows or failed closed")
        elif mode == "hybrid":
            dense = _vector_search_layers(vector, "L0", top_k=50, user_id=USER)
            lexical = _text_search_layers(query, "L0", top_k=50, user_id=USER)
            if not dense:
                raise RuntimeError("hybrid dense channel returned no rows or failed closed")
            _rrf_merge_channels({"dense_l0": dense, "lexical_l0": lexical}, top_k=10)
        else:
            result = search_knowledge_view(
                KnowledgeViewRequest(
                    query=query,
                    top_k=10,
                    scopes=["lexical", "dense"],
                    user_id=USER,
                    query_embedding=vector,
                )
            )
            if not result.get("results"):
                raise RuntimeError("final pipeline returned no rows or failed closed")

    for _ in range(5):
        call()
    samples = []
    for _ in range(20):
        start = time.perf_counter()
        call()
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def _percentile(values: list[float], fraction: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * fraction))]


def _p99(values: list[float]) -> float | str:
    if len(values) < P99_MIN_SAMPLES:
        return "INSUFFICIENT_SAMPLE_SIZE"
    return round(_percentile(values, 0.99), 3)


def _plan(size: int) -> dict:
    conn = _connect()
    with conn.cursor() as cur:
        query_vector = "[" + ",".join("0.01" for _ in range(DIM)) + "]"
        cur.execute(
            """EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
               SELECT sl.substrate_id
               FROM stratum.substrate_layers sl
               JOIN stratum.substrates s ON s.id = sl.substrate_id
               WHERE sl.layer = 'L0' AND sl.embedding IS NOT NULL
                 AND s.user_id = %s
               ORDER BY sl.embedding <=> %s::vector
               LIMIT 10""",
            (USER, query_vector),
        )
        plan = cur.fetchone()[0]
        if isinstance(plan, str):
            try:
                plan = json.loads(plan)
            except json.JSONDecodeError:
                plan = ast.literal_eval(plan)
        plan = plan[0]
    conn.close()
    root = plan["Plan"]
    nodes: list[str] = []
    indexes: list[str] = []

    def walk(node: dict) -> None:
        nodes.append(node.get("Node Type", ""))
        if node.get("Index Name"):
            indexes.append(node["Index Name"])
        for child in node.get("Plans", []):
            walk(child)

    walk(root)
    return {
        "size": size,
        "nodes": nodes,
        "indexes": indexes,
        "actual_total_time_ms": root.get("Actual Total Time"),
        "plan": plan,
    }


def _concurrency(
    mode: str, size: int, concurrency: int, requests: int = CONCURRENT_REQUESTS
) -> dict:
    query = _query(size)
    vector = _vector()

    def call(_: int) -> float:
        started = time.perf_counter()
        if mode == "vector":
            result = _vector_search_layers(vector, "L0", top_k=10, user_id=USER)
            if not result:
                raise RuntimeError("vector query returned no rows or failed closed")
        elif mode == "hybrid":
            dense = _vector_search_layers(vector, "L0", top_k=50, user_id=USER)
            lexical = _text_search_layers(query, "L0", top_k=50, user_id=USER)
            if not dense:
                raise RuntimeError("hybrid dense channel returned no rows or failed closed")
            _rrf_merge_channels({"dense_l0": dense, "lexical_l0": lexical}, top_k=10)
        else:
            result = search_knowledge_view(
                KnowledgeViewRequest(
                    query=query,
                    top_k=10,
                    scopes=["lexical", "dense"],
                    user_id=USER,
                    query_embedding=vector,
                )
            )
            if not result.get("results"):
                raise RuntimeError("final pipeline returned no rows or failed closed")
        return (time.perf_counter() - started) * 1000

    start = time.perf_counter()
    errors = 0
    timeouts = 0
    samples: list[float] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(call, index) for index in range(requests)]
        for future in futures:
            try:
                samples.append(future.result())
            except psycopg2.errors.QueryCanceled:
                errors += 1
                timeouts += 1
            except Exception:
                errors += 1
    elapsed = time.perf_counter() - start
    result = {
        "mode": mode,
        "concurrency": concurrency,
        "requests": requests,
        "duration_s": round(elapsed, 3),
        "qps": round(len(samples) / elapsed, 3),
        "errors": errors,
        "timeout_count": timeouts,
        "completed_requests": len(samples),
        "sample_count": len(samples),
    }
    if samples:
        result.update(
            {
                "p50_ms": round(statistics.median(samples), 3),
                "p95_ms": round(_percentile(samples, 0.95), 3),
                "p99_ms": _p99(samples),
            }
        )
    else:
        result.update({"p50_ms": None, "p95_ms": None, "p99_ms": None})
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dsn",
        default=os.environ.get("P2_BENCHMARK_DSN"),
    )
    parser.add_argument("--output", default="/tmp/p2_vector_hybrid_final_capacity.json")
    args = parser.parse_args()
    if not args.dsn:
        parser.error("--dsn or P2_BENCHMARK_DSN is required")
    global DSN
    DSN = args.dsn
    results = []
    plans = []
    concurrency = []
    for size in SIZES:
        _reset_schema(size)
        plans.append(_plan(size))
        for mode in MODES:
            samples = _run_mode(mode, size)
            results.append(
                {
                    "dataset": "SYNTHETIC_CAPACITY_DATA",
                    "size": size,
                    "mode": mode,
                    "p50_ms": round(statistics.median(samples), 3),
                    "p95_ms": round(_percentile(samples, 0.95), 3),
                    "p99_ms": _p99(samples),
                    "samples": len(samples),
                    "reranker": "disabled",
                }
            )
        if size == 1_000_000:
            for mode in MODES:
                for c in CONCURRENCY_LEVELS:
                    concurrency.append(_concurrency(mode, size, c))
    payload = {
        "dataset": "SYNTHETIC_CAPACITY_DATA",
        "dimension": DIM,
        "user": USER,
        "fusion": "_rrf_merge_channels",
        "final_pipeline": "KnowledgeView -> retrieve -> layer lexical/dense -> RRF -> anchor/provenance normalization",
        "chunk_and_claim_tables": "one text-only canonical fragment per source; claim/evidence tables empty",
        "fragment_vector_coverage": "NULL (layer IVFFlat is the measured canonical dense index)",
        "results": results,
        "plans": plans,
        "concurrency": concurrency,
    }
    Path(args.output).write_text(json.dumps(payload, indent=2))
    for result in results:
        print(result)
    for result in concurrency:
        print(result)
    for plan in plans:
        print("PLAN", plan["size"], plan["nodes"], plan["indexes"])


if __name__ == "__main__":
    main()
