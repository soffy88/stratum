"""步骤4.5 有向关系 — readout 法: 从讲透的 KU 读出它【已表达】的概念→概念关系。

设计 §2.1: 读出(非推断/非judge)——只提 KU 内容明确表达的关系, O(N) 一 call/KU,
质量继承 KU(先讲透不编→读关系也不编)。关系类型 derives/subsumes/prerequisite。
落 refined_directed_edge(概念骨架, M1 超边挂其上生长; 也供判同关2 判上下位)。
命门: 只读已表达的不猜; strength=表达此边的 KU 数; grade=unverified(不验证)。
读出是可加的、grade未验证、可重做 → 用便宜/配额充足的模型, 不升级 pro。

★2026-07-29: 默认改 NIM(项目内 .pipeline_keys.json ≥7 key 池轮转),
  不再用 deepseek-flash(易 402)。DeepSeek 仍可用 --provider deepseek。

用法:
  uv run python scripts/dedup/readout.py [--limit N] [--apply] [--concurrency 8]
  uv run python scripts/dedup/readout.py --limit 100 --apply
  uv run python scripts/dedup/readout.py --provider deepseek --model deepseek-flash  # 旧路
"""

from __future__ import annotations

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
from aii.api._provider import _make_deepseek_caller, register_providers  # noqa: E402
from ledger import DecisionLedger  # noqa: E402

REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
NIM_BASE = "https://integrate.api.nvidia.com/v1/chat/completions"
# 与 advmath/econ 飞轮对齐的默认 NIM 模型
DEFAULT_NIM_MODEL = os.getenv("NIM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
# ★NVIDIA NIM 免费层硬顶: 每 API key 40 req/min。超过会 429。
#   默认严格按 40 限流(间隔 1.5s/key); 可用 NIM_RPM 调低(如 36 留余量给其它飞轮同 key),
#   但不可用 NIM_RPM 抬过 40(除非显式 NIM_RPM_CAP 放开, 付费层再用)。
NIM_FREE_TIER_RPM = 40.0
_rpm_req = float(os.getenv("NIM_RPM", "40"))
_rpm_cap = float(os.getenv("NIM_RPM_CAP", str(NIM_FREE_TIER_RPM)))
DEFAULT_NIM_RPM = min(_rpm_req, _rpm_cap)


def _arg(f, d=None):
    return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d


PROVIDER = (_arg("--provider", "nim") or "nim").lower()  # nim | deepseek
MODEL = _arg(
    "--model",
    DEFAULT_NIM_MODEL if PROVIDER == "nim" else "deepseek-flash",
)
CONC = int(_arg("--concurrency", "0"))  # 0 = 自动: nim 池大小, deepseek 用 4
LIMIT = int(_arg("--limit", "0"))
APPLY = "--apply" in sys.argv
USE_LEDGER = "--no-ledger" not in sys.argv
# 已在 decision_ledger 做过 readout 的 KU 默认跳过(幂等增量); --redo 全量重读
REDO = "--redo" in sys.argv

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


def _load_pipeline_keys() -> dict[str, str]:
    """读 aii/.pipeline_keys.json (8 槽: econ/math_en/econ_zh/math_zh/advmath_*/learning)。"""
    path = ROOT / ".pipeline_keys.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    return {k: v for k, v in raw.items() if isinstance(v, str) and v.strip()}


def build_nim_pool(model: str | None = None, rpm: float | None = None):
    """多 NIM key 池: 每 key 独立 rpm 限流, 轮转并发 ≈ N×吞吐。"""
    model = model or DEFAULT_NIM_MODEL
    rpm = DEFAULT_NIM_RPM if rpm is None else rpm
    keys = _load_pipeline_keys()
    # 环境变量单 key 兜底(无 pool 文件时)
    env_key = os.getenv("NVIDIA_NIM_API_KEY", "").strip()
    if env_key and "env" not in keys:
        keys = {**keys, "env": env_key}
    if not keys:
        raise RuntimeError(
            "无可用 NIM key: 需要 aii/.pipeline_keys.json 或 NVIDIA_NIM_API_KEY"
        )
    pool = [
        (
            name,
            _make_deepseek_caller(
                key,
                model=model,
                base_url=NIM_BASE,
                rpm=rpm,  # 每 key 独立时间槽, 间隔 60/rpm 秒
            ),
        )
        for name, key in keys.items()
    ]
    # 理论峰值吞吐 = n_keys × rpm; 免费层 8×40=320/min(key 独立额度时)
    print(
        f"NIM key 池: {len(pool)} key {list(keys)} model={model} "
        f"rpm/key={rpm} (硬顶 {NIM_FREE_TIER_RPM}/key·min, 间隔 {60.0 / rpm:.2f}s)",
        flush=True,
    )
    return pool


def _llm_text(resp) -> str:
    if isinstance(resp, dict):
        parts = resp.get("content") or []
        return "".join(
            (p.get("text") or "") for p in parts if isinstance(p, dict) and p.get("type") == "text"
        )
    return str(resp or "")


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
    raw = _llm_text(r)
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
    if PROVIDER == "nim":
        pool = build_nim_pool(MODEL)
        callers = [c for _, c in pool]
        model_label = f"nim/{MODEL}"
    elif PROVIDER == "deepseek":
        register_providers()
        from obase import ProviderRegistry

        callers = [ProviderRegistry.get().llm(MODEL)]
        model_label = f"deepseek/{MODEL}"
        print(f"DeepSeek 单路 model={MODEL} (易 402, 仅兜底)", flush=True)
    else:
        raise SystemExit(f"--provider 须为 nim|deepseek, 得到 {PROVIDER!r}")

    n_callers = len(callers)
    # NIM: 默认并发=key 数(每 key 最多 1 路 in-flight)。
    #   同一 key 上叠 2 路只会在限流槽里排队, 拉长尾延迟→Timeout, 不提高吞吐;
    #   吞吐上限由 40 rpm/key 决定, 不是并发数。
    conc = CONC if CONC > 0 else (n_callers if PROVIDER == "nim" else 4)
    if PROVIDER == "nim":
        conc = min(conc, n_callers)

    rf = await asyncpg.create_pool(REFINED_URL, min_size=1, max_size=conc + 2)

    # 已读出过的 KU(台账幂等)
    done = set()
    if not REDO:
        async with rf.acquire() as c:
            rows = await c.fetch(
                "SELECT DISTINCT inputs->>'ku_id' AS kid FROM rf.decision_ledger "
                "WHERE decision_type='readout' AND inputs ? 'ku_id'"
            )
            done = {r["kid"] for r in rows if r["kid"]}
        print(f"幂等: 台账已有 readout {len(done)} 个 KU, 本轮跳过", flush=True)

    async with rf.acquire() as c:
        q = """
            SELECT k.ku_id, k.point, k.natural_text_zh,
                   jsonb_agg(jsonb_build_object('cid',c.concept_id,'name',c.name,'name_zh',c.name_zh)) AS concepts
            FROM rf.refined_ku k
            JOIN rf.refined_ku_concept kc ON kc.ku_id=k.ku_id
            JOIN rf.refined_concept c ON c.concept_id=kc.concept_id
            GROUP BY k.ku_id, k.point, k.natural_text_zh HAVING count(*)>=2
            ORDER BY k.created_at DESC
        """
        kus = await c.fetch(q)
    if done:
        kus = [r for r in kus if r["ku_id"] not in done]
    if LIMIT > 0:
        kus = kus[:LIMIT]

    print(
        f"[{'APPLY' if APPLY else 'DRY-RUN'}] readout: {len(kus)} 个 KU(≥2概念) "
        f"provider={PROVIDER} model={model_label} conc={conc}",
        flush=True,
    )
    if not kus:
        print("无可读 KU, 退出")
        await rf.close()
        return

    sem = asyncio.Semaphore(conc)
    agg = defaultdict(lambda: {"n": 0, "kus": []})  # (s,d,t) -> strength/evidence
    fails = [0]
    fail_samples: list[str] = []
    ok_n = [0]
    counter = {"i": 0}
    lock = asyncio.Lock()

    async def next_caller():
        async with lock:
            i = counter["i"]
            counter["i"] = i + 1
            return callers[i % n_callers]

    async def one(row):
        async with sem:
            llm = await next_caller()
            try:
                edges, raw = await asyncio.wait_for(readout_ku(row, llm), timeout=180)
            except Exception as e:  # noqa: BLE001
                fails[0] += 1
                if len(fail_samples) < 5:
                    fail_samples.append(f"{row['ku_id'][:40]}: {type(e).__name__}: {e}")
                return
        ok_n[0] += 1
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
                    model=model_label,
                    llm_raw={"response": (raw or "")[:800]},
                    actor="llm",
                )
        if (ok_n[0] + fails[0]) % 50 == 0:
            print(
                f"  progress ok={ok_n[0]} fail={fails[0]} edges={len(agg)}",
                flush=True,
            )

    await asyncio.gather(*(one(r) for r in kus))

    by_type = defaultdict(int)
    for (s, d, t), v in agg.items():
        by_type[t] += 1
    print(
        f"读出边: {len(agg)} 条(去重) | 类型: {dict(by_type)} | "
        f"成功 {ok_n[0]} | 失败 {fails[0]}",
        flush=True,
    )
    if fail_samples:
        print("失败样本:")
        for s in fail_samples:
            print(f"  · {s}")

    if not APPLY:
        print("样本:")
        async with rf.acquire() as c:
            for (s, d, t), v in sorted(agg.items(), key=lambda x: -x[1]["n"])[:8]:
                sn = await c.fetchval("SELECT name FROM rf.refined_concept WHERE concept_id=$1", s)
                dn = await c.fetchval("SELECT name FROM rf.refined_concept WHERE concept_id=$1", d)
                print(f"  {sn} --{t}--> {dn}  (×{v['n']})")
        print(f"\nDRY-RUN: 将落/合并 {len(agg)} 条 refined_directed_edge。--apply 落库")
        await rf.close()
        return

    # 合并进已有边(无 UNIQUE 约束, 手动 upsert by src/dst/type)
    async with rf.acquire() as c:
        existing = await c.fetch(
            "SELECT edge_id, src_concept, dst_concept, relation_type, strength, evidence "
            "FROM rf.refined_directed_edge"
        )
        ex_map = {
            (r["src_concept"], r["dst_concept"], r["relation_type"]): r for r in existing
        }
        inserted = updated = 0
        for (s, d, t), v in agg.items():
            strength = min(1.0, 0.5 + 0.1 * v["n"])
            key = (s, d, t)
            if key in ex_map:
                old = ex_map[key]
                old_ev = old["evidence"]
                if isinstance(old_ev, str):
                    try:
                        old_ev = json.loads(old_ev)
                    except Exception:
                        old_ev = {}
                old_ev = old_ev or {}
                kus_old = list(old_ev.get("kus") or [])
                for kid in v["kus"]:
                    if kid not in kus_old and len(kus_old) < 10:
                        kus_old.append(kid)
                new_count = int(old_ev.get("count") or 0) + v["n"]
                new_ev = {"kus": kus_old, "count": new_count}
                new_strength = min(1.0, 0.5 + 0.1 * new_count)
                await c.execute(
                    "UPDATE rf.refined_directed_edge SET strength=$2, evidence=$3 "
                    "WHERE edge_id=$1",
                    old["edge_id"],
                    new_strength,
                    json.dumps(new_ev, ensure_ascii=False),
                )
                updated += 1
            else:
                await c.execute(
                    """INSERT INTO rf.refined_directed_edge
                         (src_concept,dst_concept,relation_type,strength,grade,evidence)
                       VALUES($1,$2,$3,$4,'unverified',$5)""",
                    s,
                    d,
                    t,
                    strength,
                    json.dumps({"kus": v["kus"], "count": v["n"]}, ensure_ascii=False),
                )
                inserted += 1
    print(
        f"✓ 落库 refined_directed_edge: +{inserted} 新 / ~{updated} 合并更新 "
        f"(本轮读出 {len(agg)} 条骨架)",
        flush=True,
    )
    await rf.close()


if __name__ == "__main__":
    asyncio.run(main())
