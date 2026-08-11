"""单章全链路: 修复版md按章切 → 打磨版HQ抽KU(双语) → 打chapter_id → 归一 → 章内建边.
验证 抽KU(双语)+章内建边 完整机制. Usage: chapter_ingest.py <chapter_n>"""

import asyncio, json, os, re, sys
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
import asyncpg
from aii.api._provider import register_providers
from aii.service import onto_prompts as P
from aii.service import onto_vocab as V

# persist_ontology_result 只在 ingest_chapter() 里用,懒加载避免 omodul 依赖在 import 时触发
from aii.service.concept_onto_ops import vectorize_and_normalize
from aii.service.cross_chunk_link import gen_candidates, judge_and_link
from aii.storage.pg_backend import PgBackend
from obase import ProviderRegistry

# ★md 文件可 env 覆盖(给第二本书=数学书用), 默认微观经济学
SM = Path(
    os.getenv(
        "AII_MD_FILE",
        "/home/soffy/shared/stratum-to-aii/Principles_of_Microeconomics_The_Way_We__01KVAJCX.md",
    )
)

_CN = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn2int(s):
    # ★阿拉伯数字章节("第1章")先于中文数字判断——很多中文书(尤其经济学)用阿拉伯数字编号,
    # 原逻辑只认汉字数字, 阿拉伯数字全部 return 0(falsy)被静默丢弃, 导致这些书识别不到任何章节.
    if s.isdigit():
        return int(s)
    # 一..九 / 十 / 十一..十九 / 二十..
    if s in _CN:
        return _CN[s]
    if s.startswith("十"):
        return 10 + (_CN.get(s[1:], 0))
    if "十" in s:  # 二十/二十一..
        a, _, b = s.partition("十")
        return _CN[a] * 10 + (_CN.get(b, 0) if b else 0)
    return _CN.get(s, 0)


def _zh_chapter_starts(text):
    """中文教材 第N章: 跳 TOC, 每章取首个正文出现(页眉重复取第一个).

    ★TOC 识别改用结构特征(而非"含省略号/末尾页码"这类脆弱启发式, 对无省略号/无
    页码的干净目录——常见于 epub/markdown 衍生书——完全失效, 导致目录里的"第1章"
    被误当正文起点, slice_chapter 切出的"正文"其实是几十字的目录列表): 连续递增
    编号("第N章"紧跟"第N+1章"...)且彼此间距过短(< TOC_GAP, 真实一章内容不可能
    这么短)的一串, 整体判定为目录块并剔除."""
    TOC_GAP = 1500
    TOC_GAP_SHORT = 300  # ★2026-08-10 教辅短章节(单元/讲/课/节)间距小, 用更短 GAP 防误杀 TOC
    _SHORT_WORDS = ("单元", "讲", "课", "节", "部分", "回", "篇")
    raw = []
    # ★2026-08-10 扩展教辅结构: 除 第N章 外兼容 第N单元/第N讲/第N课/第N节/第N部分
    #   (夸克教辅=知识点/考点/真题, 常用这些章节词, 原正则只认"章"→ 54 本全判无章节)
    for m in re.finditer(r"(?m)^#{0,4}\s*第([一二三四五六七八九十百千0-9]+)(章|单元|讲|课|节|部分|回|篇)", text):
        num = _cn2int(m.group(1))
        if num:
            raw.append((m.start(), num, m.group(2)))
    raw.sort()

    is_toc = [False] * len(raw)
    i = 0
    while i < len(raw) - 1:
        j = i
        while (
            j + 1 < len(raw)
            and raw[j + 1][1] == raw[j][1] + 1
            and raw[j + 1][0] - raw[j][0]
            < (TOC_GAP_SHORT if raw[j][2] in _SHORT_WORDS else TOC_GAP)
        ):
            j += 1
        if j > i:  # 至少3项(i..j含2次递增跳转)连续递增+紧邻 → 判定目录块
            for k in range(i, j + 1):
                is_toc[k] = True
            i = j + 1
        else:
            i += 1

    # 每个章号收集全部候选位置(非TOC), 供下面按序挑选(不再"首个出现即用")
    candidates = {}
    for (pos, num, _w), toc in zip(raw, is_toc):
        if toc:
            continue
        # ★兜底窗口固定取标题后60字符(不用 find('\n')到行尾)——换行破损的书里一整段
        # 正文可能都挤在标题所在的同一"行", 用行尾会把标题后面一大段正文也纳入检测,
        # 正文引用里的省略号(如"……董事会主席")会被误判成 TOC 特征而漏掉真正的正文章节.
        line = text[pos : pos + 60]
        if "…" in line or re.search(r"\s\d+\s*$", line):  # 兜底: 孤立目录条目(未成块)
            continue
        candidates.setdefault(num, []).append(pos)

    # ★序号必须随位置单调递增(真实书里章节顺序=编号顺序): 前言/后记讲述后续章节内容
    # ("第3章就是一个好示例…")偶尔恰好换行落在行首, 被误当正文起点, 但位置比更小编号
    # 的章还靠前——矛盾, 说明该候选是误判. 跳过它, 改选同一章号里位置更靠后(晚于上一
    # 章)的候选; 找不到就丢弃该章(宁缺不流出乱序边界).
    starts = {}
    prev_pos = -1
    for num in sorted(candidates):
        pick = next((p for p in candidates[num] if p > prev_pos), None)
        if pick is None:
            continue
        starts[num] = pick
        prev_pos = pick
    return starts


def _bare_n_decimal_starts(text):
    """裸小节编号 'N. 标题'(无 '#'、无第二级 'N.M')兜底.
    markitdown 纯文本流输出常见 '1. Introduction' 独占一行当章节标题(无 '#' 前缀),
    之前只认 'N.M' 二级编号导致这类书完全切不了。误报控制:
      - 行首(允许缩进) + 独占一行(到行尾, 标题短语 3-80 字符)
      - 英文: Title Case 短语(非完整句子, 无句末标点)
      - 中文: 'N、'/'N.'/'一、' 开头短行, 排除句末标点(完整句子非标题)
      - 页眉/目录重复: 同编号同文本只取首个位置
      - 间距过滤: 相邻候选须 > MIN_GAP 字符(页眉间隔均匀且短, 正文标题间隔大)
    """
    MIN_GAP = 3000
    cand: dict[int, list[tuple[int, str]]] = {}
    # 英文: 1. Introduction  (Title Case 短语, 无句末标点, 行尾)
    for m in re.finditer(
        r"(?m)^[ \t]*(\d{1,2})\.\s+[A-Z][A-Za-z0-9 ,'\-]{2,70}$", text
    ):
        n = int(m.group(1))
        cand.setdefault(n, []).append((m.start(), m.group(0).strip()))
    # 中文: 一、标题 / 1、标题 / 1. 标题 (排除句末标点→非标题)
    for m in re.finditer(
        r"(?m)^[ \t]*(?:([一二三四五六七八九十百]+|[0-9]{1,2}))[、．.][ \t]*[^。！？!?\n]{2,60}$",
        text,
    ):
        s = m.group(1)
        n = _cn2int(s) if not s.isdigit() else int(s)
        if n:
            cand.setdefault(n, []).append((m.start(), m.group(0).strip()))
    # 去重(同编号同文本→页眉/目录重复) + 全局间距过滤(章节起点须与上一已选章节拉开距离)
    result: dict[int, int] = {}
    prev_pos = -1
    for n in sorted(cand):
        seen_txt: set[str] = set()
        for pos, txt in sorted(cand[n], key=lambda x: x[0]):
            if txt in seen_txt:  # 页眉重复: 同编号同文本跳过
                continue
            seen_txt.add(txt)
            if prev_pos < 0 or pos > prev_pos + MIN_GAP:  # 与上一已选章节的间距(页眉/练习题密集区被跳过)
                result[n] = pos
                prev_pos = pos
                break  # 每编号取一个(正文首次出现)
    return result


def _bare_english_chapter_starts(text):
    """裸英文 'Chapter N Title' / 'CHAPTER N TITLE'(无 '#' 前缀).
    markitdown 输出常见 'CHAPTER 1 **Title** 7'——带页码的是页眉(每页重复),
    页码会被剥离后去重取首; 真正章节标题行则保留。误报控制:
      - 行首(允许缩进) 'Chapter|CHAPTER' + 数字
      - 行尾可选页码(页眉特征) → 剥离不影响编号
      - 同编号多次出现(页眉/目录重复)只取首个位置
    """
    cand: dict[int, list[int]] = {}
    for m in re.finditer(
        r"(?m)^[ \t]*#{0,2}[ \t]*(?:Chapter|CHAPTER)\s+([0-9]{1,3})\b[^\n]{0,80}$",
        text,
    ):
        n = int(m.group(1))
        cand.setdefault(n, []).append(m.start())
    return {n: min(poses) for n, poses in cand.items()}


def _md_heading_starts(text):
    """最后兜底: 任意 markdown 标题行当章节起点.
    适用: 书有 '#'/'##' 标题但无 'Chapter N'/'第N章'/'N.' 编号格式
    (如《沉思录》H2×109、《50堂经典哲学思维课》H2×58)。误报控制:
      - H1(>=3个) 优先于 H2
      - 页眉/目录重复: 同标题文本多次出现只取首个
      - 间距过滤: 相邻章节起点须 > MIN_GAP 字符(真实章节内容不可能更短), 过滤密集小标题
      - 上限 200 章(防碎片化)
    """
    MIN_GAP = 3000
    MAX_CH = 200
    h1 = re.findall(r"(?m)^#\s+([^\n]{2,80})$", text)
    h2 = re.findall(r"(?m)^##\s+([^\n]{2,80})$", text)
    # 去重(页眉/目录重复), 保留首次出现位置
    seen: dict[str, int] = {}
    for m in re.finditer(r"(?m)^#\s+([^\n]{2,80})$", text):
        seen.setdefault(m.group(1).strip(), m.start())
    h1_uniq = sorted(seen.values())
    if len(h1_uniq) >= 3:
        picks = [h1_uniq[0]]
        for p in h1_uniq[1:]:
            if p - picks[-1] > MIN_GAP and len(picks) < MAX_CH:
                picks.append(p)
        if len(picks) >= 3:
            return {i + 1: picks[i] for i in range(len(picks))}
    seen2: dict[str, int] = {}
    for m in re.finditer(r"(?m)^##\s+([^\n]{2,80})$", text):
        seen2.setdefault(m.group(1).strip(), m.start())
    h2_uniq = sorted(seen2.values())
    if len(h2_uniq) >= 3:
        picks = [h2_uniq[0]]
        for p in h2_uniq[1:]:
            if p - picks[-1] > MIN_GAP and len(picks) < MAX_CH:
                picks.append(p)
        if len(picks) >= 3:
            return {i + 1: picks[i] for i in range(len(picks))}
    return {}


def _decimal_chapter_starts(text):
    """章节没有"Chapter N"/"第N章"字样, 只靠小节编号(如"1.1 Something")体现结构时的兜底
    ——只在上面两条规则都找不到时才启用(纯新增路径, 不影响已经工作的书)。现代教材
    (尤其高级数学/经济学, 如2026-07-07 高级数学经济专用飞轮这批书)很常见章节标题就是
    直接的名字(不含"Chapter N"字样), 靠小节编号体现结构——不加这条这类书直接切不了章,
    不是"分类判断"层面的问题(那个见 classify_md.py 的 decimal_ch), 是真正内容抽取切不
    出章节。用每个大节号N下最小的小节M的位置近似当章节起点(会漏掉章首引言到第一小节
    之间的几段, 但总比整本书因为没有"Chapter"字样就完全切不了强)。
    ★markitdown(2026-07-07起换用, 见 econ_convert.py/math_convert.py)是纯 pdfminer 文本流,
    不像 pymupdf4llm 那样按字号推断标题级别——"1.1 Finding Words for Intuitions"这类小节
    标题在 markitdown 输出里没有"#"前缀, 只是普通一行。所以除了带"#"的正规写法, 还兜底
    识别"裸"小节行: 独占一行、紧跟在空行后(段落边界)、"N.M 短标题"且标题部分是Title Case
    短语(非完整句子, 没有句末标点)——降低把"如1.1节所述"这类正文引用误判成标题的概率。"""
    cand: dict[int, list[tuple[int, int]]] = {}
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


def chapter_starts(text):
    """章起始位置(英文 # Chapter N: 或中文 第N章). 自动判格式.
    各格式独立检测, 选唯一编号数最多的(1个孤立 '# Chapter 1' 不压过 27 个裸 'N. 标题');
    与 md_quality_check 的 chapter_structure 判定同口径。"""
    canon = {int(m.group(1)): m.start() for m in re.finditer(r"(?m)^#\s+Chapter\s+(\d+):", text)}
    zh = _zh_chapter_starts(text)
    bare_en = _bare_english_chapter_starts(text)
    dec = _decimal_chapter_starts(text)
    bare_n = _bare_n_decimal_starts(text)
    md_h = _md_heading_starts(text)
    cands = [c for c in (canon, zh, bare_en, dec, bare_n, md_h) if c]
    if not cands:
        return {}
    return max(cands, key=len)


def chapter_numbers(text):
    return sorted(chapter_starts(text).keys())


def slice_chapter(text, n):
    starts = chapter_starts(text)
    if n not in starts:
        raise SystemExit(f"chapter {n} not found; have {sorted(starts)}")
    s = starts[n]
    e = starts.get(n + 1, len(text))
    chap = text[s:e]
    # ★末章截掉书末 back-matter(GLOSSARY/INDEX, 可能间隔字母 'G L O S S A R Y')—— 防全书术语表误抽进末章
    # 中文书back-matter(作者简介/译者简介/关于封面/出版社社区推广)常是纯文本无markdown标题,
    # 且紧跟在末章正文后一起被切进"末章"——LLM 会把这段简介/致谢/推广文字误抽成假KU
    # (曾抽出"贝叶斯层次化模型"这种文不对题的概念, 实际内容是译者后记+异步社区广告).
    bm = re.search(
        r"(?im)^#{1,3}\s*\**\s*(?:g\s*l\s*o\s*s\s*s\s*a\s*r\s*y|i\s*n\s*d\s*e\s*x)\b"
        r"|^(?:作者简介|译者简介|关于封面|欢迎来到异步社区)\s*$",
        chap,
    )
    if bm:
        chap = chap[: bm.start()]
    return chap


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    sub = f"microecon_en_ch{n}"
    register_providers()
    backend = PgBackend()
    backend.dsn = os.getenv("DATABASE_URL")
    llm = ProviderRegistry.get().llm("default")
    from oskill import ontology_extract

    text = SM.read_text(encoding="utf-8", errors="replace")
    chap = slice_chapter(text, n)
    title = chap.splitlines()[0].lstrip("# ").strip()
    print(
        f"[{sub}] chapter {n}: '{title[:60]}'  chars={len(chap)} (~{len(chap) // 2000} chunks)",
        flush=True,
    )

    # 1. 抽取 — 打磨版 HQ + 双语
    r = await ontology_extract(
        source_text=chap,
        llm=llm,
        chunk_size=2000,
        doc_type="textbook",
        source_credibility="high",
        pass1_chunk_tmpl=P.PASS1_CHUNK_TMPL,
        pass1_chunk_system=P.PASS1_CHUNK_SYSTEM,
        pass1_outline_tmpl=P.PASS1_OUTLINE_TMPL,
        pass1_outline_system=P.PASS1_OUTLINE_SYSTEM,
        pass2_chunk_tmpl=P.PASS2_CHUNK_TMPL_HQ,
        pass2_system=P.PASS2_SYSTEM_HQ,
        valid_knowledge_types=V.VALID_KNOWLEDGE_TYPES,
        valid_sub_types=V.VALID_SUB_TYPES,
        valid_relation_types=V.VALID_RELATION_TYPES,
    )
    print(f"  extracted {len(r.ku_candidates)} KU candidates", flush=True)

    # 2. 持久化
    from aii.service.onto_persist import persist_ontology_result  # 懒加载(omodul依赖在运行时才需要)

    trail = Path("/tmp/onto_trails")
    trail.mkdir(parents=True, exist_ok=True)
    ps = await persist_ontology_result(
        dsn=backend.dsn, substrate_id=sub, result=r, trail_dir=trail, backend=backend
    )
    print(
        f"  persisted registered={ps.get('registered')} rejected={ps.get('rejected')} rej_struct={ps.get('rejected_structural', 0)}",
        flush=True,
    )

    conn = await asyncpg.connect(backend.dsn)
    from pgvector.asyncpg import register_vector

    await register_vector(conn)
    # 3. 打 chapter_id (provenance)
    await conn.execute(
        "UPDATE aii.ku_onto SET provenance = provenance || jsonb_build_object('chapter',$2::int) WHERE substrate_id=$1",
        sub,
        n,
    )
    # 4. 概念归一 (章内, 供共现预筛)
    norm = await vectorize_and_normalize(conn, llm, substrate_id=sub, discipline="经济学")
    print(f"  normalize: {norm['before']}→{norm['after']} concepts", flush=True)
    # 5. 章内建边: 共现预筛候选 → LLM 判真关系
    cands = await gen_candidates(conn, substrate_id=sub, sem_threshold=0.80)
    print(f"  chapter-internal candidates={len(cands)}", flush=True)
    estats = await judge_and_link(conn, llm, cands, substrate_id=sub)
    print(
        f"  edges built: linked={estats['linked']}/{estats['candidates']} by_relation={estats['by_relation']}",
        flush=True,
    )

    n_ku = await conn.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", sub)
    n_zh = await conn.fetchval(
        "SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1 AND natural_text_zh<>''", sub
    )
    await conn.close()
    print(
        f"\nDONE {sub}: KU={n_ku} zh={n_zh} edges_linked={estats['linked']} chapter_id={n}",
        flush=True,
    )


if __name__ == "__main__":
    asyncio.run(main())
