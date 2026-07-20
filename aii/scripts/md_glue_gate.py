"""MD 粘连门 —— OCR 抹掉空格的书, 在 ingest 入口就拦下, 退回 Stratum 返工。

★为什么要这道门(2026-07-20 实测):
  Probability Theory 一书粘连率 76%, 实测结果是【①②双双归零】:
    · ① 书自带括号名: 抠到的"名字"一半是记号(Ω,𝒜,ℙ / X j), 真概念名 12/338 = 3.6%
    · ② 规划审核: 判要丢弃 84% 候选 → 安全阀触发 → 该章 0 个名字
  更糟的是【过滤器无法察觉自己失败】: 粘连把
  "Say we have three urns, each containing white and black balls."
  变成 "Saywehavethreeurns,eachcontainingwhiteandblackballs." ——纯字母+逗号句号,
  _is_name 的字符类挡不住, 整句话被当成概念名放行(假阳性)。
  空格没了, 句子和概念名在字符层面不可区分。

★为什么退回而不是自弃(Wiki 2026-07-20 裁决):
  粘连是 R4/R9 级的【上游转换失败】, 是 Stratum 的 PDF→MD 环节没做好。
  自弃 = 把上游的病记在自己账上; 退回 md_rework_queue 才是治本
  (AII-STRATUM-MD-SPEC-001 §"不合格→不抽→写 rework 请求"的既有闭环)。

★阈值 30%(保守起点, 留人调):
  实测只有两个锚点 —— 76% 时死区, ≈0% 时 ② 命名 93.9%。中间地带无数据。
  宁可多退几本给 Stratum, 不让半烂的书在管线里产半假的概念。
  "多少算烂"没有客观裁判(原则二) → 阈值是参数不是常量, 有数据再松。

用法:
  python scripts/md_glue_gate.py <md_path>                 # 只测, 打印粘连率
  python scripts/md_glue_gate.py <md_path> --substrate ID --title T --report
        # 超阈值时写 md_rework_queue.json(复用 econ_stratum_feedback 的链路)
退出码: 0=通过, 2=粘连超阈值(调用方应跳过该书, 不进②)
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

GLUE_THRESHOLD = float(__import__("os").getenv("MD_GLUE_THRESHOLD", "0.30"))

# 粘连判据: 连续 12+ 个小写字母不带空格。正常英文单词极少这么长(longest common
# words ~10), 中文行不受影响(无小写字母)。故意用同一条判据测 title 和正文, 与
# 2026-07-20 量化 math_prog 时用的判据一致(那次算出全库 19.1% 粘连)。
_GLUE = re.compile(r"[a-z]{12,}")


def glue_ratio(text: str) -> tuple[float, int, int]:
    """返回 (粘连行占比, 粘连行数, 计入统计的行数)。

    只统计"含足够字母的行"——空行/公式行/纯数字行不该稀释分母。
    """
    lines = [ln for ln in text.split("\n") if len(re.findall(r"[A-Za-z]", ln)) >= 20]
    if not lines:
        return 0.0, 0, 0
    bad = sum(1 for ln in lines if _GLUE.search(ln))
    return bad / len(lines), bad, len(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("md_path")
    ap.add_argument("--substrate", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--report", action="store_true", help="超阈值时写 rework 队列")
    args = ap.parse_args()

    p = Path(args.md_path)
    if not p.exists():
        print(f"❌ 文件不存在: {p}", file=sys.stderr)
        return 1
    ratio, bad, total = glue_ratio(p.read_text(encoding="utf-8", errors="replace"))
    verdict = "超阈值" if ratio > GLUE_THRESHOLD else "通过"
    print(f"粘连率 {ratio:.1%} ({bad}/{total} 行) | 阈值 {GLUE_THRESHOLD:.0%} → {verdict}")

    if ratio <= GLUE_THRESHOLD:
        return 0

    print(
        "  ⚠ 该书 OCR 粘连过重: 空格丢失后句子与概念名在字符层面不可区分,\n"
        "    ①书自带名会抠出记号、②规划审核会大规模误判, 且过滤器无法察觉失败。\n"
        "    → 不抽, 退回 Stratum 返工(AII-STRATUM-MD-SPEC-001)。",
        file=sys.stderr,
    )
    if args.report and args.substrate:
        reason = f"FAIL:R4:OCR空格丢失(粘连率{ratio:.0%}, {bad}/{total}行), 概念命名不可用"
        try:
            subprocess.run(
                [
                    sys.executable,
                    "scripts/econ_stratum_feedback.py",
                    args.substrate,
                    args.title or p.stem,
                    str(p),
                    reason,
                ],
                check=True,
            )
            print("  📤 已写入 md_rework_queue.json")
        except Exception as e:  # 反馈失败不该顶掉"拦下"这个主结论
            print(f"  ⚠ 写返工队列失败(仍判定不抽): {e}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
