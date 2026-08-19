"""判断一本 MD 是否带有转换器遗留的乱码伪影——
跟 math_extractable_gate.py(判断"能不能抠出编号定理")是两回事: 这里判断"就算抠得出
编号, 陈述本身是不是已经被转换器搞坏了"。已知四种伪影:
  1.(2026-07-07,pymupdf4llm/marker,"萨金特Stochastic Finance"一案)
    公式/图表整体丢失, 转换器留下占位符 "==> picture [WxH] intentionally omitted <=="
  2.(同上) 上下标渲染失败, 残留 <sup>/<sub> 标签 + Unicode替换符 U+FFFD("�", 编码/字体缺字)
  3.(2026-07-25,markitdown,"Group Chunks in Model Theory and Algebra"一案)
    PDF内嵌数学字体未正确解码为Unicode, 原始字形编号原样泄漏, 如 "(cid:101)"
  4.(同上, 及中文OCR"抽象代数(陈猛等)"一案) 多栏排版/公式被误判为markdown表格,
    整段陈述被打碎成大量短碎片单元格(中文OCR还会在字与字间插入多余空格),
    如 "| Proof.  | Immediate |  | from Lemma |...|" 或 "| 基础 学 科 | ..."
  5.(同上) 词间空格丢失, 多个单词连写成一长串无空格字母(与 4 常同源但不同段落,
    KU 粒度上二者不总是同时出现, 需独立判定), 如
    "Acategoryissaidtobelocallysmall"
0-LLM程序抽取(math_program_ingest.py)没有LLM去"看懂"这些伪影替换回正确内容——
原样抠出来就是乱码KU。阈值凭实测样本(见 quarantine_corrupted_md 分析,
以及 2026-07-25 对 15 本随机抽样对照书的复核)取宽松线, 不误伤正常書
(少量脚注/引用型上标是正常的; 真正内容表格的行密度远低于伪影碎表格).
"""

from __future__ import annotations

import re

_OMITTED = re.compile(r"intentionally omitted")
_SUP = re.compile(r"</?sup>|</?sub>")
_REPLACEMENT = "�"
_CID_LEAK = re.compile(r"\(cid:\d+\)")
_TABLE_SHRED_ROW = re.compile(r"^\s*\|[^|]{1,20}\|[^|]{1,20}\|", re.M)
_LONG_RUN = re.compile(r"[A-Za-z]{28,}")  # 连续28+字母无空格, 正常英文单词不会这么长

MIN_LINES_FOR_RATIO = 200  # 太短的文件(误判风险高)不判定, 交给下游正常流程


def corruption_signals(text: str) -> dict:
    lines = text.split("\n")
    n_lines = max(len(lines), 1)
    return {
        "omitted_hits": len(_OMITTED.findall(text)),
        "sup_hits": len(_SUP.findall(text)),
        "replacement_hits": text.count(_REPLACEMENT),
        "cid_hits": len(_CID_LEAK.findall(text)),
        "table_shred_hits": len(_TABLE_SHRED_ROW.findall(text)),
        "long_run_hits": len(_LONG_RUN.findall(text)),
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
    cid_ratio = sig["cid_hits"] / sig["n_lines"]
    table_shred_ratio = sig["table_shred_hits"] / sig["n_lines"]
    # cid_ratio: 真书从未出现"(cid:N)"字面量(15本随机对照样本全为0); 已知坏书
    # 0.058~0.136。阈值取0.005, 远低于坏书下限、远高于对照噪声(0)。
    # table_shred_ratio: 对照样本里真表格密集书(Calculus Vol2/贝叶斯思维)也只有
    # ~0.01~0.011; 已知坏书(含中文OCR"抽象代数"一案, 无cid泄漏但表格碎片率0.48)
    # 0.22~0.48。阈值取0.05, 二者间隔清楚, 且不与cid_ratio耦合判定(表格打碎可独立
    # 于字形泄漏发生, 如中文OCR案).
    long_run_ratio = sig["long_run_hits"] / sig["n_lines"]
    # long_run_ratio: 15本对照样本全为0(连28+字母都没有); 已知坏书0.009~0.028。
    # 阈值取0.003——这是本轮(2026-07-25)补的第三种独立伪影(词间空格丢失),
    # 事出"Group Chunks"一书内仍有82条KU(全书291条里的28%)既不含cid泄漏、
    # 也不含表格打碎、但逐条抽查确认同样是乱码("Acategoryissaidtobelocallysmall"
    # 这类连写), 说明前两个信号在 KU 粒度(而非整书粒度)下不足以覆盖同一本
    # 坏书的所有段落——三信号独立判定, 不互相依赖.
    bad = (
        omitted_ratio > 0.01
        or sup_ratio > 0.05
        or replacement_ratio > 0.05
        or cid_ratio > 0.005
        or table_shred_ratio > 0.05
        or long_run_ratio > 0.003
    )
    return bad, sig


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    txt = open(path, encoding="utf-8", errors="replace").read()
    bad, sig = is_corrupted(txt)
    print(f"{'✗判定乱码(应重转)' if bad else '✓正常'}  {sig}  {path}")
