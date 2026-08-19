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

_RE_CANON_CHAPTER = re.compile(r"(?m)^#{0,4}\s*Chapter\s+(\d+)\b")        # R1 规范章首 '# Chapter N:'(允许无#)
_RE_BARE_EN_CHAPTER = re.compile(r"(?m)^#{0,2}[ \t]*(?:Chapter|CHAPTER)\s+([0-9]{1,3})\b[^\n]{0,80}$")  # 裸 Chapter N
_RE_ZH_CHAPTER = re.compile(r"(?m)^#{0,4}\s*第([一二三四五六七八九十百千0-9]+)章")  # 中文章节格式
_RE_DECIMAL_CHAPTER = re.compile(r"(?m)^#{0,4}\s+\**\d{1,2}\.\d+\b")      # 小数编号 (1.1, 2.3)
_RE_BARE_N_HEADING = re.compile(r"(?m)^[ \t]*(?:[一二三四五六七八九十百]+|[0-9]{1,2})[、．.][ \t]*[^\n]{2,60}$")  # 裸 '1. 标题'/'一、标题'
_RE_H1 = re.compile(r"(?m)^#\s+[^\n]{2,80}$")   # 任意 H1 标题(无编号格式时的最后兜底)
_RE_H2 = re.compile(r"(?m)^##\s+[^\n]{2,80}$")  # 任意 H2 标题
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

    # ★Multi-format chapter detection: all three formats work with chapter_ingest.chapter_starts
    # 1) Canonical English: # Chapter N:
    canon_chap = [int(m.group(1)) for m in _RE_CANON_CHAPTER.finditer(t)]
    # 2) Chinese: 第N章
    _CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    def _cn2int(s):
        if s.isdigit(): return int(s)
        if s in _CN: return _CN[s]
        if s.startswith("十"): return 10 + _CN.get(s[1:], 0)
        if "十" in s:
            a, _, b = s.partition("十")
            return _CN[a] * 10 + (_CN.get(b, 0) if b else 0)
        return _CN.get(s, 0)
    zh_chapters_raw = []
    for m in _RE_ZH_CHAPTER.finditer(t):
        n = _cn2int(m.group(1))
        if n: zh_chapters_raw.append(n)
    # 3) Decimal: 1.1, 2.3 → use major number as chapter
    dec_chapters_raw = []
    for m in _RE_DECIMAL_CHAPTER.finditer(t):
        parts = m.group(0).split()
        for part in parts:
            if "." in part:
                try:
                    dec_chapters_raw.append(int(part.split(".")[0]))
                except ValueError:
                    pass
    # 3b) 裸 'Chapter N'(无#) / 裸 'N. 标题'/'N、标题' — 与 chapter_ingest._bare_*_starts 同口径
    bare_en_chapters = [int(m.group(1)) for m in _RE_BARE_EN_CHAPTER.finditer(t)]
    bare_n_raw = []
    for m in _RE_BARE_N_HEADING.finditer(t):
        head = m.group(0).lstrip()
        mnum = re.match(r"^([一二三四五六七八九十百]+|[0-9]{1,2})", head)
        if not mnum:
            continue
        s2 = mnum.group(1)
        n = _cn2int(s2) if not s2.isdigit() else int(s2)
        if n: bare_n_raw.append(n)
    # 3c) 任意 H1/H2 标题(最后兜底, 无编号格式的书) — 与 chapter_ingest._md_heading_starts 同口径
    h1_raw = []
    for m in _RE_H1.finditer(t):
        h1_raw.append(m.start())
    h2_raw = []
    for m in _RE_H2.finditer(t):
        h2_raw.append(m.start())
    # 模拟 _md_heading_starts: H1≥3 用 H1, 否则 H2; 间距过滤 3000字符; 上限 200
    def _md_heading_count(h_positions):
        if not h_positions:
            return 0
        picks = [h_positions[0]]
        for p in h_positions[1:]:
            if p - picks[-1] > 3000 and len(picks) < 200:
                picks.append(p)
        return len(picks)
    md_heading_count = _md_heading_count(h1_raw) if len(h1_raw) >= 3 else _md_heading_count(h2_raw)
    spaced = len(_RE_SPACED_HEADER.findall(t))
    fig_ph = len(_RE_FIG_PLACEHOLDER.findall(t))
    dangling = len(_RE_DANGLING_FIG.findall(t))
    table_frag = len(_RE_TABLE_FRAGMENT.findall(t))
    math_hits = len(_RE_MATH_SIGNAL.findall(t))
    latex_hits = len(_RE_LATEX.findall(t))
    metrics = {"canonical_chapter_headings": len(canon_chap), "zh_chapter_headings": len(zh_chapters_raw),
               "decimal_chapter_headings": len(dec_chapters_raw),
               "bare_en_chapter_headings": len(bare_en_chapters), "bare_n_headings": len(bare_n_raw),
               "md_heading_chapters": md_heading_count,
               "total_detected_chapters": len(set(canon_chap + zh_chapters_raw + dec_chapters_raw
                                                 + bare_en_chapters + bare_n_raw)),
               "spaced_chapter_headers": spaced,
               "figure_placeholders": fig_ph, "dangling_figure_refs": dangling,
               "table_fragments": table_frag, "math_signals": math_hits, "latex_spans": latex_hits}

    is_book = medium == "book"
    if is_book:
        # ★Multi-format chapter detection (all recognized by chapter_ingest.chapter_starts)
        # 与 chapter_starts 同口径: 各格式独立统计, 选唯一编号数最多的(1个孤立的
        # '# Chapter 1' 不应压过 27 个裸 'N. 标题')
        formats = [("canon", canon_chap), ("zh", zh_chapters_raw),
                   ("bare_en", bare_en_chapters), ("dec", dec_chapters_raw),
                   ("bare_n", bare_n_raw), ("md_heading", list(range(md_heading_count)))]
        best_fmt, best_chapters = max(formats, key=lambda kv: len(set(kv[1])))
        all_chapters = best_chapters
        n_unique_chapters = len(set(all_chapters)) if all_chapters else 0
        
        if n_unique_chapters < 3:
            # No recognizable chapter structure at all → hard fail
            fmt_parts = []
            if canon_chap: fmt_parts.append(f"# Chapter N:{len(set(canon_chap))}")
            if zh_chapters_raw: fmt_parts.append(f"第N章:{len(set(zh_chapters_raw))}")
            if dec_chapters_raw: fmt_parts.append(f"小数编号:{len(set(dec_chapters_raw))}")
            if bare_en_chapters: fmt_parts.append(f"裸Chapter:{len(set(bare_en_chapters))}")
            if bare_n_raw: fmt_parts.append(f"裸N.标题:{len(set(bare_n_raw))}")
            if md_heading_count: fmt_parts.append(f"H1/H2标题:{md_heading_count}")
            hard.append({"check": "chapter_structure",
                         "detail": f"可识别章节数={n_unique_chapters}<3 (格式: {'; '.join(fmt_parts) if fmt_parts else '无'})"})
        else:
            # Has enough chapters. Only check gaps/dups for canonical English format.
            # ★2026-08-04: gap/dup 降级为 advisory——OpenStax 等多卷合订本正文偶缺章标题
            #   (OCR丢章)或目录副本重复, chapter_ingest 抽取时字典后出现者获胜(正文覆盖目录),
            #   仍能正确抽取现有章节; 缺章损失由质量门完整率把关, 不应在预检堵死整本书。
            if canon_chap:
                uniq = sorted(set(canon_chap))
                if len(uniq) != len(canon_chap):
                    adv.append({"check": "chapter_dup",
                                "detail": f"章号重复(正文混入目录副本?): 共{len(canon_chap)}个/去重{len(uniq)}个 → 抽取取正文后出现者"})
                if uniq != list(range(1, len(uniq) + 1)):
                    adv.append({"check": "chapter_gap", "detail": f"章号非连续 1..N: {uniq[:25]} → 缺章由质量门完整率把关"})
            # For non-canonical formats (Chinese/decimal): no gap/dup hard checks
            # These books can still pass precheck and will work with chapter_ingest's flexible parsing
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
