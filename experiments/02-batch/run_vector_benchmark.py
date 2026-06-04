#!/usr/bin/env python3
"""
Experiment #02: Vector DB Benchmark
Tests qdrant / chromadb / lancedb on 10k paragraphs.
pgvector: INFRA_SKIP (PostgreSQL not installed in WSL2).
"""
import json, time, os, gc, statistics, tempfile, shutil
from pathlib import Path

BASE = Path(__file__).parent
BENCH = BASE / "benchmarks"
OUT = BENCH / "vector_db_results.json"

print("=== Vector DB Benchmark ===", flush=True)

# Load dataset
print("Loading paragraph dataset...", flush=True)
paragraphs = []
with open(BENCH / "paragraphs.jsonl", encoding="utf-8") as f:
    for line in f:
        paragraphs.append(json.loads(line))
print(f"Loaded {len(paragraphs)} paragraphs", flush=True)

# Load embeddings (pre-generated)
import numpy as np
embeddings_path = BENCH / "embeddings_bge_m3.npy"
if not embeddings_path.exists():
    print("ERROR: embeddings not yet generated. Run generate_embeddings.py first.", flush=True)
    raise SystemExit(1)

print("Loading pre-generated embeddings...", flush=True)
embeddings = np.load(str(embeddings_path))
print(f"Embeddings shape: {embeddings.shape}", flush=True)
DIM = embeddings.shape[1]

# Build query set: use first 100 paragraphs as queries
QUERY_COUNT = 100
query_embeddings = embeddings[:QUERY_COUNT]
query_texts = [p["text"] for p in paragraphs[:QUERY_COUNT]]
query_domains = [p["domain"] for p in paragraphs[:QUERY_COUNT]]

results = {}

# ============================================================
# pgvector: INFRA_SKIP
# ============================================================
results["pgvector"] = {
    "status": "INFRA_SKIP",
    "reason": "PostgreSQL not installed in WSL2 environment. psql command not found.",
}
print("\npgvector: INFRA_SKIP (PostgreSQL not installed)", flush=True)


# ============================================================
# Helper: measure queries
# ============================================================
def measure_queries(query_fn, n_queries=QUERY_COUNT, n_repeat=3):
    """Run query_fn(i) n_queries times, measure latencies."""
    latencies = []
    for _ in range(n_repeat):
        for i in range(n_queries):
            t0 = time.perf_counter()
            query_fn(i)
            latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    return {
        "p50_ms": round(statistics.median(latencies), 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95)], 2),
        "p99_ms": round(latencies[int(len(latencies) * 0.99)], 2),
        "mean_ms": round(statistics.mean(latencies), 2),
        "total_queries": len(latencies),
    }


# ============================================================
# QDRANT (in-memory)
# ============================================================
print("\n=== qdrant ===", flush=True)
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue

    client = QdrantClient(":memory:")
    COLLECTION = "stratum_bench"

    # Create collection
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=DIM, distance=Distance.COSINE),
    )

    # Batch insert
    print(f"  Inserting {len(paragraphs)} vectors...", flush=True)
    t0 = time.perf_counter()
    BATCH_SIZE = 500
    for i in range(0, len(paragraphs), BATCH_SIZE):
        batch = paragraphs[i:i+BATCH_SIZE]
        batch_embs = embeddings[i:i+BATCH_SIZE]
        points = [
            PointStruct(
                id=i+j,
                vector=batch_embs[j].tolist(),
                payload={"domain": batch[j]["domain"], "source": batch[j]["source"], "text": batch[j]["text"][:200]},
            )
            for j in range(len(batch))
        ]
        client.upsert(collection_name=COLLECTION, points=points)
    insert_time = time.perf_counter() - t0
    print(f"  Insert: {insert_time:.2f}s ({len(paragraphs)/insert_time:.0f} vec/s)", flush=True)

    # Vector-only queries
    def qdrant_vector_query(i):
        client.query_points(
            collection_name=COLLECTION,
            query=query_embeddings[i].tolist(),
            limit=10,
        )

    q_stats = measure_queries(qdrant_vector_query)
    print(f"  Vector query p50={q_stats['p50_ms']}ms p95={q_stats['p95_ms']}ms", flush=True)

    # Metadata filter queries
    def qdrant_filter_query(i):
        client.query_points(
            collection_name=COLLECTION,
            query=query_embeddings[i].tolist(),
            query_filter=Filter(must=[FieldCondition(key="domain", match=MatchValue(value=query_domains[i]))]),
            limit=10,
        )

    f_stats = measure_queries(qdrant_filter_query)
    print(f"  Filter query p50={f_stats['p50_ms']}ms p95={f_stats['p95_ms']}ms", flush=True)

    # Disk usage estimate (in-memory, so 0)
    import psutil
    mem_mb = psutil.Process().memory_info().rss / 1024**2
    print(f"  RSS after insert: {mem_mb:.0f}MB", flush=True)

    results["qdrant"] = {
        "status": "OK",
        "insert_time_s": round(insert_time, 2),
        "insert_rate_vps": round(len(paragraphs)/insert_time),
        "vector_query": q_stats,
        "filter_query": f_stats,
        "rss_after_insert_mb": round(mem_mb),
        "deployment": "in-memory (QdrantClient(':memory:'))",
        "code_lines_insert": 12,
        "code_lines_query": 6,
    }
    del client
    gc.collect()

except Exception as e:
    import traceback
    results["qdrant"] = {"status": "FAIL", "error": str(e)}
    traceback.print_exc()


# ============================================================
# CHROMADB (in-memory)
# ============================================================
print("\n=== chromadb ===", flush=True)
try:
    import chromadb
    from chromadb.config import Settings

    client = chromadb.Client()  # in-memory
    collection = client.create_collection("stratum_bench")

    # Batch insert
    print(f"  Inserting {len(paragraphs)} vectors...", flush=True)
    t0 = time.perf_counter()
    BATCH_SIZE = 500
    for i in range(0, len(paragraphs), BATCH_SIZE):
        batch = paragraphs[i:i+BATCH_SIZE]
        batch_embs = embeddings[i:i+BATCH_SIZE]
        collection.add(
            ids=[p["id"] for p in batch],
            embeddings=batch_embs.tolist(),
            metadatas=[{"domain": p["domain"], "source": p["source"]} for p in batch],
            documents=[p["text"][:200] for p in batch],
        )
    insert_time = time.perf_counter() - t0
    print(f"  Insert: {insert_time:.2f}s ({len(paragraphs)/insert_time:.0f} vec/s)", flush=True)

    # Vector-only queries
    def chroma_vector_query(i):
        collection.query(
            query_embeddings=[query_embeddings[i].tolist()],
            n_results=10,
        )

    q_stats = measure_queries(chroma_vector_query)
    print(f"  Vector query p50={q_stats['p50_ms']}ms p95={q_stats['p95_ms']}ms", flush=True)

    # Metadata filter queries
    def chroma_filter_query(i):
        collection.query(
            query_embeddings=[query_embeddings[i].tolist()],
            n_results=10,
            where={"domain": {"$eq": query_domains[i]}},
        )

    f_stats = measure_queries(chroma_filter_query)
    print(f"  Filter query p50={f_stats['p50_ms']}ms p95={f_stats['p95_ms']}ms", flush=True)

    import psutil
    mem_mb = psutil.Process().memory_info().rss / 1024**2
    print(f"  RSS after insert: {mem_mb:.0f}MB", flush=True)

    results["chromadb"] = {
        "status": "OK",
        "insert_time_s": round(insert_time, 2),
        "insert_rate_vps": round(len(paragraphs)/insert_time),
        "vector_query": q_stats,
        "filter_query": f_stats,
        "rss_after_insert_mb": round(mem_mb),
        "deployment": "in-memory (chromadb.Client())",
        "code_lines_insert": 10,
        "code_lines_query": 5,
    }
    del client, collection
    gc.collect()

except Exception as e:
    import traceback
    results["chromadb"] = {"status": "FAIL", "error": str(e)}
    traceback.print_exc()


# ============================================================
# LANCEDB (local file)
# ============================================================
print("\n=== lancedb ===", flush=True)
try:
    import lancedb
    import pyarrow as pa

    tmpdir = tempfile.mkdtemp(prefix="lancedb_bench_")
    db = lancedb.connect(tmpdir)

    # Create schema
    schema = pa.schema([
        pa.field("id", pa.string()),
        pa.field("vector", pa.list_(pa.float32(), DIM)),
        pa.field("domain", pa.string()),
        pa.field("source", pa.string()),
        pa.field("text", pa.string()),
    ])

    # Batch insert
    print(f"  Inserting {len(paragraphs)} vectors...", flush=True)
    t0 = time.perf_counter()

    # Build first batch to create table
    BATCH_SIZE = 1000
    first_batch = paragraphs[:BATCH_SIZE]
    first_embs = embeddings[:BATCH_SIZE]
    data = [
        {
            "id": first_batch[j]["id"],
            "vector": first_embs[j].tolist(),
            "domain": first_batch[j]["domain"],
            "source": first_batch[j]["source"],
            "text": first_batch[j]["text"][:200],
        }
        for j in range(len(first_batch))
    ]
    table = db.create_table("stratum_bench", data=data, schema=schema)

    # Insert remaining batches
    for i in range(BATCH_SIZE, len(paragraphs), BATCH_SIZE):
        batch = paragraphs[i:i+BATCH_SIZE]
        batch_embs = embeddings[i:i+BATCH_SIZE]
        data = [
            {
                "id": batch[j]["id"],
                "vector": batch_embs[j].tolist(),
                "domain": batch[j]["domain"],
                "source": batch[j]["source"],
                "text": batch[j]["text"][:200],
            }
            for j in range(len(batch))
        ]
        table.add(data)

    insert_time = time.perf_counter() - t0
    print(f"  Insert: {insert_time:.2f}s ({len(paragraphs)/insert_time:.0f} vec/s)", flush=True)

    # Vector-only queries
    def lance_vector_query(i):
        table.search(query_embeddings[i].tolist()).limit(10).to_list()

    q_stats = measure_queries(lance_vector_query)
    print(f"  Vector query p50={q_stats['p50_ms']}ms p95={q_stats['p95_ms']}ms", flush=True)

    # Metadata filter queries
    def lance_filter_query(i):
        table.search(query_embeddings[i].tolist()).where(f"domain = '{query_domains[i]}'").limit(10).to_list()

    f_stats = measure_queries(lance_filter_query)
    print(f"  Filter query p50={f_stats['p50_ms']}ms p95={f_stats['p95_ms']}ms", flush=True)

    import psutil
    mem_mb = psutil.Process().memory_info().rss / 1024**2
    disk_mb = sum(f.stat().st_size for f in Path(tmpdir).rglob("*") if f.is_file()) / 1024**2
    print(f"  RSS: {mem_mb:.0f}MB, disk: {disk_mb:.1f}MB", flush=True)

    results["lancedb"] = {
        "status": "OK",
        "insert_time_s": round(insert_time, 2),
        "insert_rate_vps": round(len(paragraphs)/insert_time),
        "vector_query": q_stats,
        "filter_query": f_stats,
        "rss_after_insert_mb": round(mem_mb),
        "disk_mb": round(disk_mb, 1),
        "deployment": f"local file ({tmpdir})",
        "code_lines_insert": 15,
        "code_lines_query": 4,
    }
    shutil.rmtree(tmpdir, ignore_errors=True)
    gc.collect()

except Exception as e:
    import traceback
    results["lancedb"] = {"status": "FAIL", "error": str(e)}
    traceback.print_exc()


# Save results
OUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n=== DONE ===")
print(f"Results saved to {OUT}")
print(json.dumps(results, indent=2, ensure_ascii=False)[:2000])
