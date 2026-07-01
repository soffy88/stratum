"""B仓步骤4.5 第①层 · 有向关系 refined_directed_edge dry_run(只算+打印, --commit才写).

AII-REFINED-REPO-MASTER-001 §4.5/§8。在 524 canonical 概念上 readout 建骨架(concept→concept:
derives/subsumes/prerequisite)。**确定性语言信号法**(港自legacy directed_edges.py, NIM-free,
全三书): 句内 概念A [信号词] 概念B → 有向边; 否定前缀过滤; 证据计数=strength。
全局聚合(跨书canonical, 非per-book)。grade=unverified(后续M2/验证再升级)。
命门: 边是骨架, 默认unverified + strength加权 + 证据可回查; 宁少毋噪(NEG过滤+邻近55字+len≥6)。
用法(建边, NIM-free): cd aii; .venv/bin/python scripts/refined_directed_edge_dryrun.py [--commit] [--min-ev 2]
用法(item10 · LLM验证已落的边, 需NIM): cd aii; NVIDIA_NIM_API_KEY=<key> .venv/bin/python \
        scripts/refined_directed_edge_dryrun.py --verify [--commit] [--limit N]
  --verify  读 rf.refined_directed_edge 里 grade='unverified' 的边, NIM 逐边判向
            (CONFIRM/REJECT/UNCERTAIN); dry-run 存裁决 refined_edge_verify_verdicts.json;
            --commit 才升级 grade(CONFIRM→verified, REJECT→low, UNCERTAIN→不动)。
            命门: 拿不准→UNCERTAIN不升级; 方向反/共现噪声→REJECT。
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


VERIFY_SYS = (
    "你判断一条【有向知识关系】是否真实成立且方向正确(为知识图谱骨架验证, 命门宁缺毋附会)。"
    "关系类型: derives(源A 导致/推出 目标B) / subsumes(源A 包含/涵盖子类 目标B) / "
    "prerequisite(源A 是 目标B 的前提, 即先掌握A才能理解B)。"
    "给你 源概念、目标概念、关系类型、及证据句。判断该【有向】关系是否成立且方向无误。"
    "★命门: 拿不准/证据弱→UNCERTAIN(不升级); 明显共现噪声或方向相反→REJECT; 证据确凿且方向对→CONFIRM。"
    "只输出JSON: {\"verdict\":\"CONFIRM|REJECT|UNCERTAIN\",\"why\":\"≤20字\"}。"
)


async def _verify_edges(commit, limit):
    """item10: NIM 逐边验证已落的 unverified 有向边, 升级 grade。"""
    sys.path.insert(0, str(ROOT / "scripts"))
    from refined_ingest_dryrun import _build_nim_pool
    b = await asyncpg.connect(B_DSN)
    rows = await b.fetch("""
        SELECT e.edge_id, e.relation_type, e.strength, e.evidence,
               s.name src_name, d.name dst_name
        FROM rf.refined_directed_edge e
        JOIN rf.refined_concept s ON s.concept_id = e.src_concept
        JOIN rf.refined_concept d ON d.concept_id = e.dst_concept
        WHERE e.grade = 'unverified'
        ORDER BY e.strength DESC""" + (f" LIMIT {int(limit)}" if limit else ""))
    print(f"== item10 有向边 LLM 验证 =={'  [COMMIT]' if commit else '  (dry-run, 不改grade)'}")
    print(f"待验 unverified 边 = {len(rows)}\n", flush=True)
    if not rows:
        await b.close(); return

    pool = _build_nim_pool()
    sem = asyncio.Semaphore(len(pool))

    async def _vote(idx, r):
        ev = r["evidence"]
        ev = ev if isinstance(ev, dict) else json.loads(ev or "{}")
        samples = "; ".join(s.get("sent", "") for s in ev.get("samples", [])[:3])
        prompt = (f"源概念: {r['src_name']}\n目标概念: {r['dst_name']}\n关系类型: {r['relation_type']}\n"
                  f"证据句: {samples}\n\n该有向关系是否成立且方向正确? 只输出JSON。")
        async with sem:
            try:
                resp = await asyncio.wait_for(pool[idx % len(pool)](
                    messages=[{"role": "user", "content": prompt}],
                    system=VERIFY_SYS, max_tokens=80), timeout=120)
                t = "".join(x.get("text", "") for x in resp.get("content", []) if x.get("type") == "text")
                m = re.search(r"\{.*\}", t, re.DOTALL)
                j = json.loads(m.group(0)) if m else {}
                v = (j.get("verdict") or "UNCERTAIN").upper()
                return {"edge_id": r["edge_id"], "rel": r["relation_type"],
                        "src": r["src_name"], "dst": r["dst_name"],
                        "verdict": v if v in ("CONFIRM", "REJECT", "UNCERTAIN") else "UNCERTAIN",
                        "why": (j.get("why") or "")[:30]}
            except Exception as e:
                return {"edge_id": r["edge_id"], "rel": r["relation_type"], "src": r["src_name"],
                        "dst": r["dst_name"], "verdict": "UNCERTAIN", "why": f"err:{type(e).__name__}"}

    verdicts = await asyncio.gather(*(_vote(i, r) for i, r in enumerate(rows)))
    conf = [v for v in verdicts if v["verdict"] == "CONFIRM"]
    rej = [v for v in verdicts if v["verdict"] == "REJECT"]
    unc = [v for v in verdicts if v["verdict"] == "UNCERTAIN"]
    print(f"裁决: CONFIRM={len(conf)}(→verified)  REJECT={len(rej)}(→low)  UNCERTAIN={len(unc)}(不动)\n")
    for v in verdicts:
        mark = {"CONFIRM": "✓", "REJECT": "✗", "UNCERTAIN": "?"}[v["verdict"]]
        print(f"  {mark} {v['src'][:26]:26s} --{v['rel'][:5]}--> {v['dst'][:26]:26s} ({v['why']})")

    (ROOT / "econ_pipeline" / "ckpts" / "refined_edge_verify_verdicts.json").write_text(
        json.dumps(verdicts, ensure_ascii=False, indent=1))
    if not commit:
        print(f"\nDONE (dry-run). 裁决存 refined_edge_verify_verdicts.json。--commit 才升级 grade。")
        await b.close(); return

    for v in conf:
        await b.execute("UPDATE rf.refined_directed_edge SET grade='verified' WHERE edge_id=$1", v["edge_id"])
    for v in rej:
        await b.execute("UPDATE rf.refined_directed_edge SET grade='low' WHERE edge_id=$1", v["edge_id"])
    print(f"\n[COMMIT] 升级: {len(conf)} 边→verified, {len(rej)} 边→low; {len(unc)} 保持 unverified。")
    await b.close()


async def main():
    commit = "--commit" in sys.argv
    if "--verify" in sys.argv:      # item10: LLM 逐边验证模式
        limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
        await _verify_edges(commit, limit)
        return
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
