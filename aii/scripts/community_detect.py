#!/usr/bin/env python3
"""B 仓概念图社区检测 (graphify 启发③) — 确定性 louvain, 零 LLM。

流程:
  1. B 仓图(概念+边) → networkx 无向图
  2. greedy_modularity_communities(louvain 近似) → 社区
  3. 规模 ≥ 3 概念的社区 → refined_theme_kc(确定性命名: hub 概念, 诚实标注来源)
     + refined_kc_member(社区概念挂载的 KU)
  4. 生成自包含 graph.html(力导向, 社区着色) + graph.json

不覆盖存量主题(29 条 LLM 生成), 新增确定性社区主题并行。

用法:
    .venv/bin/python scripts/community_detect.py [--dry-run] [--min-size 3] [--max-themes 50]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
import networkx as nx

AII_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
OUT_DIR = Path(__file__).resolve().parents[1] / "refined_graph"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-size", type=int, default=3)
    ap.add_argument("--max-themes", type=int, default=50)
    args = ap.parse_args()

    r = await asyncpg.connect(REFINED_URL)

    # 1. 图加载
    concepts = await r.fetch("SELECT concept_id, name FROM rf.refined_concept WHERE name IS NOT NULL")
    edges = await r.fetch(
        "SELECT DISTINCT src_concept, dst_concept FROM rf.refined_directed_edge"
        " WHERE src_concept IS NOT NULL AND dst_concept IS NOT NULL")
    ku_counts = dict(await r.fetch(
        "SELECT concept_id, count(*) FROM rf.refined_ku_concept GROUP BY 1"))
    names = {c["concept_id"]: c["name"] for c in concepts}

    G = nx.Graph()
    G.add_nodes_from(names.keys())
    G.add_edges_from((s, d) for s, d in edges if s in names and d in names)
    print(f"图: {G.number_of_nodes()} 节点 / {G.number_of_edges()} 边", flush=True)

    # 2. louvain 社区
    communities = list(nx.community.greedy_modularity_communities(G))
    comms = sorted(communities, key=len, reverse=True)
    print(f"社区: {len(comms)} 个", flush=True)

    # 3. 主题落库
    created = 0
    graph_nodes, graph_links = [], []
    palette = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4",
               "#46f0f0", "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff"]
    for ci, comm in enumerate(comms[: args.max_themes]):
        cids = list(comm)
        if len(cids) < args.min_size:
            continue
        # hub = KU 挂载数最高概念
        hub = sorted(cids, key=lambda c: -ku_counts.get(c, 0))[:2]
        theme_en = " / ".join(names.get(h, f"#{h}") for h in hub)
        total_ku = sum(ku_counts.get(c, 0) for c in cids)
        # 社区概念挂载的 KU
        ku_ids = await r.fetch(
            "SELECT DISTINCT ku_id FROM rf.refined_ku_concept WHERE concept_id = ANY($1::bigint[])",
            cids)
        member_kus = [k["ku_id"] for k in ku_ids]

        if not args.dry_run:
            kc_id = await r.fetchval(
                "INSERT INTO rf.refined_theme_kc"
                " (version, is_current, theme_name_en, summary, source_books, grade)"
                " VALUES (1, true, $1, $2, $3::jsonb, 'unverified')"
                " RETURNING kc_id",
                theme_en,
                f"确定性社区检测 v1: {len(cids)} 概念, hub: {theme_en}, KU {total_ku}",
                json.dumps(["community_detect_v1"]),
            )
            if member_kus:
                await r.executemany(
                    "INSERT INTO rf.refined_kc_member (kc_id, ku_id) VALUES ($1, $2)"
                    " ON CONFLICT DO NOTHING",
                    [(kc_id, k) for k in member_kus])
        created += 1
        print(f"  [{ci}] 主题: {theme_en[:50]} | {len(cids)} 概念 | {total_ku} KU | {len(member_kus)} member")

        # 可视化数据
        color = palette[ci % len(palette)]
        for c in cids:
            graph_nodes.append({
                "id": c, "name": names.get(c, f"#{c}"), "community": ci,
                "ku_count": ku_counts.get(c, 0), "color": color,
            })
    for s, d in edges:
        if s in names and d in names:
            graph_links.append({"source": s, "target": d})

    # 4. graph.html + graph.json
    if not args.dry_run and graph_nodes:
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / "graph.json").write_text(json.dumps(
            {"nodes": graph_nodes, "links": graph_links}, ensure_ascii=False))
        (OUT_DIR / "graph.html").write_text(_render_html(graph_nodes, graph_links))
        print(f"可视化: {OUT_DIR / 'graph.html'} ({len(graph_nodes)} 节点 / {len(graph_links)} 边)")

    await r.close()
    print(f"完成: 新建主题 {created} ({'DRY-RUN' if args.dry_run else '已写库'})")
    return 0


def _render_html(nodes: list[dict], links: list[dict]) -> str:
    """自包含力导向图(内联 JS canvas 物理, 无 CDN)。"""
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>B 仓概念图 — 社区视图</title><style>
body{{margin:0;font-family:system-ui;background:#111;color:#ddd}}
#tip{{position:fixed;background:#222;border:1px solid #444;padding:6px 10px;
border-radius:6px;font-size:12px;pointer-events:none;display:none;z-index:9}}
#legend{{position:fixed;top:10px;left:10px;font-size:11px;background:#1a1a1a;
padding:8px;border-radius:8px;border:1px solid #333}}
h1{{font-size:14px;margin:0 0 6px}} #stats{{color:#888;font-weight:normal}}
</style></head><body>
<div id="legend"><h1>B 仓概念图 <span id="stats"></span></h1></div>
<div id="tip"></div>
<canvas id="cv"></canvas>
<script>
const NODES={json.dumps(nodes, ensure_ascii=False)};
const LINKS={json.dumps(links, ensure_ascii=False)};
const cv=document.getElementById('cv'),ctx=cv.getContext('2d');
let W,H,D=0;
function resize(){{W=cv.width=innerWidth;H=cv.height=innerHeight}}
addEventListener('resize',resize);resize();
const ids=[];NODES.forEach((n,i)=>{{n.x=Math.random()*W;n.y=Math.random()*H;n.vx=0;n.vy=0;ids[n.id]=i}});
const LN=LINKS.map(l=>({{a:ids[l.source],b:ids[l.target]}})).filter(l=>l.a!==undefined&&l.b!==undefined);
document.getElementById('stats').textContent=`${{NODES.length}} 节点 · ${{LN.length}} 边 · ${{new Set(NODES.map(n=>n.community)).size}} 社区`;
let hover=-1;
for(let iter=0;iter<400;iter++){{
  for(const l of LN){{
    const a=NODES[l.a],b=NODES[l.b];
    let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1;
    const f=(d-120)*0.0008;dx/=d;dy/=d;
    a.vx+=dx*f;b.vx-=dx*f;a.vy+=dy*f;b.vy-=dy*f;
  }}
  for(let i=0;i<NODES.length;i++){{
    for(let j=i+1;j<NODES.length;j++){{
      const a=NODES[i],b=NODES[j];
      let dx=b.x-a.x,dy=b.y-a.y,d=Math.hypot(dx,dy)||1;
      const f=Math.min(4000/(d*d),0.5);dx/=d;dy/=d;
      a.vx-=dx*f;b.vx+=dx*f;a.vy-=dy*f;b.vy+=dy*f;
    }}
  }}
  for(const n of NODES){{
    n.vx+=(W/2-n.x)*0.0004;n.vy+=(H/2-n.y)*0.0004;
    n.x+=n.vx;n.y+=n.vy;n.vx*=0.85;n.vy*=0.85;
  }}
}}
function draw(){{
  ctx.clearRect(0,0,W,H);
  ctx.strokeStyle='rgba(255,255,255,0.08)';ctx.lineWidth=1;
  for(const l of LN){{
    const a=NODES[l.a],b=NODES[l.b];
    ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
  }}
  for(const n of NODES){{
    ctx.beginPath();ctx.arc(n.x,n.y,Math.min(2+Math.sqrt(n.ku_count||0)*1.5,14),0,7);
    ctx.fillStyle=n.color;ctx.globalAlpha=0.9;ctx.fill();ctx.globalAlpha=1;
  }}
}}
cv.onmousemove=e=>{{
  const x=e.clientX,y=e.clientY;hover=-1;
  for(let i=0;i<NODES.length;i++){{
    const n=NODES[i];
    if(Math.hypot(n.x-x,n.y-y)<18){{hover=i;break}}
  }}
  const tip=document.getElementById('tip');
  if(hover>=0){{
    const n=NODES[hover];
    tip.style.display='block';tip.style.left=(x+12)+'px';tip.style.top=(y+12)+'px';
    tip.textContent=`${{n.name}} · ${{n.ku_count}} KU · 社区#${{n.community}}`;
  }} else tip.style.display='none';
  draw();
}};
draw();
</script></body></html>"""


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
