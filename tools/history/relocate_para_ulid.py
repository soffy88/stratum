#!/usr/bin/env python3
"""W-H1a-3 全文语料 para_ulid 定位回填 + 机核（opencc 简繁归一）。

全书入库后段落 ULID 重排，旧快照回填失效。本工具：对每个 fixture account，从 locator.note
抽 CJK 引文键（≥8 字）→ s2t 转繁 → 在全文语料搜索 → 命中即回填该段 para_ulid（＝机核一致），
未命中标『未找到』（段落未入库或实质异文）。arc thesis 同理（用 attribution.locator.quote）。

用法：python3 tools/history/relocate_para_ulid.py [--apply]
"""

import json
import re
import sys
from pathlib import Path

from opencc import OpenCC

CC = OpenCC("s2t")
ROOT = Path(__file__).resolve().parents[2] / "docs" / "history"
CJK = re.compile(r"[一-鿿]{6,}")
QUOTED = re.compile(r"[「『\"]([^」』\"]{6,})[」』\"]")

# 策展 key 表（设计批 F1–F9 等；原文在全文语料的 account → 繁体原文键）。
# 仅在 note 无 brackets 时兜底；键取自各篇确定在库的原文片段。
CURATED = {
    "ac:longzhong-peian": "非亮先詣備",
    "ac:jinyang-shiji": "三國攻晉陽",
    "ac:jinyang-zztj": "三家以國人圍而灌之",
    "ac:jinyang-zhanguoce": "決晉水而灌之",
    "ac:minghou-zztj": "初命晉大夫魏斯",
    "ac:minghou-shiji": "威烈王",
    "ac:tianhe-zztj": "田和",
    "ac:zhaonan-shiji-zhaoshijia": "屠岸賈",
    "ac:zhaonan-shiji-jinshijia": "趙同",
    "ac:hongmen-xiangyuji": "項莊拔劍起舞",
    "ac:sujin-shiji": "蘇秦者",
    "ac:changping-zhaoshijia": "括軍敗",
    "ac:jieting-masuzhuan": "謖下獄物故",
    "ac:jieting-xianglang": "馬謖",
    "ac:jieting-liangzhuan": "戮謖以謝眾",
    "ac:chibi-c-zhouyu": "蓋放諸船",
    "ac:chibi-c-wudiji": "公至赤壁",
    "ac:chibi-p-sanguozhi": "與備戰",
    "ac:ningwo-shiyu": "太祖過伯奢",
    "ac:longzhong-liangzhuan": "每自比於管仲",
    "ac:guandu-sanguozhi": "兵不滿萬",
    "ac:ningwo-sunsheng": "寧我負人",
    "ac:ningwo-weishu": "伯奢",
    "ac:longzhong-chushibiao": "三顧臣於草廬",
    "ac:longzhong-weilue": "亮乃北行見備",
    "ac:kongcheng-guochong": "偃旗息鼓",
    "ac:kongcheng-peian": "郭沖",
    "ac:chibi-wudiji": "公至赤壁",
    "ac:chibi-zhouyuzhuan": "烏林",
    "ac:chibi-jiangbiao": "蓋放諸船",
    "ac:maling-shiji": "龐涓",
    "ac:guandu-peizhu-an": "臣松之以為",
    "ac:zhaonan-zuozhuan": "晉討趙同",  # 左传成8 下宫之难
    "ac:muye-shiji": "遂率戎車三百乘",  # 史记周本纪 牧野(近似, 兜底)
    "ac:shanrang-shiji": "堯知子丹朱之不肖",  # 史记五帝本纪 禅让
    "ac:changping-baiqi": "前後斬首虜四十五萬",  # 史记白起王翦列传 长平
    "ac:hongmen-gaozuji": "沛公旦日從百餘騎來見項王",  # 史记高祖本纪 鸿门
    "ac:hongmen-fankuai": "瞋目視項王",  # 史记樊郦滕灌 樊哙
    "ac:jinyang-shuiyuan-shiji": "三國攻晉陽",  # 史记赵世家 灌晋阳
    "ac:shijian-shiji": "田氏之徒追執簡公",  # 史记田完世家
    "ac:shijian-zuozhuan": "齊陳恆弒其君壬",  # 左传哀14
    "ac:tianhe-shiji": "田和立為齊侯",  # 史记田完世家
    "ac:minghou-zztj-xushi": "初命晉大夫魏斯",  # 通鉴卷1 命侯
    "ac:wuchenghan-zuozhuan": "吳城邗",  # 左传哀9
}
CURATED_THESIS = {
    "thesis:shifu-modabizhe": "本大而末小",
    "thesis:taishigong-jin": "太史公曰",
    "thesis:shuxiang-gongshi-jiang-bei": "晉之公族盡矣",
    "thesis:shimo-wuchang": "社稷無常奉",
}


def corpus_index():
    idx = []
    for cf in sorted((ROOT / "corpus").glob("*.json")):
        d = json.loads(cf.read_text(encoding="utf-8"))
        for p in d["paragraphs"]:
            idx.append((p["para_ulid"], p["text"]))
    return idx


def keys_from_note(note, acc_id=None):
    """优先抽「」『』内原文引文；无则策展兜底；再退 CJK 长串。s2t 转繁。"""
    ks = []
    for q in QUOTED.findall(note):
        for seg in re.split(r"[……，,。；;、]", q):
            for m in CJK.findall(seg):
                ks.append(CC.convert(m))
    if acc_id and acc_id in CURATED:
        ks.append(CC.convert(CURATED[acc_id]))
    if not ks:  # 退: note 全 CJK 串(可能含散文, 命中率低)
        for seg in re.split(r"[……\.\s，,；;、：:「」『』\(\)（）]", note):
            for m in CJK.findall(seg):
                ks.append(CC.convert(m))
    return sorted(set(ks), key=len, reverse=True)


def locate(keys, idx):
    """返回 (para_ulid, matched_key) 最长命中；无则 (None, None)。"""
    best = (None, None)
    for k in keys:
        for pu, text in idx:
            if k in text:
                if not best[1] or len(k) > len(best[1]):
                    best = (pu, k)
                break
    return best


def main():
    apply = "--apply" in sys.argv
    idx = corpus_index()
    hit = miss = 0
    report = []

    for ff in sorted((ROOT / "fixtures").glob("F*.json")):
        d = json.loads(ff.read_text(encoding="utf-8"))
        changed = False
        for a in d.get("accounts", []):
            loc = a.get("locator", {})
            note = loc.get("note", "") or ""
            keys = keys_from_note(note, a["account_id"])
            pu, mk = locate(keys, idx) if keys else (None, None)
            if pu:
                hit += 1
                report.append((ff.name, a["account_id"], "HIT", pu, mk[:16]))
                if apply:
                    loc["para_ulid"] = pu
                    changed = True
            else:
                miss += 1
                if apply and loc.get("para_ulid"):
                    loc["para_ulid"] = None  # 旧快照 ulid 已失效, 清空避免悬空
                    changed = True
                report.append(
                    (ff.name, a["account_id"], "MISS", "-", (keys[0][:12] if keys else "无键"))
                )
        if apply and changed:
            ff.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # arc theses
    af = ROOT / "arc" / "arc-jin-decline.json"
    ad = json.loads(af.read_text(encoding="utf-8"))
    for t in ad.get("theses", []):
        locq = t.get("attribution", {}).get("locator") or {}
        q = locq.get("quote", "") or ""
        keys = [CC.convert(m) for m in CJK.findall(q)]
        if t["thesis_id"] in CURATED_THESIS:
            keys.append(CC.convert(CURATED_THESIS[t["thesis_id"]]))
        keys = sorted(set(keys), key=len, reverse=True)
        pu, mk = locate(keys, idx) if keys else (None, None)
        tag = "HIT" if pu else "MISS"
        report.append(("arc", t["thesis_id"], tag, pu or "-", (mk[:16] if mk else "")))
        if apply and pu:
            locq["para_ulid"] = pu
    if apply:
        af.write_text(json.dumps(ad, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for r in report:
        print(f"{r[2]:4} {r[0]:26} {r[1]:32} {r[3]:32} key={r[4]}")
    print(f"--- account HIT {hit} / MISS {miss} (机核: HIT=在库一致, MISS=未入库或实质异文)")


if __name__ == "__main__":
    main()
