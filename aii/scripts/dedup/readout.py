"""步骤4.5 有向关系 — readout 法: 从讲透的 KU 读出它【已表达】的概念→概念关系。

设计 §2.1: 读出(非推断/非judge)——只提 KU 内容明确表达的关系, O(N) 一 call/KU,
质量继承 KU(先讲透不编→读关系也不编)。关系类型 derives/subsumes/prerequisite。
落 refined_directed_edge(概念骨架, M1 超边挂其上生长; 也供判同关2 判上下位)。
命门: 只读已表达的不猜; strength=表达此边的 KU 数; grade=unverified(不验证)。
读出是可加的、grade未验证、可重做 → 用便宜模型(flash), 不升级 pro。

用法: uv run python scripts/dedup/readout.py [--limit N] [--apply] [--concurrency 8]
"""

import asyncio
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(ROOT / "scripts"))

import asyncpg  # noqa: E402
from obase import ProviderRegistry  # noqa: E402
from aii.api._provider import register_providers  # noqa: E402
from ledger import DecisionLedger  # noqa: E402

REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")


def _arg(f, d=None):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d


MODEL = _arg("--model", "deepseek-flash")
CONC = int(_arg("--concurrency", "8"))
LIMIT = int(_arg("--limit", "0"))
APPLY = "--apply" in sys.argv
USE_LEDGER = "--no-ledger" not in sys.argv

SYSTEM = """你是知识关系读出器。给你一个知识单元(KU)正文 + 它涉及的概念列表。
铁律: 只读出正文里用【明确的关系语言】连接两个概念的有向关系。
【仅仅同时提到两个概念、或它们同属一个话题 —— 不是关系, 绝不输出。】
宁可输出空数组, 也不要猜测或用常识外推。假关系比漏关系危险得多。
关系类型(仅当正文明确用对应语言表达):
- derives: 正文明确表明 B【由 A 推导/计算/证明得出】(如"由A可得B""根据A, B成立""B 的公式含 A")
- subsumes: 正文明确表明 A 是 B 的【上位类/一般化】, B 是 A 的特例(如"B 是一种 A""A 包含 B 这类")
- prerequisite: 正文明确表明【必须先有/先理解 A 才能有 B】(如"在 A 基础上""B 依赖 A""先 A 后 B")
拿不准属于哪类、或正文只是并列/背景提及 → 不输出该对。多数 KU 可能一条明确关系都没有, 输出 {"edges":[]} 正常。
src/dst 必须来自给定概念列表。只输出 JSON: {"edges":[{"src":"概念名","dst":"概念名","type":"..."}]}"""

_TYPES = {"derives", "subsumes", "prerequisite"}


def _norm(s):
    return re.sub(r"[\s_\-]+", "", (s or "").lower())


async def readout_ku(row, llm):
    """读出一个 KU 表达的边。返回 [(src_cid, dst_cid, type)]。src/dst 映射回该 KU 的概念。"""
    concepts = row["concepts"] if isinstance(row["concepts"], list) else json.loads(row["concepts"])
    name2cid = {}
    for c in concepts:
        name2cid[_norm(c.get("name"))] = c["cid"]
        if c.get("name_zh"):
            name2cid[_norm(c["name_zh"])] = c["cid"]
    clist = ", ".join(
        f"{c.get('name')}" + (f"/{c['name_zh']}" if c.get("name_zh") else "") for c in concepts
    )
    body = (row["natural_text_zh"] or row["point"] or "")[:1500]
    prompt = f"概念列表: {clist}\n\nKU 正文:\n{body}\n\n读出正文明确表达的概念间有向关系。"
    r = await llm(messages=[{"role": "user", "content": prompt}], system=SYSTEM, max_tokens=500)
    raw = r["content"][0]["text"] if isinstance(r, dict) else str(r)
    edges, m = [], re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            for e in json.loads(m.group(0)).get("edges", []):
                t = str(e.get("type", "")).lower()
                s, d = name2cid.get(_norm(e.get("src"))), name2cid.get(_norm(e.get("dst")))
                if t in _TYPES and s and d and s != d:  # 必须映射回该KU概念, 不引入列表外
                    edges.append((s, d, t))
        except Exception:
            pass
    return edges, raw


async def main():
    register_providers()
    llm = ProviderRegistry.get().llm(MODEL)
    rf = await asyncpg.create_pool(REFINED_URL, min_size=1, max_size=CONC + 2)

    async with rf.acquire() as c:
        q = """
            SELECT k.ku_id, k.point, k.natural_text_zh,
                   jsonb_agg(jsonb_build_object('cid',c.concept_id,'name',c.name,'name_zh',c.name_zh)) AS concepts
            FROM rf.refined_ku k
            JOIN rf.refined_ku_concept kc ON kc.ku_id=k.ku_id
            JOIN rf.refined_concept c ON c.concept_id=kc.concept_id
            GROUP BY k.ku_id, k.point, k.natural_text_zh HAVING count(*)>=2
        """ + (f" LIMIT {LIMIT}" if LIMIT else "")
        kus = await c.fetch(q)
    print(
        f"[{'APPLY' if APPLY else 'DRY-RUN'}] readout: {len(kus)} 个 KU(≥2概念) model={MODEL}",
        flush=True,
    )

    sem = asyncio.Semaphore(CONC)
    agg = defaultdict(lambda: {"n": 0, "kus": []})  # (s,d,t) -> strength/evidence
    fails = [0]

    async def one(row):
        async with sem:
            try:
                edges, raw = await readout_ku(row, llm)
            except Exception:
                fails[0] += 1
                return
        for e in edges:
            agg[e]["n"] += 1
            if len(agg[e]["kus"]) < 5:
                agg[e]["kus"].append(row["ku_id"])
        if USE_LEDGER and APPLY:
            async with rf.acquire() as rc:
                await DecisionLedger(rc).record(
                    "readout",
                    {"ku_id": row["ku_id"]},
                    {"edges": [list(e) for e in edges]},
                    model=MODEL,
                    llm_raw={"response": raw[:800]},
                    actor="llm",
                )

    await asyncio.gather(*(one(r) for r in kus))

    by_type = defaultdict(int)
    for (s, d, t), v in agg.items():
        by_type[t] += 1
    print(f"读出边: {len(agg)} 条(去重) | 类型: {dict(by_type)} | 失败 {fails[0]}")

    if not APPLY:
        print("样本:")
        async with rf.acquire() as c:
            for (s, d, t), v in sorted(agg.items(), key=lambda x: -x[1]["n"])[:8]:
                sn = await c.fetchval("SELECT name FROM rf.refined_concept WHERE concept_id=$1", s)
                dn = await c.fetchval("SELECT name FROM rf.refined_concept WHERE concept_id=$1", d)
                print(f"  {sn} --{t}--> {dn}  (×{v['n']})")
        print(f"\nDRY-RUN: 将落 {len(agg)} 条 refined_directed_edge。--apply 落库")
        await rf.close()
        return

    async with rf.acquire() as c:
        rows = [
            (s, d, t, min(1.0, 0.5 + 0.1 * v["n"]), json.dumps({"kus": v["kus"], "count": v["n"]}))
            for (s, d, t), v in agg.items()
        ]
        await c.executemany(
            """INSERT INTO rf.refined_directed_edge(src_concept,dst_concept,relation_type,strength,grade,evidence)
               VALUES($1,$2,$3,$4,'unverified',$5)""",
            rows,
        )
    print(f"✓ 落库 refined_directed_edge: {len(agg)} 条(概念骨架)")
    await rf.close()


if __name__ == "__main__":
    asyncio.run(main())
