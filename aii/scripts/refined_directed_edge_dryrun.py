"""B仓步骤4.5 第①层 · 有向关系 refined_directed_edge dry_run(只算+打印, --commit才写).

AII-REFINED-REPO-MASTER-001 §4.5/§8。在 524 canonical 概念上 readout 建骨架(concept→concept:
derives/subsumes/prerequisite)。**确定性语言信号法**(港自legacy directed_edges.py, NIM-free,
全三书): 句内 概念A [信号词] 概念B → 有向边; 否定前缀过滤; 证据计数=strength。
全局聚合(跨书canonical, 非per-book)。grade=unverified(后续M2/验证再升级)。
命门: 边是骨架, 默认unverified + strength加权 + 证据可回查; 宁少毋噪(NEG过滤+邻近55字+len≥6)。
用法: cd aii; .venv/bin/python scripts/refined_directed_edge_dryrun.py [--commit]   (无需NIM)
"""
import asyncio, os, re, json, sys
from collections import Counter, defaultdict
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg

B_DSN = os.getenv("REFINED_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")

PREREQ = re.compile(r'\b(?:based on|builds? on|build upon|relies on|rely on|depends on|requires?|presupposes?|derived from|rests on|grounded in|founded on|premised on)\b', re.I)
SUBSUM = re.compile(r'\b(?:includes?|consists? of|comprises?|composed of|made up of|divided into|categor\w+ into|types of|forms of|encompasses?|subsumes?)\b', re.I)
DERIV = re.compile(r'\b(?:leads? to|results? in|gives? rise to|produces?|causes?|derives?|yields?|implies?|therefore|thus result)\b', re.I)
SIGS = [('prerequisite', PREREQ), ('subsumes', SUBSUM), ('derives', DERIV)]
NEG = re.compile(r'(?:not|n.t|never|exclud\w*|without|rather than|unlike|as opposed to|instead of|ignore\w*|omit\w*)\W*$', re.I)
PROX = 55


def norm(t):
    t = re.sub(r'\([^)]*\)', '', t or '').lower().strip()
    t = re.sub(r'[^a-z0-9\s/&-]', '', t)
    return re.sub(r's\b', '', re.sub(r'\s+', ' ', t).strip())


async def main():
    commit = "--commit" in sys.argv
    b = await asyncpg.connect(B_DSN)

    # 1) canonical 概念 → 短语词表(name + aliases, 归一, len≥6, 映射到concept_id)
    crows = await b.fetch("SELECT concept_id, name, aliases FROM rf.refined_concept")
    phrase2cid = {}
    collision = set()
    for r in crows:
        names = [r["name"]] + (r["aliases"] if isinstance(r["aliases"], list)
                               else json.loads(r["aliases"] or "[]"))
        for nm in names:
            n = norm(nm)
            if len(n) < 6:
                continue
            if n in phrase2cid and phrase2cid[n] != r["concept_id"]:
                collision.add(n)
            else:
                phrase2cid[n] = r["concept_id"]
    for n in collision:        # 多概念共用短语 → 歧义, 不用
        phrase2cid.pop(n, None)
    phrases = [(n, re.compile(r'(?<![a-z])' + re.escape(n) + r'(?:e?s)?(?![a-z])', re.I))
               for n in phrase2cid]

    # 2) 扫 refined_ku natural_text(英文体), 句内 概念-信号-概念
    kurows = await b.fetch("SELECT ku_id, natural_text FROM rf.refined_ku")
    edges = Counter()
    ev = defaultdict(list)
    for k in kurows:
        for sent in re.split(r'(?<=[.!?])\s+', k["natural_text"] or ''):
            for rtype, sig in SIGS:
                for m in sig.finditer(sent):
                    if NEG.search(sent[max(0, m.start() - 30):m.start()]):
                        continue
                    before = [(mm.end(), n) for n, rx in phrases for mm in rx.finditer(sent) if 0 <= m.start() - mm.end() <= PROX]
                    after = [(mm.start(), n) for n, rx in phrases for mm in rx.finditer(sent) if 0 <= mm.start() - m.end() <= PROX]
                    if not before or not after:
                        continue
                    A, B = max(before)[1], min(after)[1]
                    if A == B:
                        continue
                    src, dst = (B, A) if rtype == 'prerequisite' else (A, B)
                    sc, dc = phrase2cid[src], phrase2cid[dst]
                    if sc != dc:
                        edges[(sc, dc, rtype)] += 1
                        if len(ev[(sc, dc, rtype)]) < 3:
                            ev[(sc, dc, rtype)].append({"ku_id": k["ku_id"], "sent": sent.strip()[:160]})

    name = {r["concept_id"]: r["name"] for r in crows}
    print(f"== B仓步骤4.5 有向关系 refined_directed_edge dry_run =={'  [COMMIT]' if commit else '  (不写库)'}")
    print(f"canonical概念={len(crows)}  词表短语={len(phrase2cid)}(歧义剔{len(collision)})  refined_ku={len(kurows)}")
    td = Counter(rt for (_, _, rt) in edges)
    print(f"→ 有向边 {len(edges)} 条: derives={td['derives']} subsumes={td['subsumes']} prerequisite={td['prerequisite']}\n")

    print("── 证据最强的边(前20) ──────────────")
    for (s, d, rt), n in sorted(edges.items(), key=lambda kv: -kv[1])[:20]:
        print(f"  [{n:2d}] {name.get(s, s)[:28]:28s} --{rt[:5]}--> {name.get(d, d)[:28]}")
    if edges:
        ex = sorted(edges.items(), key=lambda kv: -kv[1])[0]
        print(f"\n  证据样本({name.get(ex[0][0])} --{ex[0][2]}--> {name.get(ex[0][1])}): {ev[ex[0]][0]['sent']}")

    min_ev = int(sys.argv[sys.argv.index("--min-ev") + 1]) if "--min-ev" in sys.argv else 2
    keep = {k: v for k, v in edges.items() if v >= min_ev}
    print(f"\n证据计数: count=1 {sum(1 for v in edges.values() if v==1)} | count≥{min_ev} {len(keep)}(命门宁缺毋附会→只落≥{min_ev})")

    if not commit:
        print(f"\nDONE (dry-run, 无写库). 人工核: 边是否真有向关系(非共现噪声)? 方向是否对?")
        await b.close(); return

    mx = max(keep.values()) if keep else 1
    for (s, d, rt), n in keep.items():
        await b.execute("""INSERT INTO rf.refined_directed_edge
            (src_concept, dst_concept, relation_type, strength, grade, evidence)
            VALUES($1,$2,$3,$4,'unverified',$5)""",
            s, d, rt, round(n / mx, 3), json.dumps({"evidence_count": n, "samples": ev[(s, d, rt)]}, ensure_ascii=False))
    print(f"\n[COMMIT] 完成: 插入 refined_directed_edge {len(keep)} 条 (count≥{min_ev}, grade=unverified; 滤掉count=1 {len(edges)-len(keep)}条)")
    await b.close()


if __name__ == "__main__":
    asyncio.run(main())
