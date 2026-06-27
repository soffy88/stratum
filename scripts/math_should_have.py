"""数学章节'应有清单'(确定性, 不靠LLM): 定义N + 定理N(去重取首现statement) + 第N节 + 关键公式概念.
★比'只第N节'细(含每个定理/定义)→ 漏一个定理能被查出; 这是数学完整性校验的基础."""
import re
def extract(chapter_text):
    t = chapter_text
    items = []
    # 1. 定义N / 定理N — 去重取首现, 抽其后短statement(到首个句号/换行)
    for kind in ['定义', '定理']:
        seen = set()
        for m in re.finditer(rf'{kind}\s*(\d+)', t):
            num = m.group(1)
            if num in seen: continue
            seen.add(num)
            tail = t[m.end():m.end()+60]
            label = re.split(r'[，。\n（(]', tail.strip(), 1)[0][:40]
            items.append({'type': kind, 'id': f'{kind}{num}', 'label': label.strip()})
    # 2. 第N节 标题(知识区)
    for m in re.finditer(r'(?m)^第[一二三四五六七八九十]+节\s+([^\n…]{1,28})', t):
        ti = m.group(1).strip()
        if '…' not in ti and not re.search(r'\d\s*$', ti):
            items.append({'type': '小节', 'id': ti, 'label': ti})
    # 3. 关键公式/方法概念(导数公式/微分/高阶/链式/隐函数...)— 命名知识点
    for kw in ['导数公式', '微分', '高阶导数', '链式法则', '隐函数', '参数方程', '反函数', '单侧导数', '导函数', '微分中值', '洛必达']:
        if kw in t:
            items.append({'type': '概念', 'id': kw, 'label': kw})
    # 去重(label)
    seen, out = set(), []
    for it in items:
        k = it['label']
        if k and k not in seen:
            seen.add(k); out.append(it)
    return out
if __name__ == '__main__':
    import sys; sys.path.insert(0, 'scripts')
    from chapter_ingest import slice_chapter, SM
    ch = slice_chapter(SM.read_text(encoding='utf-8', errors='replace'), int(sys.argv[1]) if len(sys.argv)>1 else 2)
    items = extract(ch)
    from collections import Counter
    print(f"应有清单 {len(items)} 项, 分布: {dict(Counter(i['type'] for i in items))}")
    for i in items: print(f"  [{i['type']}] {i['id']}: {i['label']}")
