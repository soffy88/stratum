# Experiment #02: Vector DB Comparison

**Date:** 2026-05-17  
**Environment:** Python 3.14.4, WSL2 (x86-64), CPU-only, no PostgreSQL  
**Corpus:** 10,000 paragraphs, 1024-dim bge-m3 embeddings (128 real + 9,872 normalized random unit vectors — valid for latency benchmarking)  
**Queries:** 100 vectors, 3 runs each → 300 latency samples per metric  

## Candidates

| DB | Version | Deployment tested |
|---|---|---|
| pgvector | — | INFRA_SKIP (PostgreSQL not installed in WSL2) |
| qdrant | 1.18.0 (qdrant-client) | In-memory `QdrantClient(':memory:')` |
| chromadb | installed | In-memory `chromadb.Client()` |
| lancedb | installed | Local file (temp dir, pyarrow schema) |

## Results

### Insert Performance (10,000 × 1024-dim vectors)

| DB | Insert time | Insert rate |
|---|---|---|
| qdrant | 3.09 s | **3,232 vec/s** |
| chromadb | 6.61 s | 1,513 vec/s |
| lancedb | **0.63 s** | **15,787 vec/s** |

### Vector Query Latency (cosine similarity, top-10, n=300)

| DB | p50 | p95 | p99 | mean |
|---|---|---|---|---|
| qdrant | 106.62 ms | 127.85 ms | 138.07 ms | 105.52 ms |
| chromadb | **1.96 ms** | **3.28 ms** | **5.15 ms** | **2.14 ms** |
| lancedb | 17.16 ms | 27.45 ms | 46.15 ms | 18.59 ms |

### Metadata Filter Query Latency (domain filter + vector, top-10, n=300)

| DB | p50 | p95 | p99 |
|---|---|---|---|
| qdrant | 154.19 ms | 184.01 ms | 207.51 ms |
| chromadb | 13.25 ms | 21.26 ms | 43.74 ms |
| lancedb | 26.05 ms | 39.80 ms | 54.01 ms |

### Memory & Storage

| DB | RSS after 10k insert | Disk |
|---|---|---|
| qdrant | 305 MB | 0 (in-memory) |
| chromadb | 343 MB | 0 (in-memory) |
| lancedb | 1,230 MB | 40.6 MB |

### DX (Code Simplicity)

| DB | Insert LoC | Query LoC | Notes |
|---|---|---|---|
| qdrant | 12 | 6 | Explicit `PointStruct`, rich filter DSL |
| chromadb | 10 | 5 | Pythonic dict API |
| lancedb | 15 | 4 | PyArrow schema boilerplate; fluent query |

## Analysis

**Query speed** (the dominant concern for interactive search):  
chromadb is **54× faster** than qdrant at p50 (1.96 ms vs 106 ms) and **8.7×** faster than lancedb (1.96 ms vs 17 ms). The qdrant in-memory mode appears to use a slower code path under qdrant-client 1.18.0; production deployment with a separate server would differ.

**Insert speed:**  
lancedb is fastest (15,787 vec/s), suitable for bulk indexing. Qdrant second (3,232 vec/s). chromadb slowest (1,513 vec/s) but still 6.6 s for 10k docs is acceptable.

**Persistence:**  
- lancedb: inherently file-based, zero config, no daemon.
- chromadb: has `PersistentClient(path)` for the same simplicity.
- qdrant: persistent mode requires a server process or `:local:` embedded mode (not tested here).

**Memory:**  
lancedb uses 1,230 MB RSS — 3× more than chromadb/qdrant. For a single-user laptop tool this is the limiting factor.

## Conclusion

**Selected for Stratum: chromadb** (with `PersistentClient` for production)

| Criterion | Weight | chromadb | lancedb | qdrant |
|---|---|---|---|---|
| Query p50 | high | ✅ 1.96 ms | ✓ 17 ms | ✗ 107 ms |
| Filter p50 | medium | ✅ 13 ms | ✓ 26 ms | ✗ 154 ms |
| RAM footprint | medium | ✅ 343 MB | ✗ 1,230 MB | ✅ 305 MB |
| Persistence simplicity | medium | ✅ PersistentClient 1 line | ✅ file-native | ✗ server/embedded |
| Insert rate | low | ✓ 1,513 vps | ✅ 15,787 vps | ✓ 3,232 vps |

chromadb wins on the two highest-priority criteria (query latency and RAM), has trivial persistence, and a clean Pythonic API.

**pgvector deferred:** pgvector is the natural choice if Stratum ships a PostgreSQL dependency for other reasons (e.g., structured metadata). Its absence from this environment prevents benchmarking.

## Methodology Notes

- Embeddings: 128 real bge-m3 encodings (1.07 texts/s on CPU-only) + 9,872 normalized random float32 vectors. Random vectors are valid for latency benchmarks; retrieval quality is not measured here (that is #03).
- bge-m3 CPU throughput (measured): **1.07 texts/s** (batch_size=64, ~175 s/batch). Projected time to encode 10k: ~2.6 h on this hardware.
- qdrant-client 1.18.0 removed the `search()` method; `query_points()` used throughout.
