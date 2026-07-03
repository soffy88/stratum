"""程序关(确定性, 不靠模型) — 在 LLM 判同(关3)之前拦常见错合陷阱。

关1 判别维度: 命中族后, 任一"本质维度"取值不同 → DIFFERENT（价格弹性 vs 收入弹性）。
关2 类层级/上下位: 一名是另一名的真子集/子串 → 特化, 父≠子 → DIFFERENT（机会成本 vs 生产机会成本）。
关0 术语同名: 二者经闭集词典规范到同一 canonical → SAME（跨书大小写/单复数变体）。

命门(宁碎片不错合): DIFFERENT 关优先于 SAME 关——冲突时保守判 different。
未决(None) → 交 LLM 关3。程序关取值来自闭集词典, 词典越全越确定(设计 §6.2 确定性是挣来的)。
"""

from __future__ import annotations
import re

from dictionary import canonical, family_for

_CJK = re.compile(r"[一-鿿]")
_STOP = {"of", "the", "a", "an", "and", "to", "at", "for", "in", "on", "vs", "on"}


def _tokens(name: str) -> set:
    return set(re.findall(r"[a-z]+", (name or "").lower())) - _STOP


def _dim_values(name: str, spec: dict) -> dict:
    """确定性抽取: 名称里命中的判别维度取值(长值优先, 避 price 抢 cross-price)。"""
    low = (name or "").lower()
    out = {}
    for d in spec["dimensions"]:
        for v in sorted((str(x) for x in d["values"]), key=len, reverse=True):
            if v.lower() in low:
                out[d["key"]] = (v.lower(), d["kind"])
                break
    return out


def gate1_dimensions(a: str, b: str) -> str | None:
    fam, spec = family_for(a, b)
    if not spec:
        return None
    va, vb = _dim_values(a, spec), _dim_values(b, spec)
    for k in set(va) & set(vb):
        (av, kind), (bv, _) = va[k], vb[k]
        if kind == "本质" and av != bv:
            return f"关1 判别维度族「{fam}」本质维度[{k}]取值不同: {av}≠{bv}"
    return None


def gate2_subsumption(a: str, b: str) -> str | None:
    ta, tb = _tokens(a), _tokens(b)
    if ta and tb and ta != tb:
        if ta < tb:
            return f"关2 上下位: 「{a}」是「{b}」的真子集(父≠子)"
        if tb < ta:
            return f"关2 上下位: 「{b}」是「{a}」的真子集(父≠子)"
    na, nb = re.sub(r"\s", "", a or ""), re.sub(r"\s", "", b or "")
    if _CJK.search(na + nb) and na != nb:
        if na and na in nb:
            return f"关2 上下位: 「{na}」是「{nb}」子串(父≠子)"
        if nb and nb in na:
            return f"关2 上下位: 「{nb}」是「{na}」子串(父≠子)"
    return None


def gate0_canonical(a: str, b: str) -> str | None:
    ca, cb = canonical(a), canonical(b)
    if ca and cb and ca["canonical_en"] == cb["canonical_en"]:
        return f"关0 术语同名: 均规范到「{ca['canonical_en']}」"
    return None


def run_gates(a_name: str, b_name: str) -> dict | None:
    """确定性程序关。返回 {verdict, gate, reason} 或 None(未决→LLM 关3)。DIFFERENT 关优先。"""
    for fn, verdict in (
        (gate1_dimensions, "different"),
        (gate2_subsumption, "different"),
        (gate0_canonical, "same"),
    ):
        r = fn(a_name, b_name)
        if r:
            return {"verdict": verdict, "gate": r.split()[0], "reason": r}
    return None


if __name__ == "__main__":
    for a, b in [
        ("Price Elasticity of Demand", "Income Elasticity of Demand"),
        ("Marginal Cost", "Increasing Marginal Cost"),
        ("Opportunity Cost", "Opportunity Cost of Production"),
        ("Opportunity Cost", "Opportunity costs"),
        ("Price Elasticity of Demand", "Price elasticity of demand"),
        ("Arc elasticity", "Point elasticity"),
    ]:
        print(f"{a} ⟷ {b}: {run_gates(a, b)}")
