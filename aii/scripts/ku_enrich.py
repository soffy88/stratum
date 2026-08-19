#!/usr/bin/env python3
"""KU Enrichment 二期 — 补填 intuition/insight/example/sources/fingerprint + 提升 grade。

背景: onto_persist 一期只写核心四字段, intuition/insight/example/sources/fingerprint
恒空/恒默认(见 onto_persist.py 注释 "二期 enrichment")。本脚本把二期补上:

  1. sources      ← 从 aii.substrates 取书元数据(确定性, 无 LLM)
  2. fingerprint  ← sha256(natural_text) 前缀(确定性, 无 LLM)
  3. intuition/insight/example ← NIM LLM 基于 natural_text 提炼(严格防幻觉 prompt)
  4. grade        ← enriched 后升为 'moderate'(非 verified; verified 留给人工/验证流水线)

设计: 增量飞轮式(每轮 --limit 条, NIM_RPM 节流), 可反复跑, 天然幂等(已 enriched
的跳过)。适合挂 systemd timer 或 healer 驱动, 错峰执行。

用法:
    cd aii && .venv/bin/python scripts/ku_enrich.py --limit 200 [--dry-run] [--substrate math]
环境: NVIDIA_NIM_API_KEY(缺省读 .pipeline_keys.json 的 econ 槽), NIM_MODEL。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[1]

SYS = (
    "You are a rigorous knowledge curator. Given ONE knowledge unit (KU), produce "
    "three SHORT enrichment fields in Simplified Chinese ONLY (禁止繁体字). "
    "★命门: (1) intuition: 一句话点出这条知识的直觉/本质(为什么成立/怎么想通); "
    "(2) insight: 一句话给出超过原文复述的洞见(联系、推论、适用边界)——只允许从原文 "
    "自然推出的内容, 禁止编造原文没有的事实; (3) example: 一个具体的小例子(可自行构造, "
    "但必须与知识内容一致)。 每项 ≤80 字。 Output strict JSON only: "
    '{"intuition_zh":"...","insight_zh":"...","example_zh":"..."}'
)


def _nim_key() -> str:
    k = os.getenv("NVIDIA_NIM_API_KEY")
    if k:
        return k
    try:
        d = json.loads((ROOT / ".pipeline_keys.json").read_text())
        return d.get("econ") or ""
    except Exception:
        return ""


def fp(s: str) -> str:
    return "sha256:" + hashlib.sha256(s.encode("utf-8")).hexdigest()[:40]


async def enrich_one(client: httpx.AsyncClient, model: str, title: str, text: str) -> dict:
    prompt = f"KU title: {title}\nKU text:\n{text[:4000]}"
    resp = await client.post(
        "https://integrate.api.nvidia.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {_nim_key()}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": SYS},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 600,
        },
    )
    resp.raise_for_status()
    out = resp.json()["choices"][0]["message"]["content"]
    if not out:  # NIM 偶发 message.content=null(nemotron reasoning 模型已知行为)
        raise ValueError("NIM returned empty content (known intermittent)")
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # LLM 偶发输出被截断/带前后缀文本 → 正则提取最后一个 JSON 对象
        m = re.search(r"\{.*\}", out, re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--substrate", default="")
    args = ap.parse_args()

    dsn = os.getenv("DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg")
    conn = await asyncpg.connect(dsn)

    cond = "k.grade='unverified' AND (k.intuition IS NULL OR k.sources='[]'::jsonb)"
    if args.substrate:
        cond += f" AND k.substrate_id LIKE '{args.substrate}%'"
    rows = await conn.fetch(
        f"""
        SELECT k.ku_id, k.title, k.natural_text, k.substrate_id,
               s.title AS src_title, s.medium AS src_medium, s.subject AS src_subject
        FROM aii.ku_onto k LEFT JOIN aii.ingested_substrate s ON s.substrate_id = k.substrate_id
        WHERE {cond} ORDER BY k.created_at DESC LIMIT $1
        """,
        args.limit,
    )
    if not rows:
        print("无待 enrichment 的 KU")
        await conn.close()
        return 0

    model = os.getenv("NIM_MODEL", "nvidia/llama-3.3-nemotron-super-49b-v1.5")
    if not _nim_key():
        print("❌ 无 NIM key(设 NVIDIA_NIM_API_KEY 或 .pipeline_keys.json 的 econ 槽)")
        await conn.close()
        return 2

    ok = fail = 0
    async with httpx.AsyncClient(timeout=180) as client:
        for r in rows:
            try:
                enr = await enrich_one(client, model, r["title"] or "", r["natural_text"] or "")
            except Exception as e:  # noqa: BLE001 — 单条失败不中断批次
                # content=null 属瞬时抖动, 重试 1 次
                if "empty content" in str(e):
                    try:
                        enr = await enrich_one(client, model, r["title"] or "", r["natural_text"] or "")
                    except Exception as e2:  # noqa: BLE001
                        print(f"  ⚠ {r['ku_id']}: {type(e2).__name__} {e2}")
                        fail += 1
                        if fail >= 10:
                            print("  连续失败 ≥10 条, 中止本批(网络/限流?)")
                            break
                        continue
                else:
                    print(f"  ⚠ {r['ku_id']}: {type(e).__name__} {e}")
                    fail += 1
                    if fail >= 10:
                        print("  连续失败 ≥10 条, 中止本批(网络/限流?)")
                        break
                    continue
            fail = 0
            sources = []
            if r["src_title"]:
                sources.append({
                    "title": r["src_title"],
                    "medium": r["src_medium"] or "unknown",
                    "subject": r["src_subject"] or "",
                })
            if args.dry_run:
                print(f"[dry] {r['ku_id']}: intuition={enr.get('intuition_zh','')[:30]}…")
                ok += 1
                continue
            await conn.execute(
                """UPDATE aii.ku_onto SET
                     intuition=$1, insight=$2, example=$3,
                     sources=$4::jsonb, fingerprint=$5, grade='moderate',
                     updated_at=now()
                   WHERE ku_id=$6""",
                enr.get("intuition_zh"), enr.get("insight_zh"), enr.get("example_zh"),
                json.dumps(sources, ensure_ascii=False), fp(r["natural_text"] or ""),
                r["ku_id"],
            )
            ok += 1
    await conn.close()
    print(f"本批 {len(rows)} 条: enriched {ok} / 失败 {fail} ({'DRY-RUN' if args.dry_run else '已写库'})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
