"""数学书"烂文本层"检测门禁 — 判断一本书是否需要 OCR 重转.

背景: 部分数学 PDF(尤其中文扫描/老版式)自带的文本层是烂 OCR, fitz 直读出乱码
(例→囹, 圆盘→罔盘, ε-δ→ε-Ò…), 后续程序抽取再忠实也只能抠到乱码. 需要在抽取
前判断"这本书要不要先送 Unlimited-OCR(vLLM)重新识别".

设计取舍(实测校准, 见 aii-ocr-vllm-pipeline 记忆):
- 单纯"latin/cjk 比"或"已知坏字"两种简单启发式都被证伪: 干净的数学书因大量
  LaTeX(\\lim \\frac \\varepsilon)导致 latin 比例本身就高, 且"苦/寸"等所谓坏字
  其实是常见汉字, 任何正常书都会命中 → 全部误判.
- 真正管用的信号: **结构词(例/解/证明/定义/定理)密度 相对 编号行(习题编号)密度
  的比值**. 编号行的数字本身很少被 OCR 读错, 但"例""定义"这类词经常被读成乱码替
  代字. 干净的教材这个比值明显高于烂文本层版本(实测斯图: 烂 0.08-0.30, 同书OCR
  后干净 0.35-1.40, 阈值取 0.33). 仅当编号行密度本身足够高(书是习题密集的教材)
  时该比值才有意义, 否则(叙事类数学科普书, 编号行接近0)不作判断、默认不需要OCR.
"""

from __future__ import annotations

import re

STRUCT_RE_ZH = re.compile(r"例|解[:：]|证明|定义|定理")
STRUCT_RE_EN = re.compile(r"\b(?:Example|Solution|Proof|Definition|Theorem)\b", re.I)
CJK_RE = re.compile(r"[一-鿿]")
NUMBERED_RE = re.compile(r"(?m)^\s*\d{1,3}[.\s]")
CHUNK = 40_000
MIN_NUMBERED_PER_CHUNK = 30  # 编号行够密才认为是"习题教材", 否则无法判断(不误伤叙事书)
RATIO_THRESHOLD = 0.33  # 结构词/编号行 低于此值 → 判定为烂文本层


def needs_ocr(text: str) -> tuple[bool, dict]:
    """返回 (是否需要OCR, 诊断详情). 诊断详情供日志/调试, 不用于决策之外的用途."""
    # 结构词是中/英文特有词汇, 按全书 cjk 占比选对应模式(纯英文书用中文词恒命中0→误判).
    sample = text[: min(len(text), 200_000)]
    is_zh = len(CJK_RE.findall(sample)) / max(len(sample), 1) > 0.05
    struct_re = STRUCT_RE_ZH if is_zh else STRUCT_RE_EN

    chunks_judged = 0
    chunks_bad = 0
    ratios = []
    for i in range(0, len(text), CHUNK):
        seg = text[i : i + CHUNK]
        n_struct = len(struct_re.findall(seg))
        n_num = len(NUMBERED_RE.findall(seg))
        if n_num < MIN_NUMBERED_PER_CHUNK:
            continue  # 这段编号行太少, 无法用该比值判断(可能是非习题段落)
        chunks_judged += 1
        r = n_struct / n_num
        ratios.append(r)
        if r < RATIO_THRESHOLD:
            chunks_bad += 1

    detail = {
        "chunks_judged": chunks_judged,
        "chunks_bad": chunks_bad,
        "ratios_sample": ratios[:8],
    }
    if chunks_judged < 2:
        # 习题密度不足以判断(叙事类数学书等) → 默认不需要OCR, 避免误伤
        detail["reason"] = "insufficient_exercise_density"
        return False, detail

    bad_frac = chunks_bad / chunks_judged
    flagged = bad_frac >= 0.6  # 多数被判定段落都很差才触发, 避免个别噪音段落误判整本
    detail["bad_fraction"] = round(bad_frac, 2)
    detail["reason"] = "garbled_text_layer" if flagged else "clean"
    return flagged, detail


if __name__ == "__main__":
    import sys

    path = sys.argv[1]
    txt = open(path, encoding="utf-8", errors="replace").read()
    flagged, detail = needs_ocr(txt)
    print(f"{'★需要OCR' if flagged else '✓文本层正常'}: {path}")
    print(f"  详情: {detail}")
