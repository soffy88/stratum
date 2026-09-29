"""新范式防漏标准件: 确定性(不靠 LLM)识别章节"应有知识点清单"(小节标题 + 黑体定义术语),
对照抽出的 KU 清单查漏.

★新范式双命门: 不编(fabrication, 靠溯源校验) + 不漏(omission, 靠本校验).
★为何不靠 LLM: LLM 规划/合成会漏(输入截断 / lost-in-the-middle / 规划识别不全).
  本校验用书的【结构信号】兜底, 不依赖 LLM, 抓一切漏(不管什么原因).
★可靠性依赖 Stratum 交付 md 的结构质量(AII-STRATUM-MD-SPEC-001 R1-R5: 规范小节标题 # N.M /
  黑体定义术语 **TERM** 保留). md 烂(术语丢、标题乱)→ 应有清单也可能漏识别 → 见该规格.
★配套铁律: 喂规划/合成的章节文本【绝不截断】(截断=系统性漏知识); 章大 → 分块喂, 不丢内容.
"""

from __future__ import annotations

import re

# 教材结构信号(确定性):小节标题 ## **N.M Title** + 黑体定义术语 **CAPS TERM**(词汇表惯例)
_SECTION = re.compile(r"(?m)^##\s*\*\*\s*(\d+\.\d+)\s+([^*\n]+?)\s*\*?\*?\s*$")
_BOLD_TERM = re.compile(r"\*\*([A-Z][A-Z’'\- ]{3,45})\*\*")
_STOP = {
    "EXAMPLE",
    "FALSE",
    "TRUE",
    "CHAPTER",
    "FIGURE",
    "TABLE",
    "NOTE",
    "ECONOMIC FALLACY",
    "SOURCE",
    "PART",
    "EXAMPLES",
    # ★2026-09-27 教材版式/栏目名, 不是可讲授的概念, 不该进"应有知识点清单"。
    #   依据: 实际完整率报警统计(次数见括号), 这些词被当必漏术语反复误判:
    "TRY IT",                       # (20) 练习栏目标题
    "LEARNING OBJECTIVES",          # (18) 小节栏目
    "HOW TO",                       # (14) 操作指引
    "BE PREPARED",                  # (10) 栏目
    "COLLABORATIVE EXERCISE",       # (8)  栏目
    "UNIT",                         # (8)  单元标题
    "REFERENCES",                   # (6)  参考文献
    "STUDENT PROJECT",              # (6)  栏目
    "MEDIA",                        # (18) 媒体栏
    "KEY TERMS",                    # 术语表标题本身
    "GLOSSARY",
    "REVIEW",
    "SUMMARY",
    "OBJECTIVES",
    "CONTINUE",
    "ANSWER",
    "ANSWERS",
    "SOLUTION",
    "SOLUTIONS",
    "PROBLEMS",
    "EXERCISES",
    "PRACTICE",
    "HOMEWORK",
    "ACTIVITY",
    "ACTIVITIES",
    "CHECK YOUR UNDERSTANDING",
    "KEY IDEA",
    "BIG IDEA",
    "CTRL",                         # (6)  键盘按键, 出现在操作说明里
    "CTRL-C",
    "CTRL-C-X",
}

# ★2026-09-27 中文教材的跑页眉: 书名/科目名以拼音形式出现在每页页眉,
#   被 markitdown 转成 **YIWU JIAOYU JIAOKESHU** 这类黑体行, 于是"每章都漏"。
#   原有 _is_spaced_noise 只认 'C H A P T E R'(R9 记的间隔字母噪声), 认不出拼音。
#   依据实际报警统计: YIWU JIAOYU JIAOKESHU(14) / YUWEN(12) / W Q W(6) / K QK(6)。
_ZH_RUNNING_HEAD = re.compile(
    r"^(?:YIWU\s+JIAOYU\s+JIAOKESHU|YUWEN|SHUXUE|YINGYU\s*|"
    r"W\s+Q\s+W|K\s+QK(?:\s+JIE)?|D\s+DAO\s+DE\s+FA\s+ZHENG\s+FA)"
)


def _is_zh_running_head(t: str) -> bool:
    """中文教材跑页眉(拼音书名/科目名)不是知识术语."""
    return bool(_ZH_RUNNING_HEAD.match(re.sub(r"\s+", " ", (t or "").strip().upper())))


# ★2026-09-27 黑体标记只包住了同名重复词的前一半, 后一半裸露。PDF/markdown 抽取
#   时把同一术语连写两遍的排版很常见, 例如实测:
#       **GDDR** GDDR6 is used in the latest gaming graphics cards...
#       **SLIDE** is an extension to dropout
#   于是 _BOLD_TERM 抓到这个重复副本当"应有知识点", 而合成出的 KU 名只写一次,
#   字面匹配必然失败 → 每章假报漏。命中即判为排版噪声。
_ECHO_TAIL = re.compile(r"^[\s:：,，.\-–—]*" + r"(\S+)")


def _is_bold_echo(term: str, chapter_text: str, bold_end: int) -> bool:
    """黑体词后面紧跟着同一个词(裸露副本) → 排版重复, 不是术语定义."""
    t = term.strip()
    if not t or not t.isascii():
        return False
    m = _ECHO_TAIL.match(chapter_text[bold_end : bold_end + len(t) + 4])
    if not m:
        return False
    nxt = m.group(1).strip(".,;:")
    if not nxt or not nxt.isascii():
        return False
    a, b = t.lower(), nxt.lower()
    # 裸露副本完全相同, 或它以后缀方式继续这个词(GDDR → GDDR6)
    return b == a or b.startswith(a) and len(b) > len(a) and b[len(a)].isdigit()


# ★2026-09-27 缩写 ↔ 中文展开对照。check_completeness 的 covered() 走字面匹配,
#   所以章节黑体术语写 **LSTM**、而 KU 名写「长短期记忆」时会被判漏 —— 用反漏判据
#   去卡术语的两种写法, 属假阳性。只收有确定中文展开的常见缩写; 表里没有的缩写
#   行为不变(仍然严格), 避免把判据整体放松。
_ACRONYM_ZH: dict[str, str] = {
    "LSTM": "长短期记忆",
    "GRU": "门控循环",
    "RNN": "循环神经网络",
    "CNN": "卷积神经网络",
    "DNN": "深度神经网络",
    "GAN": "生成对抗网络",
    "DCGAN": "深度卷积生成对抗网络",
    "VAE": "变分自编码器",
    "AE": "自编码器",
    "NLP": "自然语言处理",
    "Nlp": "自然语言处理",
    "SGD": "随机梯度下降",
    "RELU": "修正线性单元",
    "RNNs": "循环神经网络",
    "LSTMs": "长短期记忆",
    "GRUs": "门控循环",
    "CNNs": "卷积神经网络",
    "MLP": "多层感知机",
    "BERT": "双向编码器",
    "TF-IDF": "逆文档频率",
    "SVM": "支持向量机",
    "PCA": "主成分分析",
    "LDA": "线性判别分析",
    "EM": "期望最大化",
    "MAP": "最大后验",
    "MLE": "极大似然估计",
    "GDP": "国内生产总值",
    "CPI": "消费者价格指数",
    "GDPs": "国内生产总值",
    "AD": "自动微分",
    "GNN": "图神经网络",
    "RL": "强化学习",
    "MDP": "马尔可夫决策过程",
}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower()).rstrip("s")


def _is_spaced_noise(t: str) -> bool:
    """剔除跑页眉间隔字母噪声 'C H A P T E R'(R9): 单字符 token 占多数."""
    toks = t.split()
    return len(toks) >= 4 and sum(1 for x in toks if len(x) == 1) >= len(toks) - 1


# 中文数学教材结构信号: 第N节 标题 + 定义N/定理N(替代 **TERM**)
_ZH_SECTION = re.compile(r"(?m)^第[一二三四五六七八九十]+节\s+([^\n…]{1,28})")
_MATH_SIGNAL = re.compile(r"定义\s*\d|定理\s*\d")
_ZH_SPLIT = re.compile(r"[与和、，及的]")


def _zh_math_should_have(chapter_text: str) -> dict:
    """数学模式: 第N节 标题=知识区(跳页眉重复取首现). 每节标题作 should-have."""
    secs, seen = [], set()
    for m in _ZH_SECTION.finditer(chapter_text):
        t = m.group(1).strip()
        if "…" in t or re.search(r"\d\s*$", t) or t in seen:
            continue
        seen.add(t)
        secs.append(t)
    return {
        "sections": [{"num": str(i + 1), "title": t, "terms": [t]} for i, t in enumerate(secs)],
        "bold_terms": secs,
    }


def identify_should_have(chapter_text: str) -> dict:
    """确定性识别章节应有知识点: 黑体定义术语(权威)+ 小节(各挂其内黑体术语). 不调 LLM.
    ★数学书无 **TERM** 但有 定义N/定理N → 转数学模式(第N节 标题作 should-have)."""
    # 黑体术语 + 位置
    # ★数学书: 无 **TERM** 黑体但有 定义/定理 → 数学模式(第N节)
    if not _BOLD_TERM.search(chapter_text) and _MATH_SIGNAL.search(chapter_text):
        return _zh_math_should_have(chapter_text)
    term_pos: list[tuple[int, str]] = []
    seen = set()
    for m in _BOLD_TERM.finditer(chapter_text):
        t = m.group(1).strip()
        if t in seen or _is_spaced_noise(t) or _is_zh_running_head(t):
            continue
        if _is_bold_echo(t, chapter_text, m.end()):
            continue
        if any(t == s or t.startswith(s + " ") for s in _STOP):
            continue
        seen.add(t)
        term_pos.append((m.start(), t))
    terms = [t for _, t in term_pos]
    # 小节 + 起止位置, 各挂落在其区间内的黑体术语
    secs = [(m.start(), m.group(1), m.group(2).strip()) for m in _SECTION.finditer(chapter_text)]
    sections = []
    for i, (pos, num, title) in enumerate(secs):
        end = secs[i + 1][0] if i + 1 < len(secs) else len(chapter_text)
        in_sec = [t for p, t in term_pos if pos <= p < end]
        sections.append({"num": num, "title": title, "terms": in_sec})
    return {"sections": sections, "bold_terms": terms}


def check_completeness(chapter_text: str, extracted_ku_names: list[str]) -> dict:
    """对照抽出的 KU 名查漏. 黑体术语=权威应有清单; 小节漏 iff 其全部黑体术语都漏."""
    sh = identify_should_have(chapter_text)
    blob = " ".join(_norm(n) for n in extracted_ku_names)

    def covered(label: str) -> bool:
        nt = _norm(label)
        if nt and nt in blob:
            return True
        # ★2026-09-27 缩写 ↔ 中文展开: 章节黑体写 **LSTM**、KU 名写「长短期记忆」
        #   时字面匹配必然失败 → 判漏。同一概念的两种写法不该算漏。
        #   表里没有的缩写行为不变(仍然严格), 不整体放松判据。
        _zh = _ACRONYM_ZH.get(label.strip().upper())
        if _zh and _zh in blob:
            return True
        # 中文(无空格): 子概念整体 或 任一 2-字窗 在 blob → 覆盖(模糊主题匹配)
        if re.search(r"[一-鿿]", nt):
            parts = [p for p in _ZH_SPLIT.split(nt) if len(p) >= 2]
            if any(p in blob for p in parts):
                return True
            grams = {
                nt[i : i + 2] for i in range(len(nt) - 1) if re.match(r"[一-鿿]{2}", nt[i : i + 2])
            }
            return any(g in blob for g in grams)
        words = [w for w in nt.split() if len(w) > 3]
        return bool(words) and all(w in blob for w in words)

    missing_terms = [t for t in sh["bold_terms"] if not covered(t)]
    missing_sections = [
        s for s in sh["sections"] if s["terms"] and all(not covered(t) for t in s["terms"])
    ]
    return {
        "should_have": sh,
        "missing_bold_terms": missing_terms,
        "missing_sections": [f"{s['num']} {s['title']}" for s in missing_sections],
        "covered_terms": len(sh["bold_terms"]) - len(missing_terms),
        "total_terms": len(sh["bold_terms"]),
        "complete": not missing_terms,
    }
