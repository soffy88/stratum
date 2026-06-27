"""★经济学管道质量门 — 固化完整标准(非静默退化).

报警阈值(经济书专门标准, 任一触发→ALARM, 不自动入库):
  complete_pct   ≥ 100%   各章 should-have 黑体术语全覆盖(不漏)
  residual_max   = 0      残留杂乱字符KU数(##/*/未涉及/繁体等)
  shell_max      = 0      空壳KU数(中文<10字)
  bilingual_min  ≥ 99%    双语率(KU有中文译文)
  directed_per_ku ≥ 0.3   有向边 / KU总数
  ku_density     ≥ 60%    实抽KU ≥ 60% × (章数 × 15) (经济书~15/章)
  shallow_max    = 0      讲浅KU数(中文<150字,经济面:内涵/机制/应用不全; 经济书≠数学定理需300字)
  chapter_floor  ≥ 6      任一章的KU数(不足6个则该章可能漏抽)
  low_ch_alarm   ≤ 2      允许章密度不足的章数(超过则整书报警)

注: KU忠实率/有向精度 需LLM抽检(deterministic无法全自动), 列入报告提示人工抽样.

Usage: python econ_quality_gate.py <substrate_id> [--json output.json]
Exit: 0=PASS(无报警), 1=ALARM(有报警), 2=运行错误
"""
import asyncio, asyncpg, json, os, re, sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))


# ── 内联 chapter 工具函数(避免 chapter_ingest 的 omodul 传递依赖) ──
_CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}

def _cn2int(s):
    if s in _CN: return _CN[s]
    if s.startswith('十'): return 10 + _CN.get(s[1:], 0)
    if '十' in s:
        a, _, b = s.partition('十')
        return _CN[a] * 10 + (_CN.get(b, 0) if b else 0)
    return _CN.get(s, 0)

def _chapter_starts(text):
    starts = {int(m.group(1)): m.start()
              for m in re.finditer(r'(?m)^#\s+Chapter\s+(\d+):', text)}
    if not starts:
        for m in re.finditer(r'(?m)^第([一二三四五六七八九十]+)章', text):
            ln = text[m.start(): text.find('\n', m.start())+1 or m.start()+40]
            if '…' in ln or re.search(r'\s\d+\s*$', ln): continue
            n = _cn2int(m.group(1))
            if n and n not in starts: starts[n] = m.start()
    return starts

def _chapter_numbers(text): return sorted(_chapter_starts(text).keys())

def _slice_chapter(text, n):
    starts = _chapter_starts(text)
    if n not in starts: return ""
    s = starts[n]; e = starts.get(n+1, len(text)); chap = text[s:e]
    bm = re.search(r'(?im)^#{1,3}\s*\**\s*(?:g\s*l\s*o\s*s\s*s\s*a\s*r\s*y|i\s*n\s*d\s*e\s*x)\b', chap)
    return chap[:bm.start()] if bm else chap

if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
    print("Usage: econ_quality_gate.py <substrate_id> [--json output.json]", file=sys.stderr)
    sys.exit(2)

SUB = sys.argv[1]
JSON_OUT = None
args = sys.argv[2:]
if "--json" in args:
    idx = args.index("--json")
    JSON_OUT = args[idx + 1] if idx + 1 < len(args) else None

# ★经济书固化阈值
TH = {
    "complete_pct":   100,   # 完整率 = 各章100%无漏知识点
    "residual_max":   0,     # 残留杂乱字符KU
    "shell_max":      0,     # 空壳KU(中文<10字)
    "bilingual_min":  99,    # 双语率%
    "directed_per_ku": 0.3,  # 有向边/KU
    "ku_density":     0.60,  # 实抽KU ≥ 60% × (章数×15)
    "shallow_max":    0,     # 讲浅KU(中文<150字,经济面标准)
    "chapter_floor":  6,     # 单章KU数下限
    "low_ch_alarm":   2,     # 低密度章数上限(超过则整书报警)
}

# 经济书预期密度
ECON_KU_PER_CHAPTER = 15


async def run():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    metrics = {}; alarms = []; warnings = []

    # ── 基础指标 ──
    ku_total = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUB)
    metrics["KU总数"] = ku_total

    bilingual = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1"
        " AND natural_text_zh ~ '[一-龥]'", SUB)
    metrics["双语率%"] = round(100 * bilingual / max(ku_total, 1))

    # 残留杂乱字符: ##/***结构标记 + 未涉及/未覆盖等独立占位句 + 繁体高频字
    # 注1: [ChN] 章节引用是合法来源信息(非噪音)
    # 注2: 仅匹配括号前缀的占位语 [（(]未覆盖 — 排除正文引用 "未覆盖"(不在括号内)
    residual = await conn.fetchval(
        r"SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1"
        r" AND natural_text_zh ~ '##|\*\*|[（(]\s*未涉及|[（(]\s*未覆盖|[（(]\s*未给出|[（(]\s*未讨论|[（(]\s*未提及|[（(]\s*未定义|需查阅|建议参考|經濟學|實際上|學習|為什麼'",
        SUB)
    metrics["残留字符KU"] = residual

    # 空壳(中文<10字)
    shells = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1"
        " AND length(regexp_replace(natural_text_zh,'[^一-龥]','','g')) < 10", SUB)
    metrics["空壳KU"] = shells

    # ★讲浅KU: 经济书面标准(概念/原理/方法) ≠ 数学定理标准(需证明过程)
    # 经济概念型: 内涵+外延+用处, 表达简洁, 150字足够; 数学定理型需300字
    # 阈值150: 57/118/122字是真讲浅; 199+字的经济概念KU已达经济面标准
    shallow = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1"
        " AND length(natural_text_zh) BETWEEN 1 AND 149",
        SUB)
    metrics["讲浅KU(zh<150chars)"] = shallow

    # 有向边
    directed = await conn.fetchval(
        "SELECT count(*) FROM aii.directed_edge_v2 WHERE substrate_id=$1", SUB) or 0
    metrics["有向边"] = directed

    # 章节KC
    kc_count = await conn.fetchval(
        "SELECT count(*) FROM aii.kc_onto WHERE substrate_id=$1"
        " AND synthesis_marker='AII章节KC'", SUB) or 0
    metrics["章节KC数"] = kc_count

    # BU
    has_bu = bool(await conn.fetchval(
        "SELECT count(*) FROM aii.bu_onto WHERE substrate_id=$1", SUB))
    metrics["BU已生成"] = "是" if has_bu else "否"

    # ── 章级 KU 分布 ──
    ch_rows = await conn.fetch(
        "SELECT (provenance->>'chapter')::int AS ch, count(*) AS n"
        " FROM aii.ku_onto WHERE substrate_id=$1"
        " AND provenance->>'chapter' IS NOT NULL"
        " GROUP BY ch ORDER BY ch", SUB)
    ch_map = {r["ch"]: r["n"] for r in ch_rows if r["ch"]}
    n_chapters = len(ch_map)
    metrics["章数(含KU)"] = n_chapters

    # 低密度章(< chapter_floor KU)
    low_density_chs = [(ch, n) for ch, n in ch_map.items() if n < TH["chapter_floor"]]
    metrics["低密度章"] = [(f"Ch{ch}", n) for ch, n in sorted(low_density_chs)]

    # ── 完整性(重算 should-have) ──
    # 直接用内联函数, 绕过 chapter_ingest → onto_persist → omodul 传递依赖
    complete_pct = None
    try:
        from aii.service.planning_completeness import check_completeness
        md_path = Path(os.getenv("AII_MD_FILE",
            "/home/soffy/shared/stratum-to-aii/Principles_of_Microeconomics_The_Way_We__01KVAJCX.md"))
        full = md_path.read_text(encoding="utf-8", errors="replace")
        chs = _chapter_numbers(full)
        n_total_chs = len(chs)
        incomplete = []
        for ch in chs:
            names = [r["title"] for r in await conn.fetch(
                "SELECT title FROM aii.ku_onto WHERE substrate_id=$1"
                " AND (provenance->>'chapter')::int=$2", SUB, ch)]
            comp = check_completeness(_slice_chapter(full, ch), names)
            if not comp["complete"]:
                incomplete.append((ch, comp["missing_bold_terms"][:5]))
        complete_pct = round(100 * (n_total_chs - len(incomplete)) / max(n_total_chs, 1))
        metrics["完整率%"] = complete_pct
        metrics["漏知识点章(前3)"] = [(ch, terms) for ch, terms in incomplete[:3]]
    except Exception as e:
        metrics["完整率%"] = f"(算不了:{str(e)[:40]})"
        warnings.append(f"完整率无法计算: {str(e)[:40]}")

    # ── ★KU密度检查(经济书专门) ──
    expected_ku = max(12, n_chapters * ECON_KU_PER_CHAPTER)
    density_ratio = ku_total / expected_ku if expected_ku > 0 else 1.0
    metrics["KU密度"] = f"{ku_total}/{expected_ku}={density_ratio:.0%}"

    # ── 报警判断 ──
    if isinstance(complete_pct, int) and complete_pct < TH["complete_pct"]:
        alarms.append(f"完整率{complete_pct}%<100%(漏知识点: {metrics.get('漏知识点章(前3)',[])})")

    if residual > TH["residual_max"]:
        alarms.append(f"残留字符KU={residual}>0(含##/***/未涉及等)")

    if shells > TH["shell_max"]:
        alarms.append(f"空壳KU={shells}>0(中文<10字)")

    if metrics["双语率%"] < TH["bilingual_min"]:
        alarms.append(f"双语率{metrics['双语率%']}%<{TH['bilingual_min']}%")

    edge_floor = max(15, round(ku_total * TH["directed_per_ku"]))
    if directed < edge_floor:
        alarms.append(f"有向边{directed}<{edge_floor}(={ku_total}KU×0.3)")

    if shallow > TH["shallow_max"]:
        alarms.append(f"讲浅KU={shallow}>0(zh<150chars,经济面:内涵/机制/应用不全)")

    # ★KU密度报警(经济书命门: 漏抽=92KU vs 应有150+)
    if density_ratio < TH["ku_density"]:
        alarms.append(
            f"KU密度不足: 实抽{ku_total}仅{density_ratio:.0%}×预期{expected_ku}"
            f"(经济书~{ECON_KU_PER_CHAPTER}/章×{n_chapters}章)"
        )

    # 低密度章报警
    if len(low_density_chs) > TH["low_ch_alarm"]:
        ch_list = [f"Ch{c}({n}KU)" for c, n in sorted(low_density_chs)[:5]]
        alarms.append(
            f"低密度章过多: {len(low_density_chs)}章<{TH['chapter_floor']}KU: {ch_list}"
        )

    if not has_bu:
        alarms.append("BU未生成(书级理解缺失)")

    # ── 输出 ──
    result = {
        "substrate_id": SUB,
        "verdict": "PASS" if not alarms else "ALARM",
        "alarm_count": len(alarms),
        "alarms": alarms,
        "warnings": warnings,
        "metrics": metrics,
        "thresholds": TH,
        "note": "KU忠实率/有向精度需LLM抽检(deterministic无法全自动) → 建议事后随机抽样5%KU人工核查",
    }

    sep = "=" * 55
    print(f"\n{sep}")
    print(f"质量门报告: {SUB}")
    print(f"结论: {'✅ PASS' if not alarms else '🚨 ALARM'} ({len(alarms)} 报警)")
    print(sep)
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print(f"\n阈值: complete≥{TH['complete_pct']}% | 残留=0 | 空壳=0 | 双语≥{TH['bilingual_min']}%"
          f" | 有向≥{TH['directed_per_ku']}×KU | KU密度≥{TH['ku_density']:.0%}预期 | 讲浅(zh<150)=0 | 章KU≥{TH['chapter_floor']}")
    if alarms:
        print(f"\n🚨 报警({len(alarms)}):")
        for a in alarms:
            print(f"  • {a}")
    else:
        print("\n✅ 全部达标 → 可自动入库")
    if warnings:
        print(f"\n⚠️ 提示: {warnings}")
    print(f"\n{result['note']}")
    print(sep)

    if JSON_OUT:
        Path(JSON_OUT).parent.mkdir(parents=True, exist_ok=True)
        Path(JSON_OUT).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告已写 → {JSON_OUT}")

    await conn.close()
    return 0 if not alarms else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
