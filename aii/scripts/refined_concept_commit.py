"""B仓步骤4 M0 · 应用人工签核 → 落 refined_concept + refined_ku_concept + concept_decision.

AII-REFINED-REPO-MASTER-001 §6。**应用已签核决定**(非重判, LLM非确定性故pin在此),
默认打印计划, --commit 才写库。命门: 错合=地基污染, 只合签核过的对。
源: A仓 concept_onto(name/name_zh/discipline/level/vector 1024) 限三书概念。
归一: union-find 签核MERGES → canonical(最长名为主名, 余入aliases, vector取代表)。
链接: B仓 refined_ku.sources→raw_ku_id → A仓 ku_concept_onto → A_cid → canonical → refined_ku_concept。
用法: cd aii; .venv/bin/python scripts/refined_concept_commit.py [--commit]   (无需NIM)
"""
import asyncio, os, json, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from pgvector.asyncpg import register_vector

A_DSN = os.getenv("DATABASE_URL")
B_DSN = os.getenv("REFINED_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
BOOKS = ["mankiw_principles_econ_10e", "microecon_en_full_v2", "micro_clean"]

# ★经理人签核(econ M0 dry-run econ_v2/v3, 2026-06-30): 按A仓 concept_id pin(LLM判同非确定性)
MERGES = [(664, 2983), (10123, 10165), (658, 2822), (10017, 10026), (852, 2463),
          (735, 2717), (722, 748), (740, 2823), (9860, 10109)]  # 9 真同一
HELD = [(268, 402), (715, 12), (504, 831)]  # 3 边缘上下位剔(exchange/equilibrium/economics)


class UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b): self.p[self.find(a)] = self.find(b)


async def main():
    commit = "--commit" in sys.argv
    a = await asyncpg.connect(A_DSN); await register_vector(a)
    b = await asyncpg.connect(B_DSN); await register_vector(b)

    # 1) A仓三书概念
    crows = await a.fetch("""
        SELECT DISTINCT co.concept_id, co.name, co.name_zh, co.discipline, co.level, co.vector
        FROM aii.concept_onto co
        JOIN aii.ku_concept_onto kc USING(concept_id)
        JOIN aii.ku_onto k USING(ku_id)
        WHERE k.substrate_id = ANY($1)""", BOOKS)
    C = {r["concept_id"]: dict(r) for r in crows}
    # 2) raw_ku_id → [A_cid]
    lrows = await a.fetch("""
        SELECT kc.ku_id, kc.concept_id FROM aii.ku_concept_onto kc
        JOIN aii.ku_onto k USING(ku_id) WHERE k.substrate_id = ANY($1)""", BOOKS)
    ku2cids = {}
    for r in lrows:
        ku2cids.setdefault(r["ku_id"], []).append(r["concept_id"])

    # 3) union-find 合并(只合签核MERGES, 且两端都在概念集)
    uf = UF()
    for cid in C: uf.find(cid)
    applied = 0
    for x, y in MERGES:
        if x in C and y in C:
            uf.union(x, y); applied += 1
    groups = {}
    for cid in C:
        groups.setdefault(uf.find(cid), []).append(cid)

    print(f"== M0 落 refined_concept =={'  [COMMIT]' if commit else '  (计划, 不写库)'}")
    print(f"A仓三书概念={len(C)}  签核合并对={applied}/{len(MERGES)}  held_apart={len(HELD)}")
    print(f"→ canonical 概念预计 {len(groups)} 条 (合并组{sum(1 for g in groups.values() if len(g)>1)} + 单条{sum(1 for g in groups.values() if len(g)==1)})")

    # held_apart 完整性检查: 每对两端不可在同组(否则错合)
    for x, y in HELD:
        if x in C and y in C and uf.find(x) == uf.find(y):
            print(f"  ✗✗ 错合! held_apart ({x},{y}) 落在同组 → 中止"); await a.close(); await b.close(); return
    print(f"  ✓ held_apart 校验通过: 3对均未被合并")

    if not commit:
        print("\n── 合并组样本 ──")
        for root, ids in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:12]:
            if len(ids) > 1:
                names = [C[i]["name"] for i in ids]
                print(f"  canonical={max(names, key=len)[:34]}  ⇐ {names}")
        print("\n计划OK(未写库). --commit 落 refined_concept+refined_ku_concept+concept_decision。")
        await a.close(); await b.close(); return

    # 4) 落 refined_concept, 建 A_cid→rf_cid 映射
    a2rf = {}
    ins_c = 0
    for root, ids in groups.items():
        members = [C[i] for i in ids]
        rep = max(members, key=lambda m: len(m["name"] or ""))  # 最长名为canonical
        aliases = sorted({m["name"] for m in members if m["name"] != rep["name"]} |
                         {m["name_zh"] for m in members if m["name_zh"]})
        rf_cid = await b.fetchval("""
            INSERT INTO rf.refined_concept (name, name_zh, aliases, level, discipline, embedding, sources)
            VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING concept_id""",
            rep["name"], rep["name_zh"], json.dumps(aliases, ensure_ascii=False),
            rep["level"], rep["discipline"], rep["vector"],
            json.dumps([{"raw_concept_id": i} for i in ids], ensure_ascii=False))
        for i in ids: a2rf[i] = rf_cid
        ins_c += 1

    # 5) 链接 refined_ku_concept(B仓ku → sources raw_ku → A_cid → canonical)
    kurows = await b.fetch("SELECT ku_id, sources FROM rf.refined_ku")
    links = set()
    for r in kurows:
        srcs = r["sources"] if isinstance(r["sources"], list) else json.loads(r["sources"] or "[]")
        for s in srcs:
            for acid in ku2cids.get(s.get("raw_ku_id"), []):
                if acid in a2rf:
                    links.add((r["ku_id"], a2rf[acid]))
    for ku_id, rf_cid in links:
        await b.execute("INSERT INTO rf.refined_ku_concept (ku_id, concept_id) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                        ku_id, rf_cid)

    # 6) 记录签核决定到 ledger
    async def _nm(cid): return C[cid]["name"] if cid in C else str(cid)
    for x, y in MERGES:
        await b.execute("""INSERT INTO rf.concept_decision
            (raw_concept_a,raw_concept_b,a_name,b_name,verdict,band,reason,signed_off_by,run_tag)
            VALUES($1,$2,$3,$4,'merged','green','M0签核真同一',E'经理人','econ_v2')
            ON CONFLICT (raw_concept_a,raw_concept_b) DO NOTHING""", x, y, await _nm(x), await _nm(y))
    for x, y in HELD:
        await b.execute("""INSERT INTO rf.concept_decision
            (raw_concept_a,raw_concept_b,a_name,b_name,verdict,band,reason,signed_off_by,run_tag)
            VALUES($1,$2,$3,$4,'held_apart','yellow','边缘上下位剔(宁碎片不错合)',E'经理人','econ_v2')
            ON CONFLICT (raw_concept_a,raw_concept_b) DO NOTHING""", x, y, await _nm(x), await _nm(y))

    print(f"\n[COMMIT] 完成: refined_concept {ins_c}条 | refined_ku_concept {len(links)}链接 | concept_decision {len(MERGES)+len(HELD)}条")
    await a.close(); await b.close()


if __name__ == "__main__":
    asyncio.run(main())
