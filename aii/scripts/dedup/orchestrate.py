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

from pgvector.asyncpg import register_vector  # noqa: E402
from oprim import vector_encode  # noqa: E402
from candidates import ku_candidates  # noqa: E402
from judge import judge_pair, to_merge_action  # noqa: E402
from ledger import DecisionLedger  # noqa: E402
from integrate import (
    cluster_same,
    build_contributions,
    needs_split,  # noqa: E402
    persist_refined_ku,
    render_zh,
    embed_text,
)

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
# ★2026-07-19: 原8本(07-03首批, M0概念归一唯一跑过的一批)之外, A仓已积累35本新econ书
# 从未走过这里(幂等 exclude=ingested 保证不会重复入,但没进这个硬编码列表的书永远不会
# 自动被捡到——这正是"KC建在stale快照上"问题的根因之一)。补进来后, 这个列表还是会
# 随econ飞轮持续摄入而再度过期, 需要定期人工核对/补(未来可考虑改成动态查询)。
ECON_SUBS = [
    "microecon_en_full_v2",
    "micro_clean",
    "mankiw_principles_econ_10e",
    "econ_zh_2726f38224",
    "econ_zh_da27a19f30",
    "econ_zh_3f11a8f38e",
    "econ_9ea2a19eac",
    "econ_131d7dbd3b",
    "econ_zh_5805bf6620",
    "econ_zh_495a1c50dd",
    "econ_zh_d8347c21db",
    "econ_zh_1e95f05ba2",
    "econ_zh_6b2c62a4fb",
    "econ_zh_26b4fe7a8e",
    "econ_zh_85c1e848a6",
    "econ_zh_30b3e5fbfe",
    "econ_zh_53fedeec50",
    "econ_zh_a202f2b23b",
    "econ_zh_dbbac66e8b",
    "econ_zh_07620412ec",
    "econ_zh_23f95a67ed",
    "econ_zh_e02d6f741e",
    "econ_zh_b0b27652c0",
    "econ_zh_0164798c48",
    "econ_zh_d0717121de",
    "econ_en_528f998ddd",
    "econ_zh_c9e29652c4",
    "econ_zh_04f261fef5",
    "econ_zh_130c35565a",
    "econ_zh_ce44d5c59b",
    "econ_en_aebb2f3981",
    "econ_zh_370fbfcac6",
    "econ_zh_def644a1f3",
    "econ_zh_821b2d3183",
    "econ_zh_c17913c054",
    "econ_zh_856bf79a2a",
    "econ_zh_142946e849",
    "econ_zh_1cc74ee08b",
    "econ_zh_61f168e49d",
    "econ_zh_e8b4c74665",
    "econ_zh_9f5962837c",
    "econ_zh_ba1e1ec4e3",
    "econ_zh_d335c0d77d",
]
_SUB1 = _arg("--substrate")  # 单书验证: 覆盖 SUBS
SUBS = [_SUB1] if _SUB1 else {"econ": ECON_SUBS, "all": None}.get(DISC, ECON_SUBS)

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
    rf = await asyncpg.create_pool(REFINED_URL, min_size=1, max_size=CONC + 2, init=register_vector)

    # 幂等: 已入 B仓 的 raw_ku_id 不再入(增量: A仓固定、B仓随书生长)
    async with rf.acquire() as rc:
        ing = await rc.fetch(
            "SELECT DISTINCT jsonb_array_elements(contributions)->>'raw_ku_id' AS rid FROM rf.refined_ku"
        )
    ingested = {r["rid"] for r in ing if r["rid"]}

    async with kg.acquire() as c:
        cands, dropped = await ku_candidates(c, sim=SIM, cap=CAP, substrates=SUBS, exclude=ingested)
    mode = "APPLY(落库)" if APPLY else "DRY-RUN(不落库)"
    print(
        f"[{mode}] disc={DISC} sim≥{SIM} cap={CAP} 关3弱={WEAK} 升级强={STRONG} ledger={USE_LEDGER}"
    )
    print(f"幂等: B仓已入 {len(ingested)} 个 A仓 KU, 本轮跳过")
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
            try:
                if USE_LEDGER:
                    async with rf.acquire() as rc:
                        v = await judge_pair(a, b, llm_weak, DecisionLedger(rc), **kw)
                else:
                    v = await judge_pair(a, b, llm_weak, None, **kw)
            except (
                Exception
            ) as e:  # 单对失败(重试后仍超时/断连)→ 降级 different(宁碎片), 不拖垮整批
                fails.append((c, str(e)[:60]))
                v = {"verdict": "different", "reason": f"判同失败降级(宁碎片): {str(e)[:50]}"}
        results.append((a, b, v))

    fails = []
    await asyncio.gather(*(judge_one(c) for c in cands))
    if fails:
        print(
            f"⚠ {len(fails)} 对判同失败, 已降级 different(宁碎片): {[f[0]['a_id'] for f in fails[:5]]}"
        )

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

    # 组装落库单元: 合并簇 + 单例(批内未被合并的 KU 各自独立成 refined_ku)
    merged_ids = set().union(*clusters) if clusters else set()
    async with kg.acquire() as c:
        q = (
            "SELECT ku_id FROM aii.ku_onto WHERE embedding IS NOT NULL AND is_quarantined IS NOT TRUE"
            + (" AND substrate_id = ANY($1::text[])" if SUBS else "")
        )
        all_ids = [r["ku_id"] for r in await c.fetch(q, *([list(SUBS)] if SUBS else []))]
    singleton_ids = [i for i in all_ids if i not in merged_ids and i not in ingested]
    for i in singleton_ids:  # 补齐非候选单例的 item
        if i not in item_by_id:
            async with kg.acquire() as c:
                it = await _item(c, i)
            if it:
                item_by_id[i] = it

    units = [([item_by_id[i] for i in cl if i in item_by_id], True) for cl in clusters]
    units += [([item_by_id[i]], False) for i in singleton_ids if i in item_by_id]

    built, splits, samples = [], 0, []
    for members, is_merge in units:
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
        if is_merge and len(samples) < 8:
            samples.append((members[0]["name"], len(members), sorted({m["book"] for m in members})))
        built.append((members, contribs, fc))

    print(
        f"落库单元: {len(clusters)} 合并 + {len(singleton_ids)} 单例 = {len(built)} 个 refined_ku"
    )
    print("\n同点簇样本(name / 成员数 / 跨书):")
    for name, k, books in samples:
        print(f"  · {name[:40]}  ×{k}  {books}")
    if splits:
        print(f"⚠ {splits} 个单元 facet 超原子性预算(该拆多 KU)")

    if APPLY:
        loop = asyncio.get_event_loop()
        # B仓 独立向量: BGE-M3 在合并后干净内容上重算(不搬 A仓向量)。
        # ★走共享 aii-embed 远程服务(笔记本GPU), 不在本进程 local-load BGE-M3——
        # 本机GPU常被其它进程间歇性占用, 本地 fallback 会不稳定撞 OOM。
        # ★trust_env=False 必须: 本机 http_proxy/https_proxy 指向出网代理(sing-box),
        # NO_PROXY 虽含 100.64.0.0/10(100.68.226.13 在此段内), 但 httpx 不解析 CIDR
        # 写法的 NO_PROXY(只做前缀/域名匹配)——用默认 httpx.post()(trust_env 默认真)
        # 会把这个内网请求错误地打进出网代理, 代理连不上内网 IP 后吐 502(空 body,
        # 固定~5.2s)。2026-07-19 实测: 同一请求 curl(正确认 CIDR) 200, httpx 默认 502,
        # httpx.Client(trust_env=False) 200——确认是代理误路由, 不是 aii-embed 服务问题。
        import httpx as _httpx

        embed_url = os.getenv("AII_EMBED_URL", "http://100.68.226.13:8102")

        def _embed_batch(batch):
            # read=300: 共享服务被其它飞轮并发占用时会排队, 同 aii_remote.py 既有约定。
            timeout = _httpx.Timeout(connect=10, read=300, write=30, pool=10)
            with _httpx.Client(trust_env=False, timeout=timeout) as c:
                r = c.post(f"{embed_url}/embed", json={"texts": batch})
                r.raise_for_status()
                return r.json()["embeddings"]

        texts = [embed_text(c) or (m[0].get("name") or "") for m, c, _ in built]
        BATCH = 64  # 同 math_ingest.py 既有约定, 避免单批过大拖慢/超时
        embs = []
        for i in range(0, len(texts), BATCH):
            chunk = texts[i : i + BATCH]
            embs.extend(await loop.run_in_executor(None, lambda c=chunk: _embed_batch(c)))
        persisted = 0
        for (members, contribs, fc), emb in zip(built, embs):
            names = [m.get("name") or "" for m in members]
            en = next((x for x in names if not any("一" <= ch <= "鿿" for ch in x)), None)
            zh = next((x for x in names if any("一" <= ch <= "鿿" for ch in x)), None)
            kt = _TYPE_MAP.get(members[0].get("ktype"), "conceptual")
            async with rf.acquire() as rc:
                await persist_refined_ku(
                    rc,
                    point=en or names[0],
                    point_zh=zh,
                    ku_type=kt,
                    contributions=contribs,
                    facet_count=fc,
                    embedding=emb,
                    natural_text_zh=render_zh(contribs),
                )
            persisted += 1
        print(f"\n✓ 落库 refined_ku: {persisted} 个 (含 B仓 独立向量 BGE-M3)")
    else:
        print(
            f"\nDRY-RUN: 将落库 {len(built)} 个 refined_ku "
            f"({len(clusters)}合并+{len(singleton_ids)}单例)。--apply 落库"
        )
    await kg.close()
    await rf.close()


if __name__ == "__main__":
    asyncio.run(main())
