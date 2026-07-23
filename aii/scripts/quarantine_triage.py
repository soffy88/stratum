#!/usr/bin/env python3
r"""隔离积压 triage 助手 — 用 qmd 给每条 quarantine.json 记录生成诊断。

纯只读: 不碰 quarantine.json 本身的写入逻辑, 不做任何自动"放行"/requeue——
现状本来就没有任何工具会转移 status, 这次也不新增(是否值得人工复核, 由人
判断, 不是这个脚本的活)。

诊断方式按 reason_type 分:

  chapter_structure 失败(md_quality_check.py 的 R1 硬失败, 找不到规范 '#
  Chapter N:' 章首):
    1. qmd doc-toc —— qmd 自己的标题识别(同样只认 markdown # 语法, 和
       AII 现有正则一样的盲区, 大概率也是空)
    2. qmd doc-grep 锚定正则(`^第[...]+章\s*$` / `^#*\s*Chapter\s+\d+`)——
       找"独占一行"的章节标记, 而不是正文里提到"见第三章"这种散落引用
    3. 关键一步: 检查命中位置在全文的**分布**, 不只看命中数——
       如果所有命中都挤在文档最前面一小段(比如全文5万行, 命中全部落在
       前100行内), 大概率只是目录/前言里的章节预告列表, 不是正文真实
       章节分界, chapter_ingest.py 现有的 TOC 检测启发式大概率也已经把
       这种情况正确排除了(不是漏检, 是真的没法机器分章)。
       只有命中**跨度覆盖全文大部分长度**才算"qmd 可能真找到了新线索"。

  其它失败(quality_gate 密度不足等): 用 doc-grep 搜 reason_detail 里提到
  的关键词/概念, 看是不是换了个措辞出现在文中(粗筛, 不是精确判定)。

用法: python3 scripts/quarantine_triage.py [--pipeline econ|misc|math] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

AII_ROOT = Path(__file__).resolve().parent.parent
BOOKS_MD = Path("/home/soffy/books/MD")
QMD_CONTAINER = "aii-qmd"
OUT_PATH = AII_ROOT / "quarantine_triage_report.json"

CHAPTER_LINE_RE = r"^第[一二三四五六七八九十百千0-9]+[章节]\s*$|^#{1,3}\s*Chapter\s+\d+"
# "挤在开头一小段" 的判定阈值: 命中位置全部落在全文前 X% 以内, 视为疑似目录块。
FRONT_MATTER_FRACTION = 0.10


def _qmd_path(md_path: str) -> str:
    """quarantine.json 里的绝对宿主路径 → qmd collection 相对地址。"""
    rel = Path(md_path).relative_to(BOOKS_MD)
    return f"aii-books/{rel}"


def _qmd_cli(*args: str) -> dict[str, Any] | None:
    """跑一次 qmd CLI(容器内), 解析 --json 输出。失败返回 None, 不抛异常——
    triage 是尽力而为的诊断, 单条书跑失败不该打断整批。"""
    try:
        proc = subprocess.run(
            ["docker", "exec", QMD_CONTAINER, "qmd", *args, "--json"],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None
    if proc.returncode != 0:
        return None
    try:
        result: dict[str, Any] = json.loads(proc.stdout)
        return result
    except json.JSONDecodeError:
        return None


def _doc_line_count(md_path: str) -> int:
    try:
        return sum(1 for _ in Path(md_path).open(encoding="utf-8", errors="ignore"))
    except OSError:
        return 0


def triage_chapter_structure(item: dict[str, Any]) -> dict[str, Any]:
    md_path = item["md_path"]
    qpath = _qmd_path(md_path)

    toc = _qmd_cli("doc-toc", qpath)
    toc_sections = len(toc.get("sections", [])) if toc else None

    grep = _qmd_cli("doc-grep", qpath, CHAPTER_LINE_RE)
    total_lines = _doc_line_count(md_path)

    verdict: str
    spread_fraction = None
    if grep is None or not grep.get("matches"):
        verdict = "qmd_no_signal"  # doc-toc 和锚定 doc-grep 都没找到任何章节标记行
    else:
        lines = [m["location"]["line"] for m in grep["matches"] if "location" in m]
        if not lines or total_lines == 0:
            verdict = "qmd_no_signal"
        else:
            span = max(lines) - min(lines)
            spread_fraction = span / total_lines
            if spread_fraction < FRONT_MATTER_FRACTION:
                verdict = "suspected_toc_block_not_real_chapters"
            else:
                verdict = "worth_human_look"  # 命中跨度覆盖全文大部分, qmd 可能真找到新线索

    return {
        "check": "chapter_structure",
        "qmd_doc_toc_sections": toc_sections,
        "qmd_anchored_matches": len(grep.get("matches", [])) if grep else 0,
        "match_spread_fraction": spread_fraction,
        "total_lines": total_lines,
        "verdict": verdict,
    }


def triage_generic(item: dict[str, Any]) -> dict[str, Any]:
    md_path = item["md_path"]
    qpath = _qmd_path(md_path)
    reason = item.get("reason_detail", "")

    # 从 reason_detail 里抠可能的关键词(中文术语/带方括号的缺失知识点), 粗筛用,
    # 抠不出来就跳过——这一支本来就是"尽力而为", 不是精确解析。
    terms = re.findall(r"[一-鿿]{2,8}", reason)[:5]
    hits = {}
    for term in terms:
        grep = _qmd_cli("doc-grep", qpath, re.escape(term))
        hits[term] = grep.get("total_matches", 0) if grep else None

    return {
        "check": "generic_keyword_recheck",
        "extracted_terms": terms,
        "term_hits_in_doc": hits,
        "verdict": "has_some_term_hits" if any(v for v in hits.values() if v) else "no_term_hits",
    }


def triage_one(item: dict[str, Any]) -> dict[str, Any]:
    md_path = Path(item["md_path"])
    result: dict[str, Any] = {
        "substrate_id": item.get("substrate_id"),
        "title": item.get("title"),
        "reason_type": item.get("reason_type"),
        "reason_detail": item.get("reason_detail"),
    }
    if not md_path.exists():
        result["diagnosis"] = {"verdict": "md_file_missing"}
        return result

    if "chapter_structure" in item.get("reason_detail", ""):
        result["diagnosis"] = triage_chapter_structure(item)
    else:
        result["diagnosis"] = triage_generic(item)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pipeline", choices=["econ", "misc", "math"], default=None)
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    pipelines = [args.pipeline] if args.pipeline else ["econ", "misc", "math"]
    report: dict[str, list[dict[str, Any]]] = {}

    for pipeline in pipelines:
        qpath = AII_ROOT / f"{pipeline}_pipeline" / "quarantine.json"
        if not qpath.exists():
            continue
        entries = json.loads(qpath.read_text(encoding="utf-8")).get("quarantined", [])
        if args.limit:
            entries = entries[: args.limit]

        results = []
        for item in entries:
            r = triage_one(item)
            results.append(r)
            verdict = r["diagnosis"]["verdict"]
            print(f"[{pipeline}] {r['title'][:35]:35s} -> {verdict}")
        report[pipeline] = results

    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n写入 {OUT_PATH}")

    # 摘要
    for pipeline, results in report.items():
        verdicts: dict[str, int] = {}
        for r in results:
            v = r["diagnosis"]["verdict"]
            verdicts[v] = verdicts.get(v, 0) + 1
        print(f"{pipeline}: {verdicts}")


if __name__ == "__main__":
    main()
