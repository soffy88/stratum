#!/usr/bin/env python3
"""生成「同一课本仅留人教版」的删除计划。

只产出计划与统计，不执行任何删除。删除不可逆，需人工确认。
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"

GRADE = ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级",
         "七年级", "八年级", "九年级",
         "高一", "高二", "高三"]
SUBJ = ["语文", "数学", "英语", "物理"]
PUB = ["人教", "冀教", "教科", "苏教", "苏科", "沪科", "沪教", "外研", "湘教",
       "青岛", "译林", "北师大", "仁爱", "浙教", "西南大学", "牛津", "鲁教"]

# 去掉版本/年份/册次修饰，得到「课本槽位」键
NOISE = re.compile(
    r"[（(\[【].*?[)）\]】]|"
    r"电子课本|高清(?:正式)?版|正式版|教师用书|过程稿|OCR|扫描版|彩图版|"
    r"20\d{2}[春秋夏冬年]?|\d{4}|人民教育出版社|全一册|\s+"
)


def slot(name: str) -> tuple[str | None, str | None, str]:
    seg = next((g for g in GRADE if g in name), None)
    sub = next((s for s in SUBJ if s in name), None)
    if not sub:
        return seg, sub, name
    stem = NOISE.sub("", name)
    stem = next((p for p in PUB if p in stem), "", ) and stem or stem
    for p in PUB:
        stem = stem.replace(p, "")
    key = stem[:40] or name[:40]
    return seg, sub, key


rows = list(csv.DictReader((PIPE / "manifest_4subjects.csv").open(encoding="utf-8-sig")))
groups: dict[tuple, list[dict]] = defaultdict(list)
for r in rows:
    seg, sub, key = slot(r["文件名"])
    pub = next((p for p in PUB if p in r["文件名"]), None)
    groups[(seg, sub, key)].append({**r, "_pub": pub, "_mb": float(r["大小MB"])})
for g in groups.values():
    for it in g:
        it["_mb"] = float(it["大小MB"])

dup_exact, ver_dup = [], []
for key, items in groups.items():
    if len(items) < 2:
        continue
    # 子集1: 文件名+大小 完全一致（真重复，哈希去重会折叠）
    sig = defaultdict(list)
    for it in items:
        sig[(it["文件名"], round(it["_mb"], 1))].append(it)
    for _, same in sig.items():
        if len(same) > 1:
            dup_exact.extend(same[1:])          # 保留第一份
            keep = same[:1]
            items = [x for x in items if x not in same[1:]]
            if len(keep) < len(sig):
                pass
    # 子集2: 同槽位、不同出版社，且存在人教版
    pubs = {it["_pub"] for it in items}
    if len(pubs) > 1 and "人教" in pubs:
        keep = [x for x in items if x["_pub"] == "人教"]
        drop = [x for x in items if x["_pub"] != "人教"]
        ver_dup.extend(drop)
        print(f"槽位 {key[0]}/{key[1]}/{key[2][:28]}")
        print(f"    保留 人教 {len(keep)} 份")
        for d in drop:
            print(f"    删除 [{d['_pub'] or '无标记'}] {d['_mb']:>8.1f}MB  {d['文件名'][:52]}")


def summary(name, items):
    tot = sum(x["_mb"] for x in items) / 1024
    print(f"\n{'='*58}\n{name}: {len(items)} 个 / {tot:.2f} GB")
    by = defaultdict(lambda: [0, 0.0])
    for x in items:
        c = by[(x["学段"], x["学科"])]
        c[0] += 1
        c[1] += x["_mb"] / 1024
    for (seg, sub), (n, g) in sorted(by.items()):
        print(f"    {seg:<5}{sub:<5}{n:>5} 个 / {g:>6.2f} GB")


summary("A. 完全重复（同名同大小，哈希去重会折叠）", dup_exact)
summary("B. 版本重复（同槽位有更偏爱人教）", ver_dup)
summary("C. A+B 合计可清理", dup_exact + ver_dup)

out = PIPE / "dedup_delete_plan.csv"
with out.open("w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["类别", "学段", "学科", "版本", "大小MB", "文件名", "fid"])
    for x in dup_exact:
        w.writerow(["完全重复", x["学段"], x["学科"], x["_pub"] or "", x["_mb"], x["文件名"], x["fid"]])
    for x in ver_dup:
        w.writerow(["版本重复", x["学段"], x["学科"], x["_pub"] or "", x["_mb"], x["文件名"], x["fid"]])
print(f"\n计划已写入 {out}")
