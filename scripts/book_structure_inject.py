#!/usr/bin/env python3
"""
book_structure_inject.py — AII-STRATUM-MD-SPEC-001 后处理 pipeline

R9 剔页眉 / R2 TOC分离 / R1/R3 章节H1注入 / R5 sidecar / R8 表格修复

输入:
  md_path   : 已转换的 md 文件
  pdf_path  : 原始 PDF（用于书签 + 表格重提）
  out_path  : 输出 md（默认覆盖同名 _structured.md）

用法:
  python3 book_structure_inject.py 01KVAJCXHEV751E9NTADMZ7RGV \\
    --md  /path/to/stratum-to-aii/Principles_*.md \\
    --pdf /root/.stratum/data/substrate/book/01KVAJCX*.pdf \\
    --out /path/to/stratum-to-aii/

§20: stratum/scripts/ 层。调用 fitz 公开 API。不改 oprim/oskill/omodul 源码。
R-1: 失败立刻 sys.exit(1) 并打印原因
"""
from __future__ import annotations
import re, json, sys, logging, argparse, pathlib
from dataclasses import dataclass, field

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)-8s %(message)s')
log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# 数据结构
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class ChapterInfo:
    ch_num: int
    title: str        # bare title (no "CHAPTER N " prefix)
    pdf_page: int     # 1-based
    md_offset: int | None = None   # char offset in (R9-cleaned) md


@dataclass
class InjectResult:
    chapters_found: int
    chapters_total: int
    header_noise_before: int
    header_noise_after: int
    br_tables_before: int
    br_tables_after: int
    toc_fenced: bool
    acceptance: dict = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────────────
# 步骤 0: 从 PDF 读书签
# ──────────────────────────────────────────────────────────────────────────────

def load_chapters_from_pdf(pdf_path: pathlib.Path) -> tuple[list[ChapterInfo], int]:
    """从 PDF 书签提取章节信息（level 2 优先，fallback 到 level 1）。

    支持格式:
      - 'CHAPTER N Title'  (空格分隔，any case)
      - 'Chapter N: Title' (冒号分隔)
      - 'Chapter N'        (仅编号，无标题 → 从同层级 lv1 查补)
    """
    import fitz
    doc = fitz.open(str(pdf_path))
    toc = doc.get_toc()
    total_pages = doc.page_count
    doc.close()

    # 按 page 建 lv1 标题索引（用于补全无标题的 lv2 章节）
    lv1_by_page: dict[int, str] = {}
    for level, title, page in toc:
        if level == 1 and re.match(r'CHAPTER\s+\d+', title, re.I):
            lv1_by_page[page] = title

    def _parse_chapter(title: str, page: int) -> ChapterInfo | None:
        m = re.match(r'CHAPTER\s+(\d+)(?:[:\s\-]+\s*(.*))?$', title, re.I)
        if not m:
            return None
        ch_num = int(m.group(1))
        ch_title = (m.group(2) or '').strip()
        # 无标题 → 从 lv1 同页或相近页的书签补全
        if not ch_title:
            lv1_title = lv1_by_page.get(page)
            if lv1_title:
                m2 = re.match(r'CHAPTER\s+\d+(?:[:\s\-]+\s*(.*))?$', lv1_title, re.I)
                ch_title = (m2.group(1) or '').strip() if m2 else ''
        return ChapterInfo(ch_num=ch_num, title=ch_title, pdf_page=page)

    # 先尝试 lv2 CHAPTER 书签
    chapters: list[ChapterInfo] = []
    for level, title, page in toc:
        if level != 2:
            continue
        ch = _parse_chapter(title, page)
        if ch and ch.title:  # 有效且有标题
            chapters.append(ch)

    # Fallback: lv1 CHAPTER 书签（OpenStax 等书 chapter 在 lv1）
    if not chapters:
        for level, title, page in toc:
            if level != 1:
                continue
            ch = _parse_chapter(title, page)
            if ch and ch.title:
                chapters.append(ch)

    chapters.sort(key=lambda c: c.ch_num)
    log.info("Loaded %d chapters from PDF bookmarks (total %d pages)", len(chapters), total_pages)
    return chapters, total_pages


def load_chapters_from_db(substrate_id: str) -> list[dict] | None:
    """从 DuckDB 读 chapters JSON（service 停时才能用）。"""
    try:
        sys.path.insert(0, '/app/src')
        import os; os.environ.setdefault('STRATUM_ENV', 'prod')
        from stratum.db import get_conn
        with get_conn() as conn:
            row = conn.execute(
                "SELECT content FROM derivative WHERE substrate_id=? AND kind='chapters'",
                (substrate_id,)
            ).fetchone()
            if row:
                return json.loads(row[0])
    except Exception as e:
        log.warning("DuckDB read failed: %s", e)
    return None


# ──────────────────────────────────────────────────────────────────────────────
# 步骤 1: R9 剔跑页页眉
# ──────────────────────────────────────────────────────────────────────────────

def strip_page_headers(md: str) -> str:
    """
    剔除跑页页眉 (R9):
      - 间隔字母章首: C H A P T E R  N  Title
      - 裸 **C H A P T E R** (无章号,章节隔页残余)
      - P A R T  I/II/...  Title (卷分隔跑页眉,每页重复)
      - 行首粗体页码: **N** (单独成行, 1-3位数字)
      - blockquote 形式: > C H A P T E R...  /  > **N**
    """
    before_ch = len(re.findall(r'C\s+H\s+A\s+P\s+T\s+E\s+R', md))
    before_pt = len(re.findall(r'P\s+A\s+R\s+T\s+[IVX0-9]', md))

    # "C H A P T E R  N  ..." 形式（含可选 > 前缀, 任何后续内容）
    md = re.sub(r'(?m)^[ \t]*(?:>\s*)?C\s+H\s+A\s+P\s+T\s+E\s+R\s+\d+[^\n]*\n?', '', md)
    # 裸 "**C H A P T E R**"（无章号,章节隔页残余）
    md = re.sub(r'(?m)^[ \t]*\*\*C\s+H\s+A\s+P\s+T\s+E\s+R\*\*[ \t]*\n?', '', md)
    # "P A R T  I/II/III/...  Title" 跑页眉（每页重复,5个 Part 共 586 次）
    # 含 ## **P A R T N** 形式（卷分隔页,## 前缀）
    md = re.sub(r'(?m)^[ \t]*(?:#+[ \t]*)?(?:\*\*)?P\s+A\s+R\s+T\s+[IVX0-9][^\n]*\n?', '', md)
    # "## **P A R T**" 形式（Part分隔页,无罗马数字,正文在后续 ## 行）
    md = re.sub(r'(?m)^[ \t]*##[ \t]*\*\*P\s+A\s+R\s+T\*\*[^\n]*\n?', '', md)
    # 行首粗体页码 "**N**"（独立行）
    md = re.sub(r'(?m)^[ \t]*(?:>\s*)?\*\*\d{1,3}\*\*[ \t]*\n', '\n', md)
    # 清理多余空行
    md = re.sub(r'\n{4,}', '\n\n\n', md)

    after_ch = len(re.findall(r'C\s+H\s+A\s+P\s+T\s+E\s+R', md))
    after_pt = len(re.findall(r'P\s+A\s+R\s+T\s+[IVX0-9]', md))
    log.info("R9: CHAPTER noise %d → %d; PART noise %d → %d",
             before_ch, after_ch, before_pt, after_pt)
    return md


# ──────────────────────────────────────────────────────────────────────────────
# 步骤 2: 定位各章正文 H2（注入前先找位置）
# ──────────────────────────────────────────────────────────────────────────────

def _search_chapter_h2(md: str, ch: ChapterInfo, search_start: int, search_end: int) -> int | None:
    """在 md[search_start:search_end] 里找章节正文 H2 位置。

    多种格式尝试:
      1. ## Title_prefix            (Gruber-style: 正文裸标题)
      2. ## **Chapter N: prefix     (Acemoglu-style: bold, chapter前缀, 有冒号)
      3. ## **Chapter N prefix      (同上，无冒号)
      4. ## Chapter N: prefix       (非bold，chapter前缀)
      5. ## {N} prefix / ## {N}. prefix  (数字开头, 非小节号格式)
    """
    title_words = ch.title.split()
    chunk = md[search_start:search_end]
    ch_n = ch.ch_num

    for n_words in (5, 4, 3, 2):
        if n_words > len(title_words):
            continue
        prefix = ' '.join(title_words[:n_words])
        esc = re.escape(prefix)

        patterns = [
            # 1. 裸标题（不以粗体数字+点开头 → 排除目录节号条目）
            r'(?m)^## (?!\*\*\d+[\.\d])' + esc,
            # 2. bold chapter prefix + 冒号
            r'(?m)^## \*\*Chapter ' + re.escape(str(ch_n)) + r'[\s:]+' + esc,
            # 3. non-bold chapter prefix
            r'(?m)^## Chapter ' + re.escape(str(ch_n)) + r'[\s:]+' + esc,
            # 4. bold 数字开头（如 "## **10 Title**"）
            r'(?m)^## \*\*' + re.escape(str(ch_n)) + r'\b\D*' + esc,
        ]
        for pat in patterns:
            m = re.search(pat, chunk)
            if m:
                return search_start + m.start()

    return None


def find_chapter_positions(md: str, chapters: list[ChapterInfo], total_pages: int) -> None:
    """就地填充每个 ChapterInfo.md_offset。使用锚点插值减小误差。"""
    if not chapters:
        return

    # 章1: 宽搜（前5%~30% 之间）
    ch1 = chapters[0]
    body_start_lo = max(20_000, int(len(md) * 0.01))
    body_start_hi = int(len(md) * 0.30)
    ch1.md_offset = _search_chapter_h2(md, ch1, body_start_lo, body_start_hi)

    if ch1.md_offset is None:
        log.error("Cannot find Chapter 1 body H2 — aborting position detection")
        return

    log.info("Chapter 1 anchor: pdf_page=%d → md_offset=%d (%.2f%%)",
             ch1.pdf_page, ch1.md_offset, ch1.md_offset / len(md) * 100)

    # 估算正文尾（取最后一章页码前 ~50 页 = 末尾 6%）
    last_ch_page = chapters[-1].pdf_page
    body_end_est = int(len(md) * 0.96)

    prev_offset = ch1.md_offset
    for ch in chapters[1:]:
        # 锚点插值: 相对于 ch1 的页面偏移 → md 偏移
        pages_from_ch1 = ch.pdf_page - ch1.pdf_page
        pages_body_total = max(last_ch_page - ch1.pdf_page, 1)
        md_body_total = body_end_est - ch1.md_offset
        est_offset = ch1.md_offset + int(pages_from_ch1 / pages_body_total * md_body_total)

        # 搜索窗: ±10% of total md
        window = int(len(md) * 0.10)
        s_start = max(prev_offset, est_offset - window)
        s_end   = min(len(md), est_offset + window)

        ch.md_offset = _search_chapter_h2(md, ch, s_start, s_end)

        if ch.md_offset is not None:
            log.info("Chapter %2d: pdf_page=%d est=%d actual=%d (Δ%+d)",
                     ch.ch_num, ch.pdf_page, est_offset, ch.md_offset,
                     ch.md_offset - est_offset)
            prev_offset = ch.md_offset
        else:
            log.warning("Chapter %2d: NOT FOUND in [%d, %d]", ch.ch_num, s_start, s_end)


# ──────────────────────────────────────────────────────────────────────────────
# 步骤 3: R2 TOC 围栏
# ──────────────────────────────────────────────────────────────────────────────

def fence_toc(md: str, chapters: list[ChapterInfo]) -> tuple[str, int]:
    """把 TOC 区包进 <!-- TOC START/END -->.

    TOC 结束 = 第一个有 md_offset 的章之前的最近段落边界。
    返回 (new_md, toc_end_pos_after_insertion)
    """
    if '<!-- TOC START -->' in md:
        log.info("R2: TOC markers already present, skipping")
        toc_end = md.find('<!-- TOC END -->') + len('<!-- TOC END -->\n\n')
        return md, toc_end

    first_ch = next((c for c in chapters if c.md_offset is not None), None)
    if first_ch is None:
        log.warning("R2: No chapter positions found, cannot fence TOC")
        return md, 0

    fence_at = first_ch.md_offset
    # 往前找最近双换行，作为干净的 TOC 结束点
    look_back = md[max(0, fence_at - 800):fence_at]
    last_break = look_back.rfind('\n\n')
    if last_break != -1:
        fence_at = max(0, fence_at - 800) + last_break + 2

    toc_block = '<!-- TOC START -->\n' + md[:fence_at].rstrip('\n') + '\n<!-- TOC END -->\n\n'
    md = toc_block + md[fence_at:]
    toc_end = len(toc_block)

    log.info("R2: TOC fenced at char %d (%.2f%% of original)", fence_at, fence_at / (len(md) - len(toc_block) + fence_at) * 100)

    # 修正所有 chapter md_offset（toc_block 在前面插入了字节）
    shift = len(toc_block) - fence_at
    for ch in chapters:
        if ch.md_offset is not None:
            ch.md_offset += shift

    return md, toc_end


# ──────────────────────────────────────────────────────────────────────────────
# 步骤 4: R1/R3 注入 # Chapter N: Title
# ──────────────────────────────────────────────────────────────────────────────

def inject_chapter_headers(md: str, chapters: list[ChapterInfo]) -> str:
    """把每章正文 H2 替换为 H1 (# Chapter N: Title).

    从后往前替换以保持偏移量不变。
    """
    to_inject = sorted(
        [c for c in chapters if c.md_offset is not None],
        key=lambda c: c.md_offset,
        reverse=True,
    )

    for ch in to_inject:
        pos = ch.md_offset
        line_end = md.find('\n', pos)
        if line_end == -1:
            line_end = len(md)

        h1_line = f"# Chapter {ch.ch_num}: {ch.title}"
        # 原来是 "## Title" 或 "## **Title**"，直接替换整行
        md = md[:pos] + h1_line + md[line_end:]

    found = len(to_inject)
    log.info("R1/R3: Injected %d chapter H1 headers", found)
    return md


# ──────────────────────────────────────────────────────────────────────────────
# 步骤 5: R5 sidecar JSON
# ──────────────────────────────────────────────────────────────────────────────

def write_sidecar(sidecar_path: pathlib.Path, chapters: list[ChapterInfo],
                  all_bookmarks: list[dict]) -> None:
    """输出配对 .sidecar.json，含 chapters 列表和各章 section。"""
    # 按章组织 section（level 3 书签）
    ch_pages = {c.ch_num: c.pdf_page for c in chapters}
    ch_next_page = {}
    sorted_chs = sorted(chapters, key=lambda c: c.ch_num)
    for i, c in enumerate(sorted_chs):
        nxt = sorted_chs[i + 1].pdf_page if i + 1 < len(sorted_chs) else 99999
        ch_next_page[c.ch_num] = nxt

    result = []
    for c in sorted_chs:
        if c.md_offset is None:
            continue
        sections = []
        for bm in all_bookmarks:
            if bm['level'] != 3:
                continue
            if not (c.pdf_page <= bm['page'] < ch_next_page[c.ch_num]):
                continue
            m = re.match(r'(\d+\.\d+[A-Z]?)\s+(.*)', bm['title'])
            if m:
                sections.append({'n_m': m.group(1), 'title': m.group(2).strip(), 'pdf_page': bm['page']})

        result.append({
            'n': c.ch_num,
            'title': c.title,
            'start_offset': c.md_offset,
            'sections': sections,
        })

    sidecar_path.write_text(json.dumps({'chapters': result}, indent=2, ensure_ascii=False))
    log.info("R5: Wrote sidecar %s (%d chapters)", sidecar_path.name, len(result))


# ──────────────────────────────────────────────────────────────────────────────
# 步骤 6: R8 表格修复 (fitz.find_tables 重提)
# ──────────────────────────────────────────────────────────────────────────────

def _data_to_md_table(data: list[list]) -> str:
    """把 fitz 提取的 rows×cols 转为对齐 markdown pipe 表。"""
    if not data or len(data) < 2:
        return ''
    cleaned = []
    for row in data:
        cleaned.append([str(cell or '').replace('\n', ' ').replace('|', '｜').strip() for cell in row])

    max_cols = max(len(r) for r in cleaned)
    if max_cols == 0:
        return ''
    normalized = [r + [''] * (max_cols - len(r)) for r in cleaned]

    lines = ['| ' + ' | '.join(normalized[0]) + ' |',
             '| ' + ' | '.join(['---'] * max_cols) + ' |']
    for row in normalized[1:]:
        lines.append('| ' + ' | '.join(row) + ' |')
    return '\n'.join(lines)


def fix_tables(md: str, pdf_path: pathlib.Path, chapters: list[ChapterInfo],
               total_pages: int) -> str:
    """用 fitz.find_tables() 替换 md 里的 <br> 堆叠表 (R8)."""
    import fitz

    # 找所有 <br> 堆叠的表格块
    br_table_re = re.compile(r'(\|[^\n]*<br>[^\n]*(?:\n\|[^\n]*)*)', re.M)
    bad_tables = list(br_table_re.finditer(md))
    if not bad_tables:
        log.info("R8: No <br> tables found")
        return md

    before_count = len(bad_tables)
    log.info("R8: %d malformed table blocks found", before_count)

    # 用章节 offset 建立 md_pos → pdf_page 的粗略映射
    def md_pos_to_pdf_page(pos: int) -> int:
        """近似：给定 md 字符位置 → PDF 页码。"""
        sorted_chs = sorted([c for c in chapters if c.md_offset is not None],
                            key=lambda c: c.md_offset)
        if not sorted_chs:
            return int(pos / len(md) * total_pages) + 1
        if pos < sorted_chs[0].md_offset:
            # 前置区域（TOC/frontmatter）
            return int(pos / sorted_chs[0].md_offset * sorted_chs[0].pdf_page) + 1
        for i in range(len(sorted_chs) - 1):
            a, b = sorted_chs[i], sorted_chs[i + 1]
            if a.md_offset <= pos < b.md_offset:
                ratio = (pos - a.md_offset) / max(b.md_offset - a.md_offset, 1)
                return int(a.pdf_page + ratio * (b.pdf_page - a.pdf_page))
        last = sorted_chs[-1]
        ratio = (pos - last.md_offset) / max(len(md) - last.md_offset, 1)
        return int(last.pdf_page + ratio * (total_pages - last.pdf_page))

    # 预提取 PDF 所有表格（避免重复开关文件）
    doc = fitz.open(str(pdf_path))
    pdf_tables: list[dict] = []
    for pg_i in range(len(doc)):
        try:
            tabs = doc[pg_i].find_tables()
            for tab in (tabs.tables or []):
                data = tab.extract()
                if data and len(data) >= 2 and any(any(c for c in row) for row in data[1:]):
                    pdf_tables.append({'page': pg_i + 1, 'data': data})
        except Exception:
            pass
    doc.close()
    log.info("R8: Extracted %d tables from PDF", len(pdf_tables))

    if not pdf_tables:
        return md

    replacements: list[tuple[int, int, str]] = []
    used_pdf_tables: set[int] = set()

    for match in bad_tables:
        bad_text = match.group(0)
        # 取前 ~80 字符的文字特征（剔除 markdown 符号）
        sample = re.sub(r'[|*_<>\[\]]', ' ', bad_text).lower()[:120]
        sample_words = set(w for w in sample.split() if len(w) > 3)

        # 估算 PDF 页码
        approx_page = md_pos_to_pdf_page(match.start())
        # 在估算页码 ±5 页内找最佳匹配
        candidates = [t for t in pdf_tables if abs(t['page'] - approx_page) <= 5]

        best, best_score = None, 0.0
        for pt in candidates:
            idx = pdf_tables.index(pt)
            if idx in used_pdf_tables:
                continue
            pt_text = ' '.join(str(c) for row in pt['data'][:4] for c in row).lower()
            pt_words = set(w for w in pt_text.split() if len(w) > 3)
            score = len(sample_words & pt_words) / max(len(sample_words), 1)
            if score > best_score:
                best_score, best = score, (idx, pt)

        if best and best_score >= 0.25:
            idx, pt = best
            md_table = _data_to_md_table(pt['data'])
            if md_table:
                used_pdf_tables.add(idx)
                replacements.append((match.start(), match.end(), md_table + '\n'))
                log.info("  Table p%d (score=%.2f): %d rows × %d cols",
                         pt['page'], best_score, len(pt['data']), len(pt['data'][0]) if pt['data'] else 0)
        else:
            log.warning("  No PDF table match (approx_page=%d, best_score=%.2f)", approx_page, best_score)

    # 逆序替换
    for start, end, repl in sorted(replacements, key=lambda x: x[0], reverse=True):
        md = md[:start] + repl + md[end:]

    after_count = len(re.findall(r'\|[^\n]*<br>[^\n]*', md))
    log.info("R8: %d → %d <br> table rows", before_count, after_count)
    return md


# ──────────────────────────────────────────────────────────────────────────────
# AII 验收检查
# ──────────────────────────────────────────────────────────────────────────────

def check_acceptance(md: str, expected_n: int) -> dict:
    """运行 AII-STRATUM-MD-SPEC-001 验收标准。"""
    results: dict = {}

    # R1/R3: 章节编号连续
    ch_nums = [int(m) for m in re.findall(r'^# Chapter (\d+):', md, re.M)]
    results['chapters_found'] = ch_nums
    results['R1_count'] = len(ch_nums)
    results['R1_sequential'] = ch_nums == list(range(1, len(ch_nums) + 1))
    results['R1_complete'] = len(ch_nums) == expected_n

    # R3: 无空洞（任一章不超过全书 40%）
    positions = [m.start() for m in re.finditer(r'^# Chapter \d+:', md, re.M)] + [len(md)]
    spans = [positions[i+1] - positions[i] for i in range(len(positions)-1)]
    max_span_pct = round(max(spans, default=0) / max(len(md), 1) * 100, 1)
    results['R3_max_chapter_pct'] = max_span_pct
    results['R3_no_hole'] = max_span_pct < 40

    # R2: TOC 已围栏
    results['R2_toc_fenced'] = '<!-- TOC START -->' in md

    # R9: 页眉噪声
    noise = len(re.findall(r'C\s+H\s+A\s+P\s+T\s+E\s+R\s+\d', md))
    results['R9_header_noise'] = noise
    results['R9_pass'] = noise <= 2

    # R8: <br> 堆叠表
    br_rows = len(re.findall(r'\|[^\n]*<br>[^\n]*\|', md))
    results['R8_br_table_rows'] = br_rows
    results['R8_pass'] = br_rows == 0

    results['PASS'] = (results['R1_sequential'] and results['R1_complete']
                       and results['R3_no_hole'] and results['R9_pass'])
    return results


# ──────────────────────────────────────────────────────────────────────────────
# 主函数
# ──────────────────────────────────────────────────────────────────────────────

def inject_structure(
    md_path: pathlib.Path,
    pdf_path: pathlib.Path,
    out_dir: pathlib.Path,
    substrate_id: str = '',
    skip_tables: bool = False,
    out_path: pathlib.Path | None = None,
) -> InjectResult:
    """端到端 R1-R9 后处理."""
    log.info("=== book_structure_inject: %s ===", md_path.name)

    md = md_path.read_text(encoding='utf-8', errors='replace')
    log.info("Input: %d chars, %d lines", len(md), md.count('\n'))

    # 从 PDF 读书签（优先尝试 DuckDB）
    raw_bookmarks: list[dict] = []
    chapters: list[ChapterInfo] = []
    total_pages: int = 1

    if substrate_id:
        db_chapters = load_chapters_from_db(substrate_id)
        if db_chapters:
            raw_bookmarks = db_chapters
            for bm in db_chapters:
                if bm['level'] == 2:
                    m = re.match(r'CHAPTER\s+(\d+)[:\s\-]+\s*(.*)', bm['title'], re.I)
                    if m:
                        chapters.append(ChapterInfo(ch_num=int(m.group(1)),
                                                    title=m.group(2).strip(),
                                                    pdf_page=bm['page']))

    if not chapters:
        log.info("Loading chapters from PDF bookmarks")
        raw_chaps, total_pages = load_chapters_from_pdf(pdf_path)
        chapters = raw_chaps
        import fitz
        doc = fitz.open(str(pdf_path))
        raw_bookmarks = [{'title': t[1], 'page': t[2], 'level': t[0]} for t in doc.get_toc()]
        total_pages = doc.page_count
        doc.close()

    if not chapters:
        log.error("No chapters found — cannot process")
        raise RuntimeError("no_chapters")

    expected_n = len(chapters)

    # 统计 before
    noise_before = len(re.findall(r'C\s+H\s+A\s+P\s+T\s+E\s+R\s+\d', md))
    br_before = len(re.findall(r'\|[^\n]*<br>[^\n]*\|', md))

    # R9: 剔页眉
    md = strip_page_headers(md)

    # 定位章节正文位置
    find_chapter_positions(md, chapters, total_pages)

    found_count = sum(1 for c in chapters if c.md_offset is not None)
    if found_count == 0:
        log.error("R-1: No chapter positions found — aborting")
        raise RuntimeError("no_chapter_positions")
    if found_count < expected_n * 0.5:
        log.error("R-1: Only %d/%d chapters found (< 50%%) — aborting",
                  found_count, expected_n)
        raise RuntimeError(f"too_few_chapters: {found_count}/{expected_n}")

    # R2: TOC 围栏
    md, _toc_end = fence_toc(md, chapters)

    # R1/R3: 注入章节 H1
    md = inject_chapter_headers(md, chapters)

    # R8: 修复表格
    if not skip_tables:
        md = fix_tables(md, pdf_path, chapters, total_pages)

    # 统计 after
    noise_after = len(re.findall(r'C\s+H\s+A\s+P\s+T\s+E\s+R\s+\d', md))
    br_after = len(re.findall(r'\|[^\n]*<br>[^\n]*\|', md))

    # 写输出（out_path 指定时原地覆盖，否则写 _structured.md）
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = md_path.stem
    out_md = out_path if out_path is not None else out_dir / f"{stem}_structured.md"
    out_md.write_text(md, encoding='utf-8')

    # R5: sidecar（与输出 md 同目录同 stem）
    sidecar_path = out_md.parent / f"{out_md.stem}.sidecar.json"
    write_sidecar(sidecar_path, chapters, raw_bookmarks)

    # 验收
    acceptance = check_acceptance(md, expected_n)
    log.info("=== AII Acceptance ===")
    for k, v in acceptance.items():
        log.info("  %-30s %s", k, v)

    result = InjectResult(
        chapters_found=found_count,
        chapters_total=expected_n,
        header_noise_before=noise_before,
        header_noise_after=noise_after,
        br_tables_before=br_before,
        br_tables_after=br_after,
        toc_fenced='<!-- TOC START -->' in md,
        acceptance=acceptance,
    )
    log.info("Output: %s", out_md)
    return result


def inject_structure_inplace(
    md_path: pathlib.Path,
    pdf_path: pathlib.Path,
    substrate_id: str = '',
    skip_tables: bool = True,
) -> InjectResult | None:
    """原地注入章节结构（覆盖 md_path）。供 md_export_service 在 export_one 后调用。

    skip_tables=True 默认：表格重提较慢（~60s/book），适合异步批处理。
    返回 None 表示跳过（无 CHAPTER 书签 / 非 PDF / 出错）。
    """
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        toc = doc.get_toc()
        doc.close()
        # 检查 lv2 或 lv1 的 CHAPTER-style 书签（lv1 fallback for OpenStax-style books）
        ch_marks = [t for t in toc
                    if t[0] in (1, 2) and re.match(r'CHAPTER\s+\d+', t[1], re.I)
                    and not re.match(r'CHAPTER\s+\d+\s*$', t[1], re.I)]  # 要有标题文本
        if len(ch_marks) < 2:
            return None  # 书签不足或无标题，跳过
    except Exception as e:
        log.debug("inject_structure_inplace: PDF check failed: %s", e)
        return None

    return inject_structure(
        md_path=md_path,
        pdf_path=pdf_path,
        out_dir=md_path.parent,
        substrate_id=substrate_id,
        skip_tables=skip_tables,
        out_path=md_path,  # 覆盖原文件
    )


def batch_all(shared_dir: pathlib.Path, substrate_data_root: pathlib.Path,
              skip_tables: bool = True) -> dict:
    """批量后处理 shared_dir 里所有 book md（用 PDF 书签注入章节结构）。

    shared_dir : /data/shared/stratum-to-aii/
    substrate_data_root: /root/.stratum/data/substrate/book/
    skip_tables: 默认 True（表格重提慢，留批处理）
    """
    md_files = list(shared_dir.glob('*.md'))
    log.info("batch_all: %d md files in %s", len(md_files), shared_dir)

    ok = skipped = failed = already_structured = 0
    for md_path in sorted(md_files):
        # 跳过已处理的（含 '<!-- TOC START -->'）
        content = md_path.read_text(encoding='utf-8', errors='replace')
        if '<!-- TOC START -->' in content:
            already_structured += 1
            continue
        if '# Chapter 1:' in content:
            already_structured += 1
            continue

        # 从文件名提取 substrate_id（短 ULID 8 位后缀）
        m = re.search(r'_([0-9A-Z]{8})\.md$', md_path.name)
        if not m:
            # 纯 ULID 名（老格式 01KVXXXX.md）
            m2 = re.match(r'^([0-9A-Z]{26})\.md$', md_path.name)
            short_id = m2.group(1)[:8] if m2 else None
            full_sid = m2.group(1) if m2 else None
        else:
            short_id = m.group(1)
            full_sid = None

        # 找对应 PDF
        candidates = list(substrate_data_root.glob(f'{short_id}*.pdf')) if short_id else []
        if full_sid and not candidates:
            candidates = list(substrate_data_root.glob(f'{full_sid}*.pdf'))
        if not candidates:
            log.debug("batch_all: no PDF for %s", md_path.name)
            skipped += 1
            continue

        pdf_path = candidates[0]
        try:
            result = inject_structure_inplace(
                md_path=md_path,
                pdf_path=pdf_path,
                substrate_id=full_sid or '',
                skip_tables=skip_tables,
            )
            if result is None:
                skipped += 1
            elif result.acceptance.get('PASS'):
                ok += 1
            else:
                failed += 1
                log.warning("batch_all: FAIL %s acceptance=%s", md_path.name,
                            {k: v for k, v in result.acceptance.items()
                             if k != 'chapters_found' and not v})
        except Exception as e:
            log.error("batch_all: error %s: %s", md_path.name, e)
            failed += 1

    log.info("batch_all done: ok=%d skipped=%d failed=%d already_done=%d",
             ok, skipped, failed, already_structured)
    return {'ok': ok, 'skipped': skipped, 'failed': failed, 'already_structured': already_structured}


def main() -> int:
    p = argparse.ArgumentParser(description='AII md structure injection')
    p.add_argument('substrate_id', nargs='?', default='',
                   help='Substrate ULID (for DuckDB chapters lookup)')
    p.add_argument('--md', default='', help='Input md file path (single-file mode)')
    p.add_argument('--pdf', default='', help='PDF file path (single-file mode)')
    p.add_argument('--out', default='.', help='Output directory (default: .)')
    p.add_argument('--skip-tables', action='store_true',
                   help='Skip table reextraction (faster)')
    p.add_argument('--batch-all', action='store_true',
                   help='Batch-process all book mds in shared dir')
    p.add_argument('--shared-dir', default='/data/shared/stratum-to-aii',
                   help='Shared export dir (--batch-all)')
    p.add_argument('--substrate-data', default='/root/.stratum/data/substrate/book',
                   help='Substrate PDF root dir (--batch-all)')
    args = p.parse_args()

    if args.batch_all:
        result = batch_all(
            shared_dir=pathlib.Path(args.shared_dir),
            substrate_data_root=pathlib.Path(args.substrate_data),
            skip_tables=args.skip_tables,
        )
        return 0 if result['failed'] == 0 else 1

    if not args.md or not args.pdf:
        p.error("Either --batch-all or both --md and --pdf are required")

    try:
        result = inject_structure(
            md_path=pathlib.Path(args.md),
            pdf_path=pathlib.Path(args.pdf),
            out_dir=pathlib.Path(args.out),
            substrate_id=args.substrate_id,
            skip_tables=args.skip_tables,
        )
    except RuntimeError as e:
        log.error("✗ FAILED: %s", e)
        return 1

    acc = result.acceptance
    if acc.get('PASS'):
        log.info("✓ AII ACCEPTANCE: PASS")
        return 0
    else:
        log.error("✗ AII ACCEPTANCE: FAIL — %s",
                  {k: v for k, v in acc.items() if k != 'chapters_found' and not v})
        return 1


if __name__ == '__main__':
    sys.exit(main())
