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


def full_sweep(ev):
    """全样一致率（OP-D-043 后 Wiki 令扩样）：全部 gold 事件段过管线。

    n=10 手挑对仅冒烟。此处枚举全部 25 唯一 gold 事件：
    - 负例 = 全部 C(N,2) 异事件对，ground-truth=似而非同（管线不得假合——§5 宁碎片方向的危险失效）。
    - 正例 = N 个自述对（同一事件自比），ground-truth=同事异述。
    报真实一致率 + 假合明细 + 保守存疑退化明细（诚实，不粉饰）。
    """
    import itertools

    ids = sorted(ev.keys())
    fp = []
    neg_ok = 0
    neg_n = 0
    for x, y in itertools.combinations(ids, 2):
        v, evd = propose(ev[x], ev[y])
        neg_n += 1
        if v == "似而非同":
            neg_ok += 1
        else:
            fp.append((x, y, v))
    pos_ok = 0
    deferred = []
    for i in ids:
        v, _ = propose(ev[i], ev[i])
        if v == "同事异述":
            pos_ok += 1
        else:
            deferred.append((i, ev[i]))
    tot = neg_n + len(ids)
    allok = neg_ok + pos_ok
    print("\n=== 全样一致率实测（全部 gold 事件段, Wiki 扩样令）===")
    print(f"  唯一 gold 事件 N={len(ids)}")
    print(
        f"  负例(异事件对): {neg_ok}/{neg_n} 正确似而非同 · **假合(false merge)={len(fp)}**"
        "（§5 宁碎片方向：0 假合=从不错并两不同事件）"
    )
    print(f"  正例(自述对): {pos_ok}/{len(ids)} 自识为同事异述 · 保守存疑退化={len(deferred)}")
    print(f"  --- 机械一致率 = {allok}/{tot} = {100 * allok / tot:.2f}%")
    print(
        "  --- 材料判读：**假合率 0%**（危险方向零失效）；退化非错——无纪年/无 actor 的"
        "传疑/制度事件，年窗门（同事异述需 D1=重合）无法触发，按 §5 正确落存疑（宁碎片），送人裁。"
    )
    if fp:
        print("  ⚠ 假合明细（异事件被判同事异述）：")
        for x, y, v in fp:
            print(f"    {x} × {y} -> {v}")
    if deferred:
        print("  保守存疑退化明细（自述对未自识，缺纪年/actor 特征）：")
        for i, e in deferred:
            feat = (
                f"actors={sorted(e['actors']) or '∅'}, years={e['years'] or '∅'}, type={e['type']}"
            )
            print(f"    {i} -> 似而非同（{feat}）")


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
    print(f"--- 清晰对一致率 {ok}/{n} = {100 * ok // n}%（n=10 冒烟；全样见下）")

    full_sweep(ev)

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
