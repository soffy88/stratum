#!/usr/bin/env python3
"""按学段 + 学科导出夸克盘内教育类资料清单（CSV + 分组打印）。"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"

GRADE = {
    "一年级": "小学", "二年级": "小学", "三年级": "小学", "四年级": "小学",
    "五年级": "小学", "六年级": "小学", "小学": "小学",
    "七年级": "初中", "八年级": "初中", "九年级": "初中",
    "初一": "初中", "初二": "初中", "初三": "初中", "初中": "初中",
    "高一": "高中", "高二": "高中", "高三": "高中",
    "必修": "高中", "选择性必修": "高中", "高中": "高中",
}
SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "历史", "地理", "科学", "政治", "道德与法治"]

state = json.loads((PIPE / "quark_sync_state.json").read_text(encoding="utf-8"))
done = set(state.get("deleted_fids", []))
files = json.loads((PIPE / "quark_catalog.json").read_text(encoding="utf-8"))["files"]

rows = []
for f in files:
    name = f["file_name"]
    seg = next((v for k, v in GRADE.items() if k in name), None)
    if not seg:
        continue
    subj = next((s for s in SUBJECTS if s in name), None)
    rows.append({
        "学段": seg,
        "学科": subj or "其他",
        "文件名": name,
        "大小MB": round(f["size"] / 1024 ** 2, 1),
        "大小GB": round(f["size"] / 1024 ** 3, 3),
        "状态": "已迁移" if f["fid"] in done else "待迁移",
        "fid": f["fid"],
    })

out = PIPE / "edu_manifest.csv"
with out.open("w", newline="", encoding="utf-8-sig") as fh:
    w = csv.DictWriter(fh, fieldnames=["学段", "学科", "文件名", "大小MB", "大小GB", "状态", "fid"])
    w.writeheader()
    w.writerows(rows)

print(f"已导出 {out}  共 {len(rows)} 条")
print()
grid = defaultdict(lambda: defaultdict(lambda: [0, 0]))
for r in rows:
    cell = grid[r["学段"]][r["学科"]]
    cell[0] += 1
    cell[1] += r["大小GB"]
print(f"{'学段':<6}{'学科':<10}{'数量':>6}{'体积GB':>10}")
print("-" * 34)
for seg in ["小学", "初中", "高中"]:
    for subj in SUBJECTS + ["其他"]:
        if subj in grid[seg]:
            n, g = grid[seg][subj]
            print(f"{seg:<6}{subj:<10}{n:>6}{g:>10.2f}")
    print("-" * 34)
