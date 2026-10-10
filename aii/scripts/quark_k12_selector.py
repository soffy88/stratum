#!/usr/bin/env python3
"""从夸克目录快照中筛选 K12 教育类资源，生成迁移目标清单。

分级判定（命中任一即纳入）:
  - 强特征: 学段词(小学/初中/高中/中考/高考/小升初/幼小衔接/K12) 或 教辅词
  - 强特征: 学科词 + 教材类词(课本/教材/教科书/同步/练习/习题/试卷/真题)
  - 强特征: 学科词 + 年级/册次(如 "八年级下册" "3年级")

刻意排除古籍类(医书/农书/四库/易经/命理 等)与纯商业金融书,避免把
"经济数学""古代数学"类非 K12 内容误纳入。

输出: k12_targets.json
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIPE = ROOT / "quark_pipeline"
CATALOG = PIPE / "quark_catalog.json"
STATE = PIPE / "quark_transfer_2_4_state.json"
OUT = PIPE / "k12_targets.json"

# ── 强特征 A: 学段 / 教辅类型 ──
STAGE = r"(小学|初中|高中|中考|高考|小升初|幼小衔接|升学|K12|k12|初一|初二|初三|高一|高二|高三|六年级|七年级|八年级|九年级|一年级|二年级|三年级|四年级|五年级|一册|下册|上册)"
EXTRA = r"(课本|教材|教科书|教辅|同步|练习|习题|试卷|真题|模拟题|考点|讲义|试卷|复习|背诵|知识点|字帖|字帖|阅读|作文|词语|古诗|口算|竖式|应用题|奥数|思维训练|看图说话|单词|词汇|听力|试卷库|题库)"

# ── 强特征 B: 学科词 ──
SUBJECT = r"(语文|数学|英语|物理|化学|生物|政治|历史|地理|道德与法治|科学|美术|音乐|体育|信息技术|科学|品德)"

# ── 排除: 古籍 / 医农 / 商业金融 / 纯文学 ──
EXCLUDE = re.compile(
    r"(四库|易经|命理|风水|面相|黄历|本草|黄帝内经|伤寒|金匮|难经|神农|茶经|天工开物|农书|齐民要术|考工记|天工|营造法式|鲁班|算经|九章|周髀|勾股|方术|岐黄|中医|养生|丹方|炮制|"
    r"资治通鉴|二十四史|史记|汉书|后汉书|三国志|晋书|宋书|南齐书|魏书|北齐书|周书|隋书|南史|北史|旧唐书|新唐书|旧五代史|新五代史|宋史|辽史|金史|元史|明史|清史稿|"
    r"论语|孟子|大学|中庸|诗经|楚辞|礼记|春秋|左传|公羊传|谷梁传|孝经|尔雅|说文|释名|广雅|"
    r"经济学|经济数学|金融|证券|投资|股票|期货|基金|会计|审计|税务|货币银行|微观经济|宏观经济学|"
    r"编程|Python|Java|C\+\+|算法|数据结构|机器学习|深度学习|人工智能|数据库|SQL|Linux|Git|前端|后端|黑客|网络安全|"
    r"小说|散文|诗集|文集|全集|随笔|读后感)"
)

GRADE = re.compile(r"([1-6一二三四五六七八九十]{1,2})\s*年级")


def classify(name: str) -> tuple[bool, str]:
    """返回 (是否K12, 命中理由)"""
    if EXCLUDE.search(name):
        return False, ""
    has_stage = bool(re.search(STAGE, name))
    has_subject = bool(re.search(SUBJECT, name))
    has_extra = bool(re.search(EXTRA, name))
    has_grade = bool(GRADE.search(name))

    if has_stage and (has_subject or has_extra):
        return True, "学段+学科/教辅"
    if has_subject and has_extra:
        return True, "学科+教辅类型"
    if has_subject and has_grade:
        return True, "学科+年级"
    if has_subject and re.search(r"(人教|苏教|北师大|沪教|鲁教|湘教|青岛|冀教|教科|外研|译林|牛津|剑桥|部编|统编)", name):
        return True, "学科+教材版本"
    return False, ""


def main() -> None:
    files = json.loads(CATALOG.read_text(encoding="utf-8"))["files"]
    done: set[str] = set()
    if STATE.exists():
        s = json.loads(STATE.read_text(encoding="utf-8"))
        done = set(s.get("deleted_fids", [])) | set(s.get("source_gone_fids", []))

    targets, reasons = [], {}
    for f in files:
        if f["fid"] in done:
            continue
        ok, why = classify(f["file_name"])
        if ok:
            targets.append(f)
            reasons[why] = reasons.get(why, 0) + 1

    targets.sort(key=lambda x: -x.get("size", 0))
    OUT.write_text(json.dumps(targets, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(f["size"] for f in targets) / 1024**3
    print(f"剩余总量   : {len([f for f in files if f['fid'] not in done])} 个 / "
          f"{sum(f['size'] for f in files if f['fid'] not in done) / 1024**3:.1f} GB")
    print(f"K12 命中   : {len(targets)} 个 / {total:.1f} GB")
    print("\n命中理由分布:")
    for k, v in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"  {k:<16} {v}")
    print(f"\n已写入 {OUT}")


if __name__ == "__main__":
    main()
