"""闭集词典: 判别维度族(dimensions.yaml) + 术语规范(terms.yaml)。
与判同共用(设计 §5.3/§6.3 同一套基础设施): 判同关1按本质/表述维度; 名称经 terms 受控对齐。
"""

from __future__ import annotations
import functools
from pathlib import Path
import yaml

DICT_DIR = Path(__file__).parent / "dict"


@functools.lru_cache(maxsize=1)
def _dims() -> dict:
    return yaml.safe_load((DICT_DIR / "dimensions.yaml").read_text(encoding="utf-8"))["families"]


@functools.lru_cache(maxsize=1)
def _terms() -> list:
    return yaml.safe_load((DICT_DIR / "terms.yaml").read_text(encoding="utf-8"))["terms"]


def family_for(*names: str) -> tuple[str, dict] | tuple[None, None]:
    """按名称里的关键词命中判别维度族。返回 (族名, 族定义) 或 (None, None)。"""
    blob = " ".join(n.lower() for n in names if n)
    for fam, spec in _dims().items():
        if any(kw.lower() in blob for kw in spec.get("match", [])):
            return fam, spec
    return None, None


def dimensions_hint(*names: str) -> str:
    """给判官的判别维度提示文本(本质维度取值不同=不同概念; 表述维度可合)。命中族才给。"""
    fam, spec = family_for(*names)
    if not fam:
        return ""
    lines = [f"判别维度族「{fam}」（本质维度取值不同=不同概念; 表述维度不同仍可同一）:"]
    for d in spec["dimensions"]:
        vals = "/".join(str(v) for v in d["values"][:6])
        lines.append(f"  - {d['key']}[{d['kind']}]: {vals}")
    return "\n".join(lines)


def canonical(name: str) -> dict | None:
    """名称受控对齐: 命中 terms 词典 → 返回 {canonical_en, zh, discipline}; 否则 None(不强行译)。"""
    low = (name or "").strip().lower()
    for t in _terms():
        if low == t["canonical_en"].lower() or low in [a.lower() for a in t.get("aliases", [])]:
            return {
                "canonical_en": t["canonical_en"],
                "zh": t.get("zh"),
                "discipline": t.get("discipline"),
            }
    return None


if __name__ == "__main__":
    print("family:", family_for("Price Elasticity of Demand")[0])
    print(dimensions_hint("Income Elasticity of Demand"))
    print("canonical:", canonical("opportunity costs"))
