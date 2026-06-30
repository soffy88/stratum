"""B仓步骤3 · A仓去重KU → 灌入 rf.refined_ku  dry_run(默认不落库, --commit 才插).

AII-REFINED-REPO-MASTER-001 §5.1。经济三书首跑(已验证判同+人工签核)。
流程: ②判同(复用 refined_dedup_dryrun, 缓存verdicts) → 读 rf.dedup_decision 跳 held_apart
      → union-find 成簇 → ③整合(多成员簇: 英文natural_text拼"越读越厚") → 翻译(仅混中文的~24条, NIM)
      → BGE-M3 1024维(英文natural_text) → refined_ku(sources jsonb 溯源A仓)。
命门: 宁冗余不误删(held_apart保留两份, 不并簇); 翻译忠实不失真; embedding对齐A仓BGE-M3。
红线: dry_run 默认不落库; 先经济三书; 看裸真相(打印样本人工核)。

用法: cd aii; NVIDIA_NIM_API_KEY=<econ key> .venv/bin/python scripts/refined_ingest_dryrun.py
      [--commit] [--rejudge] [--sim 0.78] [--sample 6]
"""
import asyncio, os, re, json, hashlib, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from pgvector.asyncpg import register_vector
from aii.api._provider import register_providers
from obase import ProviderRegistry

sys.path.insert(0, str(ROOT / "scripts"))
from refined_dedup_dryrun import _pairs, _judge, DEFAULT_BOOKS  # 复用判同

A_DSN = os.getenv("DATABASE_URL")  # A仓 aii_kg
B_DSN = os.getenv("REFINED_DATABASE_URL",
                  "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
VERDICT_CACHE = ROOT / "econ_pipeline" / "ckpts" / "refined_verdicts_econ.json"

# ku_onto 知识承载列(原样搬运到 refined_ku)
KU_COLS = ["ku_id", "substrate_id", "title", "natural_text", "natural_text_zh",
           "knowledge_type", "sub_type", "stance_holder", "opposing_stance",
           "grade", "grounded_by", "intuition", "insight", "example"]


# ---- union-find ----
class UF:
    def __init__(self): self.p = {}
    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]; x = self.p[x]
        return x
    def union(self, a, b): self.p[self.find(a)] = self.find(b)


def _chapter_of(ku_id: str) -> str:
    tail = ku_id.split("::", 1)[-1]
    m = re.search(r"(ch\d+|c\d+)", tail)
    return m.group(1) if m else ""


def _has_zh(s: str) -> bool:
    return bool(s) and bool(re.search(r"[一-鿿]", s))


# ---- 判同(复用), 带缓存 + ku_id ----
async def _verdicts(aconn, books, sim, mx, rejudge):
    if VERDICT_CACHE.exists() and not rejudge:
        return json.loads(VERDICT_CACHE.read_text())
    register_providers()
    llm = ProviderRegistry.get().llm("default")
    cands = await _pairs(aconn, books, sim, mx)
    sem = asyncio.Semaphore(4)
    judged = await asyncio.gather(*(_judge(llm, sem, p) for p in cands))
    out = [{"a_id": j["a_id"], "b_id": j["b_id"], "a_title": j["a_title"],
            "b_title": j["b_title"], "sim": float(j["sim"]), "verdict": j["verdict"],
            "why": j.get("why", ""), "gate": j.get("gate", False)} for j in judged]
    VERDICT_CACHE.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    return out


# ---- ③ 多成员簇整合: 英文 natural_text 拼"越读越厚"(忠实, 不臆造) ----
INTEG_SYS = (
    "你把多条讲【同一个知识点】的KU整合成一条更厚的英文知识(越读越厚, for a refined repo)。"
    "要求: 忠实合并各条的实质内容(定义+各自独有的侧面/条件/例子), 不增不减不臆造, 不重复。"
    "输出统一英文。只输出 JSON: {\"title\":\"\",\"natural_text\":\"\"}。"
)


async def _merge_cluster(llm, sem, members):
    body = "\n\n".join(f"[{i+1}] 标题:{m['title']}\n{(m['natural_text'] or '')[:900]}"
                       for i, m in enumerate(members))
    try:
        async with sem:
            r = await asyncio.wait_for(llm(
                messages=[{"role": "user", "content": f"待整合KU:\n{body}\n\n整合成一条更厚的英文知识。"}],
                system=INTEG_SYS, max_tokens=900), timeout=90)
        t = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text")
        m = re.search(r"\{.*\}", t, re.DOTALL)
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}  # 失败回退: caller 用最长成员原文(不丢知识)


# ---- 翻译(仅混中文的 natural_text, 忠实) ----
TRANS_SYS = ("把下面经济学知识文本忠实翻译成英文(换语言, 不重述/不增减/不曲解; 经济学术语用标准英文)。"
             "只输出译文, 不加说明。")


async def _translate(llm, sem, text):
    try:
        async with sem:
            r = await asyncio.wait_for(llm(messages=[{"role": "user", "content": text[:1500]}],
                          system=TRANS_SYS, max_tokens=700), timeout=90)
        out = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text").strip()
        return out or text  # 空回退原文
    except Exception:
        return text  # 失败回退原文(不丢知识; --commit 可后续补译)


def _fingerprint(text: str) -> str:
    return hashlib.sha1((text or "").strip().lower().encode()).hexdigest()[:12]


def _build_sources(members):
    return [{"book_id": m["substrate_id"], "raw_ku_id": m["ku_id"],
             "chapter": _chapter_of(m["ku_id"]), "contributed": "full"} for m in members]


async def main():
    def arg(flag, d):
        return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else d
    commit = "--commit" in sys.argv
    rejudge = "--rejudge" in sys.argv
    sim = float(arg("--sim", "0.78"))
    sample = int(arg("--sample", "6"))
    books = DEFAULT_BOOKS

    aconn = await asyncpg.connect(A_DSN); await register_vector(aconn)
    bconn = await asyncpg.connect(B_DSN); await register_vector(bconn)

    # 1) 取三书全部 KU
    rows = await aconn.fetch(
        f"SELECT {','.join(KU_COLS)} FROM aii.ku_onto WHERE substrate_id = ANY($1)", books)
    kus = {r["ku_id"]: dict(r) for r in rows}
    print(f"== B仓步骤3 灌入 dry_run =={'  [COMMIT]' if commit else '  (dry-run, 不落库)'}", flush=True)
    print(f"书={books}  A仓KU={len(kus)}", flush=True)

    # 2) 判同 verdicts + 读 held_apart
    verdicts = await _verdicts(aconn, books, sim, 200, rejudge)
    same = [v for v in verdicts if v["verdict"] == "SAME"]
    held = await bconn.fetch("SELECT raw_ku_a, raw_ku_b FROM rf.dedup_decision WHERE verdict='held_apart'")
    held_set = {frozenset((r["raw_ku_a"], r["raw_ku_b"])) for r in held}

    # 3) union-find: SAME 边(跳 held_apart), 节点=全部KU
    uf = UF()
    for k in kus: uf.find(k)
    merged_edges = 0
    for v in same:
        if frozenset((v["a_id"], v["b_id"])) in held_set:
            continue
        if v["a_id"] in kus and v["b_id"] in kus:
            uf.union(v["a_id"], v["b_id"]); merged_edges += 1
    clusters = {}
    for k in kus:
        clusters.setdefault(uf.find(k), []).append(k)
    multi = {root: ids for root, ids in clusters.items() if len(ids) > 1}
    singles = {root: ids for root, ids in clusters.items() if len(ids) == 1}

    print(f"\nSAME边={len(same)}(并入{merged_edges}, 跳held_apart{len(same)-merged_edges-len([v for v in same if v['a_id'] not in kus or v['b_id'] not in kus])})  "
          f"held_apart记录={len(held_set)}", flush=True)
    print(f"→ refined_ku 预计 {len(clusters)} 条 (合并簇{len(multi)} + 单条{len(singles)})  "
          f"压缩 {len(kus)}→{len(clusters)} (省{len(kus)-len(clusters)})", flush=True)

    register_providers()
    llm = ProviderRegistry.get().llm("default")
    from oprim.embedding.bge_m3 import BgeM3Embedder
    embedder = BgeM3Embedder()
    sem = asyncio.Semaphore(4)

    # ---- 演示样本(dry-run): 多成员簇前 sample 个 + 翻译案例 ----
    if not commit:
        demo_roots = sorted(multi, key=lambda r: -len(multi[r]))[:sample]
        print(f"\n── 多成员簇整合样本(前{len(demo_roots)}) ──────────────", flush=True)
        for root in demo_roots:
            members = sorted((kus[i] for i in multi[root]),
                             key=lambda m: -len(m.get("natural_text") or ""))
            srcs = _build_sources(members)
            merged = await _merge_cluster(llm, sem, members)
            vec = embedder.embed([merged.get("natural_text", "")])[0]
            print(f"\n  ▸ 簇({len(members)}条) 来源: {[m['ku_id'].split('::')[0][:6]+'::'+m['ku_id'].split('::')[1] for m in members]}")
            print(f"    类型: {members[0]['knowledge_type']}  向量dim={len(vec)}  fingerprint={_fingerprint(merged.get('natural_text',''))}")
            print(f"    整合title: {merged.get('title','')[:70]}")
            print(f"    整合正文: {(merged.get('natural_text','') or '')[:240]}")
            print(f"    sources : {json.dumps(srcs, ensure_ascii=False)[:200]}")
        # 翻译案例: 混中文的 natural_text
        zh_kus = [k for k in singles for k in [singles[k][0]] if _has_zh(kus[k]["natural_text"])][:3]
        if zh_kus:
            print(f"\n── 翻译案例(natural_text混中文→NIM英译, 共{sum(1 for k in kus if _has_zh(kus[k]['natural_text']))}条) ──", flush=True)
            for k in zh_kus:
                en = await _translate(llm, sem, kus[k]["natural_text"])
                print(f"\n  ▸ {k}")
                print(f"    原: {kus[k]['natural_text'][:120]}")
                print(f"    译: {en[:120]}")
        print(f"\nDONE (dry-run, 无写库). 人工核: 整合是否忠实越读越厚? 翻译是否失真? sources是否全溯源?", flush=True)
        await aconn.close(); await bconn.close(); return

    # ---- COMMIT: 全量处理并插入 ----
    print("\n[COMMIT] 开始全量处理并插入 rf.refined_ku ...", flush=True)
    inserted = 0
    # 多成员簇
    for root, ids in {**multi, **singles}.items():
        members = sorted((kus[i] for i in ids),
                         key=lambda m: -len(m.get("natural_text") or ""))
        if len(members) > 1:
            merged = await _merge_cluster(llm, sem, members)
            title = merged.get("title") or members[0]["title"]
            ntext = merged.get("natural_text") or members[0]["natural_text"]
            is_frag = True
        else:
            m0 = members[0]
            title, ntext = m0["title"], m0["natural_text"]
            if _has_zh(ntext):
                ntext = await _translate(llm, sem, ntext)
            is_frag = False
        base = members[0]
        vec = embedder.embed([ntext])[0]
        fp = _fingerprint(ntext)
        new_id = f"rf_econ_{fp}"
        srcs = _build_sources(members)
        ntext_zh = base.get("natural_text_zh")
        await bconn.execute(
            """INSERT INTO rf.refined_ku
               (ku_id,title,natural_text,natural_text_zh,knowledge_type,sub_type,
                stance_holder,opposing_stance,grade,grounded_by,intuition,insight,example,
                embedding,sources,is_fragmented,merge_count,fingerprint)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
               ON CONFLICT (ku_id) DO NOTHING""",
            new_id, title, ntext, ntext_zh, base["knowledge_type"], base["sub_type"],
            base["stance_holder"], base["opposing_stance"], "unverified",
            base["grounded_by"], base["intuition"], base["insight"], base["example"],
            vec, json.dumps(srcs, ensure_ascii=False), is_frag, len(members), fp)
        inserted += 1
        if inserted % 100 == 0:
            print(f"  ... 已插 {inserted}/{len(clusters)}", flush=True)
    print(f"[COMMIT] 完成: 插入 refined_ku {inserted} 条 (来自 {len(kus)} A仓KU)", flush=True)
    await aconn.close(); await bconn.close()


if __name__ == "__main__":
    asyncio.run(main())
