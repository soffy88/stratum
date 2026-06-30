"""B仓步骤2 · KU去重判同 dry_run(只算+打印, 绝不落库).

AII-REFINED-REPO-MASTER-001 第五部分。验证 ②KU判同先行 + ③片段整合, 不做 ④存B仓。
命门(宁冗余不误删): 判"同一个点"宁严勿松, 拿不准→UNCERTAIN→保留两份(不合)。
红线: dry_run 不落库; 先小范围(经济三书)验证; 测假朋友(高相似实非同点)是否被挡。

范围说明:
  · 候选 = A仓现成 BGE-M3 向量跨书近邻(sim≥阈值), 三本经济书 mankiw/microecon/micro_clean。
  · 判同在原文上做(llama-3.3-70b 跨语言鲁棒); ①翻译英文是 B仓存储形态, 推迟到步骤3灌入。
  · 防错合三道: (a)知识类型/标题判别词硬闸 → 确定性 DIFFERENT, 不进 LLM;
                (b)3值 LLM 判同(SAME/DIFFERENT/UNCERTAIN); (c)UNCERTAIN 当不合并。

用法: cd <repo>; .venv/bin/python scripts/refined_dedup_dryrun.py [--sim 0.78] [--max 200] [--books mankiw_principles_econ_10e,microecon_en_full_v2,micro_clean]
"""
import asyncio, os, re, json, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from pgvector.asyncpg import register_vector
from aii.api._provider import register_providers
from obase import ProviderRegistry

DEFAULT_BOOKS = ["mankiw_principles_econ_10e", "microecon_en_full_v2", "micro_clean"]

# ---- 判别词硬闸(港自 concept_onto_ops, 作用在 KU 标题) -----------------------
_DISC_FAMILIES = [
    {"price", "income"}, {"supply", "demand"}, {"import", "export"},
    {"short-run", "long-run"}, {"short run", "long run"}, {"nominal", "real"},
    {"gross", "net"}, {"micro", "macro"}, {"buyer", "seller"}, {"employer", "employee"},
    {"供给", "需求"}, {"价格", "收入"}, {"短期", "长期"}, {"进口", "出口"},
]
_DISC_QUALIFIERS = [
    "increasing", "decreasing", "perfectly", "unitary", "cross",
    "marginal", "inferior", "complement", "substitute", "递增", "递减", "边际",
]


def _forced_different(a: str, b: str) -> bool:
    la, lb = (a or "").lower(), (b or "").lower()
    for fam in _DISC_FAMILIES:
        va = {w for w in fam if w in la}
        vb = {w for w in fam if w in lb}
        if va and vb and va != vb:
            return True
    for q in _DISC_QUALIFIERS:
        if (q in la) != (q in lb):
            return True
    return False


# ---- 候选对: 三书之间, 跨书近邻 sim≥阈值 -------------------------------------
async def _pairs(conn, books, sim, limit):
    rows = await conn.fetch("""
        WITH pool AS (
          SELECT ku_id, title, knowledge_type, natural_text, substrate_id, embedding
          FROM aii.ku_onto
          WHERE substrate_id = ANY($1) AND embedding IS NOT NULL
        )
        SELECT a.ku_id a_id, a.title a_title, a.knowledge_type a_kt, a.natural_text a_tx, a.substrate_id a_sub,
               n.ku_id b_id, n.title b_title, n.knowledge_type b_kt, n.natural_text b_tx, n.substrate_id b_sub,
               round((1-(a.embedding<=>n.embedding))::numeric,3) sim
        FROM pool a
        CROSS JOIN LATERAL (
          SELECT ku_id, title, knowledge_type, natural_text, substrate_id, embedding
          FROM pool b
          WHERE b.substrate_id <> a.substrate_id
          ORDER BY a.embedding <=> b.embedding LIMIT 3
        ) n
        WHERE (1-(a.embedding<=>n.embedding)) >= $2
        ORDER BY sim DESC
    """, books, sim)
    seen, out = set(), []
    for r in rows:
        key = tuple(sorted([r["a_id"], r["b_id"]]))
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(r))
    return out[:limit]


# ---- ② KU 判同(3值, 宁严勿松) ------------------------------------------------
JUDGE_SYS = (
    "你判断两条知识单元(KU)是否在讲【同一个知识点】(为跨书去重)。"
    "同一个点 = 定义同一个概念 / 解释同一个机制 / 陈述同一个事实(措辞、深度、语言可不同)。"
    "不是同一个点 = 一个定义X而另一个用X去解释Y / 不同概念 / 上下位 / 一般vs特例。"
    "★命门: 误判SAME会删掉真知识(不可逆), 冗余只是可逆代价 → 宁可判DIFFERENT, 拿不准一律判UNCERTAIN。"
    "只输出 JSON: {\"verdict\":\"SAME|DIFFERENT|UNCERTAIN\",\"why\":\"≤20字\"}。"
)


async def _judge(llm, sem, p):
    # 硬闸: 标题判别词矛盾 → 确定性 DIFFERENT
    if _forced_different(p["a_title"], p["b_title"]):
        return {**p, "verdict": "DIFFERENT", "why": "判别词硬闸", "gate": True}
    a = f"标题:{p['a_title']} | 类型:{p['a_kt']}\n{(p['a_tx'] or '')[:600]}"
    b = f"标题:{p['b_title']} | 类型:{p['b_kt']}\n{(p['b_tx'] or '')[:600]}"
    async with sem:
        try:
            r = await llm(messages=[{"role": "user", "content":
                f"KU-A:\n{a}\n\nKU-B:\n{b}\n\n它们是同一个知识点吗? 只输出JSON。"}],
                system=JUDGE_SYS, max_tokens=80)
            t = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text")
            m = re.search(r"\{.*\}", t, re.DOTALL)
            if not m:
                return {**p, "verdict": "UNCERTAIN", "why": "无JSON输出", "gate": False}
            j = json.loads(m.group(0))
            v = (j.get("verdict") or "UNCERTAIN").upper()
            if v not in ("SAME", "DIFFERENT", "UNCERTAIN"):
                v = "UNCERTAIN"
            return {**p, "verdict": v, "why": (j.get("why") or "")[:30], "gate": False}
        except Exception as e:
            return {**p, "verdict": "UNCERTAIN", "why": f"err:{type(e).__name__}", "gate": False}


# ---- ③ 片段整合(只对 SAME): 各自独有贡献 = 越读越厚 --------------------------
INTEG_SYS = (
    "两条KU已判定为同一个知识点。请抽取【各自独有的内容贡献】(越读越厚): "
    "A独有=A讲了而B没讲的实质内容; B独有=反之; 共有=两者都讲的核心。"
    "忠实, 不臆造; 没有独有内容就写空。只输出JSON: "
    "{\"shared\":\"\",\"a_only\":\"\",\"b_only\":\"\"}。"
)


async def _integrate(llm, sem, p):
    a = f"标题:{p['a_title']}\n{(p['a_tx'] or '')[:700]}"
    b = f"标题:{p['b_title']}\n{(p['b_tx'] or '')[:700]}"
    async with sem:
        try:
            r = await llm(messages=[{"role": "user", "content": f"KU-A:\n{a}\n\nKU-B:\n{b}"}],
                          system=INTEG_SYS, max_tokens=400)
            t = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text")
            m = re.search(r"\{.*\}", t, re.DOTALL)
            return json.loads(m.group(0)) if m else {}
        except Exception:
            return {}


def _short(s):
    return (s or "")[:34]


async def main():
    def arg(flag, default):
        return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default
    sim = float(arg("--sim", "0.78"))
    mx = int(arg("--max", "200"))
    books = arg("--books", ",".join(DEFAULT_BOOKS)).split(",")

    register_providers()
    llm = ProviderRegistry.get().llm("default")
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await register_vector(conn)

    cands = await _pairs(conn, books, sim, mx)
    print(f"== B仓步骤2 KU判同 dry_run ==", flush=True)
    print(f"书={books}  sim≥{sim}  候选对={len(cands)}  (只算+打印, 不落库)\n", flush=True)

    sem = asyncio.Semaphore(4)
    judged = await asyncio.gather(*(_judge(llm, sem, p) for p in cands))

    same = [j for j in judged if j["verdict"] == "SAME"]
    diff = [j for j in judged if j["verdict"] == "DIFFERENT"]
    unc = [j for j in judged if j["verdict"] == "UNCERTAIN"]
    gated = [j for j in judged if j.get("gate")]

    print(f"裁决: SAME={len(same)}  DIFFERENT={len(diff)}(其中硬闸{len(gated)})  UNCERTAIN={len(unc)}\n")

    print("── SAME (会合并/整合, 越读越厚) ──────────────────────────")
    for j in sorted(same, key=lambda x: -x["sim"]):
        print(f"  {j['sim']:.3f} [{j['a_sub'][:6]}]{_short(j['a_title'])}  ≡  [{j['b_sub'][:6]}]{_short(j['b_title'])}  ({j['why']})")

    print("\n── UNCERTAIN (命门: 保留两份不合) ───────────────────────")
    for j in sorted(unc, key=lambda x: -x["sim"]):
        print(f"  {j['sim']:.3f} [{j['a_sub'][:6]}]{_short(j['a_title'])}  ?  [{j['b_sub'][:6]}]{_short(j['b_title'])}  ({j['why']})")

    print("\n── DIFFERENT (含假朋友, 应被挡) ─ 抽样前20 ──────────────")
    for j in sorted(diff, key=lambda x: -x["sim"])[:20]:
        g = "硬闸" if j.get("gate") else "LLM"
        print(f"  {j['sim']:.3f} [{j['a_sub'][:6]}]{_short(j['a_title'])}  ≠  [{j['b_sub'][:6]}]{_short(j['b_title'])}  ({g}:{j['why']})")

    # ③ 片段整合: 只对前若干 SAME 演示(看"越读越厚"长什么样)
    demo = sorted(same, key=lambda x: -x["sim"])[:6]
    if demo:
        print("\n── ③片段整合示例(前6对 SAME, 各自独有贡献) ──────────────")
        integ = await asyncio.gather(*(_integrate(llm, sem, p) for p in demo))
        for p, g in zip(demo, integ):
            print(f"\n  ▸ {_short(p['a_title'])} ≡ {_short(p['b_title'])} (sim={p['sim']:.3f})")
            print(f"    共有 : {(g.get('shared') or '')[:140]}")
            print(f"    A独有: {(g.get('a_only') or '(无)')[:140]}")
            print(f"    B独有: {(g.get('b_only') or '(无)')[:140]}")

    print(f"\nDONE (dry-run, 无写库). 人工核查: 真同点是否全在 SAME? 假朋友是否全在 DIFFERENT? 模糊是否落 UNCERTAIN?", flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
