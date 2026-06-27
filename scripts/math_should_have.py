"""数学章节'应有清单'(确定性, 不靠LLM): 多颗粒度识别, 取并集.
★多颗粒度:
  A. 定理层: 每个带编号的 定义/定理/推论/命题 = 一个KU (不合包)
  B. 子主题层: 一/二/三子标题 / §节名 / 第N节名 (无定理时补)
  C. 并集: 两层都查, 谁都不漏
★避免两个偏颇:
  - 只子主题层 → 漏定理(数分原问题)
  - 只定理层 → 漏没编号的重要子主题内容(方法/思想)
★每个知识点带 key_terms(内容层校验用)."""
import re

_SKIP_SUB = re.compile(r'^(例\s*\d|解\b|证\b|注\b|设\b|即\b|故\b|这\b)')
_STOP = re.compile(r'[的与和及、，,；。()（）]')

# 引用特征: "定义1 常称为..." 是对已有定义的引用, 不是新定义
_IS_REF = re.compile(r'^\s*(常称为|的结论|中的|给出|即称|简称|又称|见(上面|前面)?定义|以上|所满足|对应)')


def _key_terms(name):
    """从知识点真名抽辨识词(内容层校验): 去后缀+非辨识词, 取 ≥2 字具体子词."""
    core = re.sub(r'(举例|问题|的概念|及其计算法?|及其应用|的应用|的定义|的性质|的运算|的求法|及其导数|公式|法则|定理|的关系|概念)$', '', name).strip()
    parts = [p for p in re.split(r'[的与和及、，,；。()（）\s]+', core) if len(p) >= 2]
    specific = [p for p in parts if p not in ('导数', '函数', '微分', '关系', '应用', '计算', '方法')]
    return specific or parts or [core[:3] or name[:3]]


def _pname_zh(raw):
    """从括号名 (罗尔(Rolle)中值定理) 提取中文名, 去所有英文字母(人名/拉丁字母)."""
    s = re.sub(r'[（()）]', '', raw or '').strip()
    s = re.sub(r'[A-Za-z]+', '', s).strip().strip('- ')
    # 再次去空格/标点
    s = re.sub(r'^[\s\-–—·,，.。、]+|[\s\-–—·,，.。、]+$', '', s)
    return s if len(s) >= 2 else ''


def _sect_boundaries(chapter_text):
    """返回§节/第N节的起始位置列表, 用于节内定义去重."""
    bounds = [m.start() for m in re.finditer(r'(?m)^§\s*\d', chapter_text)]
    if not bounds:
        bounds = [m.start() for m in re.finditer(r'(?m)^第[一二三四五六七八九十]+节', chapter_text)]
    return [0] + bounds


def _sect_of(pos, bounds):
    s = 0
    for sb in bounds:
        if sb <= pos:
            s = sb
    return s


def _extract_theorem_layer(chapter_text):
    """定理层: 每个带编号的定义/定理/推论/命题 = 一个KU (不合包).

    处理两种编号格式:
    - 章前缀: 定理6.1 / 定义2.3 (华东师大数分, 全章唯一)
    - 节内序: 定义1 / 定理2 (同济/其他, 同一节内按首次出现去重, 不同节同号=不同定义)
    """
    items = []
    seen_uids = set()          # 全局uid去重(章前缀用)
    sect_bounds = _sect_boundaries(chapter_text)
    sect_seen = {}             # (sect_start, kind+num) → True (节内去重)

    # A. 章前缀项: 定理N.M / 定义N.M / 推论N.M / 命题N.M (章内全局唯一)
    for m in re.finditer(
        r'(?m)^(定义|定理|推论|命题|引理)\s*(\d+\.\d+[\d\'\"\.]*)\s*([（(][^）)\n]{1,35}[）)])?',
        chapter_text
    ):
        kind = m.group(1)
        num = re.sub(r'\s+', '', m.group(2))
        uid = kind + num
        if uid in seen_uids:
            continue
        seen_uids.add(uid)

        pname = _pname_zh(m.group(3))
        label = pname if pname else uid
        items.append({
            'type': kind, 'id': uid, 'label': label,
            'key_terms': _key_terms(label) if pname else [num],
            'pos': m.start()
        })

    # B. 节内定义/定理 (无章前缀 or 单数字): 定义1, 定理2, 推论 等
    #    - 同节同号: 只取第一次 (去重)
    #    - 不同节同号: 都取 (不同定义)
    #    - 引用行过滤: "定义1 常称为..." → 跳过
    for m in re.finditer(
        r'(?m)^(定义|定理|推论|命题)\s*(\d+[\'\"]*)\s*([（(][^）)\n]{1,25}[）)])?(?=\s+\S)',
        chapter_text
    ):
        kind = m.group(1)
        num = re.sub(r'\s+', '', m.group(2))

        # 过滤引用行
        after = chapter_text[m.end():m.end() + 50]
        if _IS_REF.match(after):
            continue

        # 节内去重
        sect = _sect_of(m.start(), sect_bounds)
        skey = (sect, kind + num)
        if skey in sect_seen:
            continue
        sect_seen[skey] = True

        # 生成章内唯一uid: 若同编号已存在(不同节), 加节序号
        uid = kind + num
        if uid in seen_uids:
            si = sect_bounds.index(sect) if sect in sect_bounds else 0
            uid = f"{kind}{num}_s{si}"
        seen_uids.add(uid)

        pname = _pname_zh(m.group(3))
        short = kind + re.sub(r"['\"]", '', num)
        label = pname if pname else short
        items.append({
            'type': kind,
            'id': uid,     # ★用完整uid(含节序后缀)作id, 防不同节同号被去重
            'label': label,
            'key_terms': _key_terms(label) if pname else [re.sub(r"['\"]", '', num)],
            'pos': m.start()
        })

    # 无编号推论 (推论 后直接跟内容, 无数字)
    for m in re.finditer(r'(?m)^(推论)\s+(?!\d)(\S)', chapter_text):
        after = chapter_text[m.start():m.start() + 40]
        if _IS_REF.match(chapter_text[m.start() + len(m.group(1)):m.start() + len(m.group(1)) + 50]):
            continue
        sect = _sect_of(m.start(), sect_bounds)
        skey = (sect, '推论_unnumbered')
        if skey in sect_seen:
            continue
        sect_seen[skey] = True
        uid = f"推论_s{sect_bounds.index(sect) if sect in sect_bounds else 0}"
        if uid not in seen_uids:
            seen_uids.add(uid)
            items.append({
                'type': '推论', 'id': '推论', 'label': '推论',
                'key_terms': ['推论'], 'pos': m.start()
            })

    items.sort(key=lambda x: x['pos'])
    return items


def extract(chapter_text):
    """多颗粒度提取并集: 定理层 + 子主题层, 谁都不漏."""
    items = []
    seen = set()        # id 去重

    def _clean(name):
        name = re.sub(r'[*#]', ' ', name)
        name = re.split(r'\\[(\[a-zA-Z]', name)[0]
        return re.sub(r'\s+', ' ', name).strip(' ·*-')

    def add_item(it):
        """加入一个 item dict, 按 id 去重."""
        iid = it['id']
        if iid and iid not in seen and len(iid) >= 2:
            seen.add(iid)
            items.append(it)

    def add_sub(name, pos):
        """加入子主题层条目 (带噪音过滤)."""
        name = _clean(name)
        if re.search(r'(时|情形|象限|可得|称为|同样|于是|因此|例如|这样|其中|以及|个方程)$', name):
            return
        if re.search(r'[。.…]|\d阶', name) or name.startswith(('三两', '一象', '二象', '三象', '四象')):
            return
        if name and name not in seen and not _SKIP_SUB.match(name) and len(name) >= 3:
            seen.add(name)
            items.append({'type': '知识点', 'id': name, 'label': name,
                          'key_terms': _key_terms(name), 'pos': pos})

    # ═══ A. 定理层 (优先加入, 保证不漏任何带编号定理/定义) ═══
    thm_items = _extract_theorem_layer(chapter_text)
    for it in thm_items:
        add_item(it)

    # ═══ B. 子主题层 (与定理层并集, 补没编号的重要内容) ═══

    # B1. 一/二/三 命名子标题
    sub_pos = [(m.start(), m.group(1).strip()) for m in
               re.finditer(r'(?m)^\s{0,4}[一二三四五六七八九十]、\s*([^\n。，,；()（）]{3,28})', chapter_text)]
    for pos, name in sub_pos:
        add_sub(name, pos)

    # B2. 第N节: 只补【无子标题且无定理】的节
    sec_marks = [(m.start(), m.group(1).strip()) for m in
                 re.finditer(r'(?m)^第[一二三四五六七八九十]+节\s+([^\n…]{1,28})', chapter_text)
                 if '…' not in m.group(1) and not re.search(r'\d\s*$', m.group(1))]
    for i, (pos, title) in enumerate(sec_marks):
        end = sec_marks[i + 1][0] if i + 1 < len(sec_marks) else len(chapter_text)
        has_sub = any(pos < sp < end for sp, _ in sub_pos)
        has_thm = any(pos <= it['pos'] < end for it in thm_items)
        if not has_sub and not has_thm:
            add_sub(title, pos)

    # B3. § N 节名 (华东师大数分格式): 只补【无子标题且无定理】的节
    # ★去重建唯一节列表: 同名页眉重复 → 只取首次出现; 节范围 = [首次, 下一不同节首次)
    _sect_all = [(m.group(1).strip(), m.start())
                 for m in re.finditer(r'(?m)^§\s*\d+\s+([^\n|…]{3,30})', chapter_text)
                 if '…' not in m.group(1)]
    # 按位置排序, 提取每个 unique title 的首次出现位置
    _unique_sects = []  # [(title, first_pos)]
    _title_seen = set()
    for title, pos in _sect_all:
        if title not in _title_seen:
            _title_seen.add(title)
            _unique_sects.append((title, pos))
    for i, (title, sect_start) in enumerate(_unique_sects):
        sect_end = _unique_sects[i + 1][1] if i + 1 < len(_unique_sects) else len(chapter_text)
        has_sub = any(sect_start <= sp < sect_end for sp, _ in sub_pos)
        has_thm = any(sect_start <= it['pos'] < sect_end for it in thm_items)
        if not has_sub and not has_thm:
            add_sub(title, sect_start)

    # B4. §节 fallback: 若整章既无子标题也无定理, 全加§节名 (纯§格式且无定理的书)
    if not items:
        for title, pos in _unique_sects:
            add_sub(title, pos)

    return items


if __name__ == '__main__':
    import sys, os
    sys.path.insert(0, 'scripts')
    # 支持 AII_MD_FILE 覆盖
    from chapter_ingest import slice_chapter, SM
    _MD = sys.argv[2] if len(sys.argv) > 2 else str(SM)
    from pathlib import Path
    ch = slice_chapter(Path(_MD).read_text(encoding='utf-8', errors='replace'),
                       int(sys.argv[1]) if len(sys.argv) > 1 else 2)
    items = extract(ch)
    print(f"应有清单 {len(items)} 知识点(真名):")
    for it in items:
        print(f"  • {it['id']}  [{it['type']}]  [校验词: {it['key_terms']}]")
