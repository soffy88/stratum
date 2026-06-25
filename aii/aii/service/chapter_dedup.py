"""章节级去重: KU 抽完(小块抽全, 含跨块冗余)→ 向量聚相似候选 → LLM 判组.

规则:
  - 同一知识点(即使换措辞)→ 一组, 留最完整/最自足的一条, 删其余.
  - 不同层次(命题/规律 vs 其背后的机制/why; 定义 vs 应用)→ 不合, 都留.
  ★只在向量相似(≥sim_threshold)的候选内判, 不全量两两(省调用).
"""
from __future__ import annotations

import asyncio
import json
import re
from collections import defaultdict

import numpy as np
from oprim import vector_encode

_DEDUP_SYS = ("You judge whether knowledge units express the SAME knowledge point or DIFFERENT ones. "
              "Same wording-variant → merge. Different LEVELS (a principle vs the mechanism/why behind it, "
              "a definition vs its application) → keep separate. Output valid JSON only.")

_DEDUP_TMPL = """\
These knowledge units from ONE textbook chapter are vector-similar — decide which are true duplicates.

{items}

Partition ONLY into SAME-groups (units stating the SAME knowledge point, even if reworded). Units at
DIFFERENT levels stay separate — DO NOT merge a principle with the mechanism/why that explains it, nor a
definition with an example/application of it. For each SAME-group, pick the most complete & self-contained
unit as the keeper.

Output JSON: {{"groups": [{{"same": [unit numbers], "keep": <unit number>}}]}}
Units that are unique (no duplicate here) → do NOT list them. If none are duplicates → {{"groups": []}}"""


def _parse(resp) -> dict:
    txt = ""
    for blk in resp.get("content", []):
        if isinstance(blk, dict) and blk.get("type") == "text":
            txt += blk.get("text", "")
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return {"groups": []}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"groups": []}


async def dedup_kus(kus: list[dict], llm, *, sim_threshold: float = 0.82, concurrency: int = 5) -> dict:
    """返回 {kept: [...], dropped: [...], groups: [...]}. kept 保 KU 原 dict."""
    n = len(kus)
    if n < 2:
        return {"kept": list(kus), "dropped": [], "groups": []}
    vecs = np.asarray(vector_encode(texts=[k.get("content", "") for k in kus], provider="default"),
                      dtype=np.float32)
    En = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-12)
    S = En @ En.T

    # 并查集: 向量相似 ≥ 阈值 的连通分量 = 候选簇
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        for j in range(i + 1, n):
            if S[i, j] >= sim_threshold:
                parent[find(i)] = find(j)
    comp = defaultdict(list)
    for i in range(n):
        comp[find(i)].append(i)
    clusters = [sorted(v) for v in comp.values() if len(v) > 1]

    drop: set[int] = set()
    groups_report: list = []
    sem = asyncio.Semaphore(concurrency)

    async def judge(cluster):
        items = "\n".join(
            f"{idx + 1}. [{kus[idx].get('knowledge_type')}] {kus[idx].get('content', '')[:320]}"
            for idx in cluster)
        async with sem:
            try:
                resp = await llm(messages=[{"role": "user", "content": _DEDUP_TMPL.format(items=items)}],
                                 system=_DEDUP_SYS, max_tokens=400)
                data = _parse(resp)
            except Exception:
                data = {"groups": []}
        local = []
        for g in data.get("groups", []):
            same = [int(x) - 1 for x in g.get("same", []) if isinstance(x, (int, str)) and str(x).strip().lstrip("-").isdigit()]
            same = [s for s in same if s in cluster]
            keep = g.get("keep")
            keep = int(keep) - 1 if keep is not None and str(keep).strip().lstrip("-").isdigit() else (same[0] if same else None)
            if len(same) >= 2 and keep in same:
                for s in same:
                    if s != keep:
                        drop.add(s)
                local.append({"same": same, "keep": keep})
        return local

    for res in await asyncio.gather(*(judge(c) for c in clusters)):
        groups_report.extend(res)

    kept = [k for i, k in enumerate(kus) if i not in drop]
    dropped = [kus[i] for i in sorted(drop)]
    return {"kept": kept, "dropped": dropped, "groups": groups_report,
            "before": n, "after": len(kept)}
