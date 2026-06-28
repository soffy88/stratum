"""同济高数 facet整理: ①豁免标记 ②真缺重合成.
Usage: uv run python scripts/tongji_retry.py
"""
import asyncio, os, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / "aii" / ".env", override=True)
except ImportError:
    pass
sys.path.insert(0, str(ROOT / "scripts"))

import httpx
from math_should_have import extract

MD = Path(os.getenv("AII_MD_FILE",
    "/home/soffy/shared/stratum-to-aii/高等数学_上册_第八版_(同济大学数学科学院_编)_(z-library.sk,_01KVQ13J.md"))
OUTDIR = Path(os.getenv("MATH_OUTDIR", str(ROOT / "scripts" / "_staging" / "tongji")))
KEY = os.getenv('DEEPSEEK_API_KEY')

_CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
def _cn2int(s):
    if s in _CN: return _CN[s]
    if s.startswith('十'): return 10 + (_CN.get(s[1:], 0))
    if '十' in s:
        a, _, b = s.partition('十'); return _CN[a] * 10 + (_CN.get(b, 0) if b else 0)
    return _CN.get(s, 0)
def slice_chapter(text, n):
    starts = {}
    for m in re.finditer(r'(?m)^第([一二三四五六七八九十]+)章', text):
        line = text[m.start(): text.find('\n', m.start()) if text.find('\n', m.start()) > 0 else m.start()+40]
        if '…' in line or re.search(r'\s\d+\s*$', line): continue
        num = _cn2int(m.group(1))
        if num and num not in starts: starts[num] = m.start()
    if n not in starts: raise SystemExit(f"chapter {n} not found; have {sorted(starts)}")
    s = starts[n]; e = starts.get(n+1, len(text))
    return text[s:e]

_MATHNONCOV = re.compile(r"未涉及|未覆盖|未出现|未给出|未提及|未定义|未讨论|需查阅|其他资料|建议参考|不在本(章|节)|超出本(章|节)")
def clean_math(t):
    if not t: return ""
    t = re.sub(r"\s*[\[【]\s*第?\s*\d+[-–]?\d*\s*页\s*[\]】]", "", t)
    t = re.sub(r"^\s*(KU|知识单元|类型|概念)\s*[:：].*$", "", t, flags=re.M)
    t = t.replace("**", "").replace("##", "")
    kept = [s for s in re.split(r"(?<=[。.！？\n])", t) if s.strip() and not _MATHNONCOV.search(s)]
    return re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()

def facets(typ):
    return {'定义': "定义内容 / 直观含义 / 与相关概念的区别 / 用途",
            '定理': "条件 / 结论 / 证明思路 / 适用场景 / 例子",
            '概念': "是什么 / 核心公式或方法 / 适用条件 / 应用",
            '小节': "该小节核心知识点概述"}.get(typ, "是什么 / 为什么 / 怎么用")

def facet_check(point_name, zh):
    issues = []
    is_summary = bool(re.search(r'基本.*公式|基本.*法则|导数公式|微分公式|积分表|公式表|汇总', point_name))
    is_thm = bool(re.search(r'法则|定理|公式', point_name)) and not is_summary
    has_proof = bool(re.search(r'证明|推导|为什么|∵|证\s*[:(（]|证\s*\d', zh)) or \
                bool(re.search(r'^\s*证\s', zh, re.MULTILINE))
    has_example = bool(re.search(r'例\s*\d|例如|例题|例\s*[:：]|例子', zh))
    has_formula = len(zh) > 0 and bool(re.search(
        r'\\[a-zA-Z]{2,}|\$.+|\\\[|\\\(|[∫∬∭∮∑∏√∂∇∈∉⊂⊆≤≥≠≈≡∞±·×÷→πθλμφψΦΔΩΣαβγ]|[a-zA-Z]\^|\|[a-zA-Z]\|', zh))
    if is_thm:
        if not has_proof: issues.append('缺证明/推导')
        if not has_example: issues.append('缺例子')
    if len(zh) < 350: issues.append('过短(讲浅)')
    if not has_formula: issues.append('无公式(数学命门)')
    return issues

SYS = ("你为数学教材合成一个讲透知识单元(KU), 严格只用本章内容、整合非创作。"
       "★数学公式必须完整保留(LaTeX原样, 如 \\frac \\lim), 公式残缺=不合格。"
       "中文主显(简体), 之后附English。书没讲的面直接不写(不要写'未涉及')。"
       "★若为定理/法则/公式型: 必须包含证明或推导思路(证明过程/关键步骤)。"
       '★若章节内有配例题(例1/例2格式), 必须将完整例题纳入KU(包含解题过程)。'
       'Output JSON {"zh":"<中文讲透,含完整LaTeX公式和例题>","en":"<English>"}.')

async def synth_one(cli, chapter, item, sem):
    intro = chapter[:1000]
    p = item.get('pos', 0)
    section = chapter[max(0, p - 300): p + 20000]
    prompt = (f"本章开头(记号约定):\n{intro}\n\n该知识点所在小节:\n{section}\n\n"
              f"为知识点「{item['label'] or item['id']}」({item['type']}型)合成讲透KU。\n"
              f"面: {facets(item['type'])}\n"
              f"★若该知识点后文有例1/例2等例题, 请完整纳入(含解题过程)。\n"
              f"★定理/法则必须包含证明思路。\n"
              f"中文讲透(公式完整)+English。")
    async with sem:
        for _ in range(3):
            try:
                r = await cli.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={"Authorization": "Bearer " + KEY},
                    json={"model": "deepseek-v4-flash",
                          "response_format": {"type": "json_object"},
                          "messages": [{"role": "system", "content": SYS},
                                       {"role": "user", "content": prompt}]})
                j = json.loads(r.json()["choices"][0]["message"]["content"])
                return j
            except Exception as e:
                print(f"  ★retry exception: {e}", flush=True)
                await asyncio.sleep(3)
    return None

# ═══ 豁免清单 (结构性/存在性/规则性定理, 书中无独立例题或证明) ═══
EXEMPT = [
    # (ch, point, 豁免facets, 原因)
    (1, '定理1',     ['缺例子'], '数列极限唯一性—结构性定理'),
    (1, '定理1_s17', ['缺例子'], '函数极限唯一性—结构性定理'),
    (1, '定理4',     ['缺例子'], '极限四则运算法则—规则性定理, 例子在后续计算中体现'),
    (1, '定理5',     ['缺例子'], '极限不等式性质—序关系定理'),
    (1, '定理2_s31', ['缺例子'], '反函数连续性—结构性连续性定理'),
    (1, '定理3_s36', ['缺例子'], '复合函数极限定理—结构性, 用于理论推导'),
    (1, '定理4_s42', ['缺证明/推导', '缺例子'], '一致连续性定理—存在性定理'),
    (3, '柯西中值定理', ['缺例子'], '柯西中值定理—主要作证明工具, 无直接应用例题'),
    (3, '曲率及其计算公式', ['缺证明/推导'], '曲率公式—推导已隐含在公式展开中'),
    (7, '定理2',     ['缺证明/推导'], 'ODE通解结构—证明是线性代数范畴, 书中不展开'),
]

# ═══ 真缺清单 (需重合成含例题+证明) ═══
TRUE_LACKING = [
    (1, '定理2_s41'),   # 零点定理
    (3, '定理2'),       # 洛必达法则 x→∞
    (3, '定理2_s15'),   # 极值第一充分条件(单调)
    (3, '定理1_s19'),   # 极值必要条件
    (3, '定理2_s19'),   # 极值第一充分条件(极值)
    (3, '定理3'),       # 极值第二充分条件
    (5, '定理1'),       # 连续函数可积性
    (5, '定理2_s9'),    # 原函数存在定理
    (5, '定理1_s22'),   # 反常积分收敛判定
    (5, '定理3_s23'),   # 比较审敛法1
    (5, '定理5'),       # 绝对收敛→收敛
    (5, '牛顿-莱布尼茨公式'),
    (7, '定理2'),       # ODE通解结构(例子)
    (7, '定理3'),       # 非齐次ODE通解结构
]

async def main():
    TEXT = MD.read_text(encoding='utf-8', errors='replace')
    sem = asyncio.Semaphore(6)

    # ─── 豁免标记 ───
    print('=== ①标记豁免 ===', flush=True)
    for ch, pt, exempt_issues, reason in EXEMPT:
        chf = OUTDIR / f'ch{ch}.json'
        kus = json.loads(chf.read_text())
        k = next((k for k in kus if k['point'] == pt), None)
        if not k:
            print(f'  ★未找到 Ch{ch}[{pt}]', flush=True)
            continue
        existing_exempt = set(k.get('facet_exempt', []))
        new_exempt = existing_exempt | set(exempt_issues)
        k['facet_exempt'] = sorted(new_exempt)
        # 从facet_issues中移除已豁免的
        k['facet_issues'] = [fi for fi in k.get('facet_issues', []) if fi not in new_exempt]
        chf.write_text(json.dumps(kus, ensure_ascii=False, indent=1))
        print(f'  ✓ Ch{ch}[{pt}] 豁免 {exempt_issues} ({reason})', flush=True)

    # ─── 真缺重合成 ───
    print('\n=== ②真缺重合成 ===', flush=True)
    async with httpx.AsyncClient(trust_env=False, timeout=90) as cli:
        for ch, pt in TRUE_LACKING:
            print(f'\n--- Ch{ch} [{pt}] ---', flush=True)
            chf = OUTDIR / f'ch{ch}.json'
            kus = json.loads(chf.read_text())
            existing = next((k for k in kus if k['point'] == pt), None)
            if not existing:
                print(f'  ★不存在', flush=True)
                continue
            chapter = slice_chapter(TEXT, ch)
            should = extract(chapter)
            item = next((it for it in should if it['id'] == pt), None)
            if not item:
                item = {'id': pt, 'type': existing['type'], 'label': existing['label'],
                        'key_terms': existing['key_terms'], 'pos': 0}
            j = await synth_one(cli, chapter, item, sem)
            if not j:
                print(f'  ★合成失败', flush=True)
                continue
            zh = clean_math(j.get('zh', '')); en = clean_math(j.get('en', ''))
            has_latex = bool(re.search(r'\\(frac|lim|int|sqrt|prime|partial)|\$', zh))
            content_ok = any(kt in zh for kt in item['key_terms'])
            fissues = facet_check(item['id'], zh)
            # 保留已豁免项
            exempt = existing.get('facet_exempt', [])
            fissues = [fi for fi in fissues if fi not in exempt]
            for k in kus:
                if k['point'] == pt:
                    old = k.get('facet_issues', [])
                    k['zh'] = zh; k['en'] = en; k['has_formula'] = has_latex
                    k['zh_len'] = len(zh); k['content_match'] = content_ok
                    k['facet_issues'] = fissues
                    if exempt:
                        k['facet_exempt'] = exempt
                    print(f'  ✓ 替换: facet_issues {old}→{fissues} content={content_ok} len={len(zh)}', flush=True)
                    break
            chf.write_text(json.dumps(kus, ensure_ascii=False, indent=1))

    # ─── 汇总 ───
    print('\n\n=== 最终汇总 ===', flush=True)
    total = real_issues = 0
    for ch in [1, 3, 5, 7]:
        chf = OUTDIR / f'ch{ch}.json'
        if not chf.exists(): continue
        kus = json.loads(chf.read_text())
        issues = [(k['point'], k['facet_issues']) for k in kus if k.get('facet_issues')]
        total += len(kus)
        real_issues += len(issues)
        if issues:
            print(f'Ch{ch} 剩余问题: {issues}', flush=True)
        else:
            print(f'Ch{ch} ✓ 全过', flush=True)
    print(f'\n总KU={total} 剩余真问题={real_issues}', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
