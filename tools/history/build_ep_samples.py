#!/usr/bin/env python3
"""生成 contracts/samples/<ep>/ 扩样例集（D-019）——samples = f(fixtures, seeds)，零漂移。

每事件一个响应文件（§8 契约形状，contract_version v0.2，形状零变更）。
事件/账/冲突取自 gold fixture 束；registry_bundle 由响应内实际引用的
src:/per:/pl:/fo: 从 seeds 过滤而来；chronology 行按 EP 配置给定。

用法：python3 tools/history/build_ep_samples.py   （重跑覆盖，幂等）
校验：tools/history/validate_gold.py 会连带校验 samples/ 全部文件。
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"

# EP 配置：event_id → (fixture 文件, chronology 行)
EP = "ep_sanjia_fenjin"
EVENTS = {
    "ev:sanjiafenjin": {
        "fixture": "F1-sanjiafenjin.json",
        "chronology": [
            {
                "source_id": "src:shiji",
                "raw": "晋出公二十二年 / 晋阳之役后二年",
                "canonical": "前453",
                "override": None,
            },
            {
                "source_id": "src:zztj",
                "raw": "周威烈王二十三年（命侯，父事件收束）",
                "canonical": "前403",
                "override": None,
            },
        ],
    },
    "ev:jinyang-zhizhan": {
        # ★取 F23 束（水源/年数冲突 + D-017 route_hint 修复），非 F1/冻结 sample 旧形——差异属 D-017/D-019 可解释
        "fixture": "F23-jinyang-shuiyuan.json",
        "chronology": [
            {
                "source_id": "src:shiji",
                "raw": "晋出公二十二年 / 晋阳之役后二年",
                "canonical": "前453",
                "override": None,
            },
        ],
    },
    "ev:minghou-403": {
        "fixture": "F24-chenguangyue.json",
        "chronology": [
            {
                "source_id": "src:zztj",
                "raw": "周威烈王二十三年",
                "canonical": "前403",
                "override": None,
            },
        ],
    },
    "ev:zhibo-suodi": {"fixture": "F22-zhibo-suodi.json", "chronology": []},
    "ev:zhixuanzi-liyao": {"fixture": "F21-zhiguo-jian.json", "chronology": []},
    "ev:jin-gongshi-bei": {"fixture": "F25-jin-liuqing.json", "chronology": []},
}

REF_RE = re.compile(r'"((?:src|per|pl|fo):[a-z0-9-]+)"')


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def seed_index():
    idx = {}
    for name, key in [
        ("persons", "person_id"),
        ("places", "place_id"),
        ("forces", "force_id"),
        ("sources", "source_id"),
    ]:
        data = load(ROOT / "seeds" / f"{name}.json")
        entries = data[name] if isinstance(data, dict) else data
        idx[name] = {e[key]: e for e in entries}
    return idx


def main():
    idx = seed_index()
    outdir = ROOT / "contracts" / "samples" / EP
    outdir.mkdir(parents=True, exist_ok=True)
    for ev_id, cfg in EVENTS.items():
        bundle = load(ROOT / "fixtures" / cfg["fixture"])
        event = next(e for e in bundle["events"] if e["event_id"] == ev_id)
        wanted_ac = set(event["accounts"]) | {event["mainline_account_ref"]}
        accounts = [a for a in bundle["accounts"] if a["account_id"] in wanted_ac]
        conflicts = [c for c in bundle["conflicts"] if c["conflict_id"] in set(event["conflicts"])]
        body = {"event": event, "accounts": accounts, "conflicts": conflicts}
        refs = set(REF_RE.findall(json.dumps(body, ensure_ascii=False)))
        resp = {
            "contract_version": "v0.2",
            "event": event,
            "accounts": accounts,
            "conflicts": conflicts,
            "registry_bundle": {
                "persons": [idx["persons"][r] for r in sorted(refs) if r.startswith("per:")],
                "places": [idx["places"][r] for r in sorted(refs) if r.startswith("pl:")],
                "forces": [idx["forces"][r] for r in sorted(refs) if r.startswith("fo:")],
                "sources": [idx["sources"][r] for r in sorted(refs) if r.startswith("src:")],
                "chronology": cfg["chronology"],
            },
        }
        out = outdir / (ev_id.removeprefix("ev:") + ".json")
        out.write_text(json.dumps(resp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{out.relative_to(ROOT)}  ac={len(accounts)} cf={len(conflicts)} refs={len(refs)}")


if __name__ == "__main__":
    main()
