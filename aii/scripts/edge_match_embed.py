#!/usr/bin/env python3
"""readout 边 embedding 匹配增强 — 语义匹配治名称漂移(零 LLM)。

背景: readout 1,704 条边只名称匹配出 533(漂移严重); B 仓概念带 hnsw embedding 索引,
用向量相似度把剩余 readout 名匹配到概念, 补插 B 仓边。

流程:
  1. 收集 concept_readout_edge 中未映射的 src/dst 名(去重)
  2. 本机 embed 服务(127.0.0.1:8102)批量 embed
  3. hnsw 检索 top1 概念(余弦距离 < 阈值) → 补插边(evidence 标 matched_by=embed)
  4. 报告新增边数

用法:
    .venv/bin/python scripts/edge_match_embed.py [--dry-run] [--threshold 0.32] [--limit 500]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path

import asyncpg

AII_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")
EMBED_URL = os.getenv("AII_EMBED_URL", "http://127.0.0.1:8102")
_REL_MAP = {"prerequisite": "prerequisite", "derives": "derives", "subsumes": "subsumes"}


def _embed(texts: list[str]) -> list[list[float]]:
    req = urllib.request.Request(
        f"{EMBED_URL}/embed",
        data=json.dumps({"texts": texts}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read())["embeddings"]


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--threshold", type=float, default=0.32,
                    help="hnsw 余弦距离阈值(越小越严; 0.32 ≈ 余弦 0.68)")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    a = await asyncpg.connect(AII_URL)
    r = await asyncpg.connect(REFINED_URL)

    # 1. 未映射 readout 名(排除已在 B 仓有边的)
    rows = await a.fetch(
        "SELECT DISTINCT src_name, dst_name, relation_type FROM aii.concept_readout_edge"
        " WHERE src_name IS NOT NULL AND dst_name IS NOT NULL")
    idx = {}
    bnames = await r.fetch("SELECT concept_id, name, name_zh FROM rf.refined_concept")
    for c in bnames:
        if c["name"]:
            idx[str(c["name"]).lower()] = c["concept_id"]
        if c["name_zh"]:
            idx[str(c["name_zh"]).lower()] = c["concept_id"]
    pending = []
    for row in rows:
        s = str(row["src_name"]).strip()
        d = str(row["dst_name"]).strip()
        if s.lower() not in idx and d.lower() not in idx:
            pending.append((s, d, row["relation_type"]))
    print(f"待向量匹配 readout 对: {len(pending)}", flush=True)
    if args.limit:
        pending = pending[: args.limit]
    if not pending:
        await a.close(); await r.close()
        return 0

    # 2. embed 全部名字(去重)
    names = sorted({n for pair in pending for n in pair[:2]})
    print(f"embedding {len(names)} 个名字 ...", flush=True)
    vecs = _embed(names)
    name_vec = dict(zip(names, vecs))

    # 3. hnsw 检索匹配
    added = skipped = 0
    for s, d, rel in pending:
        rel = _REL_MAP.get(rel or "", "prerequisite")
        src_c = idx.get(s.lower())
        dst_c = idx.get(d.lower())
        if not src_c:
            src_c = await _match(r, name_vec[s], args.threshold)
        if not dst_c:
            dst_c = await _match(r, name_vec[d], args.threshold)
        if not src_c or not dst_c or src_c == dst_c:
            skipped += 1
            continue
        exists = await r.fetchval(
            "SELECT 1 FROM rf.refined_directed_edge WHERE src_concept=$1"
            " AND dst_concept=$2 AND relation_type=$3 AND edge_source='readout'",
            src_c, dst_c, rel)
        if exists:
            skipped += 1
            continue
        added += 1
        if not args.dry_run:
            await r.execute(
                "INSERT INTO rf.refined_directed_edge"
                " (src_concept, dst_concept, relation_type, grade, edge_source, evidence)"
                " VALUES ($1,$2,$3,'unverified','readout',"
                " jsonb_build_object('matched_by', 'embed', 'src', $4::text, 'dst', $5::text))",
                src_c, dst_c, rel, s, d)
    await a.close(); await r.close()
    print(f"完成: 新增 {added} | 跳过 {skipped} ({'DRY-RUN' if args.dry_run else '已写库'})")
    return 0


async def _match(conn, vec: list[float], threshold: float) -> int | None:
    """hnsw 余弦检索 top1; 距离 < 阈值返回 concept_id。"""
    import pgvector.asyncpg
    await pgvector.asyncpg.register_vector(conn)
    row = await conn.fetchrow(
        "SELECT concept_id, embedding <=> $1 AS dist FROM rf.refined_concept"
        " WHERE embedding IS NOT NULL ORDER BY embedding <=> $1 LIMIT 1",
        vec)
    if row and row["dist"] is not None and row["dist"] < threshold:
        return row["concept_id"]
    return None


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
