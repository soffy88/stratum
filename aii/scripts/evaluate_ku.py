#!/usr/bin/env python3
"""evaluate_ku 软分 (规格 3.4, D1) — 「像知识」过滤器, 零 LLM。

对已过硬门禁(编码/span/数字对齐)的候选 KU 打软分:
  - density      信息密度(实词比, 定义/因果/步骤信号)       权重 0.35
  - atomicity    原子性(是否多主题粘连)                     权重 0.25
  - retrievability 可检索性(标题是否可当检索键)             权重 0.20
  - alignment    与 evidence 对齐度(claim/quote 长度比)     权重 0.20
总分 < PASS_THRESHOLD → reject/repair; 分数写 quality 供审计。

用法:
    from evaluate_ku import score_ku
    score = score_ku(claim=..., title=..., quotes=[...])
"""
from __future__ import annotations

import os
import re

PASS_THRESHOLD = 0.5
# NLI 严进开关(规格 12): KU_NLI_STRICT=1 时 NOT_ENTAILED 硬拒
NLI_STRICT = os.getenv("KU_NLI_STRICT", "0") == "1"
_LATIN = re.compile(r"[A-Za-z]")
_CJK = re.compile(r"[\u4e00-\u9fff]")
_PROC_KW = re.compile(r"(步骤|首先|然后|最后|方法|流程|how|step|first|then)", re.IGNORECASE)
_NUM_HINT = re.compile(r"\d+(?:\.\d+)?%?|等于|=|\d+(?:[,.]\d+)+")


def infer_claim_type(claim: str, ku_type: str = "") -> str:
    """确定性推断 claim_type(规格 11): definition|fact|procedure|relation|number|opinion"""
    c = claim or ""
    if _PROC_KW.search(c):
        return "procedure"
    if _NUM_HINT.search(c):
        return "number"
    if re.search(r"(是指|定义为|is defined|means|is called|refers to|称为)", c, re.IGNORECASE):
        return "definition"
    if re.search(r"(因为|因此|导致|取决于|implies|because|hence)", c, re.IGNORECASE):
        return "relation"
    if re.search(r"(我认为|建议|应该|可能更|it seems|should|arguably)", c, re.IGNORECASE):
        return "opinion"
    return {"conceptual": "fact", "rationale": "relation", "procedural": "procedure",
            "factual": "fact", "positional": "opinion"}.get(ku_type, "fact")


def check_lang_mix(text: str, lang: str = "zh") -> list[str]:
    """语言混杂检测(规格 8): 声明中文却大量 Latin 碎片(半译半原文)。"""
    if not text:
        return []
    latin = len(_LATIN.findall(text))
    cjk = len(_CJK.findall(text))
    if lang == "zh" and latin > 20 and cjk > 0 and latin / max(cjk + latin, 1) > 0.5:
        return ["LANG_MIX: 中文 KU 中 Latin 占比过高(半译半原文)"]
    return []


def embedding_coarse_filter(claim: str, quotes: list[dict], min_sim: float = 0.25) -> list[str]:
    """级联中的 embedding 粗滤(规格 4/5): claim 与证据拼接向量余弦过低 → HALLUCINATION。

    本机 embed 服务(127.0.0.1:8102)。失败静默(不阻断)。
    """
    import json as _json
    import urllib.request as _ur
    try:
        ev = " ".join(q.get("quote", "") for q in (quotes or []))[:1500]
        if not ev or len(claim) < 20:
            return []
        body = _json.dumps({"texts": [claim[:1500], ev]}).encode()
        req = _ur.Request("http://127.0.0.1:8102/embed", data=body,
                          headers={"Content-Type": "application/json"})
        with _ur.urlopen(req, timeout=10) as resp:
            vecs = _json.loads(resp.read())["embeddings"]
        a, b = vecs[0], vecs[1]
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        sim = dot / (na * nb) if na and nb else 0.0
        if sim < min_sim:
            return [f"HALLUCINATION: claim-证据 余弦 {sim:.2f} < {min_sim}"]
    except Exception:  # noqa: BLE001
        pass
    return []
_ALNUM = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")
_KNOWLEDGE_KW = re.compile(
    r"(is |are |means |defined|refers|因为|因此|如果|则|定理|定义|命题|"
    r"步骤|方法|由.*得|导致|取决于|等于|分为|称为)",
    re.IGNORECASE,
)


def score_ku(claim: str, title: str = "", quotes: list[dict] | None = None) -> dict:
    """返回 {density, atomicity, retrievability, alignment, total, pass}"""
    claim = claim or ""
    title = title or ""

    # 密度: 实词比 + 知识信号词
    alnum = len(_ALNUM.findall(claim))
    density = 0.0
    has_kw = bool(claim and _KNOWLEDGE_KW.search(claim))
    if claim:
        density = min(1.0, alnum / max(len(claim), 1) * 1.4)  # 实词比
        if has_kw:
            density = min(1.0, density + 0.15)  # 定义/因果信号加成
        else:
            density = min(density, 0.45)  # ★无知识信号词(口语/废话)封顶
    density = min(1.0, density)

    # 原子性: 单主题 ≈ 长度适中 + 无多枚举粘连
    sentences = len(re.findall(r"[。！？.!?；;]", claim)) + 1
    if not claim:
        atomicity = 0.0
    elif len(claim) > 600:
        atomicity = 0.2          # 超长 = 多主题粘连
    elif sentences <= 3:
        atomicity = 0.9
    elif sentences <= 5:
        atomicity = 0.6
    else:
        atomicity = 0.3

    # 可检索性: 标题可当检索键(有实词)
    tl = len(_ALNUM.findall(title))
    if not title:
        retrievability = 0.0
    elif tl < 3:
        retrievability = 0.3
    elif tl <= 12:
        retrievability = 1.0
    else:
        retrievability = 0.7

    # 对齐度: claim 与 evidence 长度比(claim 不应远超证据)
    qlen = sum(len(q.get("quote") or "") for q in (quotes or []))
    if not qlen:
        alignment = 0.0
    else:
        ratio = len(claim) / max(qlen, 1)
        alignment = 1.0 if ratio <= 3 else max(0.1, 1.5 - ratio * 0.15)

    total = (density * 0.35 + atomicity * 0.25
             + retrievability * 0.20 + alignment * 0.20)
    return {
        "density": round(density, 3),
        "atomicity": round(atomicity, 3),
        "retrievability": round(retrievability, 3),
        "alignment": round(alignment, 3),
        "total": round(total, 3),
        "pass": total >= PASS_THRESHOLD,
    }


if __name__ == "__main__":
    good = score_ku(
        "机会成本是指为了得到某种东西而必须放弃的其他东西的价值，稀缺性导致选择。",
        "机会成本", [{"quote": "机会成本是指为了得到某种东西而必须放弃的其他东西的价值"}])
    print("好 KU:", good)
    bad = score_ku("嗯嗯 好的 谢谢 哈哈哈哈", "x", [])
    print("垃圾:", bad)
