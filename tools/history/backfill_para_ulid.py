#!/usr/bin/env python3
"""§4.3 接线：把语料库 para_ulid 回填进 fixtures（备录引文 → 在库段落地址）。

匹配规则：corpus 段落 `backs_fixtures` 含某 fixture id，且该段 chapter 是 fixture account
locator.chapter 的关键子串（去括注后），则将该 account 的 `locator.para_ulid` 由 null 回填为
corpus para_ulid。只回填、不改引文文字（异文另由机核报告 + notes 记）。

用法：python3 tools/history/backfill_para_ulid.py [--apply]
  无 --apply：dry-run 打印将回填的 (fixture, account, para_ulid)。
  --apply：写回 fixtures/*.json。
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"
CORPUS = ROOT / "corpus"
FIX = ROOT / "fixtures"


def core_chapter(s: str) -> str:
    """去括注、去书名前缀，取核心篇名用于匹配。"""
    s = re.sub(r"[（(].*?[)）]", "", s)
    s = s.split("·")[-1]
    return s.strip()


def main():
    apply = "--apply" in sys.argv
    # corpus para index: fixture_id -> [(chapter_core, para_ulid, book)]
    idx = {}
    for cf in sorted(CORPUS.glob("*.json")):
        doc = json.loads(cf.read_text(encoding="utf-8"))
        for p in doc["paragraphs"]:
            for fid in p["backs_fixtures"]:
                idx.setdefault(fid, []).append(
                    (core_chapter(p["chapter"]), p["para_ulid"], doc["substrate"]["book"])
                )

    planned = []
    for ff in sorted(FIX.glob("F*.json")):
        fid = ff.name.split("-")[0]
        cands = idx.get(fid, [])
        if not cands:
            continue
        d = json.loads(ff.read_text(encoding="utf-8"))
        changed = False
        for a in d.get("accounts", []):
            loc = a.get("locator", {})
            if loc.get("para_ulid"):
                continue
            acc_ch = core_chapter(loc.get("chapter", ""))
            for cch, pulid, book in cands:
                # 双向子串匹配（篇名核心互含）
                cch_core = cch.split("·")[0]
                if (
                    cch_core
                    and (cch_core in acc_ch or acc_ch in cch_core)
                    and book.split("（")[0][:2] in (loc.get("book", "") or "")
                ):
                    planned.append((ff.name, a["account_id"], acc_ch, pulid))
                    if apply:
                        loc["para_ulid"] = pulid
                        changed = True
                    break
        if apply and changed:
            ff.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for row in planned:
        print(f"{'APPLIED' if apply else 'PLAN'}: {row[0]} | {row[1]} | 篇={row[2]} → {row[3]}")
    print(f"--- {len(planned)} para_ulid {'回填' if apply else '待回填'}")


if __name__ == "__main__":
    main()
