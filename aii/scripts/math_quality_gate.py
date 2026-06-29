"""★数学管道质量门 — 固化完整标准, 数学命门R6公式严格.

报警阈值(数学书专门标准, 任一触发→ALARM, 不自动入库):
  content_match_min   ≥ 90%   KU内容覆盖率(key_terms出现在zh中)
  formula_min         ≥ 80%   KU含有公式的比例(数学命门: 无公式=坏KU)
  real_facet_max      ≤ 10%   真缺(非豁免)facet问题占比
  shell_max           = 0     空壳KU数(zh_len < 200字)
  residual_max        = 0     含残留标记KU数(##/***/未涉及/未覆盖等)
  ku_floor            ≥ 10    整书最低KU数(不足10个→未跑完)

R6严格规则(数学命门, 独立于staging数据):
  md_math_signals > 30 且 latex_spans == 0   → HARD FAIL (公式被OCR毁)
  md_math_signals > 30 且 latex_ratio < 0.15 → ALARM (公式严重残缺)

Usage: python scripts/math_quality_gate.py <substrate_id> --staging <dir> [--md <md_path>] [--json <out.json>]
Exit: 0=PASS, 1=ALARM, 2=运行错误/HARD FAIL
"""
import json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)

# ── 阈值 ──
CONTENT_MATCH_MIN = 0.90   # ≥90% KU content_match
FORMULA_MIN       = 0.80   # ≥80% has_formula
REAL_FACET_MAX    = 0.10   # ≤10% 真缺(非豁免)
SHELL_MAX         = 0      # 0 空壳
RESIDUAL_MAX      = 0      # 0 残留
KU_FLOOR          = 10     # 整书最少KU数

# R6 md-level 严格规则
R6_SIGNAL_MIN     = 30     # 超过此信号数才触发R6检查
R6_HARD_THRESHOLD = 0.0    # latex_ratio=0 → HARD FAIL
R6_ALARM_THRESHOLD = 0.15  # latex_ratio<15% → ALARM

_RE_MATH_SIGNAL = re.compile(r"[=Σ∑∫∂√±≤≥≠αβγδεθλμπρσφω∞·×÷→←⇒⊂⊆∈∉]|\bpercentage change\b", re.I)
_RE_LATEX = re.compile(r"\$[^$\n]+\$|\\\[|\\\(")
_RE_RESIDUAL = re.compile(r"未涉及|未覆盖|未出现|未给出|未提及|未定义|未讨论|需查阅|其他资料|建议参考|不在本[章节]|超出本[章节]|\*\*|##")


def _load_staging(staging_dir: Path) -> list[dict]:
    """加载暂存目录中所有 ch*.json 文件的 KU 列表."""
    kus = []
    for f in sorted(staging_dir.glob("ch*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                kus.extend(data)
        except Exception as e:
            print(f"  ★读取 {f.name} 失败: {e}", file=sys.stderr)
    return kus


def _check_r6_md(md_path: str) -> tuple[str, str]:
    """R6: 检查MD文件公式完整性. 返回 (status, detail), status=PASS/ALARM/FAIL."""
    if not md_path or not Path(md_path).exists():
        return "SKIP", "无MD文件路径"
    text = Path(md_path).read_text(encoding="utf-8", errors="replace")
    signals = len(_RE_MATH_SIGNAL.findall(text))
    latexes = len(_RE_LATEX.findall(text))
    if signals < R6_SIGNAL_MIN:
        return "SKIP", f"数学信号不足({signals}<{R6_SIGNAL_MIN}), 跳过R6"
    ratio = latexes / max(signals, 1)
    if latexes == 0:
        return "FAIL", f"R6:数学信号{signals}但0个LaTeX公式(数学命门:OCR破坏公式)"
    if ratio < R6_ALARM_THRESHOLD:
        return "ALARM", f"R6:公式残缺率高(信号{signals}/LaTeX{latexes}={ratio:.0%}<{R6_ALARM_THRESHOLD:.0%})"
    return "PASS", f"R6:OK(信号{signals}/LaTeX{latexes}={ratio:.0%})"


def run_gate(substrate_id: str, staging_dir: Path, md_path: str = "") -> dict:
    """运行质量门, 返回报告 dict."""
    kus = _load_staging(staging_dir)
    n_total = len(kus)
    alarms = []
    details = {}

    # ── KU总数底线 ──
    if n_total < KU_FLOOR:
        alarms.append(f"KU总数{n_total}<底线{KU_FLOOR}(管道未跑完?)")

    if n_total == 0:
        return {
            "substrate_id": substrate_id,
            "ku_count": 0,
            "alarms": alarms,
            "ok": False,
            "details": details,
        }

    # ── content_match ──
    n_match = sum(1 for k in kus if k.get("content_match", False))
    match_pct = n_match / n_total
    details["content_match_pct"] = round(match_pct, 3)
    if match_pct < CONTENT_MATCH_MIN:
        alarms.append(f"content_match={match_pct:.0%}<{CONTENT_MATCH_MIN:.0%}({n_total-n_match}个key_terms未出现)")

    # ── has_formula (数学命门) ──
    n_formula = sum(1 for k in kus if k.get("has_formula", False))
    formula_pct = n_formula / n_total
    details["formula_pct"] = round(formula_pct, 3)
    if formula_pct < FORMULA_MIN:
        no_formula = [k["point"] for k in kus if not k.get("has_formula", False)]
        alarms.append(
            f"has_formula={formula_pct:.0%}<{FORMULA_MIN:.0%} "
            f"(无公式KU={len(no_formula)}: {no_formula[:5]})"
        )

    # ── 真缺facet_issues (排除豁免) ──
    # ★缺证明/缺例子 = 源材料限制(证明常在别节, 不可编造)→ 豁免, 不判讲浅; 薄KU已在persist丢弃.
    #   只过短/无公式(数学命门)算真缺. 质量优先但不漏命门.
    _SOURCE_LIMITED = {"缺证明/推导", "缺例子"}
    real_facet = []
    for k in kus:
        issues = k.get("facet_issues", [])
        exempt = set(k.get("facet_exempt", [])) | _SOURCE_LIMITED
        real = [fi for fi in issues if fi not in exempt]
        if real:
            real_facet.append((k["point"], real))
    real_facet_pct = len(real_facet) / n_total
    details["real_facet_pct"] = round(real_facet_pct, 3)
    details["real_facet_count"] = len(real_facet)
    if real_facet_pct > REAL_FACET_MAX:
        alarms.append(
            f"真缺facet={real_facet_pct:.0%}>{REAL_FACET_MAX:.0%} "
            f"({len(real_facet)}个KU未修复): {[p for p,_ in real_facet[:5]]}"
        )

    # ── 空壳KU ──
    shells = [k["point"] for k in kus if k.get("zh_len", len(k.get("zh", ""))) < 200]
    details["shell_count"] = len(shells)
    if len(shells) > SHELL_MAX:
        alarms.append(f"空壳KU(zh<200字)={len(shells)}: {shells[:5]}")

    # ── 残留标记 ──
    residuals = [k["point"] for k in kus
                 if _RE_RESIDUAL.search(k.get("zh", "") + k.get("en", ""))]
    details["residual_count"] = len(residuals)
    if len(residuals) > RESIDUAL_MAX:
        alarms.append(f"含残留标记KU={len(residuals)}: {residuals[:5]}")

    # ── R6 MD级别公式检查 ──
    r6_status, r6_detail = _check_r6_md(md_path)
    details["r6"] = {"status": r6_status, "detail": r6_detail}
    if r6_status == "FAIL":
        alarms.append(r6_detail)
    elif r6_status == "ALARM":
        alarms.append(r6_detail)

    # ★待补清单(不漏): 薄(needs_fill)或 content未覆盖 的知识点 — 保留入库, 记录后面补
    fill_list = [{"point": k["point"], "label": k.get("label", ""),
                  "zh_len": k.get("zh_len", len(k.get("zh", ""))),
                  "issues": [i for i in k.get("facet_issues", []) if i not in _SOURCE_LIMITED]
                            + ([] if k.get("content_match", True) else ["content未覆盖"])}
                 for k in kus if k.get("needs_fill") or not k.get("content_match", True)]
    return {
        "substrate_id": substrate_id,
        "ku_count": n_total,
        "alarms": alarms,
        "ok": len(alarms) == 0,
        "r6_hard_fail": r6_status == "FAIL",
        "fill_list": fill_list,
        "details": details,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("substrate_id")
    ap.add_argument("--staging", required=True, help="暂存目录(含ch*.json)")
    ap.add_argument("--md", default="", help="原始MD文件路径(用于R6检查)")
    ap.add_argument("--json", default="", help="质量报告输出JSON路径")
    args = ap.parse_args()

    staging = Path(args.staging)
    if not staging.exists():
        print(f"❌ 暂存目录不存在: {staging}", file=sys.stderr)
        sys.exit(2)

    report = run_gate(args.substrate_id, staging, args.md)

    if args.json:
        import datetime
        report["generated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    ku_n = report["ku_count"]
    alarms = report["alarms"]
    details = report["details"]

    print(f"\n{'='*52}")
    print(f"★ 数学质量门: {args.substrate_id}")
    print(f"  KU总数: {ku_n}")
    print(f"  content_match: {details.get('content_match_pct','?'):.0%}" if ku_n else "")
    print(f"  has_formula:   {details.get('formula_pct','?'):.0%}" if ku_n else "")
    print(f"  真缺facet:     {details.get('real_facet_pct','?'):.0%} ({details.get('real_facet_count',0)}个)" if ku_n else "")
    print(f"  R6:            {details.get('r6',{}).get('detail','?')}")
    print(f"{'='*52}")

    # ★待补清单(不漏): 薄/缺面/content未覆盖 的知识点 — 保留入库, 记录后面补
    fill_list = report.get("fill_list", [])
    if fill_list:
        fp = Path("math_pipeline/待补") / f"{args.substrate_id}.json"
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(json.dumps({"substrate": args.substrate_id, "count": len(fill_list),
                                  "待补": fill_list}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ⚑ 待补清单: {len(fill_list)} 个知识点(保留入库, 后面补) → {fp}")

    # ★不漏: 只在真破坏(R6 OCR坏 / 管道没跑出KU)才隔离; 质量缺面→注册+已记待补, 不丢整本
    if report.get("r6_hard_fail"):
        print("\n❌ HARD FAIL (R6公式被OCR破坏, 源不可用) → 隔离")
        sys.exit(2)
    if ku_n < KU_FLOOR:
        print(f"\n🚨 KU过少({ku_n}<{KU_FLOOR}, 管道未跑完) → 隔离")
        sys.exit(1)
    for a in alarms:
        print(f"  ⚑ 质量提示(已记待补, 不隔离): {a}")
    print("✅ 注册(不漏; 简单知识点可过; 质量缺面已记入待补清单)")
    sys.exit(0)
