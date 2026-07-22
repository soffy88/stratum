#!/usr/bin/env python3
"""§4.4 抽取器选型 held-out 评测（本地 ollama 候选，D-026 禁云端）。

防污染：prompt 只给**史料白文**（语料库原文），**不含 gold 事件结构/判定**。
评分：抽取字段 vs gold 字段（人工钉的 held-out 答案，见 GOLD_KEYS）字段级命中。
输出：定型报告表（含落选者数据）。

用法：python3 tools/history/eval_extractor.py [--models m1,m2] [--report path]
需 ollama 在 :11434。
"""

import json
import subprocess
import sys

OLLAMA = "http://localhost:11434/api/generate"
MODELS = ["qwen3-8b", "qwen2.5vl:7b"]

PROMPT = (
    "/no_think 你是文言史料结构化抽取器。从下面这段史料抽取, 只输出 JSON, 不要解释。"
    '字段: {"title":事件名, "date":时间(有干support则给,如"前403"), '
    '"persons":[主要人物], "place":地点或null, '
    '"event_type":一个值∈["战役","政变","会盟","册命","迁都","变法","灾异","制度","人事","其他"]}。'
    "\n史料: 「%s」"
)

# held-out 评分键（人工钉·gold 侧不入 prompt）：passage 文言 + 期望字段
CASES = [
    {
        "id": "左传哀14/F10",
        "text": "甲午，齊陳恆弒其君壬于舒州。",
        "gold": {
            "persons_any": ["陈恒", "田常", "壬", "简公", "齐简公"],
            "place": ["舒州"],
            "type": ["政变", "人事"],
            "title_kw": ["弑", "陈恒", "田常"],
            "date_trap": "甲午为日干支非年",
        },
    },
    {
        "id": "通鉴命侯/F24",
        "text": "初命晉大夫魏斯、趙籍、韓虔為諸侯。",
        "gold": {
            "persons_any": ["魏斯", "赵籍", "韩虔"],
            "place": None,
            "type": ["册命"],
            "title_kw": ["命", "诸侯", "侯"],
            "date_trap": None,
        },
    },
    {
        "id": "左传哀9/F20",
        "text": "秋，吳城邗，溝通江、淮。",
        "gold": {
            "persons_any": ["吴", "夫差"],
            "place": ["邗"],
            "type": ["制度", "其他", "迁都"],
            "title_kw": ["邗", "城", "沟"],
            "date_trap": None,
        },
    },
    {
        "id": "史记晋世家/F25",
        "text": "六卿彊，公室卑。",
        "gold": {
            "persons_any": [],
            "place": None,
            "type": ["制度", "人事", "其他"],
            "title_kw": ["六卿", "公室"],
            "date_trap": None,
        },
    },
    {
        "id": "战国策魏一/F22",
        "text": "知伯索地於魏桓子，魏桓子弗予。任章曰：君不如與之，以驕知伯。",
        "gold": {
            "persons_any": ["知伯", "智伯", "魏桓子", "任章"],
            "place": None,
            "type": ["人事", "其他", "会盟"],
            "title_kw": ["索地", "知伯", "智伯"],
            "date_trap": None,
        },
    },
]

CASES += [
    {"id": "左传桓2/师服", "text": "今晉，甸侯也，而建國，本既弱矣，其能久乎？",
     "gold": {"persons_any": ["师服", "晋"], "place": None, "type": ["其他", "人事"],
              "title_kw": ["晋", "建国", "本弱"], "date_trap": None}},
    {"id": "左传昭3/叔向", "text": "晉之公族盡矣。欒、郤、胥、原、狐、續、慶、伯，降在皁隸，政在家門，民無所依。",
     "gold": {"persons_any": ["叔向", "晋", "栾", "郤"], "place": None, "type": ["其他", "人事", "制度"],
              "title_kw": ["公族", "晋", "政"], "date_trap": None}},
    {"id": "左传昭32/史墨", "text": "社稷無常奉，君臣無常位，自古以然。三后之姓於今為庶。",
     "gold": {"persons_any": ["史墨", "蔡墨"], "place": None, "type": ["其他", "人事"],
              "title_kw": ["社稷", "君臣", "无常"], "date_trap": None}},
    {"id": "史记项羽/鸿门", "text": "項莊拔劍起舞，項伯亦拔劍起舞，常以身翼蔽沛公，莊不得擊。",
     "gold": {"persons_any": ["项庄", "项伯", "沛公", "刘邦"], "place": None, "type": ["政变", "其他", "人事"],
              "title_kw": ["舞", "剑", "项"], "date_trap": None}},
    {"id": "国语晋9/智果", "text": "智宣子將以瑤為後，智果曰：不如宵也。若果立瑤也，智宗必滅。",
     "gold": {"persons_any": ["智宣子", "智果", "瑶", "宵"], "place": None, "type": ["人事", "其他"],
              "title_kw": ["立", "后", "智"], "date_trap": None}},
    {"id": "通鉴/围晋阳", "text": "三家以國人圍而灌之。智伯行水，魏桓子御，韓康子驂乘。",
     "gold": {"persons_any": ["智伯", "魏桓子", "韩康子"], "place": None, "type": ["战役", "其他"],
              "title_kw": ["围", "灌", "晋阳"], "date_trap": None}},
    {"id": "三国志/空城", "text": "亮意氣自若，敕軍中皆臥旗息鼓，又令大開四城門，埽地卻灑。宣王疑其有伏兵，於是引軍北趣山。",
     "gold": {"persons_any": ["亮", "诸葛亮", "宣王", "司马懿"], "place": None, "type": ["战役", "其他"],
              "title_kw": ["城", "空城", "退兵", "亮"], "date_trap": None}},
]


def run(model, text):
    payload = json.dumps(
        {"model": model, "prompt": PROMPT % text, "stream": False, "options": {"temperature": 0}}
    )
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "120", OLLAMA, "-d", payload],
            capture_output=True,
            text=True,
            timeout=130,
        ).stdout
        resp = json.loads(out).get("response", "")
    except Exception as e:
        return None, f"ERR:{e}"
    m = resp
    # 抽 JSON
    import re

    jm = re.search(r"\{.*\}", resp, re.S)
    if not jm:
        return None, resp[:120]
    try:
        return json.loads(jm.group(0)), resp[:120]
    except Exception:
        return None, resp[:120]


def score(ext, gold):
    if not ext:
        return {"person": 0, "place": 0, "type": 0, "title": 0, "date_ok": None}
    s = {}
    persons = "".join(str(x) for x in (ext.get("persons") or []))
    s["person"] = (
        1 if (not gold["persons_any"] or any(p in persons for p in gold["persons_any"])) else 0
    )
    pl = str(ext.get("place") or "")
    s["place"] = 1 if (gold["place"] is None or any(p in pl for p in gold["place"])) else 0
    s["type"] = 1 if str(ext.get("event_type")) in gold["type"] else 0
    title = str(ext.get("title") or "")
    s["title"] = 1 if any(k in title for k in gold["title_kw"]) else 0
    if gold["date_trap"]:
        d = str(ext.get("date") or "")
        s["date_ok"] = 0 if ("甲午" in d and "年" in d) or d == "甲午年" else 1
    else:
        s["date_ok"] = None
    return s


def main():
    models = MODELS
    for a in sys.argv:
        if a.startswith("--models"):
            models = sys.argv[sys.argv.index(a) + 1].split(",")
    results = {}
    for model in models:
        rows = []
        for c in CASES:
            ext, raw = run(model, c["text"])
            sc = score(ext, c["gold"])
            rows.append({"case": c["id"], "score": sc, "ext": ext, "raw": raw})
            print(f"[{model}] {c['id']}: {sc} | ext={ext}")
        results[model] = rows
    # 汇总
    print("\n=== 汇总（字段命中率）===")
    for model, rows in results.items():
        tot = {"person": 0, "place": 0, "type": 0, "title": 0}
        n = len(rows)
        dtrap_ok = dtrap_n = 0
        for r in rows:
            for k in tot:
                tot[k] += r["score"][k]
            if r["score"]["date_ok"] is not None:
                dtrap_n += 1
                dtrap_ok += r["score"]["date_ok"]
        avg = sum(tot.values()) / (4 * n)
        print(
            f"{model}: title {tot['title']}/{n} person {tot['person']}/{n} "
            f"place {tot['place']}/{n} type {tot['type']}/{n} | 字段均 {avg:.2f} | "
            f"日期陷阱 {dtrap_ok}/{dtrap_n}"
        )
    return results


if __name__ == "__main__":
    main()
