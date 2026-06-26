"""KU 呈现清洗(机械, 不改知识): 去脚手架结构标签/元标记/markdown 标记/正文来源标注/(未涉及)面.
来源命门: [Ch...] 标注从正文剥离 → 收集到 citations(存 provenance.citations), 底层保留可溯源.
clean(text) -> (clean_text, citations:list[str]); is_empty_shell(clean_text) -> bool.
"""
from __future__ import annotations
import re

# 脚手架 header 关键词(整行 #/##/### 标题且文本是纯结构 → 删整行)
_SCAFFOLD = (r"knowledge unit|综合阐述|知识单元|english|中文|"
             r"what|why|how|when|implication|meaning|essence|boundary|use|rationale|evidence|mechanism|"
             r"是什么|为什么|如何应用|如何|何时|推论|含义|内涵|外延|用处|用途|本质|边界|机制|"
             r"为何成立|为何正确|为何重要|原理依据|理由|证据|应用方式|定义")
_HDR = re.compile(rf"^\s*#{{1,6}}\s*\**\s*(?:{_SCAFFOLD})\b[^\n]*$", re.I)
# 行/条目开头的脚手架面标签: "- **Essence**:" "**内涵**：" "**WHAT (内涵...)**:" → 剥标签留内容
_LABEL = re.compile(rf"^\s*[-*]?\s*\**\s*(?:{_SCAFFOLD})\b[^:：\n]{{0,28}}\**\s*[:：]\s*", re.I)
# 正文来源标注 [Ch3, ...] / [Ch9: "..."] / 【Ch3，第3.2节】(可含引文)
_CITE = re.compile(r"\s*[\[【]\s*Ch\s*\d+[^\]】]*[\]】]")
# 非覆盖语句(标记 + 解释"书没讲"的整句)→ 删: 既删"(not covered)"标记, 也删"第N章未定义X…"解释句
_NONCOV = re.compile(
    r"(未涉及|未提及|未定义|未讨论|未阐述|未提供|未明确|未被提及|未解释|未具体|未单独|不涉及|"
    r"没有(?:讨论|涉及|定义|提及|阐述)|not covered|does not (?:define|discuss|mention|provide|cover|"
    r"address|elaborate|specify|explicitly)|is not (?:covered|discussed|defined|mentioned|addressed))", re.I)


def clean(text: str) -> tuple[str, list[str]]:
    if not text:
        return "", []
    cites: list[str] = []
    # 收集并剥离来源标注
    for m in _CITE.finditer(text):
        cites.append(m.group(0).strip())
    text = _CITE.sub("", text)
    out = []
    for line in text.split("\n"):
        if _HDR.match(line):                      # 脚手架标题整行删
            continue
        line = _LABEL.sub("", line)               # 剥面标签留内容
        line = re.sub(r"^\s*[-*]\s+", "", line)   # 去开头无序列表符
        line = line.replace("**", "").replace("__", "")  # 去 markdown 粗体标记
        line = re.sub(r"^\s*#{1,6}\s*", "", line)  # 去残留 # 标题符
        line = re.sub(r"[ \t]+", " ", line).rstrip()
        out.append(line)
    txt = "\n".join(out)
    # 句级删非覆盖语句(标记 + "书没讲X"解释句): 按句/行切, 含非覆盖语的句丢弃
    kept = []
    for seg in re.split(r"(?<=[。！？\n])", txt):
        s = seg.strip()
        if s and not _NONCOV.search(s):
            kept.append(seg)
    txt = "".join(kept)
    txt = re.sub(r"[ \t]*\n[ \t]*", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt).strip()
    return txt, cites


# 实质内容判据: 去掉空白/标点/数字编号后还剩中文或英文字母 ≥ 一定量
_SUBSTANCE = re.compile(r"[一-鿿A-Za-z]")


def is_empty_shell(clean_text: str) -> bool:
    """清洗后无实质内容(全是 未涉及 被删空, 或仅剩编号/标点)→ 空壳."""
    core = re.sub(r"[\s\d.、，,。;:：；()（）\-—…•]", "", clean_text)
    return len(_SUBSTANCE.findall(core)) < 8
