"""矛盾检测(P1⑥): 向量近邻配对 → LLM 判定冲突 → 记 ku_contradiction + 标 grade.

候选: 余弦相似 ≥ 阈值的 KU 对(同主题), 偏好跨书/跨章(同章近邻多为粒度重复, 非矛盾).
判定: LLM 给 SAME/CONTRADICT/COMPLEMENTARY/DIFFERENT; 仅 CONTRADICT 入表.
入库: 仅写 ku_contradiction(人工复核队列). ★不自动改 grade —
  本地小模型有误报(同章粒度拆分常被误判 CONTRADICT), grade 变更应由更强/投票判定或人工确认.

用法: python3 scripts/detect_contradictions.py [--sim 0.82] [--max 60] [--apply]
  --apply 才写复核队列(默认 dry-run 只打印). ECON_LLM_PROVIDER=ollama 用本地模型判.
"""
import asyncio, os, re, json, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from aii.api._provider import register_providers
from obase import ProviderRegistry

JUDGE_SYS = ("You compare two knowledge statements about a similar topic. Output valid JSON only. "
             "verdict ∈ {SAME, CONTRADICT, COMPLEMENTARY, DIFFERENT}. "
             "CONTRADICT = they make logically incompatible claims about the same thing. "
             "SAME = same claim (duplicate). COMPLEMENTARY = compatible, different aspects. "
             "DIFFERENT = unrelated/different scope. Be conservative: only CONTRADICT if a real conflict.")


async def _pairs(conn, sim: float, limit: int):
    """向量近邻配对(LATERAL 走 HNSW 索引), 去重 + 偏好跨 substrate/章."""
    rows = await conn.fetch("""
        SELECT a.ku_id a_id, a.substrate_id a_sub, a.natural_text a_tx,
               n.ku_id b_id, n.substrate_id b_sub, n.natural_text b_tx,
               1 - (a.embedding <=> n.embedding) sim
        FROM aii.ku_onto a
        CROSS JOIN LATERAL (
            SELECT ku_id, substrate_id, natural_text, embedding FROM aii.ku_onto b
            WHERE b.ku_id <> a.ku_id AND b.embedding IS NOT NULL
            ORDER BY b.embedding <=> a.embedding LIMIT 4
        ) n
        WHERE a.embedding IS NOT NULL AND 1 - (a.embedding <=> n.embedding) >= $1
        ORDER BY sim DESC
    """, sim)
    seen, out = set(), []
    for r in rows:
        key = tuple(sorted([r["a_id"], r["b_id"]]))
        if key in seen:
            continue
        seen.add(key)
        # 同章近邻(粒度重复)优先级低: 取章前缀比较
        a_ch = "::".join(r["a_id"].split("::")[:2])
        b_ch = "::".join(r["b_id"].split("::")[:2])
        out.append({**dict(r), "cross": a_ch != b_ch})
    out.sort(key=lambda x: (not x["cross"], -x["sim"]))  # 跨章/跨书优先
    return out[:limit]


async def main():
    sim = float(sys.argv[sys.argv.index("--sim") + 1]) if "--sim" in sys.argv else 0.82
    mx = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 60
    apply = "--apply" in sys.argv
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    model = os.getenv("OLLAMA_MODEL", "deepseek") if os.getenv("ECON_LLM_PROVIDER") == "ollama" else "deepseek"
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await conn.execute((ROOT / "migrations" / "0005_ku_contradiction.sql").read_text())
    cands = await _pairs(conn, sim, mx)
    print(f"{len(cands)} candidate pairs (sim≥{sim}, judging…)", flush=True)

    sem = asyncio.Semaphore(4)
    async def judge(p):
        async with sem:
            try:
                r = await llm(messages=[{"role": "user", "content":
                    f"A: {(p['a_tx'] or '')[:600]}\n\nB: {(p['b_tx'] or '')[:600]}\n\n"
                    f'JSON: {{"verdict":"..","rationale":".."}}'}],
                    system=JUDGE_SYS, max_tokens=200)
                t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
                m = re.search(r"\{.*\}", t, re.DOTALL)
                d = json.loads(m.group(0)) if m else {}
            except Exception as e:
                return None
            return {**p, "verdict": (d.get("verdict") or "").upper(), "rationale": d.get("rationale", "")}

    judged = [j for j in await asyncio.gather(*(judge(p) for p in cands)) if j]
    contras = [j for j in judged if j["verdict"] == "CONTRADICT"]
    print(f"verdicts: " + ", ".join(f"{v}={sum(1 for j in judged if j['verdict']==v)}"
                                    for v in ["SAME", "CONTRADICT", "COMPLEMENTARY", "DIFFERENT"]))
    for c in contras:
        print(f"  ⚠ CONTRADICT sim={c['sim']:.2f} {c['a_id'][-22:]} ↔ {c['b_id'][-22:]}: {c['rationale'][:90]}")
        if apply:
            a, b = sorted([c["a_id"], c["b_id"]])
            await conn.execute("""INSERT INTO aii.ku_contradiction(ku_a,ku_b,similarity,verdict,rationale,confidence,judged_by)
                VALUES($1,$2,$3,'contradict',$4,$5,$6) ON CONFLICT (ku_a,ku_b) DO NOTHING""",
                a, b, c["sim"], c["rationale"][:500], c["sim"], model)
    print(f"\nDONE: {len(contras)} contradictions → 复核队列" + (" (written)" if apply else " (dry-run, use --apply)"), flush=True)
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
