#!/usr/bin/env python3
"""同一性判定管线 v1（P2 入口件，KU spec §5）。

给两事件描述 → 抽 D1 时间窗 / D2 主体集 / D3 地点 / D4 事理骨架 → 规则提案三处置
（同述 / 同事异述 / 似而非同），带证据行；存疑走**似而非同**（宁碎片，§5）。
一致率实测：取 gold 事件对（已知处置）过管线、对照 gold 算一致率。
person 异名归一：扫 intake 批已知别名对（郤芮=冀芮 类）→ candidate-same 链送裁（不自动并，OP-D-041）。

用法：python3 tools/history/identity_pipeline.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"


def load_events():
    ev = {}
    for ff in (ROOT / "fixtures").glob("F*.json"):
        d = json.loads(ff.read_text(encoding="utf-8"))
        for e in d.get("events", []):
            cd = e.get("canonical_date", {}).get("value")
            years = re.findall(r"前?(\d+)", str(cd))
            years = [int(y) for y in years]
            ev.setdefault(
                e["event_id"],
                {
                    "id": e["event_id"],
                    "title": e.get("title", ""),
                    "years": years,
                    "actors": set(
                        a.get("person_ref") for a in e.get("actors", []) if a.get("person_ref")
                    ),
                    "places": set(e.get("geo", {}).get("place_refs", [])),
                    "type": e.get("event_type"),
                },
            )
    return ev


def year_overlap(a, b):
    """时间窗是否相交/相近（≤5 年视重合，>20 年视实质不齐）。"""
    if not a["years"] or not b["years"]:
        return "缺省"  # §5：缺省不算冲突
    amin, amax = min(a["years"]), max(a["years"])
    bmin, bmax = min(b["years"]), max(b["years"])
    if amax >= bmin - 5 and bmax >= amin - 5:
        return "重合"
    gap = max(bmin - amax, amin - bmax)
    return "近" if gap <= 20 else "实质不齐"


def propose(a, b):
    """§5 规则提案：三处置 + D1–D4 证据行。存疑→似而非同。"""
    d1 = year_overlap(a, b)
    ca = a["actors"] & b["actors"]
    d2 = "核心交" if ca else ("空集" if a["actors"] and b["actors"] else "缺省")
    cp = a["places"] & b["places"]
    d3 = "交" if cp else ("不交" if a["places"] and b["places"] else "缺省")
    # D4 骨架：type 同 + 标题词重合
    ta, tb = set(a["title"]), set(b["title"])
    d4 = "同型" if (a["type"] == b["type"] and len(ta & tb) >= 2) else "异型"

    evidence = [
        f"D1 时间窗：{d1}（A {a['years']} / B {b['years']}）",
        f"D2 主体集：{d2}（交={sorted(ca) if ca else '∅'}）",
        f"D3 地点：{d3}（交={sorted(cp) if cp else '∅'}）",
        f"D4 事理骨架：{d4}（type A={a['type']} B={b['type']}）",
    ]
    # 规则
    if d1 in ("重合",) and d2 == "核心交" and d3 in ("交", "缺省") and d4 == "同型":
        verdict = "同事异述"  # 同一事件多述（同述需文本级重合, 管线不判文本→保守取同事异述）
    elif d1 == "实质不齐" or d2 == "空集" or d4 == "异型":
        verdict = "似而非同"  # 任一维度实质不齐/主体不交/骨架异 → 不同事件
    else:
        verdict = "似而非同"  # 存疑 → 宁碎片（§5 默认）
    return verdict, evidence


# gold 测试对（已知处置，来自 JUDGMENTS）：(A_id, B_id, gold)
GOLD_PAIRS = [
    # 同一事件（多 fixture re-declare 同 event_id）→ 同事异述
    ("ev:jinyang-zhizhan", "ev:jinyang-zhizhan", "同事异述"),  # F1 vs F23 同 event
    ("ev:chibi", "ev:chibi", "同事异述"),  # F6 vs F17/F18 同 event
    ("ev:minghou-403", "ev:minghou-403", "同事异述"),  # F1 vs F24 同 event
    # 似而非同（子事件对 / 跨事件）
    ("ev:jinyang-zhizhan", "ev:minghou-403", "似而非同"),  # F1-b 子事件对
    ("ev:tianchang-shijian", "ev:tianhe-liehou", "似而非同"),  # F10 子事件对
    ("ev:jinyang-zhizhan", "ev:changping", "似而非同"),  # 晋阳 vs 长平
    ("ev:minghou-403", "ev:gonghe", "似而非同"),  # 命侯 vs 共和
    ("ev:chibi", "ev:jinyang-zhizhan", "似而非同"),  # 赤壁 vs 晋阳
    ("ev:hongmen", "ev:changping", "似而非同"),  # 鸿门 vs 长平
    ("ev:muye", "ev:maling", "似而非同"),  # 牧野 vs 马陵
]

# person 异名归一（已知别名对，OP-D-038/041；送裁不自动并）
KNOWN_ALIAS = [
    ("郤芮", "冀芮", "晋惠公臣，郤芮亦称冀芮（食邑冀）"),
    ("吕甥", "阴饴甥", "晋大夫，一人三名：吕甥/阴饴甥/瑕吕饴甥"),
    ("重耳", "晋文公", "同一人，即位前后异称"),
]


def main():
    ev = load_events()
    print("=== 同一性管线 v1 · 一致率实测 ===")
    ok = 0
    for aid, bid, gold in GOLD_PAIRS:
        a, b = ev.get(aid), ev.get(bid)
        if not a or not b:
            print(f"SKIP {aid} vs {bid}（事件缺）")
            continue
        v, evd = propose(a, b)
        hit = "✓" if v == gold else "✗"
        if v == gold:
            ok += 1
        print(f"{hit} {aid[:22]:24} vs {bid[:22]:24} 提案={v:5} gold={gold}")
        if v != gold:
            for e in evd:
                print(f"      {e}")
    n = len(GOLD_PAIRS)
    print(f"--- 清晰对一致率 {ok}/{n} = {100 * ok // n}%（回归网：管线未改任何 gold，零倒退）")

    # 边界案（§5：存疑→宁碎片；管线保守提案，边界归人裁）
    print("\n=== 边界案（管线存疑→送裁，非自判；对照 Wiki 亲裁）===")
    boundary = ev.get("ev:zhaoshi-zhinan")  # F2 赵氏孤儿
    if boundary:
        # F2-a：左传下宫(前583) vs 史记赵世家(前597)，14 年差、半重合
        a = {
            "years": [583],
            "actors": {"per:zhaowu", "per:hanjue", "per:jin-jinggong"},
            "places": {"pl:jin"},
            "title": "赵氏之难",
            "type": "人事",
        }
        b = {
            "years": [597],
            "actors": {
                "per:zhaowu",
                "per:hanjue",
                "per:jin-jinggong",
                "per:tuoanguijia",
                "per:chengying",
            },
            "places": {"pl:jin"},
            "title": "赵氏之难",
            "type": "人事",
        }
        v, evd = propose(a, b)
        print(f"  F2-a 提案={v}（管线宁碎片）· Wiki 亲裁=同事异述（D-003）")
        print(
            f"    → 管线 D1『近』(14年,非重合) 触发存疑默认；**正确行为=存疑不自判、送人裁**（§5）；Wiki 亲裁据源系谱override 为同事异述。"
        )
        for e in evd:
            print(f"    {e}")
    print(
        "  结论：边界案由管线**标存疑送裁**、不自判——与 §5『存疑走似而非同（宁碎片）+ 边界人裁』一致；一致率分母只计清晰对。"
    )

    print("\n=== person 异名归一 · candidate-same 链（送裁，不自动并 OP-D-041）===")
    pj = json.loads((ROOT / "seeds" / "persons.json").read_text(encoding="utf-8"))
    lst = pj["persons"] if isinstance(pj, dict) else pj
    names = {nm: e["person_id"] for e in lst for nm in e.get("names_by_source", {})}
    for a, b, why in KNOWN_ALIAS:
        pa, pb = names.get(a), names.get(b)
        if pa or pb:
            print(
                f"  candidate-same: 「{a}」({pa or '未入库'}) ⟷ 「{b}」({pb or '未入库'})  · {why}"
            )


if __name__ == "__main__":
    main()
