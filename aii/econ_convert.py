"""经济源文件(PDF/EPUB)→ MD: 找未转的, 检查可转性, 转换+入 经济学 文件夹.
仿 math_convert.py, 但用经济关键词密度门(经济书无编号定理).
用法: econ_convert.py          # 分析报告(不转)
      econ_convert.py --do     # 转换可转的(文字层+章节)并入 /books/MD/经济学
"""
import os, re, sys, glob, subprocess
import fitz  # pymupdf
from pathlib import Path
from collections import Counter

SRC = "/home/soffy/books/Economic"
DST = "/home/soffy/books/MD/经济学"
DO = "--do" in sys.argv

# 经济关键词(同 classify_md.py 的 ECON), 用于密度判定
ECON = ['经济','市场','需求','供给','价格','成本','货币','资本','利润','通货','宏观','微观','贸易',
        '金融','投资','边际','弹性','需求曲线','gdp','demand','supply','market','price','cost','profit',
        'capital','inflation','macroeconom','microeconom','marginal','elasticity','fiscal','monetary',
        'economy','economic']

def norm(s):  # 归一标题(去 z-lib/作者括号/空格标点)用于匹配
    s = re.sub(r'\(z-lib[^)]*\)|\(z-library[^)]*\)|\([^)]*1lib[^)]*\)', '', s, flags=re.I)
    s = re.sub(r'\.(pdf|epub)$', '', s, flags=re.I)
    s = re.sub(r'[\s_\-（）()【】\[\]·,，.。、:：;；]+', '', s)
    return s.lower()

def _ingested_titles():
    """权威已完成清单: aii.ingested_substrate 的书名(已入库的不能再转, 否则文件名不同→重复入库)."""
    try:
        out = subprocess.run(
            ["docker", "exec", "aii-postgres", "psql", "-U", "aii", "-d", "aii_kg", "-tAc",
             "SELECT title FROM aii.ingested_substrate WHERE title IS NOT NULL"],
            capture_output=True, text=True, timeout=20).stdout
        return [l for l in out.splitlines() if l.strip()]
    except Exception as e:
        print(f"  ⚠ 取已入库清单失败(只按MD去重): {e}", file=sys.stderr)
        return []

# 已完成的归一标题(查重): 已有MD(经济学目录+MD根) ∪ 已入库标题
existing = set()
for d in (DST, "/home/soffy/books/MD"):
    for f in glob.glob(f"{d}/*.md"):
        existing.add(norm(Path(f).stem))
for t in _ingested_titles():
    existing.add(norm(t))

def matched(stem):
    ns = norm(stem)
    if ns in existing:           # 精确(短标题也算)
        return True
    for e in existing:
        if len(e) >= 6 and (e in ns or ns in e):  # 子串含(长标题/带描述)
            return True
    return False

def chapters(text):
    return len(re.findall(r'(?m)^#\s+Chapter\s+\d|^第[一二三四五六七八九十百\d]+章|^Chapter\s+\d', text))

def analyze(path):
    stem = Path(path).stem
    if matched(stem):
        return ('已转', stem, None)
    try:
        d = fitz.open(path)
    except Exception:
        return ('打不开', stem, None)
    npg = d.page_count
    # 抽样查文字层
    txt = ""
    for p in range(0, min(npg, 60), 6):
        txt += d[p].get_text()
    txt_ratio = len(txt) / max(min(npg, 60) // 6, 1)
    full = "".join(d[p].get_text() for p in range(npg))
    nch = chapters(full)
    if txt_ratio < 200:
        return ('需OCR(无文字层)', stem, npg)
    if nch < 3:
        return ('无章节结构', stem, npg)
    return ('可转', stem, npg)

def convert(path):
    """PDF/EPUB → 清洗后的 MD 文本(去页眉页脚/页码, 章节行提升为 # 标题). 同 math_convert."""
    d = fitz.open(path)
    pages = [d[p].get_text() for p in range(d.page_count)]
    cnt = Counter()
    for pg in pages:
        ls = [l.strip() for l in pg.splitlines() if l.strip()]
        if ls:
            cnt[ls[0]] += 1; cnt[ls[-1]] += 1
    headers = {l for l, c in cnt.items() if c > len(pages) * 0.12 and len(l) < 80}
    out = []
    for pg in pages:
        for l in pg.splitlines():
            s = l.strip()
            if not s or s in headers or re.fullmatch(r'\d{1,4}', s):
                continue
            if re.match(r'^(Chapter\s+\d+|第[一二三四五六七八九十百\d]+章|CHAPTER\s+\d+)\b', s):
                out.append(f"\n# {s}\n")
            else:
                out.append(s)
    return "\n".join(out)

def econ_textbook(text):
    """判定: 是否经济教材(经济密度 + 章节). 经济书无编号定理, 只看密度+章节."""
    n = len(text); low = text[:300000].lower()
    econ = sum(low.count(k) for k in ECON)
    nch = chapters(text)
    dens = econ / max(n/1000, 1)
    # 管道需 第N章/Chapter 结构(章≥3); 经济性: 密度≥2.0(同 classify_md 经济学门)
    ok = nch >= 3 and dens >= 2.0
    return ok, f'econ密度{dens:.1f} 章{nch}'

results = {}
for path in sorted(glob.glob(f"{SRC}/*.pdf") + glob.glob(f"{SRC}/*.epub")):
    cat, stem, npg = analyze(path)
    results.setdefault(cat, []).append((stem, npg, path))

for cat in ['可转', '需OCR(无文字层)', '无章节结构', '已转', '打不开']:
    items = results.get(cat, [])
    print(f"\n=== {cat} ({len(items)}) ===")
    for stem, npg, _ in items[:40]:
        print(f"  {'%4d页 ' % npg if npg else ''}{stem[:60]}")

if DO:
    print("\n=== 转换「可转」+ 入 经济学 文件夹 ===")
    for stem, npg, path in results.get('可转', []):
        try:
            text = convert(path)
        except Exception as e:
            print(f"  ✗ 转换失败 {stem[:40]}: {e}"); continue
        ok, m = econ_textbook(text)
        if not ok:
            print(f"  – 跳过[{m}]: {stem[:42]}"); continue
        clean = re.sub(r'\s*\(z-lib[^)]*\)|\s*\(z-library[^)]*\)', '', stem).strip()
        if matched(clean):       # 同轮稍早已转/已入库的近似书 → 不重复
            print(f"  – 重复(已转/已入库), 跳过: {clean[:40]}"); continue
        dst = f"{DST}/{clean}.md"
        if os.path.exists(dst):
            print(f"  – 已存在, 跳过: {clean[:40]}"); continue
        open(dst, 'w', encoding='utf-8').write(text)
        existing.add(norm(clean))    # 记入, 防同轮后续重复
        print(f"  ✓ [经济学] {clean[:45]} ({len(text)//1024}KB)")
    print("✓ 完成. 需OCR/无章节 的未处理(见上).")
