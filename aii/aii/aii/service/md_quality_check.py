"""md 交付合格性自检 — 飞轮入口质量门 (纯规则, 0 LLM).

依据 AII-STRATUM-MD-SPEC-001 的验收标准. 摄取前对每本 md 自检:
  合格 → 进入抽取;  不合格 → 不抽 + 自动写 rework 请求到 aii-to-stratum, 等 Stratum 返工.
★脏 md 挡在门外, 不进抽取产生垃圾 KU (690 本规模化的入口质量门).
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

_OUTPUT_DIR = Path(os.getenv("FLYWHEEL_OUTPUT_DIR", "/home/soffy/shared/aii-to-stratum"))

_RE_CANON_CHAPTER = re.compile(r"(?m)^#\s+Chapter\s+(\d+)\b")        # R1 规范章首 '# Chapter N:'
_RE_SPACED_HEADER = re.compile(r"C\s+H\s+A\s+P\s+T\s+E\s+R")          # R9 间隔字母跑页眉
_RE_DANGLING_FIG = re.compile(
    r"\b(the (green|blue|red|shaded|dashed) (rectangle|area|region|box|line|curve)"
    r"|as shown (above|below)|in the figure (above|below))\b", re.I)   # R7 悬空图引用
_RE_FIG_PLACEHOLDER = re.compile(r"!\[[^\]]*[Ff]igure", re.I)          # R7 规范图占位
_RE_TABLE_FRAGMENT = re.compile(r"(?m)^[^\n|]*\bTable\s+\d+\.\d+[^\n]*\|\s*$")  # R8 表格残片
_RE_MATH_SIGNAL = re.compile(r"[=Σ∑∫∂√±≤≥≠αβγδεθλμπρσφω]|\bpercentage change\b", re.I)
_RE_LATEX = re.compile(r"\$[^$\n]+\$")


def check_md_quality(text: str, *, medium: str = "book", title: str = "") -> dict:
    """返回 {ok, hard_failures:[...], advisories:[...], metrics:{...}}.
    只对 medium='book' 做章节硬结构检查; 文章/论文(无章节)不卡章节."""
    t = text or ""
    L = max(len(t), 1)
    hard: list[dict] = []
    adv: list[dict] = []

    chap = [int(m.group(1)) for m in _RE_CANON_CHAPTER.finditer(t)]
    spaced = len(_RE_SPACED_HEADER.findall(t))
    fig_ph = len(_RE_FIG_PLACEHOLDER.findall(t))
    dangling = len(_RE_DANGLING_FIG.findall(t))
    table_frag = len(_RE_TABLE_FRAGMENT.findall(t))
    math_hits = len(_RE_MATH_SIGNAL.findall(t))
    latex_hits = len(_RE_LATEX.findall(t))
    metrics = {"canonical_chapter_headings": len(chap), "spaced_chapter_headers": spaced,
               "figure_placeholders": fig_ph, "dangling_figure_refs": dangling,
               "table_fragments": table_frag, "math_signals": math_hits, "latex_spans": latex_hits}

    is_book = medium == "book"
    if is_book:
        # 硬项 1-4 (章节结构, AII-STRATUM-MD-SPEC §3)
        if not chap:
            hard.append({"check": "chapter_structure",
                         "detail": "无规范 '# Chapter N:' 章首 (R1); 无法机器分章"})
        else:
            uniq = sorted(set(chap))
            if len(uniq) != len(chap):
                hard.append({"check": "chapter_dup",
                             "detail": f"章号重复(正文混入目录副本?): 共{len(chap)}个/去重{len(uniq)}个"})
            if uniq != list(range(1, len(uniq) + 1)):
                hard.append({"check": "chapter_gap", "detail": f"章号非连续 1..N: {uniq[:25]}"})
        if spaced > 5:
            hard.append({"check": "running_header_noise",
                         "detail": f"间隔字母 'C H A P T E R' x{spaced} (R9)"})

    # 内容保真项 (R6-R8) — 默认 advisory(不单独卡门), 但 book 且严重时升级
    if math_hits >= 30 and latex_hits == 0:
        adv.append({"check": "latex_fidelity", "detail": f"数学信号 {math_hits} 但 0 LaTeX(R6 公式可能被OCR毁)"})
    if dangling > 0 and fig_ph == 0:
        adv.append({"check": "dangling_figures", "detail": f"{dangling} 处悬空图引用且无图占位(R7 致依赖图死KU)"})
    if table_frag > 0:
        adv.append({"check": "table_fragments", "detail": f"{table_frag} 处表格残片(R8 致表格碎片死KU)"})

    return {"ok": not hard, "hard_failures": hard, "advisories": adv, "metrics": metrics}


def write_md_rework(*, substrate_id: str, file_name: str, title: str, result: dict) -> None:
    """把不合格 md 的 rework 请求合并进 aii-to-stratum/md_quality_spec.json 的 rework_request(按 id 去重)."""
    try:
        _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path = _OUTPUT_DIR / "md_quality_spec.json"
        spec = {}
        if path.exists():
            try:
                spec = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                spec = {}
        rework = spec.get("rework_request", []) if isinstance(spec, dict) else []
        ids = {r.get("id") for r in rework}
        if substrate_id not in ids:
            reasons = [f["check"] + ":" + f["detail"] for f in result.get("hard_failures", [])]
            reasons += ["(advisory)" + a["check"] for a in result.get("advisories", [])]
            rework.append({"id": substrate_id, "file": file_name, "title": title[:80],
                           "reason": "chapter_structure_unreliable: " + "; ".join(reasons),
                           "metrics": result.get("metrics", {}),
                           "flagged_at": datetime.now(timezone.utc).isoformat()})
            if isinstance(spec, dict):
                spec["rework_request"] = rework
                path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        import logging
        logging.getLogger(__name__).exception("write_md_rework failed (non-fatal)")
