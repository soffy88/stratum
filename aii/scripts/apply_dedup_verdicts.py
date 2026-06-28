"""应用 Claude 判官的去重/同义裁决(强判官, 非4B本地模型).

输入: scratchpad/verdicts_*.json(裁决) + pairs.json(配对元数据).
动作:
  SAME 同书 → 并查集聚类, 每簇留 natural_text 最长者为 keeper, 其余 supersede→keeper
            (软取代, valid_until+superseded_by, 可逆留痕; 非硬删) + 边重指向 keeper.
  SAME 跨书 → 建 same_as 边(跨书同一知识互联, 不删).
  CONTRADICT → ku_contradiction 复核队列.
落库前全量备份受影响 KU 行到 backup_dedup.json.

用法: python3 scripts/apply_dedup_verdicts.py [--apply]   # 默认 dry-run
"""
import os, json, glob, asyncio, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
S = "/tmp/claude-1000/-home-soffy-projects-AII/26ea80e4-5a7a-4098-bcf7-95c0b817f892/scratchpad/"


def _uf_clusters(pairs_same):
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        parent[find(a)] = find(b)
    for a, b in pairs_same:
        union(a, b)
    cl = {}
    for x in parent:
        cl.setdefault(find(x), set()).add(x)
    return [c for c in cl.values() if len(c) > 1]


async def main():
    apply = "--apply" in sys.argv
    pairs = {tuple(sorted([p["a_id"], p["b_id"]])): p for p in json.load(open(S + "pairs.json"))}
    verds = {}
    for f in sorted(glob.glob(S + "verdicts_*.json")):
        for v in json.load(open(f)):
            verds[tuple(sorted([v["a_id"], v["b_id"]]))] = v["verdict"].upper()

    same_sb, same_cb, contra = [], [], []
    for k, vd in verds.items():
        p = pairs.get(k)
        if not p:
            continue
        if vd == "SAME":
            (same_sb if p["a_sub"] == p["b_sub"] else same_cb).append(k)
        elif vd == "CONTRADICT":
            contra.append(k)

    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    # 取真实文本长度(权 keeper)
    ids = {x for k in same_sb for x in k}
    lens = {r["ku_id"]: r["len"] for r in await conn.fetch(
        "SELECT ku_id, length(coalesce(natural_text,'')) len FROM aii.ku_onto WHERE ku_id = ANY($1)", list(ids))}

    clusters = _uf_clusters(same_sb)
    drops = []  # (drop, keeper)
    for c in clusters:
        keeper = max(c, key=lambda x: lens.get(x, 0))
        for d in c:
            if d != keeper:
                drops.append((d, keeper))
    print(f"SAME同书: {len(same_sb)}对 → {len(clusters)}簇, supersede {len(drops)} KU")
    print(f"SAME跨书: {len(same_cb)} → same_as 边")
    print(f"CONTRADICT: {len(contra)}")

    if not apply:
        for d, k in drops[:12]:
            print(f"  merge {d[-26:]} → {k[-26:]}")
        print("\n(dry-run; --apply 落库)")
        await conn.close(); return

    # 备份受影响 KU
    backup = [dict(r) for r in await conn.fetch(
        "SELECT * FROM aii.ku_onto WHERE ku_id = ANY($1)", [d for d, _ in drops])]
    for b in backup:
        b["embedding"] = None  # 备份不存大向量
        for kk, vv in list(b.items()):
            if hasattr(vv, "isoformat"): b[kk] = vv.isoformat()
    json.dump(backup, open(S + "backup_dedup.json", "w"), ensure_ascii=False, default=str)

    merged = 0
    async with conn.transaction():
        for drop, keeper in drops:
            # 边重指向 keeper, 去自环
            await conn.execute("UPDATE aii.edge_onto SET src_id=$2 WHERE src_id=$1", drop, keeper)
            await conn.execute("UPDATE aii.edge_onto SET dst_id=$2 WHERE dst_id=$1", drop, keeper)
            await conn.execute("DELETE FROM aii.edge_onto WHERE src_id=dst_id")
            # 软取代(非删): 留历史, 检索 valid_until IS NULL 自动排除
            await conn.execute(
                "UPDATE aii.ku_onto SET valid_until=now(), superseded_by=$2, updated_at=now() "
                "WHERE ku_id=$1 AND valid_until IS NULL", drop, keeper)
            merged += 1
        # 跨书 same_as 边
        edges = 0
        for k in same_cb:
            a, b = pairs[k]["a_id"], pairs[k]["b_id"]
            exists = await conn.fetchval(
                "SELECT 1 FROM aii.edge_onto WHERE relation_type='same_as' AND "
                "((src_id=$1 AND dst_id=$2) OR (src_id=$2 AND dst_id=$1)) LIMIT 1", a, b)
            if not exists:
                await conn.execute(
                    "INSERT INTO aii.edge_onto(substrate_id,src_id,dst_id,relation_type,grade,extraction_method,evidence) "
                    "VALUES($1,$2,$3,'same_as','moderate','claude_judge',$4)",
                    pairs[k]["a_sub"], a, b, f"cross-book dup sim={pairs[k]['sim']}")
                edges += 1
        # 矛盾入队
        await conn.execute((ROOT / "migrations" / "0005_ku_contradiction.sql").read_text())
        for k in contra:
            a, b = sorted([pairs[k]["a_id"], pairs[k]["b_id"]])
            await conn.execute(
                "INSERT INTO aii.ku_contradiction(ku_a,ku_b,similarity,verdict,rationale,confidence,judged_by) "
                "VALUES($1,$2,$3,'contradict','claude judge',$3,'claude') ON CONFLICT (ku_a,ku_b) DO NOTHING",
                a, b, pairs[k]["sim"])
    cur = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE valid_until IS NULL")
    print(f"\nDONE: superseded {merged} dup KU, +{edges} same_as 边, {len(contra)} 矛盾入队")
    print(f"当前版本 KU: {cur} (备份 → backup_dedup.json, supersede 可逆)")
    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
