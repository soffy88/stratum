"""M0 概念归一(步骤4) — 在去重 KU 涉及的 A仓概念上做 concept canonical。

范围: B仓 refined_ku 的 contributions.raw_ku_id → A仓 ku_concept_onto → 涉及的 A仓概念。
流程: 概念向量粗筛 → 四道关判同(kind=concept, 程序关+分级LLM) → cluster_same
      → 每簇=一个 refined_concept(canonical名/别名/判别维度/B仓独立向量) + KU↔概念 incidence。
命门: 宁碎片不错合(错合=地基污染, 上层超边/本性全错); dry_run 强制(默认不落库)。

用法: uv run python scripts/dedup/m0.py [--sim 0.9] [--cap 400] [--weak deepseek-flash]
      [--strong deepseek-pro] [--apply] [--no-ledger] [--concurrency 6]
"""

import asyncio
import sys
from collections import Counter, defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / "scripts"))

import asyncpg  # noqa: E402
import numpy as np  # noqa: E402
from pgvector.asyncpg import register_vector  # noqa: E402
from obase import ProviderRegistry  # noqa: E402
from oprim import vector_encode  # noqa: E402
from aii.api._provider import register_providers  # noqa: E402

from judge import judge_pair  # noqa: E402
from ledger import DecisionLedger  # noqa: E402
from integrate import cluster_same, persist_refined_concept  # noqa: E402
from gates import extract_dims  # noqa: E402

import os  # noqa: E402

KG_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")


def _arg(f, d=None):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d


WEAK = _arg("--weak", "deepseek-flash")
STRONG = _arg("--strong", "deepseek-pro")
SIM = float(_arg("--sim", "0.90"))
CAP = int(_arg("--cap", "400"))
CONC = int(_arg("--concurrency", "6"))
APPLY = "--apply" in sys.argv
USE_LEDGER = "--no-ledger" not in sys.argv
_CJK = lambda s: any("一" <= ch <= "鿿" for ch in (s or ""))


async def scope_concepts(rf, kg):
    """B仓已入 raw_ku_id → A仓涉及概念(有向量)。返回 {a_cid: {name,name_zh,discipline,aliases,vec}}。"""
    async with rf.acquire() as rc:
        rows = await rc.fetch(
            "SELECT DISTINCT jsonb_array_elements(contributions)->>'raw_ku_id' AS rid FROM rf.refined_ku"
        )
    raw_ids = [r["rid"] for r in rows if r["rid"]]
    async with kg.acquire() as kc:
        await register_vector(kc)
        crows = await kc.fetch(
            """
            SELECT DISTINCT c.concept_id, c.name, c.name_zh, c.discipline, c.aliases::text AS aliases, c.vector
            FROM aii.concept_onto c
            JOIN aii.ku_concept_onto kc ON kc.concept_id=c.concept_id
            WHERE kc.ku_id = ANY($1::text[])
            """,
            raw_ids,
        )
        # incidence 用: raw_ku_id → [a_cid]
        inc = await kc.fetch(
            "SELECT ku_id, concept_id FROM aii.ku_concept_onto WHERE ku_id = ANY($1::text[])",
            raw_ids,
        )
    concepts = {
        r["concept_id"]: {
            "name": r["name"],
            "name_zh": r["name_zh"],
            "discipline": r["discipline"],
            "aliases": r["aliases"],
            "vec": np.asarray(r["vector"], dtype=np.float32) if r["vector"] is not None else None,
        }
        for r in crows
    }
    raw2cid = defaultdict(list)
    for r in inc:
        raw2cid[r["ku_id"]].append(r["concept_id"])
    return concepts, raw2cid


def nn_pairs(concepts, sim, cap):
    cids = [c for c in concepts if concepts[c]["vec"] is not None]  # NN 只用有向量的; 无向量→单例
    V = np.array([concepts[c]["vec"] for c in cids])
    V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
    S = V @ V.T
    tri = []
    for i in range(len(cids)):
        for j in range(i + 1, len(cids)):
            if S[i, j] >= sim:
                tri.append((float(S[i, j]), cids[i], cids[j]))
    tri.sort(reverse=True)
    return [(a, b) for _, a, b in tri[:cap]], max(0, len(tri) - cap)


def _canonical(members):
    """簇内选 canonical: 英文名优先(判同对齐用), 中文名, 别名并集, 学科众数, 判别维度。"""
    names = [m["name"] for m in members if m.get("name")]
    en = next((n for n in names if not _CJK(n)), None)
    zh = next((m["name_zh"] for m in members if m.get("name_zh")), None) or next(
        (n for n in names if _CJK(n)), None
    )
    aliases = sorted({n for n in names})
    disc = Counter(m["discipline"] for m in members if m.get("discipline")).most_common(1)
    return {
        "name": en or names[0],
        "name_zh": zh,
        "aliases": aliases,
        "discipline": disc[0][0] if disc else None,
        "discriminative": extract_dims(en or names[0]),
    }


async def main():
    register_providers()
    llm_weak = ProviderRegistry.get().llm(WEAK)
    llm_strong = ProviderRegistry.get().llm(STRONG)
    kg = await asyncpg.create_pool(KG_URL, min_size=1, max_size=CONC + 2)
    rf = await asyncpg.create_pool(REFINED_URL, min_size=1, max_size=CONC + 2, init=register_vector)

    concepts, raw2cid = await scope_concepts(rf, kg)
    cands, dropped = nn_pairs(concepts, SIM, CAP)
    mode = "APPLY(落库)" if APPLY else "DRY-RUN(不落库)"
    print(
        f"[M0 {mode}] 范围概念 {len(concepts)} 个, 候选 {len(cands)} 对"
        + (f"(超cap丢弃{dropped})" if dropped else "")
        + f" | 关3弱={WEAK} 升级强={STRONG}",
        flush=True,
    )

    sem = asyncio.Semaphore(CONC)
    results, fails = [], []

    def item(cid):
        c = concepts[cid]
        return {
            "id": str(cid),
            "name": c["name"],
            "name_zh": c["name_zh"],
            "discipline": c["discipline"],
            "aliases": c["aliases"],
            "text": None,
        }

    async def judge_one(pair):
        a, b = item(pair[0]), item(pair[1])
        async with sem:
            try:
                if USE_LEDGER:
                    async with rf.acquire() as rc:
                        v = await judge_pair(
                            a,
                            b,
                            llm_weak,
                            DecisionLedger(rc),
                            kind="concept",
                            model=WEAK,
                            decision_type="concept_merge",
                            strong_llm=llm_strong,
                            strong_model=STRONG,
                        )
                else:
                    v = await judge_pair(
                        a,
                        b,
                        llm_weak,
                        None,
                        kind="concept",
                        model=WEAK,
                        decision_type="concept_merge",
                        strong_llm=llm_strong,
                        strong_model=STRONG,
                    )
            except Exception as e:  # noqa: BLE001
                fails.append(str(e)[:50])
                v = {"verdict": "different"}
        results.append((pair[0], pair[1], v))

    await asyncio.gather(*(judge_one(p) for p in cands))

    verdicts = Counter(v["verdict"] for _, _, v in results)
    gates = Counter(v.get("gate", "关3-LLM") for _, _, v in results)
    strong_calls = sum(1 for _, _, v in results if v.get("escalated"))
    same = [(a, b) for a, b, v in results if v["verdict"] == "same"]
    clusters = cluster_same(same)
    merged = set().union(*clusters) if clusters else set()
    singletons = [c for c in concepts if c not in merged]

    print(f"判定: {dict(verdicts)} | 关分布: {dict(gates)} | 强模型调用: {strong_calls}")
    print(
        f"归一: {len(clusters)} 簇合并 {len(merged)} 概念 + {len(singletons)} 单例 = "
        f"{len(clusters) + len(singletons)} 个 refined_concept"
    )
    if fails:
        print(f"⚠ {len(fails)} 对判同失败降级 different")
    print("\n合并簇样本(canonical / 别名):")
    for cl in clusters[:10]:
        can = _canonical([concepts[c] for c in cl])
        print(f"  · {can['name'][:32]}  ← {can['aliases'][:4]}")

    if not APPLY:
        print(
            f"\nDRY-RUN: 将落 {len(clusters) + len(singletons)} 个 refined_concept + KU↔概念 incidence。--apply 落库"
        )
        await kg.close()
        await rf.close()
        return

    # ---- 落库 ----
    units = [[concepts[c] | {"cid": c} for c in cl] for cl in clusters] + [
        [concepts[c] | {"cid": c}] for c in singletons
    ]
    canons = [_canonical(u) for u in units]
    embs = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: vector_encode(
            texts=[f"{c['name']} {c.get('name_zh') or ''}".strip() for c in canons],
            provider="default",
        ),
    )
    a2r = {}  # A仓 concept_id → refined_concept_id
    async with rf.acquire() as rc:
        for u, can, emb in zip(units, canons, embs):
            rcid = await persist_refined_concept(
                rc,
                name=can["name"],
                name_zh=can["name_zh"],
                aliases=can["aliases"],
                discipline=can["discipline"],
                discriminative=can["discriminative"],
                embedding=emb,
                sources={"a_concept_ids": [m["cid"] for m in u]},
            )
            for m in u:
                a2r[m["cid"]] = rcid
    print(f"✓ 落库 refined_concept: {len(units)} 个 (含 B仓独立向量)")

    # ---- KU↔概念 incidence: refined_ku → raw → A仓概念 → refined_concept ----
    async with rf.acquire() as rc:
        kurows = await rc.fetch(
            "SELECT ku_id, jsonb_path_query_array(contributions,'$[*].raw_ku_id') AS raws FROM rf.refined_ku"
        )
        import json as _j

        links = set()
        for r in kurows:
            raws = r["raws"] if isinstance(r["raws"], list) else _j.loads(r["raws"])
            for raw in raws:
                for acid in raw2cid.get(raw, []):
                    if acid in a2r:
                        links.add((r["ku_id"], a2r[acid]))
        await rc.executemany(
            "INSERT INTO rf.refined_ku_concept(ku_id,concept_id) VALUES($1,$2) ON CONFLICT DO NOTHING",
            list(links),
        )
    print(f"✓ 落库 KU↔概念 incidence: {len(links)} 条")
    await kg.close()
    await rf.close()


if __name__ == "__main__":
    asyncio.run(main())
