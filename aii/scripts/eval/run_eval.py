"""检索评测: 在 golden set 上对比 dense / hybrid / hybrid+rerank 三法.

指标(信息检索标准):
  Recall@k  — gold KU 是否进了 top-k(召回率)
  MRR       — gold 首次命中名次的倒数均值(排序质量)
  nDCG@k    — 归一化折损累积增益(名次加权)
单 gold 设定下 Recall@k=Hit@k, nDCG 退化为 1/log2(rank+1).

用法: python3 scripts/eval/run_eval.py [--rerank] [--k 10]
  需先 build_golden.py 生成 golden.json. ECON_LLM_PROVIDER=ollama 用本地模型重排.
"""
import asyncio, json, math, os, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "aii" / ".env", override=True)
from aii.api._provider import register_providers
from aii.storage.pg_backend import PgBackend
from aii.service.retrieval import llm_rerank
from obase import ProviderRegistry
import numpy as np

GOLD = ROOT / "scripts" / "eval" / "golden.json"


def _embed(embed_fn, text: str) -> list[float]:
    arr = np.array(embed_fn([text]), dtype="float32")[0]
    nrm = float(np.linalg.norm(arr))
    return [float(x) / nrm for x in arr] if nrm > 0 else [float(x) for x in arr]


def _rank_of(gold: str, results: list[dict]) -> int | None:
    for i, r in enumerate(results):
        if str(r.get("ku_id")) == gold:
            return i + 1
    return None


def _metrics(ranks: list[int | None], k: int) -> dict:
    n = len(ranks)
    hit = sum(1 for r in ranks if r and r <= k)
    mrr = sum((1.0 / r) for r in ranks if r) / n if n else 0.0
    ndcg = sum((1.0 / math.log2(r + 1)) for r in ranks if r and r <= k) / n if n else 0.0
    return {"recall@%d" % k: hit / n if n else 0, "MRR": mrr, "nDCG@%d" % k: ndcg, "n": n}


async def main():
    rerank = "--rerank" in sys.argv
    k = int(sys.argv[sys.argv.index("--k") + 1]) if "--k" in sys.argv else 10
    golden = json.loads(GOLD.read_text(encoding="utf-8"))
    register_providers()
    embed_fn = ProviderRegistry.get()._generic.get("embedding", {}).get("default")
    llm = ProviderRegistry.get().llm("default")
    be = PgBackend()

    depth = 40
    ranks = {"dense": [], "hybrid": [], "hybrid+rerank": []}
    sem = asyncio.Semaphore(8)

    async def one(g):
        async with sem:
            qv = _embed(embed_fn, g["query"])
            dense = await be.search_ku_by_vector(qv, limit=depth)
            hybrid = await be.search_ku_hybrid(qv, g["query"], limit=depth)
            row = {"dense": _rank_of(g["gold_ku_id"], dense),
                   "hybrid": _rank_of(g["gold_ku_id"], hybrid)}
            if rerank:
                rr = await llm_rerank(llm, g["query"], hybrid[:15], top_k=k)
                row["hybrid+rerank"] = _rank_of(g["gold_ku_id"], rr)
            return row

    rows = await asyncio.gather(*(one(g) for g in golden))
    for r in rows:
        for method in ranks:
            if method in r:
                ranks[method].append(r[method])

    print(f"\n=== 检索评测 (golden n={len(golden)}, k={k}) ===")
    print(f"{'method':16} {'recall@%d'%k:>10} {'MRR':>8} {'nDCG@%d'%k:>8}")
    for method in ["dense", "hybrid"] + (["hybrid+rerank"] if rerank else []):
        if not ranks[method]:
            continue
        m = _metrics(ranks[method], k)
        print(f"{method:16} {m['recall@%d'%k]:>10.3f} {m['MRR']:>8.3f} {m['nDCG@%d'%k]:>8.3f}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
