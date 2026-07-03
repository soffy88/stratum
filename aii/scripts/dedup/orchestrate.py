"""去重编排 — A仓 → B仓 首批灌库骨架(设计 §5.1 步骤①②③)。

粗筛(candidates) → 逐对判同(gates+LLM关3, 台账) → cluster_same → build_contributions
  → [dry-run: 出报告] / [--apply: persist_refined_ku]。

默认 dry-run 不落库(破坏性先 dry_run)。--no-ledger 纯预览(不写判同决策, 保 B仓纯净)。
命门: 宁碎片不错合——只有 verdict==same 才并簇; uncertain/different 各自独立。

用法: uv run python scripts/dedup/orchestrate.py [--disc econ] [--sim 0.9] [--cap 200]
      [--model deepseek-pro] [--apply] [--no-ledger] [--concurrency 4]
"""

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / "scripts"))

import asyncpg  # noqa: E402
from obase import ProviderRegistry  # noqa: E402
from aii.api._provider import register_providers  # noqa: E402

from candidates import ku_candidates  # noqa: E402
from judge import judge_pair, to_merge_action  # noqa: E402
from ledger import DecisionLedger  # noqa: E402
from integrate import cluster_same, build_contributions, needs_split, persist_refined_ku  # noqa: E402

KG_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")


def _arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


WEAK = _arg("--weak", "default")  # 关3 首判(便宜/本地; ECON_LLM_PROVIDER=ollama 时=qwen)
STRONG = _arg("--strong", "deepseek-pro")  # 仅"提议合并(same)"升级确认(最需要处才用, 省钱)
SIM = float(_arg("--sim", "0.90"))
CAP = int(_arg("--cap", "200"))
CONC = int(_arg("--concurrency", "4"))
APPLY = "--apply" in sys.argv
USE_LEDGER = "--no-ledger" not in sys.argv
DISC = _arg("--disc", "econ")
# 首批学科书目(econ: 词典最全; math: 导数族)
ECON_SUBS = [
    "microecon_en_full_v2",
    "micro_clean",
    "mankiw_principles_econ_10e",
    "econ_zh_2726f38224",
    "econ_zh_da27a19f30",
    "econ_zh_3f11a8f38e",
    "econ_9ea2a19eac",
    "econ_131d7dbd3b",
]
SUBS = {"econ": ECON_SUBS, "all": None}.get(DISC, ECON_SUBS)

_TYPE_MAP = {
    "conceptual": "conceptual",
    "rationale": "rationale",
    "procedural": "procedural",
    "factual": "factual",
    "positional": "conceptual",
    "metacognitive": "conceptual",
}


async def _item(conn, ku_id):
    r = await conn.fetchrow(
        "SELECT title, natural_text_zh, natural_text, substrate_id, knowledge_type, provenance "
        "FROM aii.ku_onto WHERE ku_id=$1",
        ku_id,
    )
    if not r:
        return None
    prov = r["provenance"]
    if isinstance(prov, str):
        try:
            prov = json.loads(prov)
        except Exception:
            prov = {}
    return {
        "id": ku_id,
        "name": r["title"],
        "text": r["natural_text_zh"] or r["natural_text"],
        "book": r["substrate_id"],
        "ktype": r["knowledge_type"],
        "chapter": (prov or {}).get("chapter"),
    }


async def main():
    register_providers()
    llm_weak = ProviderRegistry.get().llm(WEAK)
    llm_strong = ProviderRegistry.get().llm(STRONG)
    kg = await asyncpg.create_pool(KG_URL, min_size=1, max_size=CONC + 2)
    rf = await asyncpg.create_pool(REFINED_URL, min_size=1, max_size=CONC + 2)

    async with kg.acquire() as c:
        cands, dropped = await ku_candidates(c, sim=SIM, cap=CAP, substrates=SUBS)
    mode = "APPLY(落库)" if APPLY else "DRY-RUN(不落库)"
    print(
        f"[{mode}] disc={DISC} sim≥{SIM} cap={CAP} 关3弱={WEAK} 升级强={STRONG} ledger={USE_LEDGER}"
    )
    print(
        f"粗筛候选 {len(cands)} 对" + (f" (超 cap 丢弃 {dropped})" if dropped else ""), flush=True
    )

    sem = asyncio.Semaphore(CONC)
    results = []

    async def judge_one(c):
        async with kg.acquire() as kc:
            a = await _item(kc, c["a_id"])
            b = await _item(kc, c["b_id"])
        if not a or not b:
            return
        async with sem:
            kw = dict(kind="ku", model=WEAK, strong_llm=llm_strong, strong_model=STRONG)
            if USE_LEDGER:
                async with rf.acquire() as rc:
                    v = await judge_pair(a, b, llm_weak, DecisionLedger(rc), **kw)
            else:
                v = await judge_pair(a, b, llm_weak, None, **kw)
        results.append((a, b, v))

    await asyncio.gather(*(judge_one(c) for c in cands))

    verdicts = Counter(v["verdict"] for _, _, v in results)
    gates = Counter(v.get("gate", "关3-LLM") for _, _, v in results)
    strong_calls = sum(1 for _, _, v in results if v.get("escalated"))
    same_pairs = [(a["id"], b["id"]) for a, b, v in results if v["verdict"] == "same"]
    clusters = cluster_same(same_pairs)
    item_by_id = {a["id"]: a for a, b, v in results} | {b["id"]: b for a, b, v in results}

    print(f"\n判定: {dict(verdicts)}")
    print(f"关分布: {dict(gates)}")
    print(f"强模型({STRONG})调用: {strong_calls} 次 (仅 same 候选升级确认; 其余全免费)")
    print(f"同点簇: {len(clusters)} 个 (覆盖 {sum(len(c) for c in clusters)} 个 A仓 KU)")

    persisted = splits = 0
    samples = []
    for cl in clusters:
        members = [item_by_id[i] for i in cl if i in item_by_id]
        if not members:
            continue
        contribs, fc = build_contributions(
            [
                {
                    "raw_ku_id": m["id"],
                    "book": m["book"],
                    "facet": m.get("ktype") or "main",
                    "text": m["text"],
                }
                for m in members
            ]
        )
        if needs_split(fc):
            splits += 1
        books = sorted({m["book"] for m in members})
        if len(samples) < 8:
            samples.append((members[0]["name"], len(members), books))
        if APPLY:
            en = next(
                (m["name"] for m in members if not any("一" <= ch <= "鿿" for ch in m["name"])),
                None,
            )
            zh = next(
                (m["name"] for m in members if any("一" <= ch <= "鿿" for ch in m["name"])), None
            )
            kt = _TYPE_MAP.get(members[0].get("ktype"), "conceptual")
            async with rf.acquire() as rc:
                await persist_refined_ku(
                    rc,
                    point=en or members[0]["name"],
                    point_zh=zh,
                    ku_type=kt,
                    contributions=contribs,
                    facet_count=fc,
                )
            persisted += 1

    print(f"\n同点簇样本(name / 成员数 / 跨书):")
    for name, k, books in samples:
        print(f"  · {name[:40]}  ×{k}  {books}")
    if splits:
        print(f"⚠ {splits} 个簇 facet 超原子性预算(该拆多 KU, 见 needs_split)")
    if APPLY:
        print(f"\n✓ 落库 refined_ku: {persisted} 个 (碎片=未并入簇的 KU 各自独立, 后续单独灌)")
    else:
        print(f"\nDRY-RUN: 将落库 {len(clusters)} 个合并 KU(--apply 落库)。碎片各自独立。")
    await kg.close()
    await rf.close()


if __name__ == "__main__":
    asyncio.run(main())
