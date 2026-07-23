"""判断一本 MD 是否带有旧 stratum 转换器(pymupdf4llm/marker)遗留的乱码伪影——
跟 math_extractable_gate.py(判断"能不能抠出编号定理")是两回事: 这里判断"就算抠得出
编号, 陈述本身是不是已经被转换器搞坏了"。已知两种伪影(2026-07-07 从
math_prog_827bed3779等9本书里实测抽出/复核确认, 见对话记录"萨金特Stochastic
Finance"一案):
  1. 公式/图表整体丢失, 转换器留下占位符 "==> picture [WxH] intentionally omitted <=="
  2. 上下标渲染失败, 残留 <sup>/<sub> 标签 + Unicode替换符 U+FFFD("�", 编码/字体缺字)
0-LLM程序抽取(math_program_ingest.py)没有LLM去"看懂"这些伪影替换回正确内容——
原样抠出来就是乱码KU。阈值凭实测样本(见 quarantine_corrupted_md 分析)取宽松线,
不误伤正常書(少量脚注/引用型上标是正常的).
"""

from __future__ import annotations

import re

_OMITTED = re.compile(r"intentionally omitted")
_SUP = re.compile(r"</?sup>|</?sub>")
_REPLACEMENT = "�"

MIN_LINES_FOR_RATIO = 200  # 太短的文件(误判风险高)不判定, 交给下游正常流程


def corruption_signals(text: str) -> dict:
    lines = text.split("\n")
    n_lines = max(len(lines), 1)
    return {
        "omitted_hits": len(_OMITTED.findall(text)),
        "sup_hits": len(_SUP.findall(text)),
        "replacement_hits": text.count(_REPLACEMENT),
        "n_lines": n_lines,
    }


def is_corrupted(text: str) -> tuple[bool, dict]:
    sig = corruption_signals(text)
    if sig["n_lines"] < MIN_LINES_FOR_RATIO:
        return False, sig
    # 实测: 真正坏的书这三项密度远超正常书(见 Stochastic Finance 2451处omitted,
    # Probability Theory 592处替换符+1087处sup, 对照组正常书均为0)。
    omitted_ratio = sig["omitted_hits"] / sig["n_lines"]
    sup_ratio = sig["sup_hits"] / sig["n_lines"]
    replacement_ratio = sig["replacement_hits"] / sig["n_lines"]
    # replacement_ratio阈值0.05(非0.02): 实测发现纯目录页的项目符号/引导点在markitdown
    # 转换里也会变成"�"(如"Probabilityspaces�1"本应是省略号引导), 良性且重转不会消失
    # ——真正坏书的比例(0.10~0.11)跟这个噪音底线(~0.025)之间仍有清楚间隔.
    bad = omitted_ratio > 0.01 or sup_ratio > 0.05 or replacement_ratio > 0.05
    return bad, sig


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    txt = open(path, encoding="utf-8", errors="replace").read()
    bad, sig = is_corrupted(txt)
    print(f"{'✗判定乱码(应重转)' if bad else '✓正常'}  {sig}  {path}")
