#!/usr/bin/env python3
"""存量 math_prog 补跑命名(②规划审核) —— 分批, 只写 staging, 不进 concept_onto。

背景: 规划审核②因 key 断链静默死了三周, 14919 条 KU 的命名全部落到③摘首句
(title 是陈述原文不是概念名)。①书自带括号名对"正文带公式"的数学书天然失效
(干净本实测 0%), 所以②是唯一可行的命名通道。本脚本给存量补跑②。

★纪律(Wiki 2026-07-20 定):
  · 只写 staging 的 label/llm_name/concept_candidate, 【不进 concept_onto】——
    入概念层是下一道独立工序(带过滤器+去重), 分开走, 这一步错了不污染概念层。
  · 不动 KU 的内容字段(en/zh/point/chapter), 红线: 不动存量 KU 写入。
  · 先过粘连门(md_glue_gate): 超阈值的书不跑, 省下 ~220s/章 的 49B 成本。
  · 分批: 批1 验收后才放行批2-4。每批完打点报数。

用法:
  uv run python scripts/math_prog_rename_batch.py --books "书名片段1,书名片段2" --tag batch1
  uv run python scripts/math_prog_rename_batch.py --rest --tag batch2   # 跑剩下没跑过的
  加 --dry-run 只列出会跑哪些书和预估成本, 不调 LLM。
"""

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, "scripts")
from md_glue_gate import GLUE_THRESHOLD, glue_ratio  # noqa: E402

BOOK_DIRS = ["/home/soffy/books/MD/英文数学", "/home/soffy/books/MD/中文数学"]
OUT_BASE = Path("scripts/_staging/math_prog_rename")


def substrate_of(stem: str) -> str:
    return "math_prog_" + hashlib.md5(stem.encode()).hexdigest()[:10]


def pick_books(patterns, rest_mode):
    out = []
    for d in BOOK_DIRS:
        for f in sorted(Path(d).glob("*.md")):
            if patterns and not any(p.strip() and p.strip() in f.name for p in patterns):
                continue
            sub = substrate_of(f.stem)
            if rest_mode and (OUT_BASE / sub / ".done").exists():
                continue
            out.append((f, sub))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--books", default="", help="书名片段, 逗号分隔")
    ap.add_argument("--rest", action="store_true", help="跑所有还没 .done 的书")
    ap.add_argument("--tag", default="batch")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    books = pick_books(args.books.split(",") if args.books else [], args.rest)
    if not books:
        print("没有匹配到书。", file=sys.stderr)
        return 1

    plan, skipped = [], []
    for f, sub in books:
        ratio, _, _ = glue_ratio(f.read_text(encoding="utf-8", errors="replace"))
        if ratio > GLUE_THRESHOLD:
            skipped.append((f.name, ratio))
            continue
        plan.append((f, sub, ratio))

    print(f"[{args.tag}] 计划跑 {len(plan)} 本 | 粘连门拦下 {len(skipped)} 本")
    for n, r in skipped:
        print(f"   ⏭ {r:5.1%} {n[:56]}")
    if args.dry_run:
        for f, sub, r in plan:
            print(f"   · {r:5.1%} {f.name[:56]}")
        return 0

    t_all = time.time()
    done = 0
    for f, sub, ratio in plan:
        out = OUT_BASE / sub
        t0 = time.time()
        print(f"\n── [{args.tag}] {f.name[:58]} (粘连{ratio:.1%})", flush=True)
        r = subprocess.run(
            [sys.executable, "scripts/math_program_ingest.py", str(f), sub, "--staging", str(out)],
            capture_output=True,
            text=True,
        )
        sys.stdout.write(r.stdout[-1500:])
        if r.returncode != 0:
            print(f"   ❌ 失败: {r.stderr[-400:]}", file=sys.stderr)
            continue
        # 统计本书产出
        n_ku = n_named = n_cand = 0
        for j in sorted(out.glob("ch*.json")):
            try:
                items = json.loads(j.read_text(encoding="utf-8"))
            except Exception:
                continue
            n_ku += len(items)
            n_named += sum(1 for x in items if x.get("llm_name"))
            n_cand += sum(1 for x in items if x.get("concept_candidate"))
        (out / ".done").write_text(args.tag, encoding="utf-8")
        done += 1
        print(
            f"   ✅ {n_ku} KU | 有②命名 {n_named} | 概念候选 {n_cand} | {time.time() - t0:.0f}s",
            flush=True,
        )

    el = time.time() - t_all
    print(f"\n[{args.tag}] 完成 {done}/{len(plan)} 本, 总耗时 {el / 60:.1f} 分钟")
    return 0


if __name__ == "__main__":
    sys.exit(main())
