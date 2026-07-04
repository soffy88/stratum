"""B 方案:程序从原文抠数学 KU(0 LLM,忠实逐字,含证明).
规划=程序找行首 Definition/Theorem/Lemma/Proposition/Corollary/Example 标记;
内容=从标记切到下一个行首标记(该条陈述+证明,原文逐字);去引用重复、清页码/节眉。
用法: python scripts/math_program_extract.py <源MD路径> [--max N]
"""

import re
import sys
from collections import Counter
from pathlib import Path

MD = (
    sys.argv[1]
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--")
    else "/home/soffy/books/MD/英文数学/An_Introduction_to_Mathematical_Analysis_01KVAJVD.md"
)
MAXN = int(sys.argv[sys.argv.index("--max") + 1]) if "--max" in sys.argv else 0

# ★只认"行首"标记(真新条目);行中的 "by Theorem 1.3.1" 是引用,不切
MARK = re.compile(
    r"(?m)^\s{0,3}(?:#{1,4}\s*)?(?:\*\*)?\s*(Definition|Theorem|Lemma|Proposition|Corollary|Example)\s+(\d+(?:\.\d+)*)"
)
_TYPE_ZH = {
    "Definition": "定义",
    "Theorem": "定理",
    "Lemma": "引理",
    "Proposition": "命题",
    "Corollary": "推论",
    "Example": "例子",
}
MAX_LEN = 8000  # 单条封顶(含证明);标记稀疏时防跨整节


def _clean(s):
    """忠实清洗:去页码行/空标题/节眉,压空行。不改内容文字。"""
    out = []
    for ln in s.split("\n"):
        t = ln.strip()
        if re.fullmatch(r"\d{1,4}", t):  # 独立页码
            continue
        if re.fullmatch(r"#{1,4}\s*\d*", t):  # 空 markdown 标题 "## 1"
            continue
        if re.fullmatch(
            r"\d+\.\d+\.?\s+[A-Z][A-Z ,\'-]{2,}", t
        ):  # 节眉 "1.3. PROOFS, A FIRST LOOK"
            continue
        out.append(ln)
    return re.sub(r"\n{2,}", "\n", "\n".join(out)).strip()


def extract(md_text):
    marks = list(MARK.finditer(md_text))
    kus = []
    seen = set()
    for i, m in enumerate(marks):
        typ, num = m.group(1), m.group(2)
        label = f"{typ} {num}"
        if label in seen:  # ★去引用重复:同编号只留首次(真陈述+证明)
            continue
        seen.add(label)
        start = m.start(1)
        end = marks[i + 1].start(1) if i + 1 < len(marks) else len(md_text)
        end = min(end, start + MAX_LEN)  # 证明全收,仅超长兜底
        content = _clean(md_text[start:end])
        if len(content) < 15:
            continue
        kus.append(
            {
                "type": _TYPE_ZH.get(typ, typ),
                "label": label,
                "content": content,
                "len": len(content),
                "has_formula": bool(re.search(r"[∀∃∈≤≥⇒→∑∏∫√≠≈∞]|\\[a-zA-Z]+|\$", content)),
                "has_proof": bool(re.search(r"\bPROOF\b|证明", content)),
            }
        )
    return kus


text = Path(MD).read_text(encoding="utf-8", errors="replace")
kus = extract(text)
if MAXN:
    kus = kus[:MAXN]

c = Counter(k["type"] for k in kus)
wf = sum(1 for k in kus if k["has_formula"])
wp = sum(1 for k in kus if k["has_proof"])
avg = sum(k["len"] for k in kus) // max(len(kus), 1)
print(f"源: {Path(MD).name}")
print(
    f"程序抠出 KU: {len(kus)} 条 | 类型 {dict(c)} | 含公式 {wf} | 含证明 {wp} | 均长 {avg}字 | LLM 0"
)
print("=" * 74)
# 挑几个有证明的定理展示(证明进 KU 的效果)
show = [k for k in kus if k["has_proof"]][:3] + [k for k in kus if k["type"] == "定义"][:2]
for k in show:
    print(
        f"\n【{k['label']}】({k['type']}, {k['len']}字, {'含证明' if k['has_proof'] else '无证明'})"
    )
    print("  " + k["content"][:520].replace("\n", "\n  "))
