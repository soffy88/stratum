"""回归对比器 — 金集回归网存在的唯一理由: 检验"这次改动有没有改坏"。

★AII-EVALSET-SPEC-001 §2.3/§4.2 红线:
  · 本脚本只出报告, ★不自动判定放行——放不放行永远是 Wiki 的裁决权。
  · ★绝不能把这份对比结果当优化目标去自动搜索/调参判据——
    金标准来自人的本体判断, 拿它当目标函数优化 = 用裁判训练被裁判者,
    会 reward hack 出"恰好让这批标注好看"的判据(在标注之外可能更糟)。
  · 回归(原本判对→变错)是本报告最重要的一栏, 必须能解释清楚才能上。
  · 改进(原本判错→变对)不是免费的好消息——需要人工确认不是"恰好蒙对这批标注"
    (过拟合金集本身)。

用法:
  python compare_runs.py --baseline runs/<旧>.jsonl --current runs/<新>.jsonl
  不传参数时默认取 runs/ 目录里最新两次归档(次新 vs 最新)。
"""

import json
import sys
from pathlib import Path

from score import load_gold  # noqa: E402  (同目录复用, 避免另造一套金集加载逻辑)

HERE = Path(__file__).parent
RUNS_DIR = HERE / "runs"


def load_preds(path: Path) -> dict[str, str]:
    preds = {}
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            r = json.loads(ln)
            preds[r["pair_id"]] = r["predicted"]
    return preds


def correctness(gold: dict, preds: dict[str, str]) -> dict[str, bool | None]:
    """按 pair_id 算这次预测对不对。uncertain/无预测 → None(不参与回归判定)。"""
    out: dict[str, bool | None] = {}
    for pid, g in gold.items():
        if g["label"] == "uncertain" or pid not in preds:
            out[pid] = None
            continue
        out[pid] = (preds[pid] == "same") == (g["label"] == "same")
    return out


def compare(baseline_path: Path, current_path: Path) -> bool:
    gold = load_gold()
    base_correct = correctness(gold, load_preds(baseline_path))
    cur_correct = correctness(gold, load_preds(current_path))

    regressions, improvements, still_wrong, still_right = [], [], [], []
    for pid in gold:
        b, c = base_correct.get(pid), cur_correct.get(pid)
        if b is None or c is None:
            continue
        if b and not c:
            regressions.append(pid)
        elif not b and c:
            improvements.append(pid)
        elif not b and not c:
            still_wrong.append(pid)
        else:
            still_right.append(pid)

    print(f"===== 回归对比 =====\nbaseline: {baseline_path.name}\ncurrent:  {current_path.name}\n")
    print(
        f"  不变判对 {len(still_right)}  不变判错 {len(still_wrong)}  "
        f"改进 {len(improvements)}  ★回归 {len(regressions)}\n"
    )

    if regressions:
        print("  ★★★ 回归警报——以下对子原本判对,这次改动后判错了:")
        for pid in regressions:
            g = gold[pid]
            print(
                f"    [{g.get('band', '?')}/{g.get('category', '?')}] {pid}: {g['a_name']} vs {g['b_name']}  (金标={g['label']})"
            )
        print("  → 必须解释清楚这些为什么变错了才能上, 不能默认放行。\n")

    if improvements:
        print("  改进(原本判错,这次判对了)——不是免费的好消息:")
        for pid in improvements:
            g = gold[pid]
            print(f"    [{g.get('band', '?')}] {pid}: {g['a_name']} vs {g['b_name']}")
        print(
            "  → 需要人工确认这不是恰好让这批标注好看(过拟合金集), 不能只看这个数字说'变好了'。\n"
        )

    print("===== 裁决 =====")
    print("  本报告只提示'哪里变了', ★不自动判定放行——是否放行由 Wiki 裁决。")
    print("  ★不得把这份对比结果当优化目标去自动搜索/调参判据(见文件头红线)。")
    return len(regressions) == 0


def _latest_two() -> tuple[Path, Path] | None:
    runs = sorted(RUNS_DIR.glob("*.jsonl"))
    if len(runs) < 2:
        return None
    return runs[-2], runs[-1]


def main():
    if "--baseline" in sys.argv and "--current" in sys.argv:
        baseline = Path(sys.argv[sys.argv.index("--baseline") + 1])
        current = Path(sys.argv[sys.argv.index("--current") + 1])
    else:
        pair = _latest_two()
        if not pair:
            print(
                "runs/ 里归档不足两次, 没有基线可比对。先跑 run_gold.py 至少两次。", file=sys.stderr
            )
            sys.exit(2)
        baseline, current = pair
    no_regression = compare(baseline, current)
    sys.exit(0 if no_regression else 1)


if __name__ == "__main__":
    main()
