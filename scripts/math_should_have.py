"""数学章节'应有清单'(确定性, 不靠LLM): 命名小标题 一、二、三、X = 真知识点(有真名, 非截断陈述).
★根因修1: 用真名(复合函数的求导法则/链式法则), 不是截断'如果函数\\'→合成能对准.
★每个知识点带 key_terms(内容层校验用): KU内容须含这些词才算真覆盖(堵'占位骗校验')."""
import re

_SKIP = re.compile(r'^(例\s*\d|解\b|证\b|注\b|定理\s*\d|设\b|即\b|故\b|这\b)')
_STOP = re.compile(r'[的与和及、，,；。()（）]')


def _key_terms(name):
    """从知识点真名抽辨识词(内容层校验): 去后缀+非辨识词, 取 ≥2 字具体子词, 空格也切."""
    core = re.sub(r'(举例|问题|的概念|及其计算法?|及其应用|的应用|的定义|的性质|的运算|的求法|及其导数|公式|法则|定理|的关系|概念)$', '', name).strip()
    parts = [p for p in re.split(r'[的与和及、，,；。()（）\s]+', core) if len(p) >= 2]
    specific = [p for p in parts if p not in ('导数', '函数', '微分', '关系', '应用', '计算', '方法')]
    return specific or parts or [core[:3] or name[:3]]


def extract(chapter_text):
    items, seen = [], set()

    def _clean(name):
        # ★清名: 去 markdown(* #)、在 LaTeX(\( \[ \cmd)处截断、规范空格
        name = re.sub(r'[*#]', ' ', name)
        name = re.split(r'\\[(\[a-zA-Z]', name)[0]
        return re.sub(r'\s+', ' ', name).strip(' ·*-')

    def add(name, pos):
        name = _clean(name)
        # ★噪音过滤(下册复杂章): 排除例题内枚举/句子片段, 不是真知识点
        if re.search(r'(时|情形|象限|可得|称为|同样|于是|因此|例如|这样|其中|以及|个方程)$', name):
            return
        if re.search(r'[。.…]|\d阶', name) or name.startswith(('三两', '一象', '二象', '三象', '四象')):
            return
        if name and name not in seen and not _SKIP.match(name) and len(name) >= 3:
            seen.add(name)
            items.append({'type': '知识点', 'id': name, 'label': name, 'key_terms': _key_terms(name), 'pos': pos})
    # ★命名小标题 一、二、三、X = 真知识点(最细, 有真名); ★行首锚定(排除句中枚举如'三象限时')
    sub_pos = [(m.start(), m.group(1).strip()) for m in
               re.finditer(r'(?m)^\s{0,4}[一二三四五六七八九十]、\s*([^\n。，,；()（）]{3,28})', chapter_text)]
    for pos, name in sub_pos:
        add(name, pos)
    # 第N节: 只补【无子标题】的节(如 高阶导数)— 有子标题的节其子标题已是知识点(避免父子重复)
    sec_marks = [(m.start(), m.group(1).strip()) for m in
                 re.finditer(r'(?m)^第[一二三四五六七八九十]+节\s+([^\n…]{1,28})', chapter_text)
                 if '…' not in m.group(1) and not re.search(r'\d\s*$', m.group(1))]
    for i, (pos, title) in enumerate(sec_marks):
        end = sec_marks[i + 1][0] if i + 1 < len(sec_marks) else len(chapter_text)
        has_sub = any(pos < sp < end for sp, _ in sub_pos)
        if not has_sub:
            add(title, pos)
    return items


if __name__ == '__main__':
    import sys
    sys.path.insert(0, 'scripts')
    from chapter_ingest import slice_chapter, SM
    ch = slice_chapter(SM.read_text(encoding='utf-8', errors='replace'), int(sys.argv[1]) if len(sys.argv) > 1 else 2)
    items = extract(ch)
    print(f"应有清单 {len(items)} 知识点(真名):")
    for i in items:
        print(f"  • {i['id']}  [校验词: {i['key_terms']}]")
