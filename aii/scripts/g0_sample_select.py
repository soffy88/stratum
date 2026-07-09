#!/usr/bin/env python3
r"""G0 样本选择 — MINERU-AII-INTEGRATION-SPEC-001 §5.1.

三类各挑 10 份, 来源依据真实信号(不是凭空定义), 优先级从最强信号到启发式兜底:

  含公式:
    1. math_pipeline/quarantine.json 里 reason_detail 含 "has_formula" 的条目
       (质量门禁明确标过公式覆盖不足, 强信号, 实测只有 4 条)
    2. 不够则从 books/MD/{中文数学,英文数学} 扫 LaTeX 密度(`$...$`/`\[...\]`
       出现次数)补足, 按密度降序取

  密集表格:
    质量门禁没有标过"表格"这个维度, 全部走启发式——扫 books/MD/ 全语料下
    markdown 表格行(`|...|...|`)密度, 取 top 10。原计划只扫经济学/(设想数据表
    更多), 实测经济学/全体 42 本几乎 0 表格行(PDF→MD 转换多半把表格拍平成纯
    文本, 没保留 GFM 语法), 只有 1 本例外——反而是英文数学/统计学教材(概率论
    /统计/机器学习数学基础一类)表格行密度高得多, 已改成扫全语料, 如实按实测
    结果调整, 不硬守最初假设。

  扫描件/复杂版式:
    1. books/MD/待OCR/ 目录本身就是"待OCR=扫描件"标签, 全部收录(实测只有1份)
    2. 不够则从三个 quarantine.json 里 reason_detail 含
       chapter_structure/chapter_dup/chapter_gap 的条目补足(结构识别失败,
       常见于扫描/复杂版式书的目录识别错乱) —— 弱于①但仍是真实信号, 不是拍脑袋

不足 10 的类别如实标注"实际取到 N 份", 不硬凑数字。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

AII_ROOT = Path(__file__).resolve().parent.parent
BOOKS_MD = Path("/home/soffy/books/MD")
OUT_PATH = AII_ROOT / "g0_eval" / "sample_set.json"

TARGET_PER_CATEGORY = 10

LATEX_RE = re.compile(r"\$[^$\n]{2,}\$|\\\[.*?\\\]", re.DOTALL)
TABLE_ROW_RE = re.compile(r"^\s*\|.*\|.*\|\s*$", re.MULTILINE)


def _load_quarantined(pipeline: str) -> list[dict]:
    path = AII_ROOT / f"{pipeline}_pipeline" / "quarantine.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("quarantined", [])


def _all_quarantined() -> list[tuple[str, dict]]:
    out = []
    for pipeline in ("econ", "misc", "math"):
        for item in _load_quarantined(pipeline):
            out.append((pipeline, item))
    return out


def pick_formula_heavy() -> list[dict]:
    picked: list[dict] = []
    seen_paths: set[str] = set()

    for pipeline, item in _all_quarantined():
        if pipeline != "math":
            continue
        if "has_formula" in item.get("reason_detail", ""):
            md_path = item.get("md_path", "")
            picked.append(
                {
                    "path": md_path,
                    "title": item.get("title", ""),
                    "category": "formula_heavy",
                    "source": "quarantine:has_formula",
                    "detail": item.get("reason_detail", ""),
                }
            )
            seen_paths.add(md_path)

    if len(picked) >= TARGET_PER_CATEGORY:
        return picked[:TARGET_PER_CATEGORY]

    # Fallback: scan 中文数学/英文数学 for raw LaTeX density, fill remaining slots.
    candidates: list[tuple[int, Path]] = []
    for sub in ("中文数学", "英文数学"):
        d = BOOKS_MD / sub
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            if str(f) in seen_paths:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            density = len(LATEX_RE.findall(text))
            if density > 0:
                candidates.append((density, f))

    candidates.sort(key=lambda x: -x[0])
    for density, f in candidates:
        if len(picked) >= TARGET_PER_CATEGORY:
            break
        picked.append(
            {
                "path": str(f),
                "title": f.stem,
                "category": "formula_heavy",
                "source": "heuristic:latex_density",
                "detail": f"{density} LaTeX matches",
            }
        )
    return picked


def pick_table_dense() -> list[dict]:
    candidates: list[tuple[int, Path]] = []
    for sub in ("中文数学", "英文数学", "经济学", "其它"):
        d = BOOKS_MD / sub
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            density = len(TABLE_ROW_RE.findall(text))
            if density > 0:
                candidates.append((density, f))
    candidates.sort(key=lambda x: -x[0])
    picked = [
        {
            "path": str(f),
            "title": f.stem,
            "category": "table_dense",
            "source": "heuristic:table_row_density",
            "detail": f"{density} table-row lines",
        }
        for density, f in candidates[:TARGET_PER_CATEGORY]
    ]
    return picked


def pick_scanned_complex() -> list[dict]:
    picked: list[dict] = []
    ocr_dir = BOOKS_MD / "待OCR"
    if ocr_dir.exists():
        for f in ocr_dir.glob("*.md"):
            picked.append(
                {
                    "path": str(f),
                    "title": f.stem,
                    "category": "scanned_complex",
                    "source": "dir:待OCR",
                    "detail": "位于待OCR目录, 本身就是扫描件标签",
                }
            )

    if len(picked) >= TARGET_PER_CATEGORY:
        return picked[:TARGET_PER_CATEGORY]

    structural_fail_markers = ("chapter_structure", "chapter_dup", "chapter_gap")
    for pipeline, item in _all_quarantined():
        if len(picked) >= TARGET_PER_CATEGORY:
            break
        rd = item.get("reason_detail", "")
        if any(m in rd for m in structural_fail_markers):
            picked.append(
                {
                    "path": item.get("md_path", ""),
                    "title": item.get("title", ""),
                    "category": "scanned_complex",
                    "source": f"quarantine:{pipeline}:structural_failure",
                    "detail": rd,
                }
            )
    return picked


def main() -> None:
    formula = pick_formula_heavy()
    table = pick_table_dense()
    scanned = pick_scanned_complex()

    for name, items in (("含公式", formula), ("密集表格", table), ("扫描件/复杂版式", scanned)):
        n = len(items)
        flag = "" if n == TARGET_PER_CATEGORY else f" ⚠ 只取到 {n}/{TARGET_PER_CATEGORY}, 未硬凑"
        print(f"{name}: {n} 份{flag}")

    out = {
        "spec": "MINERU-AII-INTEGRATION-SPEC-001 §5.1",
        "target_per_category": TARGET_PER_CATEGORY,
        "categories": {
            "formula_heavy": formula,
            "table_dense": table,
            "scanned_complex": scanned,
        },
    }
    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {OUT_PATH}")


if __name__ == "__main__":
    main()
