"""B仓步骤4 M0 · concept canonical 归一 dry_run(只算+打印, 绝不落库).

AII-REFINED-REPO-MASTER-001 §6 "真正同一才合一" 四道关。
命门: 错合=地基污染(上层超边/本性全错,难恢复); 碎片可恢复 → 宁碎片不错合, 拿不准→CANDIDATE。
红线: dry_run不落库; 先小范围; 人工抽查SAME无错合再真合(§6.3)。

源: A仓 concept_onto(name/name_zh/discipline/vector 1024, 已对齐BGE-M3), 限三书概念(=B仓refined_ku的概念)。
候选: 同discipline 余弦≥阈值(跨学科不在此层自动合,留后续)。
四关: 关1判别维度(判别词硬闸 _forced_different 复用 + LLM本质维度) 关2类层级/互斥(LLM当场判上下位)
      关3 LLM语义(反义/方向反) 关4 高风险→CANDIDATE。+ 自一致性二次确认SAME。
用法: cd aii; NVIDIA_NIM_API_KEY=<econ key> .venv/bin/python scripts/refined_concept_canonical_dryrun.py [--sim 0.80] [--max 150]
"""
import asyncio, os, re, json, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from pgvector.asyncpg import register_vector

sys.path.insert(0, str(ROOT / "scripts"))
from refined_dedup_dryrun import _forced_different      # 判别词硬闸(price/income, consumer/producer...)
from refined_ingest_dryrun import _build_nim_pool       # 4 NIM key 池

BOOKS = ["mankiw_principles_econ_10e", "microecon_en_full_v2", "micro_clean"]
A_DSN = os.getenv("DATABASE_URL")

JUDGE_SYS = (
    "你判断两个【概念】是否【真正同一】(本体级同一, 为知识库概念归一 canonical)。"
    "真正同一 ⟺ 全部满足: ①判别维度全对齐(每个本质维度取值相同, 非名字像) "
    "②非上下位(A不是B的子类/特化/整体-部分) ③非互斥(非并列的不同类) ④核心结构相同。缺任一→DIFFERENT。"
    "★命门: 错合=地基污染(上层全错,难恢复); 碎片可恢复 → 宁碎片不错合; 拿不准/高风险一律 CANDIDATE(不自动合)。"
    "判例(务必照判): "
    "(1)price-inelastic{弹性对象:价格} vs income-inelastic{弹性对象:收入} → DIFFERENT(本质维度不同)。"
    "(2)increasing opportunity cost vs opportunity cost → DIFFERENT(前者是后者的特化/上下位)。"
    "(3)机会成本 vs Opportunity Cost(同概念跨书/跨语言, 措辞不同) → SAME。"
    "(4)consumer surplus vs producer surplus → DIFFERENT(并列互斥)。"
    "(5)机会成本 vs 经济成本 → DIFFERENT(近义非同一)。"
    "(6)price floor vs price ceiling → DIFFERENT(方向相反)。"
    "只有两概念指【同一个】东西(判别维度全同、非上下位、非互斥)才 SAME; 像/相关/上下位/互斥/反义 → DIFFERENT; 模糊→CANDIDATE。"
    "只输出 JSON: {\"verdict\":\"SAME|DIFFERENT|CANDIDATE\",\"why\":\"≤20字\"}。"
)


# ---- 概念 + 代表KU上下文 ----
async def _concepts(conn):
    rows = await conn.fetch("""
        SELECT DISTINCT co.concept_id, co.name, co.name_zh, co.discipline, co.vector
        FROM aii.concept_onto co
        JOIN aii.ku_concept_onto kc USING(concept_id)
        JOIN aii.ku_onto k USING(ku_id)
        WHERE k.substrate_id = ANY($1) AND co.vector IS NOT NULL
    """, BOOKS)
    return rows


async def _example(conn, cid, cache):
    if cid in cache:
        return cache[cid]
    r = await conn.fetchrow("""
        SELECT k.title, left(k.natural_text, 300) tx
        FROM aii.ku_concept_onto kc JOIN aii.ku_onto k USING(ku_id)
        WHERE kc.concept_id=$1 ORDER BY length(k.natural_text) DESC LIMIT 1""", cid)
    cache[cid] = (r["title"], r["tx"]) if r else ("", "")
    return cache[cid]


async def _pairs(conn, sim, limit):
    rows = await conn.fetch("""
        WITH c AS (
          SELECT DISTINCT co.concept_id, co.name, co.name_zh, co.discipline, co.vector
          FROM aii.concept_onto co
          JOIN aii.ku_concept_onto kc USING(concept_id)
          JOIN aii.ku_onto k USING(ku_id)
          WHERE k.substrate_id = ANY($1) AND co.vector IS NOT NULL)
        SELECT a.concept_id ai, a.name an, a.name_zh anz, a.discipline ad,
               b.concept_id bi, b.name bn, b.name_zh bnz, b.discipline bd,
               round((1-(a.vector<=>b.vector))::numeric,3) sim
        FROM c a JOIN c b ON a.concept_id < b.concept_id AND a.discipline = b.discipline
        WHERE (1-(a.vector<=>b.vector)) >= $2
        ORDER BY sim DESC LIMIT $3
    """, BOOKS, sim, limit)
    return [dict(r) for r in rows]


def _ctx(name, name_zh, disc, ex):
    return f"概念:{name}" + (f" / {name_zh}" if name_zh else "") + f" [{disc}]\n代表知识: {ex[0]} — {ex[1]}"


async def _vote(llm, sem, p, ca, cb):
    a = _ctx(p["an"], p["anz"], p["ad"], ca)
    b = _ctx(p["bn"], p["bnz"], p["bd"], cb)
    async with sem:
        try:
            r = await asyncio.wait_for(llm(messages=[{"role": "user", "content":
                f"概念A:\n{a}\n\n概念B:\n{b}\n\n它们是否真正同一(本体级)? 只输出JSON。"}],
                system=JUDGE_SYS, max_tokens=80), timeout=120)
            t = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text")
            m = re.search(r"\{.*\}", t, re.DOTALL)
            if not m:
                return "CANDIDATE", "无JSON"
            j = json.loads(m.group(0))
            v = (j.get("verdict") or "CANDIDATE").upper()
            return (v if v in ("SAME", "DIFFERENT", "CANDIDATE") else "CANDIDATE"), (j.get("why") or "")[:30]
        except Exception as e:
            return "CANDIDATE", f"err:{type(e).__name__}"


async def _judge(pool, sem, conn, cache, idx, p):
    # 关1硬闸: 判别词矛盾(本质维度) → 确定性 DIFFERENT
    if _forced_different(p["an"], p["bn"]) or _forced_different(p["anz"] or "", p["bnz"] or ""):
        return {**p, "verdict": "DIFFERENT", "why": "判别词硬闸", "gate": True}
    llm = pool[idx % len(pool)]
    ca = await _example(conn, p["ai"], cache)
    cb = await _example(conn, p["bi"], cache)
    v1, w1 = await _vote(llm, sem, p, ca, cb)
    if v1 != "SAME":
        return {**p, "verdict": v1, "why": w1, "gate": False}
    # 自一致性: SAME 二次确认(误合才危险), 不一致→CANDIDATE(不自动合)
    v2, w2 = await _vote(llm, sem, p, ca, cb)
    if v2 == "SAME":
        return {**p, "verdict": "SAME", "why": w1, "gate": False}
    return {**p, "verdict": "CANDIDATE", "why": f"2票不一({w2})", "gate": False}


def _s(p, side):
    return f"{p[side+'n']}" + (f"/{p[side+'nz']}" if p[side+'nz'] else "")


async def main():
    def arg(f, d): return sys.argv[sys.argv.index(f) + 1] if f in sys.argv else d
    sim = float(arg("--sim", "0.80"))
    mx = int(arg("--max", "150"))

    conn = await asyncpg.connect(A_DSN); await register_vector(conn)
    cands = await _pairs(conn, sim, mx)
    print(f"== B仓步骤4 M0 concept canonical dry_run ==", flush=True)
    print(f"书={BOOKS}  同discipline sim≥{sim}  候选对={len(cands)}  (只算+打印, 不落库)\n", flush=True)

    pool = _build_nim_pool()
    sem = asyncio.Semaphore(len(pool))
    cache = {}
    # 单连接不可并发查 → 先串行预取所有候选概念的代表KU填cache, 之后 _judge 只读cache
    for cid in {p["ai"] for p in cands} | {p["bi"] for p in cands}:
        await _example(conn, cid, cache)
    judged = await asyncio.gather(*(_judge(pool, sem, conn, cache, i, p) for i, p in enumerate(cands)))

    same = [j for j in judged if j["verdict"] == "SAME"]
    diff = [j for j in judged if j["verdict"] == "DIFFERENT"]
    cand = [j for j in judged if j["verdict"] == "CANDIDATE"]
    gated = [j for j in judged if j.get("gate")]
    print(f"裁决: SAME={len(same)}(合canonical)  DIFFERENT={len(diff)}(硬闸{len(gated)})  CANDIDATE={len(cand)}(不自动合)\n")

    print("── SAME (会归一为同一 canonical 概念) ──────────────────")
    for j in sorted(same, key=lambda x: -x["sim"]):
        print(f"  {j['sim']:.3f} [{j['ad'][:4]}] {_s(j,'a')[:34]}  ≡  {_s(j,'b')[:34]}  ({j['why']})")
    print("\n── CANDIDATE (命门: 高风险不自动合, 人工裁) ─────────────")
    for j in sorted(cand, key=lambda x: -x["sim"]):
        print(f"  {j['sim']:.3f} [{j['ad'][:4]}] {_s(j,'a')[:34]}  ?  {_s(j,'b')[:34]}  ({j['why']})")
    print("\n── DIFFERENT (应被挡的假朋友) ─ 抽样前20 ────────────────")
    for j in sorted(diff, key=lambda x: -x["sim"])[:20]:
        g = "硬闸" if j.get("gate") else "LLM"
        print(f"  {j['sim']:.3f} [{j['ad'][:4]}] {_s(j,'a')[:30]}  ≠  {_s(j,'b')[:30]}  ({g}:{j['why']})")

    # 持久化裁决(带concept_id, 供M0落库确定性应用; 不落库本身)
    dump = [{"ai": j["ai"], "bi": j["bi"], "an": j["an"], "bn": j["bn"],
             "ad": j["ad"], "sim": float(j["sim"]), "verdict": j["verdict"],
             "why": j.get("why", ""), "gate": j.get("gate", False)} for j in judged]
    (ROOT / "econ_pipeline" / "ckpts" / "refined_concept_verdicts_econ.json").write_text(
        json.dumps(dump, ensure_ascii=False, indent=1))
    print(f"\nDONE (dry-run, 无写库). 裁决已存 refined_concept_verdicts_econ.json(带concept_id)。"
          f"人工核: SAME无错合? CANDIDATE该停? 假朋友全DIFFERENT?", flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
