#!/usr/bin/env python3
"""★P2: KU 证据可视化审查 — grounded_by.evidence_quotes → 源 MD 原文高亮 HTML。

消费 grounded_by(字符定位缺失时用 quote 原文 find 兜底), 生成自包含 HTML:
  每个 KU 的证据 quote 在源文档上下文高亮, 人工审查 A 仓质量用。

用法:
  .venv/bin/python scripts/ku_visualize.py --ku <ku_id>          # 单条 KU
  .venv/bin/python scripts/ku_visualize.py --substrate <sid>     # 整本书(前 N 条)
  --out <file.html> --limit 50
"""
from __future__ import annotations

import argparse
import asyncio
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DSN = "postgresql://aii:aii_safe_pass@localhost:5435/aii_kg"
MD_POOLS = [
    Path("/home/soffy/books/MD/经济学"),
    Path("/home/soffy/books/MD/中文数学"),
    Path("/home/soffy/books/MD/英文数学"),
    Path("/home/soffy/books/MD/其它"),
    Path("/home/soffy/books/MD/教辅"),
    Path("/home/soffy/books/MD/计算机"),
    Path("/home/soffy/books/MD/论文"),
]


def _find_source_md(substrate_id: str, probe: str = "") -> str | None:
    """substrate → 源 MD。①文件名 hash 前缀 ②probe 片段内容匹配(quote 首段)。"""
    sid = (substrate_id or "").split("_")[-1][:10]
    files = []
    for pool in MD_POOLS:
        if pool.exists():
            files += list(pool.glob("*.md"))
    for md in files:
        if sid in md.stem:
            return md.read_text(encoding="utf-8", errors="replace")
    # 内容匹配(probe 前 40 字符)
    if probe:
        import re
        key = re.sub(r"\s+", "", probe[:40]).lower()
        for md in files:
            try:
                txt = md.read_text(encoding="utf-8", errors="replace")
                if key in re.sub(r"\s+", "", txt).lower():
                    return txt
            except Exception:
                continue
    return None


def _quote_spans(quotes: list[dict], text: str) -> list[tuple[int, int, str, str]]:
    """quote → 原文 span(DB span 若 [0,0] 用 find 兜底)。返回 [(start, end, kind, quote)]。"""
    out = []
    for q in quotes or []:
        quote = q.get("quote") or ""
        if not quote:
            continue
        sp = q.get("span") or [0, 0]
        start, end = sp if isinstance(sp, list) and len(sp) == 2 else (0, 0)
        if not quote or end <= start or end > len(text) or text[start:end] != quote:
            import re
            norm = re.sub(r"\s+", "", quote)
            ti = re.sub(r"\s+", "", text)
            i = ti.find(norm)
            if i < 0:
                # 模糊: quote 首 30 字(去空白)兜底(LLM 讲透版 quote 非原文逐字)
                frag = norm[:30]
                if len(frag) >= 12:
                    i = ti.find(frag)
                    if i >= 0:
                        out.append((i, i + min(len(norm), 200), q.get("kind") or "", quote[:80]))
                continue
            start, end = i, i + len(norm)
            out.append((start, end, q.get("kind") or "", quote[:80]))
            continue
        out.append((start, end, q.get("kind") or "", quote[:80]))
    return out


def _render_html(title: str, text: str, spans: list[tuple[int, int, str, str]]) -> str:
    colors = {"definition": "#ffe066", "name_hit": "#9ae6b4", "first_sentence": "#90cdf4",
              "": "#fbb6ce"}
    html = [f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{title}</title>"
            "<style>body{max-width:900px;margin:24px auto;padding:0 16px;font-family:system-ui}"
            "mark{border-radius:3px;padding:0 2px;cursor:pointer}mark b{font-size:10px;color:#fff;"
            "background:#333;border-radius:3px;padding:0 3px;margin-right:3px}"
            "h1{font-size:18px}pre{white-space:pre-wrap;line-height:1.7}</style></head><body>"
            f"<h1>{title}</h1><pre>"]
    if not spans:
        html.append(text.replace("<", "&lt;"))
    else:
        prev = 0
        for s, e, kind, _ in sorted(spans, key=lambda x: x[0]):
            if s < prev:
                continue
            html.append(text[prev:s].replace("<", "&lt;"))
            html.append(f"<mark style='background:{colors.get(kind, '#fbd38d')}'><b>{kind or 'quote'}</b>"
                        f"{text[s:e].replace('<', '&lt;')}</mark>")
            prev = e
        html.append(text[prev:].replace("<", "&lt;"))
    html.append("</pre></body></html>")
    return "".join(html)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ku", default=None)
    ap.add_argument("--substrate", default=None)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    import asyncpg
    conn = await asyncpg.connect(DSN, timeout=15)
    try:
        if args.ku:
            rows = await conn.fetch(
                "SELECT ku_id, substrate_id, title, grounded_by FROM aii.ku_onto WHERE ku_id=$1", args.ku)
        else:
            rows = await conn.fetch(
                "SELECT ku_id, substrate_id, title, grounded_by FROM aii.ku_onto "
                "WHERE substrate_id=$1 ORDER BY ku_id LIMIT $2", args.substrate, args.limit)
    finally:
        await conn.close()

    if not rows:
        print("无结果")
        return 1

    # 按 substrate 分组(同源 MD 只读一次)
    per_sub: dict[str, list[dict]] = {}
    for r in rows:
        per_sub.setdefault(r["substrate_id"], []).append(dict(r))

    html_parts = []
    for sid, kus in per_sub.items():
        src = _find_source_md(sid)
        if not src and kus:
            gb0 = kus[0]["grounded_by"]
            gb0 = json.loads(gb0) if isinstance(gb0, str) else (gb0 or {})
            qs = (gb0.get("evidence_quotes") or [])
            src = _find_source_md(sid, probe=(qs[0].get("quote") or "") if qs else "")
        text = src if src else "(源 MD 未找到)"
        for ku in kus[:args.limit]:
            _gb_raw = ku["grounded_by"]
            gb = json.loads(_gb_raw) if isinstance(_gb_raw, str) else (_gb_raw or {})
            quotes = gb.get("evidence_quotes") or []
            spans = _quote_spans(quotes, text)
            title = f"{ku['ku_id'][:40]} — {ku['title'][:50]}"
            html_parts.append(_render_html(title, text, spans))

    out = args.out or "/tmp/ku_visual.html"
    Path(out).write_text("\n<hr>\n".join(html_parts), encoding="utf-8")
    print(f"已生成 {len(html_parts)} 个 KU 可视化 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
