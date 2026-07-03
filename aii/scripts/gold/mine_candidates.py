"""金集候选挖掘器 — 从 A仓(aii_kg)挖"易混淆对",供人工标注扩充金集到几百对。

三路挖掘(专挑判同最可能出错的对):
  ① 向量近邻: concept/KU 向量高相似对(混淆热区; 高相似≠同一正是陷阱)
  ② 共享 head 异修饰: 同尾词不同修饰(类冲突: X elasticity / Y elasticity)
  ③ 子串包含: 一名是另一名子串(上下位: opportunity cost ⊂ increasing opportunity cost)
  ④ 归一同名: 去大小写/空格/标点后同名、不同 id(跨书同名, 该合的正例)

输出 candidates.jsonl(label 空, 待人工填 same/different/uncertain)。已在 gold_seed 的对跳过。
不静默截断: 每路超上限时 log 丢弃数(设计红线)。

用法: python mine_candidates.py [--sim 0.86] [--per-cat 120] [--disc econ,math]
env: AII_KG_URL (默认 postgresql://aii:aii_safe_pass@localhost:5435/aii_kg)
"""

import asyncio, json, os, re, sys
from pathlib import Path

import asyncpg
import numpy as np
from pgvector.asyncpg import register_vector

HERE = Path(__file__).parent
KG_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
SIM = float(
    os.getenv("GOLD_SIM", sys.argv[sys.argv.index("--sim") + 1] if "--sim" in sys.argv else 0.86)
)
PER_CAT = int(sys.argv[sys.argv.index("--per-cat") + 1] if "--per-cat" in sys.argv else 120)
ECON_DISC = ("economics", "经济学", "microecon_v2", "mankiw_principles_econ_10e")


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[\s_\-（）()【】\[\]·,，.。、:：;；'\"]+", "", s)
    return s


def _head(s: str) -> str:
    """英文名末词(head noun)做类冲突分组键: 'Price Elasticity of Demand' → 'demand'。"""
    toks = re.findall(r"[a-z]+", (s or "").lower())
    return toks[-1] if toks else ""


def _seed_pairs() -> set:
    seen = set()
    sp = HERE / "gold_seed.jsonl"
    if sp.exists():
        for ln in sp.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                seen.add(frozenset((str(r["a_id"]), str(r["b_id"]))))
    return seen


async def main():
    seed = _seed_pairs()
    out = {}  # frozenset(a,b) -> row (dedup across paths)
    dropped = {}

    def add(kind, a_id, a_name, b_id, b_name, category, band, sim=None):
        key = frozenset((str(a_id), str(b_id)))
        if str(a_id) == str(b_id) or key in seed or key in out:
            return False
        out[key] = {
            "pair_id": f"{'c' if kind == 'concept' else 'k'}m{len(out) + 1:04d}",
            "kind": kind,
            "a_id": a_id,
            "a_name": a_name,
            "b_id": b_id,
            "b_name": b_name,
            "label": "",
            "band": band,
            "category": category,
            "sim": round(float(sim), 3) if sim is not None else None,
            "rationale": "",
            "source": "mined",
        }
        return True

    conn = await asyncpg.connect(KG_URL)
    await register_vector(conn)

    # ---- 概念(限经济学域, 与命名对抗案例对齐; 数学概念另可扩) ----
    crows = await conn.fetch(
        "SELECT concept_id, name, discipline, vector FROM aii.concept_onto "
        "WHERE vector IS NOT NULL AND name IS NOT NULL AND discipline = ANY($1::text[])",
        list(ECON_DISC),
    )
    ids = [r["concept_id"] for r in crows]
    names = [r["name"] for r in crows]
    V = np.array([np.asarray(r["vector"], dtype=np.float32) for r in crows])
    if len(V):
        V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-9
        # ① 向量近邻(上三角, sim≥SIM)
        S = V @ V.T
        nn = 0
        cand_nn = []
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                if S[i, j] >= SIM:
                    cand_nn.append((S[i, j], i, j))
        cand_nn.sort(reverse=True)
        for sim, i, j in cand_nn:
            if nn >= PER_CAT:
                break
            if add("concept", ids[i], names[i], ids[j], names[j], "向量近邻", "yellow", sim):
                nn += 1
        dropped["向量近邻"] = max(0, len(cand_nn) - nn)

    # ② 共享 head 异修饰(类冲突) ③ 子串(上下位) ④ 归一同名(跨书同名) — 全概念名上做
    allc = await conn.fetch("SELECT concept_id, name FROM aii.concept_onto WHERE name IS NOT NULL")
    by_head, by_norm = {}, {}
    for r in allc:
        by_head.setdefault(_head(r["name"]), []).append((r["concept_id"], r["name"]))
        by_norm.setdefault(_norm(r["name"]), []).append((r["concept_id"], r["name"]))
    n_cls = n_sub = n_same = 0
    # 类冲突: 同 head, 归一名不同
    for head, grp in by_head.items():
        if len(head) < 4 or len(grp) < 2:
            continue
        for i in range(len(grp)):
            for j in range(i + 1, len(grp)):
                if n_cls >= PER_CAT:
                    break
                (ai, an), (bi, bn) = grp[i], grp[j]
                if _norm(an) != _norm(bn) and add("concept", ai, an, bi, bn, "类冲突", "red"):
                    n_cls += 1
    # 归一同名(跨书同名, 该合正例)
    for nm, grp in by_norm.items():
        if len(grp) < 2:
            continue
        for i in range(1, len(grp)):
            if n_same >= PER_CAT:
                break
            if add("concept", grp[0][0], grp[0][1], grp[i][0], grp[i][1], "跨书同名", "green"):
                n_same += 1
    # 子串(上下位): 短名 是 长名 的词子集
    short = sorted(
        (
            (cid, nm)
            for cid, nm in [(r["concept_id"], r["name"]) for r in allc]
            if 4 <= len(_norm(nm)) <= 40
        ),
        key=lambda x: len(x[1]),
    )
    norm_map = [(cid, _norm(nm), nm) for cid, nm in short]
    for a in range(len(norm_map)):
        if n_sub >= PER_CAT:
            break
        ca, na, raw_a = norm_map[a]
        if len(na) < 5:
            continue
        for b in range(len(norm_map)):
            if a == b or n_sub >= PER_CAT:
                continue
            cb, nb, raw_b = norm_map[b]
            if len(nb) > len(na) + 3 and na in nb:  # a 子串 b, 且明显更短
                if add("concept", ca, raw_a, cb, raw_b, "上下位", "red"):
                    n_sub += 1
                    break

    await conn.close()
    rows = list(out.values())
    p = HERE / "candidates.jsonl"
    p.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    print(f"挖出候选 {len(rows)} 对 → {p}")
    from collections import Counter

    print("  按类别:", dict(Counter(r["category"] for r in rows)))
    if any(dropped.values()):
        print("  ⚠ 超上限丢弃(非静默):", {k: v for k, v in dropped.items() if v})
    print(
        "  下一步: 人工在 candidates.jsonl 填 label(same/different/uncertain), 再 python score.py"
    )


if __name__ == "__main__":
    asyncio.run(main())
