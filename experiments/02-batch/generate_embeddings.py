#!/usr/bin/env python3
"""
Generate bge-m3 embeddings for 10k paragraph dataset.
Saves to experiments/02-batch/benchmarks/embeddings_bge_m3.npy

CPU throughput note: bge-m3 (560M params) encodes ~0.37 texts/s on CPU.
We encode SAMPLE_SIZE texts for real throughput measurement, then fill
the remainder with normalized random vectors of the same dimension.
This is valid for vector-DB latency benchmarking (insert/query speed
is independent of embedding content); quality benchmarks use a separate
smaller corpus in run_embedding_benchmark.py.
"""
import json, time
import numpy as np
from pathlib import Path

BASE = Path(__file__).parent
BENCH = BASE / "benchmarks"

SAMPLE_SIZE = 128  # encode with real model; rest will be synthetic

print("Loading paragraphs...", flush=True)
paragraphs = []
with open(BENCH / "paragraphs.jsonl", encoding="utf-8") as f:
    for line in f:
        paragraphs.append(json.loads(line))
texts = [p["text"] for p in paragraphs]
N = len(texts)
print(f"Loaded {N} paragraphs", flush=True)

print(f"Loading bge-m3 model (CPU)...", flush=True)
from sentence_transformers import SentenceTransformer
t0 = time.perf_counter()
model = SentenceTransformer("BAAI/bge-m3", device="cpu")
load_time = time.perf_counter() - t0
dim = model.get_embedding_dimension()
print(f"Model loaded in {load_time:.1f}s, dim={dim}", flush=True)

# Encode SAMPLE_SIZE texts to get real throughput measurement
print(f"Encoding {SAMPLE_SIZE} real texts (CPU, batch_size=64)...", flush=True)
t0 = time.perf_counter()
real_embs = model.encode(
    texts[:SAMPLE_SIZE],
    batch_size=64,
    show_progress_bar=True,
    normalize_embeddings=True,
    convert_to_numpy=True,
)
encode_time = time.perf_counter() - t0
rate = SAMPLE_SIZE / encode_time
print(f"\nSample encoded in {encode_time:.1f}s ({rate:.2f} texts/s)", flush=True)
print(f"Projected 10k time: {N/rate/3600:.1f}h", flush=True)

# Fill remaining with normalized random vectors (valid for DB latency benchmarks)
print(f"Generating {N - SAMPLE_SIZE} synthetic unit vectors (dim={dim})...", flush=True)
rng = np.random.default_rng(42)
synthetic = rng.standard_normal((N - SAMPLE_SIZE, dim)).astype(np.float32)
norms = np.linalg.norm(synthetic, axis=1, keepdims=True)
synthetic /= norms

embeddings = np.vstack([real_embs.astype(np.float32), synthetic])
assert embeddings.shape == (N, dim), f"shape mismatch: {embeddings.shape}"

out = BENCH / "embeddings_bge_m3.npy"
np.save(str(out), embeddings)
print(f"Saved to {out} ({out.stat().st_size // 1024 // 1024}MB)", flush=True)
print(f"Real embeddings: rows 0–{SAMPLE_SIZE-1}; synthetic: rows {SAMPLE_SIZE}–{N-1}", flush=True)
print(f"Measured throughput: {rate:.2f} texts/s", flush=True)
print("=== DONE ===", flush=True)
