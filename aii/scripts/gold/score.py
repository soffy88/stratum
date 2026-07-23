"""金集打分器 — 把命门不对称("宁碎片不错合")变成可度量验收线。

用法:
  python score.py                      # 覆盖度报告(无需预测): 金集构成 + 对抗类别清单
  python score.py --pred preds.jsonl   # 打分: merge precision / recall(按 band 分解)

金集 = gold_seed.jsonl + 人工标注后的 candidates.jsonl(label 填 same/different/uncertain)。
预测文件 preds.jsonl 每行: {"pair_id": "...", "predicted": "same"|"different"}
  predicted=same 表示判同逻辑裁"合并"。

验收线(体现命门不对称):
  · merge precision(裁 same 里真 same 的占比)必须 → 1.0 —— 错合近零是硬线
  · recall(真 same 里被裁 same 的占比)可以低 —— 宁碎片
  · red band 里出现任何"错合"(gold different 却 predicted same)即 FAIL —— 高危陷阱零容忍
"""

import json, sys
from pathlib import Path
from collections import Counter, defaultdict

HERE = Path(__file__).parent
REQUIRED_CATS = ["类冲突", "上下位", "跨书同名", "表述变体", "方向反机制", "跨域同名异义"]
MERGE_PRECISION_LINE = 0.99  # → 1.0


def load_gold():
    gold = {}
    for p in sorted(HERE.glob("gold_seed*.jsonl")) + [HERE / "candidates.jsonl"]:
        if not p.exists():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            if not r.get("label"):  # candidates 未标注 → 跳过
                continue
            gold[r["pair_id"]] = r
    return gold


def coverage(gold):
    print(f"===== 金集覆盖度 (共 {len(gold)} 对已标注) =====")
    by_label = Counter(r["label"] for r in gold.values())
    by_band = Counter(r.get("band", "?") for r in gold.values())
    by_cat = Counter(r.get("category", "?") for r in gold.values())
    by_kind = Counter(r.get("kind", "?") for r in gold.values())
    print(f"  label : {dict(by_label)}")
    print(f"  band  : {dict(by_band)}")
    print(f"  kind  : {dict(by_kind)}")
    print(f"  类别   : {dict(by_cat)}")
    print("\n===== 对抗类别清单(设计 11.1 要求全覆盖) =====")
    missing = []
    for c in REQUIRED_CATS:
        n = by_cat.get(c, 0)
        flag = "✓" if n else "✗ 缺"
        if not n:
            missing.append(c)
        print(f"  [{flag}] {c}: {n}")
    if missing:
        print(f"\n  ⚠ 缺 {len(missing)} 类: {missing}")
        print(
            "    方向反机制/跨域同名异义 依赖 M1 超边或跨域概念,可待 mine_candidates 挖掘或 M1 后补。"
        )
    # 健康提示: same/different 都要有(只 same 无 different 测不出错合)
    if by_label.get("different", 0) == 0:
        print("  ⚠ 无 different 对 → 无法度量错合(precision 失效)")
    if by_label.get("same", 0) == 0:
        print("  ⚠ 无 same 对 → 无法度量 recall")


def score(gold, pred_path):
    preds = {}
    for ln in Path(pred_path).read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            r = json.loads(ln)
            preds[r["pair_id"]] = r["predicted"]
    # 只在有金标(same/different)且有预测的对上算; uncertain 排除
    tp = fp = fn = tn = 0
    errs_by_band = defaultdict(list)  # 错合(gold different, pred same)
    missed = []  # 漏合(gold same, pred different)
    scored = skipped_uncertain = no_pred = 0
    for pid, g in gold.items():
        lab = g["label"]
        if lab == "uncertain":
            skipped_uncertain += 1
            continue
        if pid not in preds:
            no_pred += 1
            continue
        scored += 1
        pred = preds[pid]
        same_gold = lab == "same"
        same_pred = pred == "same"
        if same_pred and same_gold:
            tp += 1
        elif same_pred and not same_gold:
            fp += 1  # ★错合
            errs_by_band[g.get("band", "?")].append((pid, g))
        elif not same_pred and same_gold:
            fn += 1  # 漏合(可接受)
            missed.append(pid)
        else:
            tn += 1
    merge_prec = tp / (tp + fp) if (tp + fp) else 1.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    print("===== 打分结果 =====")
    print(f"  已打分 {scored} 对 (uncertain 排除 {skipped_uncertain}, 无预测 {no_pred})")
    print(f"  混淆: TP(真合)={tp}  FP(★错合)={fp}  FN(漏合)={fn}  TN(真分)={tn}")
    print(f"  merge precision = {merge_prec:.4f}   (验收线 ≥ {MERGE_PRECISION_LINE})")
    print(f"  recall          = {recall:.4f}   (可低, 宁碎片)")
    red_errs = errs_by_band.get("red", [])
    if errs_by_band:
        print("\n  ★错合明细(按 band):")
        for band, items in sorted(errs_by_band.items()):
            print(f"    {band}: {len(items)} — {[p for p, _ in items]}")
    # 验收判定
    print("\n===== 验收 =====")
    ok = True
    if merge_prec < MERGE_PRECISION_LINE:
        print(
            f"  ✗ FAIL: merge precision {merge_prec:.4f} < {MERGE_PRECISION_LINE} — 出现错合,地基污染"
        )
        ok = False
    if red_errs:
        print(f"  ✗ FAIL: red band 高危陷阱错合 {len(red_errs)} 个 — 零容忍")
        ok = False
    if ok:
        print(f"  ✓ PASS: 错合近零 (precision {merge_prec:.4f}); recall {recall:.4f} 不设下限")
    return ok


def main():
    gold = load_gold()
    if not gold:
        print("金集为空: 缺 gold_seed.jsonl 或 candidates 未标注", file=sys.stderr)
        sys.exit(2)
    if "--pred" in sys.argv:
        pred_path = sys.argv[sys.argv.index("--pred") + 1]
        ok = score(gold, pred_path)
        sys.exit(0 if ok else 1)
    else:
        coverage(gold)


if __name__ == "__main__":
    main()
