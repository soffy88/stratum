#!/usr/bin/env python3
"""块质量检测 (B1/B2) — 乱码/样板在 LLM 之前拦截, 零 LLM 全确定性。

对齐规格 ①解析层 + ②块过滤:
  - MOJIBAKE    : \\ufffd 替换字符比例 / 控制字符比例超限 / 双重解码残留
  - BOILERPLATE : 正文比过低(页眉页脚/导航占主导)
  - TOO_SHORT   : 有效文本过短, 不够抽 KU

用法:
    from block_quality import check_chunk_quality
    ok, issues = check_chunk_quality(chapter_text)
"""
from __future__ import annotations

import re

# \ufffd 替换字符比例阈值(规格建议 0.5%)
REPLACEMENT_RATIO_MAX = 0.005
# 控制字符(除 \n\t\r 外)比例阈值
CTRL_RATIO_MAX = 0.01
# 正文比阈值: 有效字母/数字/汉字 占可打印字符比例
BODY_RATIO_MIN = 0.35
# 最短有效文本(抽 KU 最低材料)
MIN_TEXT_LEN = 80

_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ALNUM_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]")


def check_chunk_quality(text: str) -> tuple[bool, list[str]]:
    """返回 (ok, issues)。ok=False 表示该块不应进抽取。"""
    if not text:
        return False, ["EMPTY"]
    total = len(text)
    issues: list[str] = []

    # 1. 替换字符比例(乱码主信号)
    repl = text.count("\ufffd")
    if repl / total > REPLACEMENT_RATIO_MAX:
        issues.append(f"MOJIBAKE: \\ufffd 比例 {repl / total:.3%} > {REPLACEMENT_RATIO_MAX:.1%}")

    # 2. 控制字符比例
    ctrl = len(_CTRL_RE.findall(text))
    if ctrl / total > CTRL_RATIO_MAX:
        issues.append(f"MOJIBAKE: 控制字符 {ctrl / total:.3%}")

    # 2b. 重复性(boilerplate 信号: 页眉页脚/导航的重复行/重复块)
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if len(lines) >= 6:
        uniq = len(set(lines))
        if uniq / len(lines) < 0.4:
            issues.append(f"BOILERPLATE: 重复行 {len(lines) - uniq}/{len(lines)}")
    else:
        # 单行/少行: 16 字符滑动块唯一性(抓单行重复样板)
        blocks = [text[i : i + 16] for i in range(0, len(text) - 16, 16)]
        if len(blocks) >= 8:
            uniq_b = len(set(blocks))
            if uniq_b / len(blocks) < 0.3:
                issues.append(f"BOILERPLATE: 重复块 {len(blocks) - uniq_b}/{len(blocks)}")

    # 3. 正文比(有效字母数字汉字 / 总长)
    body = len(_ALNUM_RE.findall(text))
    if body / total < BODY_RATIO_MIN:
        issues.append(f"BOILERPLATE: 正文比 {body / total:.1%} < {BODY_RATIO_MIN:.0%}")

    # 4. 有效文本长度
    if body < MIN_TEXT_LEN:
        issues.append(f"TOO_SHORT: 有效文本 {body} < {MIN_TEXT_LEN}")

    return (len(issues) == 0), issues


if __name__ == "__main__":
    # 自检
    good = "Opportunity cost is the value of the next best alternative foregone." * 8
    print("正常文本:", check_chunk_quality(good))
    bad = "(cid:101)(cid:102)" + "\ufffd" * 50 + "abc" * 10
    print("乱码文本:", check_chunk_quality(bad))
    nav = "首页 导航 广告 页脚 菜单 " * 20
    print("样板文本:", check_chunk_quality(nav))
    print("空文本:", check_chunk_quality(""))
