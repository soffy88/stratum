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

# 粘连判据(2026-09-09 修订): 旧正则 [a-z]{12,} 把合法长词系统性误判为粘连——
# approximation(12)/identification(14)/differential(12), 德语 wissenschaftlicher(17)、
# Nationalbibliothek(17)。pdf_inspector 重转测试中 88%→51.5% 里 560/562 行是此类
# 长词误报, 真拼接仅 2 行。真粘连 = 空格丢失, 必然留下"词界被吞"的证据:
#   1. 大小写翻转拼接:   [a-z]{8,}[A-Z]         (小写词尾紧贴大写词首, 如 theTheorem)
#   2. 长字母流内夹数字:  [A-Za-z]{8,}\d[A-Za-z]{8,}  (公式/编号与词拼死)
#   3. 标点后无空格:      [a-z]{2,}[.,;:!?][a-z]{2,}  (词,词 / 词.词)
#   4. 超长纯小写拼接:    [a-z]{18,}            (任何数学/物理/德语常词 <18 字母;
#                             只有空格全丢才拼出 Permissionisgrantedtoquotebriefpassages)
# 实测: 真粘连书(Circle Method, markitdown) 73.7% 仍被拦; 新引擎(afdr) 2.5% 通过。
# 中文行不受影响(无小写字母)。
_GLUE = re.compile(
    r"[a-z]{8,}[A-Z]"                       # 1. 大小写翻转(拼接)
    r"|[A-Za-z]{8,}\d[A-Za-z]{8,}"          # 2. 长字母流内夹数字(公式拼接)
    r"|[a-z]{2,}[.,;:!?][a-z]{2,}"          # 3. 标点后无空格
    r"|[a-z]{18,}"                          # 4. 超长纯小写拼接
)


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


# ── 概念标记预检(Wiki 2026-07-20: 淘汰率高×成本低的门先跑) ──────────────────
# 实测 Precalculus 全书 611 条【全是 Example】, 一个编号 Definition/Theorem 都没有 →
# 烧了 4300s(72分钟) LLM 产出 0 个概念候选。这种书对"概念层接入"这个目的是纯浪费。
# 该检查只做正则计数(毫秒级、零成本), 所以排在粘连门【之前】: 零标记的书连粘连都不用测。
_CONCEPT_MARK = __import__("re").compile(
    r"(?m)^\s{0,3}(?:#{1,4}\s*)?(?:\*\*)?\s*"
    r"(?:Definition|Theorem|Lemma|Proposition|Corollary|定义|定理|引理|推论|命题)\s*\d"
)


def concept_mark_count(text: str) -> int:
    """书里编号的 定义/定理/引理/推论/命题 标记数。0 = 这本书产不出概念候选。"""
    return len(_CONCEPT_MARK.findall(text))
