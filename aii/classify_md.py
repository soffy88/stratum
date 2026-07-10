import os, re, glob, sys, shutil, subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
from book_identity import norm_stem  # noqa: E402

SRC = "/home/soffy/shared/stratum-to-aii"
DST = "/home/soffy/books/MD"
DO = "--do" in sys.argv  # 默认 dry-run


def _norm(s):  # 归一标题查重 — 统一走 book_identity.norm_stem(它比旧版多剥 _01KWXXXX
    # ULID 后缀, 正是 md_export 制造重复的根源, 如"微积分的力量"跨文件夹重复案例)。
    return norm_stem(s)


def _done_norms():
    """已完成清单(不再搬入,否则文件名不同→重复入库): 已有MD名 ∪ 已入库标题."""
    done = set()
    for f in glob.glob(f"{DST}/**/*.md", recursive=True):
        done.add(_norm(Path(f).stem))
    try:
        out = subprocess.run(
            [
                "docker",
                "exec",
                "aii-postgres",
                "psql",
                "-U",
                "aii",
                "-d",
                "aii_kg",
                "-tAc",
                "SELECT title FROM aii.ingested_substrate WHERE title IS NOT NULL",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout
        for t in out.splitlines():
            if t.strip():
                done.add(_norm(t))
    except Exception as e:
        print(f"  ⚠ 取已入库清单失败(只按MD去重): {e}", file=sys.stderr)
    return done


_DONE = _done_norms()


def _is_done(name):
    ns = _norm(Path(name).stem)
    if ns in _DONE:
        return True
    return any(len(e) >= 6 and (e in ns or ns in e) for e in _DONE)


ECON = [
    "经济",
    "市场",
    "需求",
    "供给",
    "价格",
    "成本",
    "货币",
    "资本",
    "利润",
    "通货",
    "宏观",
    "微观",
    "贸易",
    "金融",
    "投资",
    "边际",
    "弹性",
    "需求曲线",
    "gdp",
    "demand",
    "supply",
    "market",
    "price",
    "cost",
    "profit",
    "capital",
    "inflation",
    "macroeconom",
    "microeconom",
    "marginal",
    "elasticity",
    "fiscal",
    "monetary",
    "economy",
    "economic",
]
MATH = [
    "定理",
    "定义",
    "引理",
    "推论",
    "证明",
    "极限",
    "导数",
    "积分",
    "微分",
    "函数",
    "矩阵",
    "向量",
    "集合",
    "拓扑",
    "微积分",
    "数学分析",
    "方程",
    "级数",
    "收敛",
    "theorem",
    "lemma",
    "corollary",
    "calculus",
    "derivative",
    "integral",
    "differential",
    "matrix",
    "manifold",
    "topology",
    "algebra",
    "geometry",
    "convergence",
]

_GARBAGE = re.compile(
    r"^(下载|Return to top|GLOBAL EDITION|LONDON|.*版权声明|.*声明$|目录|封面|扉页|致谢|参考文献)",
    re.I,
)
_PAPER = re.compile(r"\(\d{4}\)|\bWP\b|\bAER\b|\bJEL\b|\bJOEG\b|\bAEJ\b| et al")  # 学术论文名

# ★A: EPUB→MD 残渣 — 标题行是 EPUB 内部 HTML 文件名(## text/part0000.html / ## index_split_000.html
#   / ## titlepage.xhtml), 而非规范章节。转换器(omodul)拿 EPUB 内部文件名当了标题, 需清洗。
_EPUB_HEADING = re.compile(r"(?m)^#{1,6}[ \t]+\S*\.(?:x?html)[ \t]*$")
_CH_MARK = re.compile(r"^(#*)[ \t]*(第[一二三四五六七八九十百\d]+章|Chapter\s+\d+)([ \t　]?.*)$")


def _clean_md(text):
    """A: 清洗 EPUB→MD 残渣。剥掉 EPUB HTML 文件名标题行, 把内文的 第X章/Chapter N 提为 # 一级标题。
    返回 (cleaned, changed)。仅在检测到 EPUB 残渣时清洗, 其余原样返回。"""
    if not _EPUB_HEADING.search(text):
        return text, False
    out = []
    for ln in text.split("\n"):
        if _EPUB_HEADING.match(ln):
            continue  # 剥掉 HTML 文件名标题行(噪声)
        m = _CH_MARK.match(ln)
        # 章节标记行(第X章/Chapter N 独占一行, 标题≤40字防误命中正文引用)且尚非 # 标题 → 提为 # 标题
        if m and not m.group(1) and len((m.group(3) or "").strip()) <= 40:
            out.append(f"# {m.group(2)}{m.group(3) or ''}")
        else:
            out.append(ln)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(out))
    return cleaned, True


def classify(path):
    name = Path(path).stem
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return ("SKIP", "读取失败", None)
    # ★A: EPUB→MD 残渣清洗(剥 HTML 文件名标题 + 规范章节标记); 后续判定与落盘都用清洗后文本
    text, _cleaned = _clean_md(text)
    _out = text if _cleaned else None  # 有清洗 → 落盘写清洗后文本; 否则原样搬
    n = len(text)
    samp = text[:300000]
    low = samp.lower()
    fffd = text.count("�")
    zh = len(re.findall(r"[一-鿿]", samp))
    en = len(re.findall(r"[A-Za-z]", samp))
    headings = len(re.findall(r"(?m)^#{1,4}\s", text))
    chaps = len(re.findall(r"(?m)^#{1,3}\s+\**Chapter\s+\d|^第[一二三四五六七八九十百\d]+章", text))
    # ★2026-07-06: 有些教材章节标题本身没有"Chapter N"/"第N章"字样(如Mathematics for Machine
    # Learning: 章节直接叫"Introduction and Motivation", 靠小节编号"1.1/2.1"体现结构), 上面
    # 那条正则永远抓不到, 判"无章节"→ 错分去其它(即便编号定理densely, 也进不了数学). 补一条:
    # 统计标题行里出现过的"N.M"小节编号, 不同的整数大节号N≥3个, 也算有章节结构。
    # ★但学术论文的"1. Introduction/2. Related Work"也是这个格式(实测撞过3篇论文被误判成
    # 教材)——用 frontmatter 的 doc_type 精确排除, 只对 doc_type!=paper 生效。
    decimal_ch = (
        0
        if "doc_type: paper" in text[:500]
        else len(set(int(m) for m in re.findall(r"(?m)^#{1,6}\s+\**(\d{1,2})\.\d+\b", text)))
    )
    # ── 品质门 ──
    if _GARBAGE.match(name) or len(name) < 4:
        return ("低质", "垃圾/碎片名", None)
    # ★2026-07-09 实测: _PAPER 文件名正则(WP/AER/JEL/(年份)/et al)只认旧式经济学工作论文
    # 命名, 抓不到 aii_feedback_service 自动订阅拉回来的 arxiv 论文(文件名是"标题截断+ULID后
    # 缀", 不带那些引用体式标记)——查真实数据: 84个单篇论文靠这条漏网, 全部错分进"其它"(章节
    # 教材专用文件夹), misc discover 的 chapters<3 门槛又把它们永久静默跳过, querier无记录、
    # KU永远0。frontmatter 的 doc_type 是权威信号(md_export_service.py 按 medium 精确打上去
    # 的), 不靠文件名猜, 放在文件名正则前面先查, 覆盖面更广。
    if "doc_type: paper" in text[:500]:
        return ("低质", "学术论文(doc_type=paper)", None)
    if _PAPER.search(name):
        return ("低质", "学术论文(非教材)", None)
    if n < 60000:
        return ("低质", f"太小({n // 1024}KB)", None)
    if fffd / max(n, 1) > 0.008:
        return ("低质", f"OCR乱码({100 * fffd // n}%)", None)
    # ★B: EPUB 残渣清不净 或 清洗后仍无规范章节 → 不合格, 不喂飞轮(留在源, 等换源/返工)
    if _EPUB_HEADING.search(text):
        return ("低质", "EPUB残渣未清净", None)
    if _cleaned and chaps < 3:
        return ("低质", "EPUB无规范章节(清洗后<3章)", None)
    # ── 领域(域文件夹要求章节结构, 管道才能逐章处理)──
    econ = sum(low.count(k) for k in ECON)
    math = sum(low.count(k) for k in MATH)
    # ★带编号的定理/定义(教材特征, 科普没有): 定理6.1 / 定义2 / Theorem 3.1
    thm_num = len(re.findall(r"(定理|定义|引理|推论)\s*[\d一二三四五六七八九十]", samp)) + len(
        re.findall(r"\b(theorem|definition|lemma|corollary)\s+\d", low)
    )
    is_zh = zh > 1000  # 有大量中文即判中文书(中文数学教材公式里英文多, 不能用 zh>en)
    dens_e = econ / (n / 1000)
    dens_m = math / (n / 1000)
    has_ch = chaps >= 3 or decimal_ch >= 3
    # 经济学教材: econ密度高 + 有章节
    if dens_e >= 2.0 and dens_e >= dens_m and has_ch:
        return ("经济学", f"econ{dens_e:.1f} 章{max(chaps, decimal_ch)}", _out)
    # 数学教材: math密度高 或 编号定理绝对数量很多(应用型数学书, 如ML数学, 正文夹叙夹议
    # 稀释了关键词密度, 但编号定理照样densely) + 有章节。同 math_convert.py 的 math_textbook()
    # 已用的 thm>=30 or dens>=1.2 口径(2026-07-06 实测: Mathematics for Machine Learning
    # 106个编号定理但dens_m仅0.7, 原先纯AND逻辑判不进数学).
    if (dens_m >= 1.5 or thm_num >= 30) and thm_num >= 10 and dens_m > dens_e and has_ch:
        return (
            "中文数学" if is_zh else "英文数学",
            f"math{dens_m:.1f} 编号定理{thm_num} 章{max(chaps, decimal_ch)} {'中' if is_zh else '英'}",
            _out,
        )
    return (
        "其它",
        f"e{dens_e:.1f}/m{dens_m:.1f} 章{max(chaps, decimal_ch)} 编号定理{thm_num}",
        _out,
    )


cats = {}
for f in sorted(glob.glob(f"{SRC}/*.md")):
    cat, reason, cleaned = classify(f)
    cats.setdefault(cat, []).append((Path(f).name, reason, cleaned))

for cat in ["经济学", "中文数学", "英文数学", "其它", "低质", "SKIP"]:
    items = cats.get(cat, [])
    print(f"\n=== {cat} ({len(items)}) ===")
    for name, reason, _ in items[:60]:
        print(f"  [{reason}] {name[:50]}")

if DO:
    print("\n=== 执行移动(放入文件夹; 已存在则跳过避免误删; 低质留在源)===")
    moved = skipped = 0
    for cat, items in cats.items():
        if cat in ("低质", "SKIP"):
            continue
        tgt = f"{DST}/{cat}"
        os.makedirs(tgt, exist_ok=True)
        for name, _, cleaned in items:
            src = f"{SRC}/{name}"
            dst = f"{tgt}/{name}"
            if os.path.exists(dst) or _is_done(name):  # 已存在 或 已转/已入库 → 不搬(防重复入库)
                skipped += 1
            elif cleaned is not None:  # ★A: 有 EPUB 清洗 → 落盘写清洗后的合格 MD(不原样搬)
                Path(dst).write_text(cleaned, encoding="utf-8")
                os.remove(src)
                moved += 1
            else:
                shutil.move(src, dst)
                moved += 1
    print(f"✓ 移动 {moved} 个, 跳过(已存在/已入库){skipped} 个. 低质留在 {SRC}")
