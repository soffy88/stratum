#!/usr/bin/env python3
"""
Experiment #03: Embedding Model Comparison
Tests bge-m3 / qwen3-embedding on MIRACL-zh + custom queries.
voyage-3: SKIP (requires paid API key)
e5-mistral: SKIP (7B model, CPU-only environment too slow)
"""
import json, time, os, math, statistics
from pathlib import Path
import numpy as np

BASE = Path(__file__).parent
BENCH = BASE / "benchmarks"
BENCH.mkdir(exist_ok=True)

results = {}

# ============================================================
# Load MIRACL-zh subset (download from HuggingFace)
# ============================================================
print("=== Loading MIRACL-zh subset ===", flush=True)

MIRACL_CORPUS_PATH = BENCH / "miracl_zh_corpus.jsonl"
MIRACL_QUERIES_PATH = BENCH / "miracl_zh_queries.jsonl"
MIRACL_QRELS_PATH = BENCH / "miracl_zh_qrels.jsonl"

MIRACL_CORPUS_LIMIT = 1000


def _download_miracl_corpus():
    """Download MIRACL-zh corpus directly from raw files (no trust_remote_code)."""
    import gzip
    from huggingface_hub import hf_hub_download
    corpus = []
    for shard in range(10):
        path = hf_hub_download(
            "miracl/miracl-corpus",
            f"miracl-corpus-v1.0-zh/docs-{shard}.jsonl.gz",
            repo_type="dataset",
        )
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                if len(corpus) >= MIRACL_CORPUS_LIMIT:
                    break
                item = json.loads(line)
                corpus.append({
                    "id": item["docid"],
                    "text": (item.get("title", "") + "\n" + item["text"]).strip(),
                })
        if len(corpus) >= MIRACL_CORPUS_LIMIT:
            break
    return corpus


def _download_miracl_queries():
    """Download MIRACL-zh dev queries and qrels from raw TSV files."""
    from huggingface_hub import hf_hub_download
    queries_path = hf_hub_download(
        "miracl/miracl",
        "miracl-v1.0-zh/topics/topics.miracl-v1.0-zh-dev.tsv",
        repo_type="dataset",
    )
    qrels_path = hf_hub_download(
        "miracl/miracl",
        "miracl-v1.0-zh/qrels/qrels.miracl-v1.0-zh-dev.tsv",
        repo_type="dataset",
    )
    queries = []
    with open(queries_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 50:
                break
            qid, text = line.strip().split("\t", 1)
            queries.append({"id": qid, "text": text})

    qids = {q["id"] for q in queries}
    qrels = []
    with open(qrels_path, encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) < 4:
                continue
            qid, _iter, docid, rel = parts[:4]
            if qid in qids and int(rel) > 0:
                qrels.append({"qid": qid, "docid": docid, "rel": int(rel)})
    return queries, qrels


if not MIRACL_CORPUS_PATH.exists():
    print(f"Downloading MIRACL-zh corpus (first {MIRACL_CORPUS_LIMIT} docs)...", flush=True)
    try:
        corpus = _download_miracl_corpus()
        with open(MIRACL_CORPUS_PATH, "w", encoding="utf-8") as f:
            for c in corpus:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        print(f"Corpus: {len(corpus)} docs saved", flush=True)
    except Exception as e:
        print(f"MIRACL corpus download FAIL: {e}", flush=True)
        corpus = None
else:
    corpus = [json.loads(l) for l in MIRACL_CORPUS_PATH.read_text("utf-8").splitlines() if l.strip()]
    print(f"Corpus loaded: {len(corpus)} docs", flush=True)

if not MIRACL_QUERIES_PATH.exists():
    print("Downloading MIRACL-zh queries (dev, first 50)...", flush=True)
    try:
        queries, qrels = _download_miracl_queries()
        with open(MIRACL_QUERIES_PATH, "w", encoding="utf-8") as f:
            for q in queries:
                f.write(json.dumps(q, ensure_ascii=False) + "\n")
        with open(MIRACL_QRELS_PATH, "w", encoding="utf-8") as f:
            for r in qrels:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"Queries: {len(queries)}, qrels: {len(qrels)} saved", flush=True)
    except Exception as e:
        print(f"MIRACL query download FAIL: {e}", flush=True)
        queries = None
        qrels = None
else:
    queries = [json.loads(l) for l in MIRACL_QUERIES_PATH.read_text("utf-8").splitlines() if l.strip()]
    qrels = [json.loads(l) for l in MIRACL_QRELS_PATH.read_text("utf-8").splitlines() if l.strip()]
    print(f"Queries: {len(queries)}, qrels: {len(qrels)}", flush=True)

# ============================================================
# Part B: Custom queries (30 total)
# ============================================================
CUSTOM_QUERIES = [
    # Math (10): from S2/S3 topics
    {"id": "math-01", "text": "Marchenko-Pastur distribution eigenvalue distribution", "domain": "mathematics"},
    {"id": "math-02", "text": "biharmonic equation weak solution regularity", "domain": "mathematics"},
    {"id": "math-03", "text": "covariance matrix spectral theory random matrices", "domain": "mathematics"},
    {"id": "math-04", "text": "Brezis-Kato regularity nonlinear scalar field equations", "domain": "mathematics"},
    {"id": "math-05", "text": "strongly integrating fermions ground state instability", "domain": "mathematics"},
    {"id": "math-06", "text": "biharmonic Sobolev inequality logarithmic", "domain": "mathematics"},
    {"id": "math-07", "text": "Marchenko Pastur law free probability", "domain": "mathematics"},
    {"id": "math-08", "text": "Pohozaev manifold critical point theory", "domain": "mathematics"},
    {"id": "math-09", "text": "W^{2,2} Sobolev space biharmonic operator", "domain": "mathematics"},
    {"id": "math-10", "text": "matrix eigenvalue distribution Wigner semicircle", "domain": "mathematics"},
    # Classical Chinese (10): from S1 topics
    {"id": "zh-01", "text": "小說起源 先秦諸子 稗官野史", "domain": "classical_chinese"},
    {"id": "zh-02", "text": "魯迅 中國小說史略 章回小說", "domain": "classical_chinese"},
    {"id": "zh-03", "text": "唐代傳奇 志怪小說 古典文學", "domain": "classical_chinese"},
    {"id": "zh-04", "text": "史記 班固 藝文志 小說家", "domain": "classical_chinese"},
    {"id": "zh-05", "text": "三國演義 水滸傳 金瓶梅 章回體", "domain": "classical_chinese"},
    {"id": "zh-06", "text": "莊子 外物 飾小說以干縣令", "domain": "classical_chinese"},
    {"id": "zh-07", "text": "宋代話本 講史 小說演變", "domain": "classical_chinese"},
    {"id": "zh-08", "text": "儒林外史 諷刺小說 吳敬梓", "domain": "classical_chinese"},
    {"id": "zh-09", "text": "紅樓夢 人情小說 清代文學", "domain": "classical_chinese"},
    {"id": "zh-10", "text": "六朝志怪 干寶 搜神記 神話傳說", "domain": "classical_chinese"},
    # Mixed CN/EN (10)
    {"id": "mix-01", "text": "attention mechanism transformer self-attention 注意力机制", "domain": "mixed"},
    {"id": "mix-02", "text": "Karpathy neural network 神经网络 embedding", "domain": "mixed"},
    {"id": "mix-03", "text": "softmax temperature scaling 温度参数 概率分布", "domain": "mixed"},
    {"id": "mix-04", "text": "multi-head attention 多头注意力 query key value", "domain": "mixed"},
    {"id": "mix-05", "text": "position encoding sinusoidal 位置编码 序列模型", "domain": "mixed"},
    {"id": "mix-06", "text": "beam search decoding 束搜索 生成模型", "domain": "mixed"},
    {"id": "mix-07", "text": "cross-entropy loss 交叉熵 分类任务", "domain": "mixed"},
    {"id": "mix-08", "text": "layer normalization batch norm 归一化 训练稳定性", "domain": "mixed"},
    {"id": "mix-09", "text": "tokenizer BPE subword 分词 词汇表", "domain": "mixed"},
    {"id": "mix-10", "text": "encoder decoder architecture seq2seq 编码器解码器", "domain": "mixed"},
]

CORPUS_B_LIMIT = 300  # paragraphs per source file for Part B

# Load #01 parsed corpus for Part B retrieval
print("\nLoading #01 parsed corpus for Part B retrieval...", flush=True)
corpus_b = []
parsed = BASE / "parsed"
import re
for sid in ["S1", "S2", "S3", "S4", "S5"]:
    md = parsed / sid / "pymupdf4llm.md"
    if md.exists():
        text = md.read_text("utf-8")
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) >= 50]
        for i, p in enumerate(paras[:CORPUS_B_LIMIT]):
            corpus_b.append({"id": f"{sid}-{i}", "text": p, "domain": sid})
print(f"Part B corpus: {len(corpus_b)} paragraphs (max {CORPUS_B_LIMIT}/source)", flush=True)


# ============================================================
# nDCG@10 calculation
# ============================================================
def ndcg_at_k(retrieved_ids, relevant_ids, k=10):
    """Compute nDCG@k given retrieved doc IDs and relevant doc IDs."""
    rel_set = set(relevant_ids)
    dcg = 0.0
    for i, did in enumerate(retrieved_ids[:k]):
        if did in rel_set:
            dcg += 1.0 / math.log2(i + 2)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel_set), k)))
    return dcg / idcg if idcg > 0 else 0.0


def recall_at_k(retrieved_ids, relevant_ids, k=10):
    rel_set = set(relevant_ids)
    return len(rel_set & set(retrieved_ids[:k])) / max(len(rel_set), 1)


# ============================================================
# Evaluate a model
# ============================================================
def evaluate_model(model_name, hf_name, encode_kwargs=None):
    print(f"\n{'='*60}", flush=True)
    print(f"MODEL: {model_name}", flush=True)
    print(f"{'='*60}", flush=True)

    encode_kwargs = encode_kwargs or {}
    result = {"model": model_name}

    # Load model
    print(f"  Loading {hf_name} (CPU)...", flush=True)
    from sentence_transformers import SentenceTransformer
    t0 = time.perf_counter()
    try:
        model = SentenceTransformer(hf_name, device="cpu", trust_remote_code=True)
        load_time = time.perf_counter() - t0
        dim = model.get_sentence_embedding_dimension()
        print(f"  Loaded in {load_time:.1f}s, dim={dim}", flush=True)
        result["load_time_s"] = round(load_time, 1)
        result["dim"] = dim
    except Exception as e:
        print(f"  LOAD FAIL: {e}", flush=True)
        result["status"] = "LOAD_FAIL"
        result["error"] = str(e)
        return result

    # Part A: MIRACL-zh
    if corpus is not None and queries is not None:
        print(f"\n  Part A: MIRACL-zh ({len(corpus)} corpus, {len(queries)} queries)...", flush=True)
        # Build qrel lookup: qid → list of relevant docids
        from collections import defaultdict
        qrel_map = defaultdict(list)
        for r in qrels:
            qrel_map[r["qid"]].append(r["docid"])

        # Filter queries to those with relevant docs in our 1000-doc corpus
        corpus_ids = {c["id"] for c in corpus}
        valid_queries = [q for q in queries if any(d in corpus_ids for d in qrel_map[q["id"]])]
        print(f"  Valid queries with relevant docs in corpus: {len(valid_queries)}", flush=True)

        if len(valid_queries) == 0:
            print("  WARNING: No valid queries (relevant docs not in corpus subset). nDCG N/A.", flush=True)
            result["miracl_ndcg10"] = "N/A (no relevant docs in 1k subset)"
            result["miracl_recall10"] = "N/A"
        else:
            corpus_texts = [c["text"] for c in corpus]
            query_texts_a = [q["text"] for q in valid_queries]

            # Encode corpus
            t0 = time.perf_counter()
            c_embs = model.encode(corpus_texts, batch_size=64, show_progress_bar=False,
                                  normalize_embeddings=True, **encode_kwargs)
            corpus_encode_time = time.perf_counter() - t0
            result["corpus_encode_time_s"] = round(corpus_encode_time, 1)
            result["corpus_encode_rate"] = round(len(corpus_texts)/corpus_encode_time, 1)
            print(f"  Corpus encoded: {corpus_encode_time:.1f}s ({result['corpus_encode_rate']:.1f} docs/s)", flush=True)

            # Encode queries
            t0 = time.perf_counter()
            q_embs = model.encode(query_texts_a, batch_size=64, show_progress_bar=False,
                                  normalize_embeddings=True, **encode_kwargs)
            query_encode_time = time.perf_counter() - t0

            # Compute similarities and retrieve
            c_embs_np = np.array(c_embs)
            q_embs_np = np.array(q_embs)
            sims = q_embs_np @ c_embs_np.T  # (n_queries, n_corpus)

            ndcg_scores = []
            recall_scores = []
            query_latencies = []

            for i, q in enumerate(valid_queries):
                t0 = time.perf_counter()
                ranked_idx = np.argsort(-sims[i])[:10]
                query_latencies.append((time.perf_counter() - t0) * 1000)
                retrieved_ids = [corpus[j]["id"] for j in ranked_idx]
                relevant = qrel_map[q["id"]]
                ndcg_scores.append(ndcg_at_k(retrieved_ids, relevant, k=10))
                recall_scores.append(recall_at_k(retrieved_ids, relevant, k=10))

            result["miracl_ndcg10"] = round(statistics.mean(ndcg_scores), 4)
            result["miracl_recall10"] = round(statistics.mean(recall_scores), 4)
            result["miracl_n_valid_queries"] = len(valid_queries)
            result["query_latency_p50_ms"] = round(statistics.median(query_latencies), 3)
            print(f"  nDCG@10={result['miracl_ndcg10']}, Recall@10={result['miracl_recall10']}", flush=True)
            print(f"  Query latency p50={result['query_latency_p50_ms']}ms", flush=True)

    # Part B: Custom queries (LLM-as-judge)
    print(f"\n  Part B: Custom queries ({len(CUSTOM_QUERIES)} queries)...", flush=True)
    b_texts = [c["text"] for c in corpus_b]
    b_embs = model.encode(b_texts, batch_size=64, show_progress_bar=False,
                           normalize_embeddings=True, **encode_kwargs)
    b_embs_np = np.array(b_embs)

    q_custom_embs = model.encode([q["text"] for q in CUSTOM_QUERIES], batch_size=64,
                                  show_progress_bar=False, normalize_embeddings=True, **encode_kwargs)
    q_custom_np = np.array(q_custom_embs)
    sims_b = q_custom_np @ b_embs_np.T

    # LLM-as-judge: call Claude to assess top-3 retrieval for each query
    custom_results = []
    judge_scores = []

    try:
        import anthropic
        ac = anthropic.Anthropic()

        for i, q in enumerate(CUSTOM_QUERIES):
            top3_idx = np.argsort(-sims_b[i])[:3]
            top3_texts = [corpus_b[j]["text"][:300] for j in top3_idx]

            judge_prompt = f"""You are evaluating information retrieval quality.

Query: {q["text"]}
Domain: {q["domain"]}

Top-3 retrieved passages:
1. {top3_texts[0]}
2. {top3_texts[1]}
3. {top3_texts[2]}

For each passage, rate 1 (relevant) or 0 (not relevant) to the query.
Respond with exactly: X,X,X (three integers, comma-separated, no spaces)"""

            try:
                resp = ac.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=20,
                    messages=[{"role": "user", "content": judge_prompt}],
                )
                scores_str = resp.content[0].text.strip()
                scores = [int(s) for s in scores_str.split(",")]
                relevance = sum(scores) / 3.0
                judge_scores.append(relevance)
                custom_results.append({"query_id": q["id"], "relevance": relevance, "raw": scores_str})
            except Exception as e:
                custom_results.append({"query_id": q["id"], "relevance": None, "error": str(e)})

        if judge_scores:
            result["custom_judge_pass_rate"] = round(sum(j > 0 for j in judge_scores) / len(judge_scores), 3)
            result["custom_judge_mean_relevance"] = round(statistics.mean(judge_scores), 3)
            print(f"  LLM-judge pass rate: {result['custom_judge_pass_rate']}, mean relevance: {result['custom_judge_mean_relevance']}", flush=True)
        result["custom_query_results"] = custom_results

    except ImportError:
        print("  anthropic package not available for LLM-as-judge, using heuristic fallback", flush=True)
        # Heuristic: if top-1 sim > 0.5, likely relevant
        heuristic_pass = sum(1 for i in range(len(CUSTOM_QUERIES)) if sims_b[i].max() > 0.5)
        result["custom_judge_pass_rate"] = round(heuristic_pass / len(CUSTOM_QUERIES), 3)
        result["custom_judge_method"] = "heuristic (top1_sim > 0.5)"
        print(f"  Heuristic pass rate: {result['custom_judge_pass_rate']}", flush=True)

    # Throughput benchmark (50 texts)
    sample_texts = b_texts[:50]
    t0 = time.perf_counter()
    model.encode(sample_texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True)
    throughput_time = time.perf_counter() - t0
    result["throughput_50texts_s"] = round(throughput_time, 2)
    result["throughput_texts_per_s"] = round(50 / throughput_time, 1)
    print(f"  Throughput: {result['throughput_texts_per_s']} texts/s (50 sample)", flush=True)

    result["status"] = "OK"
    del model
    import gc; gc.collect()
    return result


# ============================================================
# Run models
# ============================================================

# voyage-3: SKIP (paid API)
results["voyage-3"] = {
    "status": "SKIP",
    "reason": "Paid API requires API key not provided. Cost: $0.06/1M tokens.",
}
print("\nvoyage-3: SKIP (paid API)", flush=True)

# e5-mistral: SKIP (7B model, no GPU)
results["e5-mistral-7b"] = {
    "status": "SKIP",
    "reason": "7B model requires GPU. WSL2 environment has CUDA driver but no GPU-capable torch.",
}
print("e5-mistral-7b: SKIP (7B, no GPU)", flush=True)

# bge-m3
results["bge-m3"] = evaluate_model("bge-m3", "BAAI/bge-m3")

# qwen3-embedding-0.6B (smaller variant feasible on CPU)
results["qwen3-embedding-0.6B"] = evaluate_model(
    "qwen3-embedding-0.6B",
    "Qwen/Qwen3-Embedding-0.6B",
    encode_kwargs={"prompt_name": "query"},
)

# Save
out_path = BENCH / "embedding_results.json"
out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\n=== DONE ===")
print(f"Results saved to {out_path}")
