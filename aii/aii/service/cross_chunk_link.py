"""根因A 修复: 跨块连接 (concept/语义筛候选 → LLM 判真关系 → 连边).

依据 AII-EXTRACT-VALIDATION-001 根因A: ontology_extract 逐块抽取, 边只在块内,
同主题 KU 散在不同块永远连不上 → 覆盖率受限.

★红线: 概念/语义只用来【筛候选】(缩小该判断的 KU 对范围), 绝不"共享概念=边".
真正连边的唯一依据是 LLM 判定的真实关系; LLM 答 none 即不连.
新边标 extraction_method='cross_chunk_llm', relation_type 必属受控词表.
"""
from __future__ import annotations

import asyncio
import json
import re

import numpy as np
from oprim._aii_graph_types import VALID_RELATION_TYPES

_CHUNK = re.compile(r'ku_c(\d+)_')


def _chunk_of(ku_id: str) -> str | None:
    m = _CHUNK.match(ku_id)
    return m.group(1) if m else None


async def gen_candidates(conn, *, substrate_id: str, sem_threshold: float = 0.80) -> list[tuple]:
    """产候选对 (只筛范围, 不连边):
      ① 共享归一后概念 + 跨块 + 无边
      ② KU embedding 语义相似 >= sem_threshold + 跨块 + 无边
    返回去重无序对列表 [(k1,k2), ...].
    """
    shared = await conn.fetch("""
      SELECT DISTINCT a.ku_id k1, b.ku_id k2 FROM aii.ku_concept_onto a
      JOIN aii.ku_concept_onto b ON a.concept_id=b.concept_id AND a.ku_id<b.ku_id
      JOIN aii.ku_onto ka ON a.ku_id=ka.ku_id AND ka.substrate_id=$1
      JOIN aii.ku_onto kb ON b.ku_id=kb.ku_id AND kb.substrate_id=$1
      WHERE substring(ka.ku_id from 'ku_c([0-9]+)_') <> substring(kb.ku_id from 'ku_c([0-9]+)_')
      AND NOT EXISTS(SELECT 1 FROM aii.edge_onto e
                     WHERE (e.src_id=a.ku_id AND e.dst_id=b.ku_id)
                        OR (e.src_id=b.ku_id AND e.dst_id=a.ku_id))
    """, substrate_id)
    pairs = {tuple(sorted((r['k1'], r['k2']))) for r in shared}

    rows = await conn.fetch(
        "SELECT ku_id, embedding FROM aii.ku_onto WHERE substrate_id=$1 AND embedding IS NOT NULL",
        substrate_id)
    ids = [r['ku_id'] for r in rows]
    E = np.array([[float(x) for x in r['embedding']] for r in rows])
    En = E / np.linalg.norm(E, axis=1, keepdims=True)
    S = En @ En.T
    existing = set()
    for e in await conn.fetch("SELECT src_id,dst_id FROM aii.edge_onto"):
        existing.add((e['src_id'], e['dst_id']))
        existing.add((e['dst_id'], e['src_id']))
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if S[i, j] >= sem_threshold and _chunk_of(ids[i]) != _chunk_of(ids[j]) \
                    and (ids[i], ids[j]) not in existing:
                pairs.add(tuple(sorted((ids[i], ids[j]))))
    return sorted(pairs)


_JUDGE_SYS = ("You are a precise knowledge-graph relation judge. "
              "You only assert a relation when it genuinely, directly holds. "
              "When two units merely share a topic but have no direct relation, you answer 'none'. "
              "Output valid JSON only.")

_JUDGE_TMPL = """\
Two knowledge units from one economics textbook:

[A] {a}

[B] {b}

Is there a TRUE, DIRECT knowledge relation between A and B? Default to "none" unless a
specific relation clearly holds — sharing a topic is NOT a relation.

Valid relations: explains, causes, prerequisite_of, special_case_of, contrasts_with, subsumes, supported_by.

Output JSON: {{"relation": "<one valid relation or 'none'>", "direction": "AtoB" or "BtoA"}}"""


def _parse(resp) -> dict:
    txt = ""
    for blk in resp.get("content", []):
        if isinstance(blk, dict) and blk.get("type") == "text":
            txt += blk.get("text", "")
    m = re.search(r'\{.*\}', txt, re.DOTALL)
    if not m:
        return {"relation": "none"}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"relation": "none"}


async def judge_and_link(conn, llm, candidates, *, substrate_id: str, concurrency: int = 5) -> dict:
    """对每个候选对 LLM 判关系; 非 none 且受控 → 连边 (cross_chunk_llm)."""
    texts = {r['ku_id']: r['natural_text'] for r in await conn.fetch(
        "SELECT ku_id, natural_text FROM aii.ku_onto WHERE substrate_id=$1", substrate_id)}
    sem = asyncio.Semaphore(concurrency)
    results = []

    async def judge(k1, k2):
        async with sem:
            prompt = _JUDGE_TMPL.format(a=texts.get(k1, "")[:600], b=texts.get(k2, "")[:600])
            try:
                resp = await llm(messages=[{"role": "user", "content": prompt}],
                                 system=_JUDGE_SYS, max_tokens=120)
                j = _parse(resp)
            except Exception:
                j = {"relation": "none"}
            return (k1, k2, j)

    for fut in asyncio.as_completed([judge(k1, k2) for k1, k2 in candidates]):
        results.append(await fut)

    linked = 0
    by_rel = {}
    for k1, k2, j in results:
        rel = (j.get("relation") or "none").strip().lower()
        if rel == "none" or rel == "same_as" or rel not in VALID_RELATION_TYPES:
            continue  # LLM 说无关系 / 非受控 → 不连
        src, dst = (k1, k2) if j.get("direction") != "BtoA" else (k2, k1)
        await conn.execute(
            """INSERT INTO aii.edge_onto(substrate_id, src_id, dst_id, relation_type, extraction_method)
               VALUES ($1,$2,$3,$4,'cross_chunk_llm')""",
            substrate_id, src, dst, rel)
        linked += 1
        by_rel[rel] = by_rel.get(rel, 0) + 1

    return {"candidates": len(candidates), "linked": linked,
            "none": len(candidates) - linked, "by_relation": by_rel}
