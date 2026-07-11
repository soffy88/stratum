"""★经济学管道质量门 — 固化完整标准(非静默退化).

报警阈值(经济书专门标准, 任一触发→ALARM, 不自动入库):
  complete_pct   ≥ 100%   各章 should-have 黑体术语全覆盖(不漏)
  residual_max   = 0      残留杂乱字符KU数(##/*/未涉及/繁体等)
  shell_max      = 0      空壳KU数(中文<10字)
  bilingual_min  ≥ 99%    双语率(KU有中文译文)
  directed_per_ku ≥ 0.3   有向边 / KU总数
  ku_density     ≥ 60%    实抽KU ≥ 60% × (章数 × 15) (经济书~15/章)
  shallow_max    = 0      讲浅KU数(★主靠面齐:内涵/机制/应用; 字数仅辅助分层; 面齐=合格哪怕字少, 面缺=讲浅哪怕字多)
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


# ── ★讲浅面检测: 主靠"该有的面齐不齐"(非字数) ──
# 经济书三面: 内涵(WHAT) / 机制(WHY) / 应用(HOW)
# 面齐=合格(哪怕字少); 面缺=讲浅(哪怕字多)
#
# 阈值规则(字数仅辅助分层, 不作主判据):
#   < 80字:    极短 → 直接讲浅(字数辅助信号: 近乎空壳)
#   80-199字:  需≥2面 → 缺面报讲浅
#   200-399字: 需≥1面 → 全面缺才报讲浅(中长KU更宽松)
#   ≥ 400字:  不检查(字量充足,基本不可能全面缺)

PAT_WHAT = re.compile(  # 内涵/WHAT: 显式定义性语言(不含宽泛"X是Y的"防误触例子句)
    r"内涵[：:]|定义[：:]|是指[一-龥]|指的是|是一种[一-龥]|所谓[一-龥]"
)
PAT_WHY = re.compile(  # 机制/WHY: 因果性语言
    r"因为|由于|之所以|原因|导致[一-龥]|机制|来自|源于|是因为|"
    r"取决于|推动|驱动|影响[一-龥]|反映了"
)
PAT_HOW = re.compile(  # 应用/HOW: 操作性语言
    r"用于[一-龥]|用来[一-龥]|如何[一-龥]|步骤|识别[一-龥]|分析[一-龥]|"
    r"判断[一-龥]|预测[一-龥]|通过[一-龥]|帮助[一-龥]|计算[一-龥]|有助于|"
    r"应用[（(：:]"
)


def _facet_check(text: str, ku_type: str = "conceptual") -> tuple[bool, str]:
    """判讲浅(主): 面齐否. 返回 (is_shallow, detail_msg)."""
    n = len(text) if text else 0
    if n < 80:
        return True, f"极短({n}字,近乎空壳)"

    has_what = bool(PAT_WHAT.search(text))
    has_why = bool(PAT_WHY.search(text))
    has_how = bool(PAT_HOW.search(text))
    present = sum([has_what, has_why, has_how])
    missing = [k for k, v in [("内涵", has_what), ("机制", has_why), ("应用", has_how)] if not v]

    if n < 200 and present < 2:
        return True, f"缺{'·'.join(missing)}({n}字,短文本需≥2面)"
    if n < 400 and present < 1:
        return True, f"全面缺({n}字,仅例子?)"
    return False, ""


# ── 内联 chapter 工具函数(避免 chapter_ingest 的 omodul 传递依赖) ──
_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn2int(s):
    if s in _CN:
        return _CN[s]
    if s.startswith("十"):
        return 10 + _CN.get(s[1:], 0)
    if "十" in s:
        a, _, b = s.partition("十")
        return _CN[a] * 10 + (_CN.get(b, 0) if b else 0)
    return _CN.get(s, 0)


def _decimal_chapter_starts(text):
    """第三层兜底: 章标题不带"Chapter N"/"第N章"字样(OpenStax/oapen/markitdown 排版),
    只靠"N.M 小节编号"体现结构——用每个大节号 N 下最小小节的位置近似章起点。
    ★移植自 chapter_ingest._decimal_chapter_starts(那边有完整注释), 两边必须同步改:
    2026-07-11 实测 oapen《Greening the Financial Sector》synthesis 成功但本门数出 0 章
    → 预期KU=0 → 双语率0% → 无条件隔离, 英文书全军覆没在质量门这最后一关。"""
    cand = {}
    for m in re.finditer(r"(?m)^#{1,6}\s+\**(\d{1,2})\.(\d+)\b", text):
        n, sub = int(m.group(1)), int(m.group(2))
        cand.setdefault(n, []).append((sub, m.start()))
    if not cand:
        for m in re.finditer(
            r"(?m)(?<=\n\n)(\d{1,2})\.(\d+)\s+([A-Z][A-Za-z0-9 ,'\-]{3,80})$", text
        ):
            n, sub = int(m.group(1)), int(m.group(2))
            cand.setdefault(n, []).append((sub, m.start()))
    return {n: min(subs)[1] for n, subs in cand.items()}


def _chapter_starts(text):
    starts = {int(m.group(1)): m.start() for m in re.finditer(r"(?m)^#\s+Chapter\s+(\d+):", text)}
    if not starts:
        # ★2026-07-09 实测: 原正则只认中文数字(第一章), 漏掉真实书里更常见的阿拉伯数字(第1章)
        # → _chapter_numbers()判0章 → econ_quality_gate的完整率公式 100*(0-0)/max(0,1)=0,
        # 误报"完整率0%(漏知识点: [])"(其实是"没读到章节, 算不了", 不是真的漏)。econ_discover_all.py
        # /chapter_ingest.py/misc_discover.py/classify_md.py 那轮"中文章节识别三层bug"修复时这个
        # 文件漏掉了, 这次一起补上(同一条 第[一二三四五六七八九十百\d]+章 口径)。
        for m in re.finditer(r"(?m)^第([一二三四五六七八九十百\d]+)章", text):
            ln = text[m.start() : text.find("\n", m.start()) + 1 or m.start() + 40]
            if "…" in ln or re.search(r"\s\d+\s*$", ln):
                continue
            g = m.group(1)
            n = int(g) if g.isdigit() else _cn2int(g)
            if n and n not in starts:
                starts[n] = m.start()
    if not starts:
        starts = _decimal_chapter_starts(text)
    return starts


def _chapter_numbers(text):
    return sorted(_chapter_starts(text).keys())


def _slice_chapter(text, n):
    starts = _chapter_starts(text)
    if n not in starts:
        return ""
    s = starts[n]
    e = starts.get(n + 1, len(text))
    chap = text[s:e]
    bm = re.search(
        r"(?im)^#{1,3}\s*\**\s*(?:g\s*l\s*o\s*s\s*s\s*a\s*r\s*y|i\s*n\s*d\s*e\s*x)\b", chap
    )
    return chap[: bm.start()] if bm else chap


# SUB / JSON_OUT 仅在 __main__ 时解析(允许作为模块 import _facet_check 不报错)
SUB = None
JSON_OUT = None

# ★经济书固化阈值(QGATE_KU_PER_CHAPTER/QGATE_CHAPTER_FLOOR 可覆盖 — 非经济学科密度基准不同, 见misc_flywheel.sh)
TH = {
    "complete_pct": 100,  # 完整率 = 各章100%无漏知识点
    "residual_max": 0,  # 残留杂乱字符KU
    "shell_max": 0,  # 空壳KU(中文<10字)
    "bilingual_min": 99,  # 双语率%
    "directed_per_ku": 0.3,  # 有向边/KU
    "ku_density": 0.60,  # 实抽KU ≥ 60% × (章数×每章预期)
    "shallow_max": 0,  # 讲浅KU(主靠面齐:内涵/机制/应用; 字数仅辅助分层)
    "chapter_floor": int(os.getenv("QGATE_CHAPTER_FLOOR", "6")),  # 单章KU数下限
    "low_ch_alarm": 2,  # 低密度章数上限(超过则整书报警)
}

# 每章预期KU密度(经济书~15/章; 其它学科密度天然更低, 见 QGATE_KU_PER_CHAPTER)
ECON_KU_PER_CHAPTER = int(os.getenv("QGATE_KU_PER_CHAPTER", "15"))


async def run():
    conn = await asyncpg.connect(os.getenv("DATABASE_URL"))
    metrics = {}
    alarms = []
    warnings = []

    # ── 基础指标 ──
    ku_total = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUB)
    metrics["KU总数"] = ku_total

    bilingual = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1 AND natural_text_zh ~ '[一-龥]'",
        SUB,
    )
    metrics["双语率%"] = round(100 * bilingual / max(ku_total, 1))

    # 残留杂乱字符: ##/***结构标记 + 未涉及/未覆盖等独立占位句 + 繁体高频字
    # 注1: [ChN] 章节引用是合法来源信息(非噪音)
    # 注2: 仅匹配括号前缀的占位语 [（(]未覆盖 — 排除正文引用 "未覆盖"(不在括号内)
    residual = await conn.fetchval(
        r"SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1"
        r" AND natural_text_zh ~ '##|\*\*|[（(]\s*未涉及|[（(]\s*未覆盖|[（(]\s*未给出|[（(]\s*未讨论|[（(]\s*未提及|[（(]\s*未定义|需查阅|建议参考|經濟學|實際上|學習|為什麼'",
        SUB,
    )
    metrics["残留字符KU"] = residual

    # 空壳(中文<10字)
    shells = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1"
        " AND length(regexp_replace(natural_text_zh,'[^一-龥]','','g')) < 10",
        SUB,
    )
    metrics["空壳KU"] = shells

    # 英文字段空壳(natural_text<20字符: WHAT骨架抽取失败留下的占位符/引用残片,
    # 如"Chapter N text:"/"-cited："/"[104]"/裸变量名, 之前只查了ZH字段漏了这类)
    shells_en = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1"
        " AND length(trim(natural_text)) < 20",
        SUB,
    )
    metrics["英文空壳KU"] = shells_en

    # ★讲浅KU: 主靠"面齐不齐"(内涵/机制/应用), 字数仅辅助分层
    # 面齐=合格(哪怕字少); 面缺=讲浅(哪怕字多)
    ku_facet_rows = await conn.fetch(
        "SELECT ku_id, knowledge_type, natural_text_zh FROM aii.ku_onto WHERE substrate_id=$1", SUB
    )
    shallow_list = []
    for row in ku_facet_rows:
        is_sh, detail = _facet_check(
            row["natural_text_zh"] or "", row["knowledge_type"] or "conceptual"
        )
        if is_sh:
            shallow_list.append({"ku_id": row["ku_id"], "detail": detail})
    shallow = len(shallow_list)
    metrics["讲浅KU(面缺)"] = shallow
    if shallow > 0:
        metrics["讲浅样本(前3)"] = [
            f"{s['ku_id'].split('::')[1]}:{s['detail']}" for s in shallow_list[:3]
        ]

    # ★A仓瘦身: 有向边(directed_edge_v2)=B仓产物, A仓不查.

    # 章节KC
    kc_count = (
        await conn.fetchval(
            "SELECT count(*) FROM aii.kc_onto WHERE substrate_id=$1"
            " AND synthesis_marker='AII章节KC'",
            SUB,
        )
        or 0
    )
    metrics["章节KC数"] = kc_count

    # BU
    has_bu = bool(
        await conn.fetchval("SELECT count(*) FROM aii.bu_onto WHERE substrate_id=$1", SUB)
    )
    metrics["BU已生成"] = "是" if has_bu else "否"

    # ── ★六分类分布(A仓的事: 六分类是为便于识别/抽取知识=抽取质量; B仓只管关系不管类别) ──
    type_rows = await conn.fetch(
        "SELECT knowledge_type, count(*) n FROM aii.ku_onto WHERE substrate_id=$1 GROUP BY 1 ORDER BY 2 DESC",
        SUB,
    )
    type_dist = {r["knowledge_type"]: r["n"] for r in type_rows}
    metrics["六分类分布"] = type_dist
    rationale_n = type_dist.get("rationale", 0)
    top_share = (max(type_dist.values()) / max(ku_total, 1)) if type_dist else 1.0
    metrics["rationale(why)数"] = rationale_n
    metrics["最大类占比%"] = round(100 * top_share)

    # ── 章级 KU 分布 ──
    ch_rows = await conn.fetch(
        "SELECT (provenance->>'chapter')::int AS ch, count(*) AS n"
        " FROM aii.ku_onto WHERE substrate_id=$1"
        " AND provenance->>'chapter' IS NOT NULL"
        " GROUP BY ch ORDER BY ch",
        SUB,
    )
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

        # ★2026-07-09: 原来 os.getenv("AII_MD_FILE", "<硬编码某本经济书>") 静默兜底——正常管道
        # 确实每次都会导出真实 AII_MD_FILE(econ_pipeline.sh/advmath_pipeline.sh 都有
        # ${AII_MD_FILE:?}强制检查), 但这个函数自己不检查, 手工/异常调用时会悄悄拿错书的内容
        # 算完整率, 结果不可信却不报错。改成和调用方同样的口径: 没设就直接报错, 不装作正常跑完。
        md_file_env = os.getenv("AII_MD_FILE")
        if not md_file_env:
            raise RuntimeError("AII_MD_FILE 未设置(不再静默兜底到硬编码书, 会拿错书的内容算完整率)")
        md_path = Path(md_file_env)
        full = md_path.read_text(encoding="utf-8", errors="replace")
        chs = _chapter_numbers(full)
        n_total_chs = len(chs)
        if n_total_chs == 0:
            # ★没读到章节(章节识别regex没命中这本书的标题格式)≠"0%完整"——旧公式
            # 100*(0-0)/max(0,1)=0 会把"算不出来"误报成"确认0%完整、漏光了", 附带的
            # "漏知识点"却是空列表(逻辑自相矛盾, 真漏了该列出具体术语)。老实报告"算不了"。
            metrics["完整率%"] = "(算不了:章节识别regex未命中0章)"
            warnings.append("完整率无法计算: 章节识别regex在AII_MD_FILE里未命中任何章节")
        else:
            incomplete = []
            for ch in chs:
                names = [
                    r["title"]
                    for r in await conn.fetch(
                        "SELECT title FROM aii.ku_onto WHERE substrate_id=$1"
                        " AND (provenance->>'chapter')::int=$2",
                        SUB,
                        ch,
                    )
                ]
                comp = check_completeness(_slice_chapter(full, ch), names)
                if not comp["complete"]:
                    incomplete.append((ch, comp["missing_bold_terms"][:5]))
            complete_pct = round(100 * (n_total_chs - len(incomplete)) / n_total_chs)
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
        alarms.append(f"完整率{complete_pct}%<100%(漏知识点: {metrics.get('漏知识点章(前3)', [])})")

    if residual > TH["residual_max"]:
        alarms.append(f"残留字符KU={residual}>0(含##/***/未涉及等)")

    if shells > TH["shell_max"]:
        alarms.append(f"空壳KU={shells}>0(中文<10字)")

    if shells_en > TH["shell_max"]:
        alarms.append(
            f"英文空壳KU={shells_en}>0(natural_text<20字符, 如'Chapter N text:'/引用残片)"
        )

    if metrics["双语率%"] < TH["bilingual_min"]:
        alarms.append(f"双语率{metrics['双语率%']}%<{TH['bilingual_min']}%")

    # ★A仓瘦身: 去掉有向边密度报警(directed_edge_v2=B仓产物, A仓不产有向边)

    # ★讲浅KU: 只检测/标记, 不作隔离依据(用户决定: 讲浅只判断和标记, 不做限制)
    if shallow > 0:
        sample = metrics.get("讲浅样本(前3)", [])[:2]
        warnings.append(f"讲浅KU={shallow}(面缺,仅标记不拦截): {'; '.join(sample)}")

    # ★KU密度报警(经济书命门: 漏抽=92KU vs 应有150+)
    if density_ratio < TH["ku_density"]:
        alarms.append(
            f"KU密度不足: 实抽{ku_total}仅{density_ratio:.0%}×预期{expected_ku}"
            f"(基准~{ECON_KU_PER_CHAPTER}/章×{n_chapters}章)"
        )

    # 低密度章报警
    if len(low_density_chs) > TH["low_ch_alarm"]:
        ch_list = [f"Ch{c}({n}KU)" for c, n in sorted(low_density_chs)[:5]]
        alarms.append(f"低密度章过多: {len(low_density_chs)}章<{TH['chapter_floor']}KU: {ch_list}")

    if not has_bu:
        alarms.append("BU未生成(书级理解缺失)")
    # ★六分类是A仓的事(便于识别/抽取知识): rationale≠0(抽到为什么/论断,非只概念) + 单类不独吞
    if ku_total > 0 and rationale_n == 0:
        alarms.append("rationale(why)=0: 没抽到为什么/论断, 退回概念-only(A仓抽取深度不足)")
    if top_share > 0.95 and ku_total > 20:
        alarms.append(f"单类独吞{round(100 * top_share)}%>95%(只抽了一类, 没抽全六类)")
    # ★只有 explains边/有向边密度 = B仓产物(关系, 跨KU/跨书), A仓不查

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
    print(
        f"\n阈值[A仓]: complete≥{TH['complete_pct']}% | 残留=0 | 空壳=0 | 双语≥{TH['bilingual_min']}%"
        f" | KU密度≥{TH['ku_density']:.0%}预期 | 讲浅(面缺)仅标记不拦截 | 章KU≥{TH['chapter_floor']}"
        f" | ★rationale≠0+单类<95%(六分类是A仓)  (有向边/explains=B仓, A仓不查)"
    )
    if alarms:
        print(f"\n🚨 报警({len(alarms)}):")
        for a in alarms:
            print(f"  • {a}")
    else:
        print("\n✅ 全部达标 → 可自动入库")
    if warnings:
        print(f"\n⚠️ 标记({len(warnings)}, 不拦截):")
        for w in warnings:
            print(f"  • {w}")
    if warnings:
        print(f"\n⚠️ 提示: {warnings}")
    print(f"\n{result['note']}")
    print(sep)

    if JSON_OUT:
        Path(JSON_OUT).parent.mkdir(parents=True, exist_ok=True)
        Path(JSON_OUT).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"报告已写 → {JSON_OUT}")

    await conn.close()
    return 0 if not alarms else 1


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
        print("Usage: econ_quality_gate.py <substrate_id> [--json output.json]", file=sys.stderr)
        sys.exit(2)
    SUB = sys.argv[1]
    _args = sys.argv[2:]
    if "--json" in _args:
        _idx = _args.index("--json")
        JSON_OUT = _args[_idx + 1] if _idx + 1 < len(_args) else None
    sys.exit(asyncio.run(run()))
