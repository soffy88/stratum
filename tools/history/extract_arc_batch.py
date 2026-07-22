#!/usr/bin/env python3
"""§4.5 首批新事件抽取（P1 出口件）+ §4.4 ≥30 段 held-out 评测（合一）· qwen3-8b。

从全文左传语料采样**晋系**段落（含 晉/趙/韓/魏/欒/郤/智/範/中行 等），qwen3-8b 抽取事件
（date 不产出 D-028）→ 注册表解析（persons/places 命中率＝§4.4 指标 + person 解析率趋势）→
新人物/地名以 **candidate 状态**随包送裁（不入正式注册表，§4.4 红线：候选不入 gold）。
抽检包 = 事件 + 解析 + 简易同一性判定记录（与既有 25 gold 事件标题/主体粗比）。

用法：python3 tools/history/extract_arc_batch.py [N] > docs/history/extract/W-H1a-3-arc-candidates.json
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "qwen3-8b"
JIN = re.compile(r"[晉趙韓魏欒郤智範氏中行祁羊舌曲沃驪姬六卿]")
PROMPT = (
    "/no_think 你是文言史料结构化抽取器。从史料抽取, 只输出JSON不解释:"
    '{"title":事件名,"persons":[人物],"place":地点或null,'
    '"event_type":∈["战役","政变","会盟","册命","迁都","变法","灾异","制度","人事","其他"],'
    '"is_event":true/false(是否叙述一具体历史事件)}。不要年份。史料:「%s」'
)


def registry():
    persons, places = {}, {}
    pj = json.loads((ROOT / "seeds" / "persons.json").read_text(encoding="utf-8"))
    for e in pj["persons"] if isinstance(pj, dict) else pj:
        persons[e["person_id"]] = "".join(e.get("names_by_source", {}).keys())
    qj = json.loads((ROOT / "seeds" / "places.json").read_text(encoding="utf-8"))
    for e in qj["places"] if isinstance(qj, dict) else qj:
        places[e["place_id"]] = "".join(e.get("name_by_era", {}).values())
    return persons, places


def gold_events():
    ev = []
    for ff in (ROOT / "fixtures").glob("F*.json"):
        d = json.loads(ff.read_text(encoding="utf-8"))
        for e in d.get("events", []):
            ev.append((e["event_id"], e.get("title", "")))
    return ev


def run(text):
    payload = json.dumps(
        {
            "model": MODEL,
            "prompt": PROMPT % text[:220],
            "stream": False,
            "options": {"temperature": 0, "num_ctx": 2048},
        }
    )
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "60", OLLAMA, "-d", payload],
            capture_output=True,
            text=True,
            timeout=70,
        ).stdout
        resp = json.loads(out).get("response", "")
        jm = re.search(r"\{.*\}", resp, re.S)
        return json.loads(jm.group(0)) if jm else None
    except Exception:
        return None


def main():
    N = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 35
    persons, places = registry()
    golds = gold_events()
    zz = json.loads((ROOT / "corpus" / "zuozhuan.json").read_text(encoding="utf-8"))
    # 采样晋系段（长度适中、含晋系关键字），跨全书均匀取 N
    cands_src = [
        p for p in zz["paragraphs"] if JIN.search(p["text"]) and 20 <= len(p["text"]) <= 200
    ]
    step = max(1, len(cands_src) // N)
    off = (step // 2) if len(sys.argv) > 2 and sys.argv[2] == "shift" else 0
    sample = cands_src[off::step][:N]

    out_cands = []
    pn_tot = pn_hit = 0
    valid = type_ok = 0
    for p in sample:
        ext = run(p["text"])
        if not ext:
            continue
        valid += 1
        if str(ext.get("event_type")) in [
            "战役",
            "政变",
            "会盟",
            "册命",
            "迁都",
            "变法",
            "灾异",
            "制度",
            "人事",
            "其他",
        ]:
            type_ok += 1
        # 注册表解析
        res_p, new_p = [], []
        for pn in [str(x) for x in (ext.get("persons") or [])]:
            pn_tot += 1
            hit = next(
                (pid for pid, lbl in persons.items() if pn and (pn in lbl or lbl in pn)), None
            )
            if hit:
                pn_hit += 1
                res_p.append({"name": pn, "registry": hit})
            else:
                new_p.append(pn)
        place_hit = None
        pl = str(ext.get("place") or "")
        if pl:
            place_hit = next((pid for pid, lbl in places.items() if pl in lbl or lbl in pl), None)
        # 简易同一性: 与 gold 标题粗比
        idn = next(
            (
                eid
                for eid, tt in golds
                if tt
                and ext.get("title")
                and (ext["title"][:3] in tt or tt[:3] in str(ext.get("title")))
            ),
            None,
        )
        out_cands.append(
            {
                "source_para_ulid": p["para_ulid"],
                "source_chapter": p["chapter"],
                "extracted": ext,
                "registry_resolution": {
                    "persons_hit": res_p,
                    "persons_candidate": new_p,
                    "place_candidate": (pl if pl and not place_hit else None),
                    "place_registry": place_hit,
                },
                "identity": {
                    "matches_gold_event": idn,
                    "verdict": "同一(粗比)" if idn else "新事件(候选)",
                },
                "is_gold": False,
            }
        )
    summary = {
        "n_sampled": len(sample),
        "n_valid_json": valid,
        "type_in_enum": f"{type_ok}/{valid}",
        "person_resolve_rate": f"{pn_hit}/{pn_tot}"
        + (f" ({100 * pn_hit // pn_tot}%)" if pn_tot else ""),
        "new_person_candidates": sum(
            len(c["registry_resolution"]["persons_candidate"]) for c in out_cands
        ),
        "identity_matched_gold": sum(1 for c in out_cands if c["identity"]["matches_gold_event"]),
    }
    print(
        json.dumps(
            {
                "batch": "W-H1a-3 左传晋系首批抽取（P1 出口件·候选非gold）",
                "model": MODEL,
                "date_policy": "不产出(D-028)",
                "is_gold": False,
                "eval_metrics_note": "held-out=全文左传晋系段, gold结构不入prompt",
                "summary": summary,
                "candidates": out_cands,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
