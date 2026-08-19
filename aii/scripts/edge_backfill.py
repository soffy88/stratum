#!/usr/bin/env python3
"""B 仓概念边补抽 (graphify 启发①) — 确定性回填, 零 LLM。

补齐三类边, 全部带 edge_source 标注(graphify EXTRACTED/INFERRED 三态映射):

  1. readout(INFERRED): A 仓 concept_readout_edge 1,704 条 → B 仓边
     (src_name/dst_name → refined_concept 名称匹配; edge_source='readout')
  2. explicit(EXTRACTED): A 仓 provenance.explains(KU→KU 显式链 2,382 条)
     → KU 概念投影 → 概念级 explains 边(edge_source='explicit')
  3. hyperedge(EXTRACTED): explains 链同时落 refined_hyperedge(KU 级超边,
     head=解释方 KU, members=被解释方 KU) —— 设计上有但同步管道从未落

幂等: 已存在同 (src,dst,type,source) 跳过; 重复跑安全。

用法:
    .venv/bin/python scripts/edge_backfill.py [--dry-run] [--source readout|explicit|hyperedge]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

import asyncpg

AII_URL = os.getenv("AII_KG_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
REFINED_URL = os.getenv("REFINED_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined")

_REL_MAP = {"prerequisite": "prerequisite", "derives": "derives", "subsumes": "subsumes"}


async def _concept_lookup(conn) -> dict[str, int]:
    """name/name_zh/aliases → concept_id 索引(小写)。"""
    idx: dict[str, int] = {}
    rows = await conn.fetch("SELECT concept_id, name, name_zh, aliases FROM rf.refined_concept")
    for r in rows:
        for cand in (r["name"], r["name_zh"]):
            if cand:
                idx[cand.lower()] = r["concept_id"]
        for al in (r["aliases"] or []):
            if al:
                idx[str(al).lower()] = r["concept_id"]
    return idx


def _match_concept(idx: dict[str, int], name: str) -> int | None:
    """概念名匹配: 精确(小写) → 包含(短名≥5 且单边包含)。零 LLM 保守匹配。"""
    key = name.lower()
    hit = idx.get(key)
    if hit:
        return hit
    for c2, cid in idx.items():
        if len(c2) >= 5 and len(key) >= 5 and (key in c2 or c2 in key):
            return cid
    return None


async def _a_ku_concept(a, r, idx, ku_id: str) -> int | None:
    """A 仓 KU → aii.concept_onto → B 仓 refined_concept(名称匹配)。"""
    name = await a.fetchval(
        "SELECT c.name FROM aii.ku_concept_onto kc"
        " JOIN aii.concept_onto c ON c.concept_id=kc.concept_id"
        " WHERE kc.ku_id=$1 LIMIT 1", ku_id)
    if not name:
        return None
    return idx.get(str(name).lower())


async def backfill_readout(a, r, idx, dry: bool) -> int:
    rows = await a.fetch(
        "SELECT DISTINCT src_name, dst_name, relation_type FROM aii.concept_readout_edge"
        " WHERE src_name IS NOT NULL AND dst_name IS NOT NULL")
    n = 0
    for row in rows:
        src = idx.get((row["src_name"] or "").lower())
        dst = idx.get((row["dst_name"] or "").lower())
        rel = _REL_MAP.get(row["relation_type"] or "", "prerequisite")
        if not src or not dst or src == dst:
            continue
        exists = await r.fetchval(
            "SELECT 1 FROM rf.refined_directed_edge WHERE src_concept=$1"
            " AND dst_concept=$2 AND relation_type=$3 AND edge_source='readout'",
            src, dst, rel)
        if exists:
            continue
        if not dry:
            await r.execute(
                "INSERT INTO rf.refined_directed_edge"
                " (src_concept, dst_concept, relation_type, grade, edge_source, evidence)"
                " VALUES ($1,$2,$3,'unverified','readout',"
                " jsonb_build_object('backfill', true, 'src', $4::text, 'dst', $5::text))",
                src, dst, rel, row["src_name"], row["dst_name"])
        n += 1
    print(f"readout 回填: {n} 条新边(去重后)")
    return n


async def backfill_explicit(a, r, idx, dry: bool) -> tuple[int, int]:
    """explains 链: A 仓 provenance.explains(概念名) → 概念级边 + 超边。

    explains 值是概念名(如 "Consumer Sovereignty")——本 KU 显式解释该概念。
    EXTRACTED 类(源数据显式声明)。"""
    rows = await a.fetch(
        "SELECT ku_id, provenance FROM aii.ku_onto"
        " WHERE provenance->>'explains' IS NOT NULL AND provenance->>'explains' <> 'null'")
    n_edge = n_hyper = 0
    for row in rows:
        try:
            prov = json.loads(row["provenance"])
            ex = prov.get("explains")
        except Exception:  # noqa: BLE001
            continue
        if not ex:
            continue
        ex_names = ex if isinstance(ex, list) else [ex]
        src_c = await r.fetchval(
            "SELECT kc.concept_id FROM rf.refined_ku_concept kc"
            " WHERE kc.ku_id=$1 LIMIT 1", row["ku_id"])
        if not src_c:
            src_c = await _a_ku_concept(a, r, idx, row["ku_id"])
        for ex_name in ex_names:
            en = str(ex_name or "").strip()
            if not en:
                continue
            # 超边(KU 级, EXTRACTED)
            dst_c = _match_concept(idx, en)
            if src_c and dst_c and src_c != dst_c:
                exists2 = await r.fetchval(
                    "SELECT 1 FROM rf.refined_directed_edge WHERE src_concept=$1"
                    " AND dst_concept=$2 AND relation_type='explains'"
                    " AND edge_source='explicit'", src_c, dst_c)
                if not exists2:
                    n_edge += 1
                    if not dry:
                        await r.execute(
                            "INSERT INTO rf.refined_directed_edge"
                            " (src_concept, dst_concept, relation_type, grade, edge_source, evidence)"
                            " VALUES ($1,$2,'explains','unverified','explicit',"
                            " jsonb_build_object('backfill', true, 'head_ku', $3::text, 'explains', $4::text))",
                            src_c, dst_c, row["ku_id"], en)
            # B 仓 ku_id 是哈希, A 仓原始 id 在 contributions.raw_ku_id
            b_ku = await r.fetchval(
                "SELECT ku_id FROM rf.refined_ku WHERE EXISTS ("
                " SELECT 1 FROM jsonb_array_elements(contributions) e"
                " WHERE e->>'raw_ku_id' = $1) LIMIT 1", row["ku_id"])
            if b_ku:
                exists_h = await r.fetchval(
                    "SELECT 1 FROM rf.refined_hyperedge WHERE relation_type='explains'"
                    " AND head_ku_id=$1 AND evidence->>'explains'=$2",
                    b_ku, en)
                if not exists_h:
                    n_hyper += 1
                    if not dry:
                        await r.execute(
                            "INSERT INTO rf.refined_hyperedge"
                            " (relation_type, head_ku_id, grade, evidence)"
                            " VALUES ('explains', $1, 'unverified',"
                            " jsonb_build_object('explains', $2::text, 'backfill', true))",
                            b_ku, en)
    print(f"explicit 回填: 概念边 {n_edge} | 超边 {n_hyper}")
    return n_edge, n_hyper


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--source", default="all", choices=["all", "readout", "explicit", "hyperedge"])
    args = ap.parse_args()

    a = await asyncpg.connect(AII_URL)
    r = await asyncpg.connect(REFINED_URL)
    idx = await _concept_lookup(r)
    print(f"概念索引: {len(idx)} 个别名")

    total = 0
    if args.source in ("all", "readout"):
        total += await backfill_readout(a, r, idx, args.dry_run)
    if args.source in ("all", "explicit", "hyperedge"):
        ne, nh = await backfill_explicit(a, r, idx, args.dry_run)
        total += ne + nh
    if args.dry_run:
        print("(DRY-RUN 未写库)")

    await a.close()
    await r.close()
    print(f"完成: 新增 {total} 条 ({'DRY-RUN' if args.dry_run else '已写库'})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
