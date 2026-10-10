"""B仓主题KC(谱社区)构建 — Leiden社区检测 + LLM自动命名 + 固化入
rf.refined_theme_kc / rf.refined_kc_member。

AII-KNOWLEDGE-FIRST-SPEC-001 改进二。2026-07-19: 只读预览(/api/graph/communities,
resolution=1.0/min_size=3 实测 modularity 0.90+、社区主题连贯)验证过效果后,
用户明确要求固化——这打破了 SPEC 开头写的"三个改进都只读 B/C 仓"红线,是用户
看过预览结果后主动要求的,不是本脚本自己决定违反只读原则。

★与预览接口(graph_concepts.py 的 graph_communities)共用同一套 resolution/min_size/
seed=42, 保证"固化的就是审过的那个结果", 不会预览一套、固化时又悄悄换了参数。

★refined_kc_member 挂的是 KU(ku_id), 不是 concept——B仓社区检测在概念-概念边图上算
(概念共现/关系骨架), 但持久化 schema 设计成挂 KU(见 migrations/refined/0001), 所以
每个社区的概念集合要经 rf.refined_ku_concept 反查出对应 KU 集合再写 (kc_id, ku_id) 行。
一个 KU 若关联该社区里的任意概念就算成员; 一个 KU 可能touch多个社区的概念, 不强行
唯一分配到一个主题(如实反映数据本来的样子, 不为了"整洁"编造假的单一归属)。

★概念成员另存 rf.refined_kc_concept(migrations/refined/0005): KU 成员是反查出来的衍生物,
反查不回概念集合, 而聚类的原始产物就是概念归属。不存它, 读接口(/api/graph/themes)只能
每次重跑 Leiden 再按 size 顺序猜 kc_id 对齐, 概念图一变就静默错位染色。两张表各答各的
问题("这主题由哪些概念构成" vs "这主题涉及哪些KU"), 不是替代关系。

★主题命名走 LLM(仿 scripts/name_communities.py 的 deepseek 直调模式, 未走
ProviderRegistry——那个脚本已经验证过这个简单直接的模式好用), 满足 SPEC §2.2 红线3
"必须人工/LLM命名, 不留数字id"(LLM 命名是红线允许的两个选项之一, 不是人工审的替代)。

★不含 embedding: refined_theme_kc.embedding 列留 NULL(HNSW 索引对 NULL 行不索引,
不报错, 只是暂时不能语义搜索主题——这是已知的、故意留白的范围外功能, 不是半成品bug,
需要的话是独立的后续工作)。

★grade='unverified'(migrations/refined/0004_theme_kc_grade.sql): 主题KC是Leiden聚类+
LLM命名的AII综合物, 同refined_ku/refined_directed_edge的grade铁律——综合物默认不可信,
必须显式标记, 人工审过再手动升级'verified'(本脚本不会自动升级)。

用法:
  uv run python scripts/build_theme_kc.py --dry-run          # 只看会产出哪些社区,不写库
  uv run python scripts/build_theme_kc.py                    # 真跑: LLM命名 + 写入
  uv run python scripts/build_theme_kc.py --resolution 1.5   # 换参数(仍需人工决定,不自动调优)
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
import httpx
import igraph as ig
import leidenalg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

REFINED_DSN = os.getenv(
    "REFINED_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined"
)
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")

_SYS = (
    "Given a cluster of academic concepts (may span multiple disciplines), output a SHORT "
    "theme name + one-line summary in Simplified Chinese, plus an English label. The theme "
    "must be the GENUINE common subject shared by these concepts — no forced/superficial "
    'grouping (不附会). Output strict JSON: {"label":"<主题名,≤8字>","label_en":"<English label>",'
    '"summary":"<一句话概括这批概念的共同主题>"}'
)


async def _name_cluster(client: httpx.AsyncClient, concept_names: list[str]) -> dict:
    try:
        r = await client.post(
            "https://api.deepseek.com/chat/completions",
            headers={"Authorization": "Bearer " + DEEPSEEK_KEY},
            json={
                "model": "deepseek-v4-flash",
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": _SYS},
                    {"role": "user", "content": "Concepts: " + ", ".join(concept_names)},
                ],
            },
            timeout=40,
        )
        return json.loads(r.json()["choices"][0]["message"]["content"])
    except Exception as e:
        return {"label": None, "label_en": None, "summary": f"命名失败: {str(e)[:80]}"}


def _build_partition(concepts, edges, resolution: float):
    """跟 aii/aii/api/routes/graph_concepts.py 的 graph_communities 预览接口
    完全同一套图构建+参数(resolution/seed=42)——固化的必须是审过的那个结果。"""
    id_list = [c["concept_id"] for c in concepts]
    idx_of = {cid: i for i, cid in enumerate(id_list)}

    g = ig.Graph()
    g.add_vertices(len(id_list))
    edge_pairs: list[tuple[int, int]] = []
    weights: list[float] = []
    seen: set[tuple[int, int]] = set()
    for e in edges:
        s, t = e["src_concept"], e["dst_concept"]
        if s not in idx_of or t not in idx_of or s == t:
            continue
        key = tuple(sorted((idx_of[s], idx_of[t])))
        if key in seen:
            continue
        seen.add(key)
        edge_pairs.append(key)
        weights.append(float(e["strength"] or 1.0))
    g.add_edges(edge_pairs)
    if weights:
        g.es["weight"] = weights

    partition = leidenalg.find_partition(
        g,
        leidenalg.RBConfigurationVertexPartition,
        resolution_parameter=resolution,
        weights="weight" if weights else None,
        seed=42,
    )
    return id_list, partition


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--resolution", type=float, default=1.0)
    ap.add_argument("--min-size", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    conn = await asyncpg.connect(REFINED_DSN)
    try:
        concepts = await conn.fetch(
            "SELECT concept_id, name, name_zh, discipline FROM rf.refined_concept"
        )
        edges = await conn.fetch(
            "SELECT src_concept, dst_concept, strength FROM rf.refined_directed_edge"
        )

        by_id = {c["concept_id"]: c for c in concepts}
        id_list, partition = _build_partition(concepts, edges, args.resolution)

        print(
            f"共 {len(id_list)} 概念, {len(partition)} 个社区(含单例), "
            f"modularity={partition.modularity:.4f}"
        )

        clusters = [list(m) for m in partition if len(m) >= args.min_size]
        clusters = [[id_list[i] for i in m] for m in clusters]
        clusters.sort(key=len, reverse=True)
        print(f"size>={args.min_size} 的社区: {len(clusters)} 个")

        if args.dry_run:
            for members in clusters[:15]:
                names = [by_id[m]["name_zh"] or by_id[m]["name"] for m in members]
                print(f"  ({len(members)}) {names[:8]}")
            return

        if not DEEPSEEK_KEY:
            print("缺 DEEPSEEK_API_KEY, 无法命名, 中止(不写半成品数据)", file=sys.stderr)
            sys.exit(1)

        # ★固化前把旧的当前版本标记冻结(不删除历史——见 schema 注释"重聚类产新版,旧版冻结")
        await conn.execute("UPDATE rf.refined_theme_kc SET is_current=false WHERE is_current=true")

        total_kc = 0
        async with httpx.AsyncClient(trust_env=False, timeout=45) as client:
            for members in clusters:
                concept_names = [by_id[m]["name_zh"] or by_id[m]["name"] for m in members]
                j = await _name_cluster(client, concept_names)
                disciplines = sorted(
                    {by_id[m]["discipline"] for m in members if by_id[m]["discipline"]}
                )

                ku_rows = await conn.fetch(
                    "SELECT DISTINCT ku_id FROM rf.refined_ku_concept WHERE concept_id = ANY($1::bigint[])",
                    members,
                )
                ku_ids = [r["ku_id"] for r in ku_rows]

                kc_id = await conn.fetchval(
                    """
                    INSERT INTO rf.refined_theme_kc
                        (version, is_current, theme_name, theme_name_en, summary, summary_zh, source_books, grade)
                    VALUES (1, true, $1, $2, $3, $3, $4, 'unverified')
                    RETURNING kc_id
                    """,
                    j.get("label") or f"社区{total_kc}(命名失败)",
                    j.get("label_en"),
                    j.get("summary"),
                    json.dumps(disciplines, ensure_ascii=False),
                )
                if ku_ids:
                    await conn.executemany(
                        "INSERT INTO rf.refined_kc_member (kc_id, ku_id) VALUES ($1, $2) "
                        "ON CONFLICT DO NOTHING",
                        [(kc_id, k) for k in ku_ids],
                    )
                # ★概念成员才是聚类的原始产物(Leiden 跑在概念图上), 如实存下来——
                # 不存的话读接口只能重跑 Leiden 再按位置猜 kc_id, 图一变就静默错位染色
                # (见 migrations/refined/0005_kc_concept_member.sql)。
                await conn.executemany(
                    "INSERT INTO rf.refined_kc_concept (kc_id, concept_id) VALUES ($1, $2) "
                    "ON CONFLICT DO NOTHING",
                    [(kc_id, m) for m in members],
                )
                total_kc += 1
                print(
                    f"  kc_id={kc_id} 【{j.get('label')}】{len(members)}概念/{len(ku_ids)}KU: "
                    f"{(j.get('summary') or '')[:40]}"
                )

        print(f"\n固化完成: {total_kc} 个主题KC → rf.refined_theme_kc(version=1, is_current=true)")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
