#!/usr/bin/env python3
"""
Qwen3-Embedding-0.6B evaluation (supplement to run_embedding_benchmark.py).
Adds/replaces qwen3-embedding-0.6B entry in embedding_results.json.
Requires: transformers>=5.8.0, MIRACL data already downloaded.
"""
import json, time, math, statistics, re
from pathlib import Path
import numpy as np

BASE = Path(__file__).parent
BENCH = BASE / "benchmarks"

# Load existing results
out_path = BENCH / "embedding_results.json"
results = json.loads(out_path.read_text("utf-8")) if out_path.exists() else {}

# Load MIRACL data (already downloaded)
corpus = [json.loads(l) for l in (BENCH / "miracl_zh_corpus.jsonl").read_text("utf-8").splitlines() if l.strip()]
queries = [json.loads(l) for l in (BENCH / "miracl_zh_queries.jsonl").read_text("utf-8").splitlines() if l.strip()]
qrels = [json.loads(l) for l in (BENCH / "miracl_zh_qrels.jsonl").read_text("utf-8").splitlines() if l.strip()]
print(f"Corpus: {len(corpus)}, queries: {len(queries)}, qrels: {len(qrels)}")

# Load corpus_b
CORPUS_B_LIMIT = 300
corpus_b = []
parsed = BASE / "parsed"
for sid in ["S1", "S2", "S3", "S4", "S5"]:
    md = parsed / sid / "pymupdf4llm.md"
    if md.exists():
        text = md.read_text("utf-8")
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) >= 50]
        for i, p in enumerate(paras[:CORPUS_B_LIMIT]):
            corpus_b.append({"id": f"{sid}-{i}", "text": p, "domain": sid})
print(f"Corpus_b: {len(corpus_b)} paragraphs")

CUSTOM_QUERIES = [
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


def ndcg_at_k(retrieved_ids, relevant_ids, k=10):
    rel_set = set(relevant_ids)
    dcg = sum(1.0 / math.log2(i + 2) for i, did in enumerate(retrieved_ids[:k]) if did in rel_set)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(rel_set), k)))
    return dcg / idcg if idcg > 0 else 0.0


def recall_at_k(retrieved_ids, relevant_ids, k=10):
    rel_set = set(relevant_ids)
    return len(rel_set & set(retrieved_ids[:k])) / max(len(rel_set), 1)


print("\n" + "="*60)
print("MODEL: qwen3-embedding-0.6B")
print("="*60)

from sentence_transformers import SentenceTransformer
import os

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

t0 = time.perf_counter()
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", device="cpu", trust_remote_code=True)
load_time = time.perf_counter() - t0
dim = model.get_embedding_dimension()
print(f"Loaded in {load_time:.1f}s, dim={dim}")

result = {"model": "qwen3-embedding-0.6B", "load_time_s": round(load_time, 1), "dim": dim}

# Part A: MIRACL-zh
from collections import defaultdict
qrel_map = defaultdict(list)
for r in qrels:
    qrel_map[r["qid"]].append(r["docid"])

corpus_ids = {c["id"] for c in corpus}
valid_queries = [q for q in queries if any(d in corpus_ids for d in qrel_map[q["id"]])]
print(f"Valid MIRACL queries: {len(valid_queries)}/{len(queries)}")

corpus_texts = [c["text"] for c in corpus]
t0 = time.perf_counter()
c_embs = model.encode(corpus_texts, batch_size=64, show_progress_bar=False,
                       normalize_embeddings=True, prompt_name="query")
corpus_encode_time = time.perf_counter() - t0
rate = len(corpus_texts) / corpus_encode_time
print(f"Corpus encoded: {corpus_encode_time:.1f}s ({rate:.1f} docs/s)")
result["corpus_encode_time_s"] = round(corpus_encode_time, 1)
result["corpus_encode_rate"] = round(rate, 1)

if valid_queries:
    q_texts = [q["text"] for q in valid_queries]
    q_embs = model.encode(q_texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True, prompt_name="query")
    c_embs_np = np.array(c_embs)
    q_embs_np = np.array(q_embs)
    sims = q_embs_np @ c_embs_np.T

    ndcg_scores, recall_scores, q_lats = [], [], []
    for i, q in enumerate(valid_queries):
        t0 = time.perf_counter()
        ranked_idx = np.argsort(-sims[i])[:10]
        q_lats.append((time.perf_counter() - t0) * 1000)
        retrieved_ids = [corpus[j]["id"] for j in ranked_idx]
        relevant = qrel_map[q["id"]]
        ndcg_scores.append(ndcg_at_k(retrieved_ids, relevant))
        recall_scores.append(recall_at_k(retrieved_ids, relevant))

    result["miracl_ndcg10"] = round(statistics.mean(ndcg_scores), 4)
    result["miracl_recall10"] = round(statistics.mean(recall_scores), 4)
    result["miracl_n_valid_queries"] = len(valid_queries)
    result["query_latency_p50_ms"] = round(statistics.median(q_lats), 3)
    print(f"nDCG@10={result['miracl_ndcg10']}, Recall@10={result['miracl_recall10']}")
else:
    result["miracl_ndcg10"] = "N/A"
    result["miracl_recall10"] = "N/A"
    print("No valid queries in corpus subset")

# Part B: Custom queries with LLM-as-judge
print(f"\nPart B: Custom queries ({len(CUSTOM_QUERIES)} queries)...")
b_texts = [c["text"] for c in corpus_b]
b_embs = model.encode(b_texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True, prompt_name="query")
b_embs_np = np.array(b_embs)

q_custom_embs = model.encode([q["text"] for q in CUSTOM_QUERIES], batch_size=64,
                               show_progress_bar=False, normalize_embeddings=True, prompt_name="query")
q_custom_np = np.array(q_custom_embs)
sims_b = q_custom_np @ b_embs_np.T

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
            if (i + 1) % 5 == 0:
                print(f"  Judge: {i+1}/{len(CUSTOM_QUERIES)} done", flush=True)
        except Exception as e:
            custom_results.append({"query_id": q["id"], "relevance": None, "error": str(e)})

    if judge_scores:
        result["custom_judge_pass_rate"] = round(sum(j > 0 for j in judge_scores) / len(judge_scores), 3)
        result["custom_judge_mean_relevance"] = round(statistics.mean(judge_scores), 3)
        result["custom_judge_method"] = "LLM (claude-haiku-4-5-20251001)"
        print(f"LLM-judge pass rate: {result['custom_judge_pass_rate']}, mean relevance: {result['custom_judge_mean_relevance']}")
    result["custom_query_results"] = custom_results

except ImportError:
    heuristic_pass = sum(1 for i in range(len(CUSTOM_QUERIES)) if sims_b[i].max() > 0.5)
    result["custom_judge_pass_rate"] = round(heuristic_pass / len(CUSTOM_QUERIES), 3)
    result["custom_judge_method"] = "heuristic (top1_sim > 0.5)"
    print(f"Heuristic pass rate: {result['custom_judge_pass_rate']}")

# Throughput benchmark
sample_texts = b_texts[:50]
t0 = time.perf_counter()
model.encode(sample_texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True, prompt_name="query")
throughput_time = time.perf_counter() - t0
result["throughput_50texts_s"] = round(throughput_time, 2)
result["throughput_texts_per_s"] = round(50 / throughput_time, 1)
print(f"Throughput: {result['throughput_texts_per_s']} texts/s (50 sample)")

result["status"] = "OK"

# Update results file
results["qwen3-embedding-0.6B"] = result
out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nResults saved to {out_path}")
print(f"\nbge-m3 vs qwen3 summary:")
for m in ["bge-m3", "qwen3-embedding-0.6B"]:
    r = results.get(m, {})
    if r.get("status") == "OK":
        print(f"  {m}: nDCG@10={r.get('miracl_ndcg10', 'N/A')}, pass_rate={r.get('custom_judge_pass_rate', 'N/A')}, tput={r.get('throughput_texts_per_s', 'N/A')} texts/s")
print("=== DONE ===")
