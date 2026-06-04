#!/usr/bin/env python3
"""
Patch: compute heuristic custom_judge_pass_rate for qwen3-embedding-0.6B
if LLM-as-judge failed (no API key). Adds heuristic from top-1 cosine sim.
"""
import json, re, os
from pathlib import Path
import numpy as np

os.environ["HF_HUB_DISABLE_XET"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"

BASE = Path(__file__).parent
BENCH = BASE / "benchmarks"

results = json.loads((BENCH / "embedding_results.json").read_text("utf-8"))
qwen3 = results.get("qwen3-embedding-0.6B", {})

if "custom_judge_pass_rate" in qwen3:
    print(f"qwen3 already has custom_judge_pass_rate={qwen3['custom_judge_pass_rate']}, no patch needed")
    exit(0)

if qwen3.get("status") != "OK":
    print(f"qwen3 status={qwen3.get('status')}, cannot patch")
    exit(1)

CUSTOM_QUERIES = [
    {"id": "math-01", "text": "Marchenko-Pastur distribution eigenvalue distribution"},
    {"id": "math-02", "text": "biharmonic equation weak solution regularity"},
    {"id": "math-03", "text": "covariance matrix spectral theory random matrices"},
    {"id": "math-04", "text": "Brezis-Kato regularity nonlinear scalar field equations"},
    {"id": "math-05", "text": "strongly integrating fermions ground state instability"},
    {"id": "math-06", "text": "biharmonic Sobolev inequality logarithmic"},
    {"id": "math-07", "text": "Marchenko Pastur law free probability"},
    {"id": "math-08", "text": "Pohozaev manifold critical point theory"},
    {"id": "math-09", "text": "W^{2,2} Sobolev space biharmonic operator"},
    {"id": "math-10", "text": "matrix eigenvalue distribution Wigner semicircle"},
    {"id": "zh-01", "text": "小說起源 先秦諸子 稗官野史"},
    {"id": "zh-02", "text": "魯迅 中國小說史略 章回小說"},
    {"id": "zh-03", "text": "唐代傳奇 志怪小說 古典文學"},
    {"id": "zh-04", "text": "史記 班固 藝文志 小說家"},
    {"id": "zh-05", "text": "三國演義 水滸傳 金瓶梅 章回體"},
    {"id": "zh-06", "text": "莊子 外物 飾小說以干縣令"},
    {"id": "zh-07", "text": "宋代話本 講史 小說演變"},
    {"id": "zh-08", "text": "儒林外史 諷刺小說 吳敬梓"},
    {"id": "zh-09", "text": "紅樓夢 人情小說 清代文學"},
    {"id": "zh-10", "text": "六朝志怪 干寶 搜神記 神話傳說"},
    {"id": "mix-01", "text": "attention mechanism transformer self-attention 注意力机制"},
    {"id": "mix-02", "text": "Karpathy neural network 神经网络 embedding"},
    {"id": "mix-03", "text": "softmax temperature scaling 温度参数 概率分布"},
    {"id": "mix-04", "text": "multi-head attention 多头注意力 query key value"},
    {"id": "mix-05", "text": "position encoding sinusoidal 位置编码 序列模型"},
    {"id": "mix-06", "text": "beam search decoding 束搜索 生成模型"},
    {"id": "mix-07", "text": "cross-entropy loss 交叉熵 分类任务"},
    {"id": "mix-08", "text": "layer normalization batch norm 归一化 训练稳定性"},
    {"id": "mix-09", "text": "tokenizer BPE subword 分词 词汇表"},
    {"id": "mix-10", "text": "encoder decoder architecture seq2seq 编码器解码器"},
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

from sentence_transformers import SentenceTransformer
print("Loading qwen3-embedding-0.6B...", flush=True)
model = SentenceTransformer("Qwen/Qwen3-Embedding-0.6B", device="cpu", trust_remote_code=True)
print("Loaded", flush=True)

b_texts = [c["text"] for c in corpus_b]
print(f"Encoding {len(b_texts)} corpus_b...", flush=True)
b_embs = model.encode(b_texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True, prompt_name="query")
b_embs_np = np.array(b_embs)

print(f"Encoding {len(CUSTOM_QUERIES)} custom queries...", flush=True)
q_embs = model.encode([q["text"] for q in CUSTOM_QUERIES], batch_size=64,
                       show_progress_bar=False, normalize_embeddings=True, prompt_name="query")
q_np = np.array(q_embs)
sims_b = q_np @ b_embs_np.T

heuristic_pass = sum(1 for i in range(len(CUSTOM_QUERIES)) if sims_b[i].max() > 0.5)
pass_rate = round(heuristic_pass / len(CUSTOM_QUERIES), 3)
print(f"Heuristic pass_rate: {pass_rate}", flush=True)

results["qwen3-embedding-0.6B"]["custom_judge_pass_rate"] = pass_rate
results["qwen3-embedding-0.6B"]["custom_judge_method"] = "heuristic (top1_sim > 0.5)"
(BENCH / "embedding_results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print("Results updated", flush=True)
print("=== DONE ===", flush=True)
