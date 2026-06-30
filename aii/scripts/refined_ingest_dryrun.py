"""B仓步骤3 · A仓去重KU → 灌入 rf.refined_ku  dry_run(默认不落库, --commit 才插).

AII-REFINED-REPO-MASTER-001 §5.1。经济三书首跑(已验证判同+人工签核)。
★语言策略(经理人2026-06-30拍板, 覆盖"英文统一"): **正文 natural_text 存原语言(不翻译, 免失真+免NIM瓶颈),
  仅 title 翻英文(为跨语言核对)**。BGE-M3 跨语言→原语言向量仍对齐。
流程: ②判同(复用 refined_dedup_dryrun, 缓存verdicts) → 读 rf.dedup_decision 跳 held_apart
      → union-find 成簇 → ③整合(★同语言簇: 原语言"越读越厚"; ★跨语言簇: 不融合, 留最长成员+sources记全)
      → title 翻英文 → BGE-M3 1024维(原语言natural_text) → refined_ku(sources jsonb 溯源A仓)。
命门: 宁冗余不误删(held_apart保留两份, 不并簇); 正文不译免失真; embedding对齐A仓BGE-M3。
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


# ---- ③ 同语言簇整合: 原语言 natural_text 拼"越读越厚"(忠实, 不臆造) + 英文标题 ----
INTEG_SYS = (
    "你把多条讲【同一个知识点】的KU整合成一条更厚的知识(越读越厚, for a refined repo)。"
    "★正文 natural_text 保持这些KU的原语言(不翻译成其他语言), 忠实合并各条实质内容"
    "(定义+各自独有的侧面/条件/例子), 不增不减不臆造, 不重复。"
    "★另给一个简短【英文】标题 title_en(仅标题用英文, 为跨语言核对)。"
    "只输出 JSON: {\"title_en\":\"\",\"natural_text\":\"\"}。"
)


async def _merge_cluster(llm, sem, members):
    body = "\n\n".join(f"[{i+1}] 标题:{m['title']}\n{(m['natural_text'] or '')[:900]}"
                       for i, m in enumerate(members))
    try:
        async with sem:
            r = await asyncio.wait_for(llm(
                messages=[{"role": "user", "content": f"待整合KU:\n{body}\n\n整合成一条更厚的英文知识。"}],
                system=INTEG_SYS, max_tokens=900), timeout=180)
        t = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text")
        m = re.search(r"\{.*\}", t, re.DOTALL)
        return json.loads(m.group(0)) if m else {}
    except Exception:
        return {}  # 失败回退: caller 用最长成员原文(不丢知识)


# ---- 标题翻英(仅 title, 为跨语言核对; 正文不译) ----
TRANS_SYS = ("把下面经济学知识点的【标题】忠实翻译成英文(简短, 术语用标准英文)。"
             "只输出英文标题, 不加说明/不加引号。")


async def _translate(llm, sem, text):
    for _ in range(2):  # 重试一次(NIM负载下首次易超时)
        try:
            async with sem:
                r = await asyncio.wait_for(llm(messages=[{"role": "user", "content": text[:1500]}],
                              system=TRANS_SYS, max_tokens=700), timeout=180)
            out = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text").strip()
            if out and not _has_zh(out):   # 译文须无中文; 残留中文=翻译失败→重试
                return out
        except Exception:
            pass
    return text  # 两次失败回退原文(不丢知识; 标记待补译)


def _fingerprint(text: str) -> str:
    return hashlib.sha1((text or "").strip().lower().encode()).hexdigest()[:12]


def _build_sources(members):
    return [{"book_id": m["substrate_id"], "raw_ku_id": m["ku_id"],
             "chapter": _chapter_of(m["ku_id"]), "contributed": "full"} for m in members]


# ---- NIM key 池: 4 key 各自限流, 轮转并发 ~4x 吞吐 ----
def _build_nim_pool():
    from aii.api._provider import _make_deepseek_caller
    keys = json.loads((ROOT / ".pipeline_keys.json").read_text())
    pool = [_make_deepseek_caller(
                k, model=os.getenv("NIM_MODEL", "meta/llama-3.3-70b-instruct"),
                base_url="https://integrate.api.nvidia.com/v1/chat/completions", rpm=36)
            for k in keys.values()]
    print(f"NIM key 池: {len(pool)} key 轮转并发", flush=True)
    return pool


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

    pool = _build_nim_pool()
    from oprim.embedding.bge_m3 import BgeM3Embedder
    embedder = BgeM3Embedder()
    sem = asyncio.Semaphore(len(pool))   # 并发=key数, round-robin 每item一key

    # 簇列表(members 已按 natural_text 长度降序: [0]=最长=base/回退基底)
    cluster_list = [sorted((kus[i] for i in ids), key=lambda m: -len(m.get("natural_text") or ""))
                    for ids in {**multi, **singles}.values()]

    async def _prep(idx, members):
        """并发组装一条 refined_ku(轮转第 idx%len 个key)。正文存原语言, 仅标题翻英。"""
        llm = pool[idx % len(pool)]
        base = members[0]  # 已按 natural_text 长度降序 → [0]=最长
        if len(members) > 1 and len({_has_zh(m["natural_text"]) for m in members}) == 1:
            # 同语言簇: 原语言整合"越读越厚" + 英文标题
            merged = await _merge_cluster(llm, sem, members)
            ntext = merged.get("natural_text") or base["natural_text"]   # 失败回退最长成员
            title = merged.get("title_en") or base["title"]
            is_frag = bool(merged.get("natural_text"))                   # 真融合才算片段化
        else:
            # 单条 或 跨语言簇: 不融合, 留最长成员原文(sources 已记全部成员可回查)
            ntext, title = base["natural_text"], base["title"]
            is_frag = False
        if _has_zh(title):                          # 标题保证英文(为核对); 正文不动
            title = await _translate(llm, sem, title)
        return {"base": base, "members": members, "title": title, "ntext": ntext, "is_frag": is_frag}

    # ---- 演示样本(dry-run): sample 个多成员簇 + 3 个混中文翻译, 并发 ----
    if not commit:
        demo = sorted((m for m in cluster_list if len(m) > 1), key=lambda m: -len(m))[:sample]
        zh_demo = [m for m in cluster_list if len(m) == 1 and _has_zh(m[0]["natural_text"])][:3]
        picks = demo + zh_demo
        prepped = await asyncio.gather(*(_prep(i, m) for i, m in enumerate(picks)))
        vecs = embedder.embed([p["ntext"] for p in prepped])
        print(f"\n── 多成员簇整合样本(前{len(demo)}) ──────────────", flush=True)
        for p, vec in list(zip(prepped, vecs))[:len(demo)]:
            ms = p["members"]
            print(f"\n  ▸ 簇({len(ms)}条) 来源: {[m['ku_id'].split('::')[0][:6]+'::'+m['ku_id'].split('::')[1] for m in ms]}")
            print(f"    类型: {ms[0]['knowledge_type']}  向量dim={len(vec)}  fingerprint={_fingerprint(p['ntext'])}")
            print(f"    整合title: {(p['title'] or '')[:70]}")
            print(f"    整合正文: {(p['ntext'] or '')[:240]}")
            print(f"    sources : {json.dumps(_build_sources(ms), ensure_ascii=False)[:200]}")
        zh_cnt = sum(1 for k in kus if _has_zh(kus[k]['natural_text']))
        if zh_demo:
            print(f"\n── 原语言保留案例(正文存原语言不译, 仅title翻英; 中文体共{zh_cnt}条) ──", flush=True)
            for p in prepped[len(demo):]:
                print(f"\n  ▸ {p['base']['ku_id']}")
                print(f"    原标题: {(p['base']['title'] or '')[:55]}  →  英文title: {(p['title'] or '')[:55]}")
                print(f"    正文(原语言,存原): {(p['ntext'] or '')[:110]}")
        print(f"\nDONE (dry-run, 无写库). 人工核: 整合是否忠实越读越厚? 翻译是否失真? sources是否全溯源?", flush=True)
        await aconn.close(); await bconn.close(); return

    # ---- COMMIT: 全量并发组装 → 批量嵌入 → 插入 ----
    print(f"\n[COMMIT] 并发组装 {len(cluster_list)} 条(轮转{len(pool)}key)...", flush=True)
    prepped = await asyncio.gather(*(_prep(i, m) for i, m in enumerate(cluster_list)))
    print(f"[COMMIT] 文本就绪, 批量 BGE-M3 嵌入 ...", flush=True)
    vecs = embedder.embed([p["ntext"] for p in prepped])
    inserted = 0
    for p, vec in zip(prepped, vecs):
        base, members = p["base"], p["members"]
        fp = _fingerprint(p["ntext"]); new_id = f"rf_econ_{fp}"
        await bconn.execute(
            """INSERT INTO rf.refined_ku
               (ku_id,title,natural_text,natural_text_zh,knowledge_type,sub_type,
                stance_holder,opposing_stance,grade,grounded_by,intuition,insight,example,
                embedding,sources,is_fragmented,merge_count,fingerprint)
               VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
               ON CONFLICT (ku_id) DO NOTHING""",
            new_id, p["title"], p["ntext"], base.get("natural_text_zh"),
            base["knowledge_type"], base["sub_type"], base["stance_holder"],
            base["opposing_stance"], "unverified", base["grounded_by"], base["intuition"],
            base["insight"], base["example"], vec,
            json.dumps(_build_sources(members), ensure_ascii=False), p["is_frag"], len(members), fp)
        inserted += 1
    print(f"[COMMIT] 完成: 插入 refined_ku {inserted} 条 (来自 {len(kus)} A仓KU)", flush=True)
    await aconn.close(); await bconn.close()


if __name__ == "__main__":
    asyncio.run(main())
