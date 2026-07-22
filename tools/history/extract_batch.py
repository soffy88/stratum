#!/usr/bin/env python3
"""§4.5 半自动抽取批（抽检包生成器）· D-026 本地 qwen2.5vl:7b。

在语料库白文上跑抽取器 → 候选事件（date 留空，交注册表解析）→ 注册表解析核（persons/places
命中率）→ 输出抽检包 JSON。**全部候选标 is_gold=false**（§4.4 红线：抽取候选永不直接成 gold）。
date 不产出（§4.4 发现：抽取器 date 全废，走 chronology 注册表）。

用法：python3 tools/history/extract_batch.py > docs/history/extract/W-H1a-1-candidates.json
"""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"
OLLAMA = "http://localhost:11434/api/generate"
MODEL = "qwen2.5vl:7b"
PROMPT = (
    "你是文言史料结构化抽取器。从史料抽取, 只输出 JSON 不解释。"
    '字段 {"title":事件名,"persons":[人物],"place":地点或null,'
    '"event_type":∈["战役","政变","会盟","册命","迁都","变法","灾异","制度","人事","其他"]}。'
    "不要输出年份。史料:「%s」"
)


def registry_ids():
    names = {}
    for nm, key, field in [
        ("persons", "person_id", "names_by_source"),
        ("places", "place_id", "name_by_era"),
    ]:
        data = json.loads((ROOT / "seeds" / f"{nm}.json").read_text(encoding="utf-8"))
        for e in data[nm] if isinstance(data, dict) else data:
            label = "".join(list(e.get(field, {}).keys()))
            names[e[key]] = label
    return names


def run(text):
    payload = json.dumps(
        {"model": MODEL, "prompt": PROMPT % text, "stream": False, "options": {"temperature": 0}}
    )
    out = subprocess.run(
        ["curl", "-s", "--max-time", "120", OLLAMA, "-d", payload],
        capture_output=True,
        text=True,
        timeout=130,
    ).stdout
    resp = json.loads(out).get("response", "")
    jm = re.search(r"\{.*\}", resp, re.S)
    return json.loads(jm.group(0)) if jm else None


def main():
    reg = registry_ids()
    cands = []
    for cf in sorted((ROOT / "corpus").glob("*.json")):
        doc = json.loads(cf.read_text(encoding="utf-8"))
        for p in doc["paragraphs"]:
            ext = run(p["text"])
            if not ext:
                continue
            # 注册表解析核：抽取 person 名是否命中注册表某 person 的 names
            persons = [str(x) for x in (ext.get("persons") or [])]
            resolved = []
            for pn in persons:
                hit = next(
                    (
                        pid
                        for pid, lbl in reg.items()
                        if pid.startswith("per:") and pn and (pn in lbl or lbl in pn)
                    ),
                    None,
                )
                resolved.append({"name": pn, "registry": hit})
            cands.append(
                {
                    "source_para_ulid": p["para_ulid"],
                    "source_chapter": doc["substrate"]["book"] + "·" + p["chapter"],
                    "extracted": ext,
                    "registry_resolution": resolved,
                    "is_gold": False,
                    "note": "抽取候选（半自动·qwen2.5vl:7b）·非 gold·date 留注册表·顾问审重待",
                }
            )
    n_person = sum(len(c["registry_resolution"]) for c in cands)
    n_hit = sum(1 for c in cands for r in c["registry_resolution"] if r["registry"])
    print(
        json.dumps(
            {
                "batch": "W-H1a-1 半自动抽取抽检包",
                "model": MODEL,
                "is_gold": False,
                "date_policy": "不产出, 走 chronology 注册表(§4.4发现)",
                "candidates": cands,
                "summary": {
                    "n_candidates": len(cands),
                    "person_resolve_hit": f"{n_hit}/{n_person}",
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
