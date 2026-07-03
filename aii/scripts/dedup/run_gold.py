"""金集自证: 用真判官(判同)在对抗金集上跑 → preds.jsonl → score.py。
回测有罪推定: 判同逻辑先过金集(merge precision→1)才准碰真数据/灌库。

用法: uv run python scripts/dedup/run_gold.py [--model deepseek-pro] [--limit N]
env: AII_KG_URL(A仓 5435) / REFINED_URL(B仓 5436) / DEEPSEEK_API_KEY(.env)
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # aii 项目根
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(Path(__file__).parent))  # judge/ledger/dictionary
sys.path.insert(0, str(ROOT / "scripts"))

import asyncpg  # noqa: E402
from obase import ProviderRegistry  # noqa: E402
from aii.api._provider import register_providers  # noqa: E402

from ledger import DecisionLedger  # noqa: E402
from judge import judge_pair, to_merge_action  # noqa: E402

KG_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
MODEL = (
    sys.argv[sys.argv.index("--model") + 1]
    if "--model" in sys.argv
    else os.getenv("GOLD_JUDGE_MODEL", "deepseek-pro")
)
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
STRONG = (
    sys.argv[sys.argv.index("--strong") + 1] if "--strong" in sys.argv else None
)  # 分级: same 候选升级确认
USE_LEDGER = "--no-ledger" not in sys.argv  # 纯评测: 不写生产台账
GOLD_DIR = Path(__file__).parent.parent / "gold"


async def fetch_item(conn, kind: str, oid) -> dict | None:
    if kind == "concept":
        r = await conn.fetchrow(
            "SELECT name, name_zh, discipline, aliases::text AS aliases FROM aii.concept_onto WHERE concept_id=$1",
            int(oid),
        )
        if not r:
            return None
        return {
            "id": str(oid),
            "name": r["name"],
            "name_zh": r["name_zh"],
            "discipline": r["discipline"],
            "aliases": r["aliases"],
            "text": None,
        }
    r = await conn.fetchrow(
        "SELECT title, natural_text_zh, natural_text FROM aii.ku_onto WHERE ku_id=$1", str(oid)
    )
    if not r:
        return None
    return {
        "id": str(oid),
        "name": r["title"],
        "name_zh": None,
        "discipline": None,
        "aliases": None,
        "text": r["natural_text_zh"] or r["natural_text"],
    }


async def main():
    register_providers()
    llm = ProviderRegistry.get().llm(MODEL)
    llm_strong = ProviderRegistry.get().llm(STRONG) if STRONG else None
    kg_pool = await asyncpg.create_pool(KG_URL, min_size=1, max_size=6)
    rf_pool = await asyncpg.create_pool(REFINED_URL, min_size=1, max_size=6)

    pairs = [
        json.loads(l)
        for f in sorted(GOLD_DIR.glob("gold_seed*.jsonl"))
        for l in f.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    if LIMIT:
        pairs = pairs[:LIMIT]
    sem = asyncio.Semaphore(4)
    preds, misses = [], []

    async def one(p):
        async with kg_pool.acquire() as kg:  # 每任务独立连接(asyncpg 不可并发共用)
            a = await fetch_item(kg, p["kind"], p["a_id"])
            b = await fetch_item(kg, p["kind"], p["b_id"])
        if not a or not b:
            misses.append(p["pair_id"])
            return
        async with sem, rf_pool.acquire() as rfc:
            v = await judge_pair(
                a,
                b,
                llm,
                DecisionLedger(rfc) if USE_LEDGER else None,
                kind=p["kind"],
                model=MODEL,
                strong_llm=llm_strong,
                strong_model=STRONG,
            )
        pred = to_merge_action(v["verdict"])
        ok = (pred == "same") == (p["label"] == "same") or p["label"] == "uncertain"
        rep = " [replay]" if v.get("replayed") else ""
        print(
            f"  [{'✓' if ok else '✗错'}] {p['pair_id']} {p['band']}/{p['category']}: "
            f"金标={p['label']} 判={v['verdict']}→{pred}{rep}  {v.get('reason', '')[:48]}",
            flush=True,
        )
        preds.append({"pair_id": p["pair_id"], "predicted": pred})

    await asyncio.gather(*(one(p) for p in pairs))
    await kg_pool.close()
    await rf_pool.close()

    out = GOLD_DIR / "preds_judge.jsonl"
    out.write_text("\n".join(json.dumps(r) for r in preds) + "\n", encoding="utf-8")
    if misses:
        print(f"⚠ A仓缺失 {len(misses)}: {misses}", flush=True)
    print(f"\n判官={MODEL}, 预测 {len(preds)} 对 → {out}\n", flush=True)
    subprocess.run([sys.executable, str(GOLD_DIR / "score.py"), "--pred", str(out)])


if __name__ == "__main__":
    asyncio.run(main())
