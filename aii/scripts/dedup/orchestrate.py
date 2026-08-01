"""去重编排 — A仓 → B仓 首批灌库骨架(设计 §5.1 步骤①②③)。

粗筛(candidates) → 逐对判同(gates+LLM关3, 台账) → cluster_same → build_contributions
  → [dry-run: 出报告] / [--apply: persist_refined_ku]。

默认 dry-run 不落库(破坏性先 dry_run)。--no-ledger 纯预览(不写判同决策, 保 B仓纯净)。
命门: 宁碎片不错合——只有 verdict==same 才并簇; uncertain/different 各自独立。

用法: uv run python scripts/dedup/orchestrate.py [--disc econ|math|misc|all] [--sim 0.9] [--cap 200]
      [--strong deepseek-pro] [--apply] [--no-ledger] [--concurrency 4]
      [--singletons-only] [--max-new N] [--substrate ID]
"""

import asyncio
import json
import os
import re
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
# 止血落后: 只落单例, 跳过判同/并簇(宁冗余不误删; 合并留给后续金集过关的判同轮)
SINGLETONS_ONLY = "--singletons-only" in sys.argv
# 每轮最多新增多少 A仓 KU(定时器安全阀; 0=不限)
MAX_NEW = int(_arg("--max-new", "0"))
# 历史硬编码书目保留作 fallback 文档; 运行时 --disc econ|math|misc 动态发现 A仓 substrate。
# 硬编码会过期(2026-07-19 已踩过: 飞轮新书不进列表 → B仓永久漏灌)。
ECON_SUBS_LEGACY = [
    "microecon_en_full_v2",
    "micro_clean",
    "mankiw_principles_econ_10e",
    "econ_zh_2726f38224",
    "econ_zh_da27a19f30",
    "econ_zh_3f11a8f38e",
    "econ_9ea2a19eac",
    "econ_131d7dbd3b",
]
_SUB1 = _arg("--substrate")  # 单书验证: 覆盖 SUBS
# SUBS 在 main() 里动态解析; 这里只放 CLI 单书覆盖占位
SUBS = [_SUB1] if _SUB1 else None  # None → main 里按 DISC 发现


def _disc_match(substrate_id: str, disc: str) -> bool:
    """学科 substrate 归属(与飞轮命名约定对齐, 看裸前缀不猜书名)。"""
    s = (substrate_id or "").lower()
    if disc == "all":
        return True
    if disc == "econ":
        return bool(
            re.search(r"(^|_)econ(_|$)|mankiw|microecon|micro_clean|经济", s)
            or "经济" in (substrate_id or "")
        )
    if disc == "math":
        return bool(
            re.search(
                r"(^|_)(math|advmath|math_prog)(_|$)|shufen|shida|calculus|algebra|topology|analysis",
                s,
            )
        )
    if disc == "misc":
        return s.startswith("misc") or s.startswith("paper")
    return False


async def discover_substrates(kg, disc: str):
    """从 A仓 动态拉该学科全部 substrate(有向量、未隔离)。"""
    if disc == "all":
        return None  # None = 不按书过滤
    rows = await kg.fetch(
        "SELECT DISTINCT substrate_id FROM aii.ku_onto "
        "WHERE embedding IS NOT NULL AND is_quarantined IS NOT TRUE "
        "AND substrate_id IS NOT NULL"
    )
    found = sorted(r["substrate_id"] for r in rows if _disc_match(r["substrate_id"], disc))
    if not found and disc == "econ":
        # 极端空库 fallback, 不阻断手工验证
        return list(ECON_SUBS_LEGACY)
    return found

_TYPE_MAP = {
    "conceptual": "conceptual",
    "rationale": "rationale",
    "procedural": "procedural",
    "factual": "factual",
    "positional": "conceptual",
    "metacognitive": "conceptual",
}


def _row_to_item(ku_id, r):
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


async def _item(conn, ku_id):
    r = await conn.fetchrow(
        "SELECT title, natural_text_zh, natural_text, substrate_id, knowledge_type, provenance "
        "FROM aii.ku_onto WHERE ku_id=$1",
        ku_id,
    )
    return _row_to_item(ku_id, r)


async def _items_batch(conn, ku_ids):
    """批量取 KU 元数据(大批量单例补灌避免 N 次 round-trip 卡死)。"""
    if not ku_ids:
        return {}
    rows = await conn.fetch(
        "SELECT ku_id, title, natural_text_zh, natural_text, substrate_id, knowledge_type, provenance "
        "FROM aii.ku_onto WHERE ku_id = ANY($1::text[])",
        list(ku_ids),
    )
    out = {}
    for r in rows:
        it = _row_to_item(r["ku_id"], r)
        if it:
            out[r["ku_id"]] = it
    return out


async def main():
    global SUBS
    register_providers()
    llm_weak = ProviderRegistry.get().llm(WEAK) if not SINGLETONS_ONLY else None
    llm_strong = ProviderRegistry.get().llm(STRONG) if not SINGLETONS_ONLY else None
    kg = await asyncpg.create_pool(KG_URL, min_size=1, max_size=CONC + 2)
    rf = await asyncpg.create_pool(REFINED_URL, min_size=1, max_size=CONC + 2, init=register_vector)

    # 幂等: 已入 B仓 的 raw_ku_id 不再入(增量: A仓固定、B仓随书生长)
    async with rf.acquire() as rc:
        ing = await rc.fetch(
            "SELECT DISTINCT jsonb_array_elements(contributions)->>'raw_ku_id' AS rid FROM rf.refined_ku"
        )
    ingested = {r["rid"] for r in ing if r["rid"]}

    # 动态学科书目(除非 --substrate 已钉死单书)
    if SUBS is None:
        async with kg.acquire() as c:
            SUBS = await discover_substrates(c, DISC)
    mode = "APPLY(落库)" if APPLY else "DRY-RUN(不落库)"
    only = " singletons-only" if SINGLETONS_ONLY else ""
    print(
        f"[{mode}{only}] disc={DISC} substrates={len(SUBS) if SUBS else 'ALL'} "
        f"sim≥{SIM} cap={CAP} max_new={MAX_NEW or '∞'} "
        f"关3弱={WEAK} 升级强={STRONG} ledger={USE_LEDGER}"
    )
    if SUBS is not None and len(SUBS) <= 12:
        print(f"  books: {SUBS}")
    elif SUBS is not None:
        print(f"  books sample: {SUBS[:8]} ... (+{len(SUBS) - 8})")
    print(f"幂等: B仓已入 {len(ingested)} 个 A仓 KU, 本轮跳过")

    clusters = []
    results = []
    item_by_id = {}
    cands, dropped = [], 0

    if not SINGLETONS_ONLY:
        async with kg.acquire() as c:
            cands, dropped = await ku_candidates(
                c, sim=SIM, cap=CAP, substrates=SUBS, exclude=ingested
            )
        print(
            f"粗筛候选 {len(cands)} 对" + (f" (超 cap 丢弃 {dropped})" if dropped else ""),
            flush=True,
        )

        sem = asyncio.Semaphore(CONC)

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
                ) as e:  # 单对失败→ 降级 different(宁碎片), 不拖垮整批
                    fails.append((c, str(e)[:60]))
                    v = {"verdict": "different", "reason": f"判同失败降级(宁碎片): {str(e)[:50]}"}
            results.append((a, b, v))

        fails = []
        await asyncio.gather(*(judge_one(c) for c in cands))
        if fails:
            print(
                f"⚠ {len(fails)} 对判同失败, 已降级 different(宁碎片): "
                f"{[f[0]['a_id'] for f in fails[:5]]}"
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
    else:
        print("跳过判同(singletons-only): 全部未入 B 的 KU 各成独立 refined_ku", flush=True)

    # 组装落库单元: 合并簇 + 单例(批内未被合并的 KU 各自独立成 refined_ku)
    merged_ids = set().union(*clusters) if clusters else set()
    print("查询本学科 A仓 KU 列表…", flush=True)
    async with kg.acquire() as c:
        q = (
            "SELECT ku_id FROM aii.ku_onto WHERE embedding IS NOT NULL AND is_quarantined IS NOT TRUE"
            + (" AND substrate_id = ANY($1::text[])" if SUBS else "")
            + " ORDER BY created_at ASC"  # 先旧后新, 定时器分批可预测
        )
        all_ids = [r["ku_id"] for r in await c.fetch(q, *([list(SUBS)] if SUBS else []))]
    print(f"A仓本学科 {len(all_ids)} 条(有向量)", flush=True)
    singleton_ids = [i for i in all_ids if i not in merged_ids and i not in ingested]
    if MAX_NEW > 0:
        # 合并簇优先占额度, 余量给单例(止血时通常无簇)
        budget = max(0, MAX_NEW - sum(len(cl) for cl in clusters))
        if len(singleton_ids) > budget:
            print(f"max-new={MAX_NEW}: 单例截断 {len(singleton_ids)} → {budget}", flush=True)
            singleton_ids = singleton_ids[:budget]
    missing = [i for i in singleton_ids if i not in item_by_id]
    # 簇成员也可能缺 item(判同路径已填); 一并补齐
    for cl in clusters:
        for i in cl:
            if i not in item_by_id:
                missing.append(i)
    if missing:
        print(f"批量拉取 {len(missing)} 条 KU 元数据…", flush=True)
        async with kg.acquire() as c:
            # 分块, 避免超大 ANY 参数
            CHUNK = 2000
            for off in range(0, len(missing), CHUNK):
                batch = missing[off : off + CHUNK]
                item_by_id.update(await _items_batch(c, batch))
                print(f"  …{min(off + CHUNK, len(missing))}/{len(missing)}", flush=True)

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
        # B仓 向量策略:
        #  · 单例(1:1 未合并): 直接复用 A仓 embedding(内容未改, BGE-M3 同模型; 省 GPU/避 OOM)
        #  · 合并簇: 必须在合并后文本上重算(走 aii-embed; trust_env=False 防代理误路由)
        import httpx as _httpx
        import numpy as np

        embed_url = os.getenv("AII_EMBED_URL", "http://127.0.0.1:8102")

        def _embed_batch(batch):
            timeout = _httpx.Timeout(connect=10, read=300, write=30, pool=10)
            with _httpx.Client(trust_env=False, timeout=timeout) as c:
                r = c.post(f"{embed_url}/embed", json={"texts": batch})
                r.raise_for_status()
                return r.json()["embeddings"]

        # 1) 尽量从 A仓 搬单例向量
        need_reembed_idx = []  # indices into built that must re-embed
        embs: list = [None] * len(built)
        singleton_raw_ids = []
        singleton_pos = []
        for i, (members, contribs, fc) in enumerate(built):
            if len(members) == 1:
                singleton_raw_ids.append(members[0]["id"])
                singleton_pos.append(i)
            else:
                need_reembed_idx.append(i)
        if singleton_raw_ids:
            print(f"复用 A仓向量: {len(singleton_raw_ids)} 单例…", flush=True)
            async with kg.acquire() as c:
                await register_vector(c)
                CHUNK = 2000
                got = {}
                for off in range(0, len(singleton_raw_ids), CHUNK):
                    chunk_ids = singleton_raw_ids[off : off + CHUNK]
                    rows = await c.fetch(
                        "SELECT ku_id, embedding FROM aii.ku_onto "
                        "WHERE ku_id = ANY($1::text[]) AND embedding IS NOT NULL",
                        chunk_ids,
                    )
                    for r in rows:
                        got[r["ku_id"]] = np.asarray(r["embedding"], dtype=np.float32)
            for rid, pos in zip(singleton_raw_ids, singleton_pos):
                if rid in got:
                    embs[pos] = got[rid]
                else:
                    need_reembed_idx.append(pos)
            print(
                f"  复用成功 {sum(1 for e in embs if e is not None)} / "
                f"需重算 {len(need_reembed_idx)}",
                flush=True,
            )

        # 2) 合并簇 + 缺向量单例: 调 aii-embed
        if need_reembed_idx:
            texts = []
            for i in need_reembed_idx:
                members, contribs, _ = built[i]
                texts.append(embed_text(contribs) or (members[0].get("name") or "") or " ")
            BATCH = int(os.getenv("B_REPO_EMBED_BATCH", "8"))  # 长文小批, 防 10G 卡 OOM
            print(
                f"重算嵌入 {len(texts)} 条 → {embed_url} (batch={BATCH})…", flush=True
            )
            fresh = []
            for i in range(0, len(texts), BATCH):
                chunk = texts[i : i + BATCH]
                fresh.extend(await loop.run_in_executor(None, lambda c=chunk: _embed_batch(c)))
                print(f"  embed {min(i + BATCH, len(texts))}/{len(texts)}", flush=True)
            for pos, emb in zip(need_reembed_idx, fresh):
                embs[pos] = emb

        persisted = 0
        print(f"写入 rf.refined_ku ×{len(built)}…", flush=True)
        for (members, contribs, fc), emb in zip(built, embs):
            if emb is None:
                print(f"⚠ skip no-embedding: {members[0]['id']}", flush=True)
                continue
            names = [m.get("name") or "" for m in members]
            en = next((x for x in names if not any("一" <= ch <= "鿿" for ch in x)), None)
            zh = next((x for x in names if any("一" <= ch <= "鿿" for ch in x)), None)
            kt = _TYPE_MAP.get(members[0].get("ktype"), "conceptual")
            async with rf.acquire() as rc:
                await persist_refined_ku(
                    rc,
                    point=en or names[0] or members[0]["id"],
                    point_zh=zh,
                    ku_type=kt,
                    contributions=contribs,
                    facet_count=fc,
                    embedding=emb,
                    natural_text_zh=render_zh(contribs),
                )
            persisted += 1
            if persisted % 500 == 0 or persisted == len(built):
                print(f"  write {persisted}/{len(built)}", flush=True)
        print(f"\n✓ 落库 refined_ku: {persisted} 个 (单例复用A向量 / 合并重算BGE-M3)")
    else:
        print(
            f"\nDRY-RUN: 将落库 {len(built)} 个 refined_ku "
            f"({len(clusters)}合并+{len(singleton_ids)}单例)。--apply 落库"
        )
    await kg.close()
    await rf.close()


if __name__ == "__main__":
    asyncio.run(main())
