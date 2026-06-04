#!/usr/bin/env python3
"""
Re-run bge-m3 Part B with LLM-as-judge (anthropic now installed).
Updates only the Part B fields in embedding_results.json.
"""
import json, time, math, statistics, re, os
from pathlib import Path
import numpy as np

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

BASE = Path(__file__).parent
BENCH = BASE / "benchmarks"

out_path = BENCH / "embedding_results.json"
results = json.loads(out_path.read_text("utf-8"))

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
print(f"Corpus_b: {len(corpus_b)} paragraphs", flush=True)

print("Loading bge-m3...", flush=True)
from sentence_transformers import SentenceTransformer
t0 = time.perf_counter()
model = SentenceTransformer("BAAI/bge-m3", device="cpu")
print(f"Loaded in {time.perf_counter()-t0:.1f}s", flush=True)

b_texts = [c["text"] for c in corpus_b]
print(f"Encoding corpus_b ({len(b_texts)} texts)...", flush=True)
t0 = time.perf_counter()
b_embs = model.encode(b_texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)
print(f"\nCorpus_b encoded: {time.perf_counter()-t0:.1f}s", flush=True)
b_embs_np = np.array(b_embs)

print(f"Encoding {len(CUSTOM_QUERIES)} custom queries...", flush=True)
q_custom_embs = model.encode([q["text"] for q in CUSTOM_QUERIES], batch_size=64,
                               show_progress_bar=False, normalize_embeddings=True)
q_custom_np = np.array(q_custom_embs)
sims_b = q_custom_np @ b_embs_np.T

import anthropic
ac = anthropic.Anthropic()

custom_results = []
judge_scores = []

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
    pass_rate = round(sum(j > 0 for j in judge_scores) / len(judge_scores), 3)
    mean_rel = round(statistics.mean(judge_scores), 3)
    print(f"bge-m3 LLM-judge: pass_rate={pass_rate}, mean_relevance={mean_rel}", flush=True)

    results["bge-m3"]["custom_judge_pass_rate"] = pass_rate
    results["bge-m3"]["custom_judge_mean_relevance"] = mean_rel
    results["bge-m3"]["custom_judge_method"] = "LLM (claude-haiku-4-5-20251001)"
    results["bge-m3"]["custom_query_results"] = custom_results

    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {out_path}", flush=True)

print("=== DONE ===", flush=True)
