"""B 接入版:程序抠数学 KU + 轻 LLM 命名 → 输出 math_ingest 可用的 staging.
- 规划+内容:程序(0 LLM)——行首标记切"陈述+证明",忠实逐字。
- 命名:每章 1 次 LLM 批量给概念名(唯一的 LLM 用途,~1call/章)。
- 输出:staging <dir>/ch{N}.json,字段对齐 math_ingest(point/label/type/zh/en/chapter)。
用法: python scripts/math_program_ingest.py <源MD> <substrate_id> [--only-chapter N] [--staging DIR]
之后: python scripts/math_ingest.py --substrate <substrate_id> --staging DIR
"""

import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

MD = sys.argv[1]
SUBSTRATE = sys.argv[2]
ONLY = int(sys.argv[sys.argv.index("--only-chapter") + 1]) if "--only-chapter" in sys.argv else 0
STAGING = (
    Path(sys.argv[sys.argv.index("--staging") + 1])
    if "--staging" in sys.argv
    else Path(f"scripts/_staging/math_prog/{SUBSTRATE}")
)

MARK = re.compile(
    r"(?m)^\s{0,3}(?:#{1,4}\s*)?(?:\*\*)?\s*"
    r"(Definition|Theorem|Lemma|Proposition|Corollary|Example|定义|定理|引理|推论|命题|例题|例)"
    r"\s*(\d+(?:\.\d+)*)"
)
_TYPE_ZH = {
    "Definition": "定义",
    "Theorem": "定理",
    "Lemma": "引理",
    "Proposition": "命题",
    "Corollary": "推论",
    "Example": "例子",
}
MAX_LEN = 8000
_KEY = os.getenv("NVIDIA_NIM_API_KEY", "")
_MODEL = os.getenv("NIM_MODEL", "meta/llama-3.1-70b-instruct")


def _clean(s):
    out = []
    for ln in s.split("\n"):
        t = ln.strip()
        if re.fullmatch(r"\d{1,4}", t) or re.fullmatch(r"#{1,4}\s*\d*", t):
            continue
        if re.fullmatch(r"(CHAPTER \d+\.?.*|\d+\.\d+\.?\s+[A-Z][A-Z ,\'-]{2,})", t):
            continue
        if re.fullmatch(r"[*_\s]+", t):  # 只剩 **/*/_ 的残留行
            continue
        if re.fullmatch(
            r"#{1,4}\s+\*{0,2}[A-Za-z][^\n]{0,45}", t
        ):  # markdown 页眉/小标题(EXAMPLE 2.16…)
            continue
        out.append(ln)
    txt = re.sub(r"\n{2,}", "\n", "\n".join(out)).strip()
    return txt.replace("**", "").strip()  # 去 markdown 粗体残留(数学用 $/LaTeX 不用 **)


def split_chapters(text):
    """按 'Chapter N' 行首切章;返回 {n: chapter_text}."""
    marks = [
        (int(m.group(1)), m.start())
        for m in re.finditer(r"(?m)^\s*(?:#+\s*)?Chapter\s+(\d+)\b", text)
    ]
    chapters = {}
    for i, (n, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        if n not in chapters:
            chapters[n] = text[pos:end]
    return chapters


def extract_chapter(ch_text, chapter_n):
    marks = list(MARK.finditer(ch_text))
    kus, seen = [], set()
    for i, m in enumerate(marks):
        typ, num = m.group(1), m.group(2)
        label = f"{typ} {num}"
        if label in seen:
            continue
        seen.add(label)
        start = m.start(1)
        end = min(marks[i + 1].start(1) if i + 1 < len(marks) else len(ch_text), start + MAX_LEN)
        content = _clean(ch_text[start:end])
        if len(content) < 15:
            continue
        kus.append(
            {
                "type": _TYPE_ZH.get(typ, typ),
                "label": label,
                "point": label,
                "en": content,
                "zh": "",
                "chapter": chapter_n,
                "key_terms": [],
            }
        )
    return kus


# 名字合法性:首字母大写(或多词)+ 只字母/空格/常见标点,≥3字(排除公式括号如 (A∨B))
_NAME_OK = re.compile(r"^[A-Za-z][A-Za-z ,.\-'’&]+$")


def _is_name(s):
    s = s.strip()
    if len(s) < 3 or not _NAME_OK.match(s):
        return False
    return s[0].isupper() or " " in s


def name_kus(kus):
    """★程序命名(0 LLM,更忠实):抠书自带括号名(过滤公式括号)→ 无名用标记。
    实测优于 LLM 命名(LLM 95% 超时退化 + 有发挥/改错风险)。"""
    for k in kus:
        k["point"] = k["label"]  # 标记(Theorem X.Y)留 provenance
        m = re.match(
            r"^(?:Definition|Theorem|Lemma|Proposition|Corollary|Example)\s+[\d.]+\s*\(([^)]{2,45})\)",
            k["en"].strip(),
        )
        if m and _is_name(m.group(1)):
            k["label"] = m.group(1).strip()  # 书自带名: Urysohn / Metric Completion...
        # 否则 label 保持标记(书自己的编号,忠实)


def _headers(text):
    """章头(第N章 / Chapter N)与节头(N.N 标题)的位置, 供扁平编号书按位置定位.
    返回 (chaps=[(pos,章号)], secs=[(pos,'N.N')])."""
    chaps, secs = [], []
    for m in re.finditer(r"(?m)^\s*(?:#+\s*)?(?:Chapter\s+(\d+)|第\s*(\d+)\s*章)", text):
        chaps.append((m.start(), int(m.group(1) or m.group(2))))
    for m in re.finditer(r"(?m)^\s*(?:#+\s*)?(\d+\.\d+)\s+\S", text):
        secs.append((m.start(), m.group(1)))
    return chaps, secs


def _before(items, pos, default=None):
    r = default
    for p, v in items:
        if p <= pos:
            r = v
        else:
            break
    return r


def extract_all(text):
    """整本抽取, 跨标记切、证明全收。兼容两类编号:
    - 层级编号(Theorem 1.3.1, 含'.'): 章号取首位, 全局唯一→按 label 去重(正式书).
    - 扁平编号(例 1, 每节重置): 按'第N章'定章、label 冠以'N.N'节号→同章不同节的"例1"各成一KU
      且 ku_id(sub::章::point) 不撞. 这是中文本科教材(斯图/同济)的形态."""
    marks = list(MARK.finditer(text))
    chaps, secs = _headers(text)
    kus, seen = [], set()
    for i, m in enumerate(marks):
        typ, num = m.group(1), m.group(2)
        hierarchical = "." in num and num.split(".")[0].isdigit()
        if hierarchical:
            ch = int(num.split(".")[0])
            label = f"{typ} {num}"
        else:
            sec = _before(secs, m.start())
            if sec:
                label = f"{sec} {typ} {num}"
                ch = int(sec.split(".")[0])  # 章号取自节号首位, 与 label 一致
            else:
                label = f"{typ} {num}"
                ch = _before(chaps, m.start(), 0)  # 无节号时回退'第N章'位置
        if label in seen:
            continue
        seen.add(label)
        start = m.start(1)
        end = min(marks[i + 1].start(1) if i + 1 < len(marks) else len(text), start + MAX_LEN)
        content = _clean(text[start:end])
        # ★去掉标记本身后须有实质内容(丢 "Theorem 4.6" 这种空标记)
        body = re.sub(
            r"^\s*(?:Definition|Theorem|Lemma|Proposition|Corollary|Example|定义|定理|引理|推论|命题|例题|例)\s*[\d.]+\s*",
            "",
            content,
        )
        if len(body.strip()) < 10:
            continue
        kus.append(
            {
                "type": _TYPE_ZH.get(typ, typ),
                "label": label,
                "point": label,
                "en": content,
                "zh": "",
                "chapter": ch,
                "key_terms": [],
            }
        )
    return kus


from collections import defaultdict

text = Path(MD).read_text(encoding="utf-8", errors="replace")
by_ch = defaultdict(list)
for k in extract_all(text):
    by_ch[k["chapter"]].append(k)
STAGING.mkdir(parents=True, exist_ok=True)
total = 0
for n in sorted(by_ch):
    if ONLY and n != ONLY:
        continue
    kus = by_ch[n]
    name_kus(kus)
    time.sleep(1.8)  # NIM 限流
    (STAGING / f"ch{n}.json").write_text(
        json.dumps(kus, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    total += len(kus)
    print(
        f"  ch{n}: {len(kus)} KU → 命名样例: "
        + " / ".join(f"{k['label']}={k['point']}" for k in kus[:3])
    )
print(f"★ 完成: {total} KU → {STAGING}  (LLM 调用 = 章数)")
