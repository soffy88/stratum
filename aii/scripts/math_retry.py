"""重试: ①5条超时缺失 ②13条真缺例子(重合成含例).
Usage: uv run python scripts/math_retry.py
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

_CN = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
def _cn2int(s):
    if s in _CN: return _CN[s]
    if s.startswith('十'): return 10+(_CN.get(s[1:],0))
    if '十' in s: a,_,b=s.partition('十'); return _CN[a]*10+(_CN.get(b,0) if b else 0)
    return _CN.get(s,0)
def slice_chapter(text, n):
    starts={}
    for m in re.finditer(r'(?m)^第([一二三四五六七八九十]+)章',text):
        line=text[m.start():text.find('\n',m.start()) if text.find('\n',m.start())>0 else m.start()+40]
        if '…' in line or re.search(r'\s\d+\s*$',line): continue
        num=_cn2int(m.group(1))
        if num and num not in starts: starts[num]=m.start()
    if n not in starts: raise SystemExit(f"chapter {n} not found; have {sorted(starts)}")
    s=starts[n]; e=starts.get(n+1,len(text)); return text[s:e]

KEY = os.getenv('DEEPSEEK_API_KEY')
OUTDIR = Path(os.getenv("MATH_OUTDIR", str(ROOT/"scripts"/"_staging"/"math_full")))
MD = Path(os.getenv("AII_MD_FILE",
    "/home/soffy/shared/stratum-to-aii/数学分析(第5版)_上_(华东师范大学数学系)_(z-library.sk,_1_01KVQ2BQ.md"))

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
       '★若章节内有配例题(例1/例2格式), 必须将完整例题纳入KU(包含解题过程)。'
       'Output JSON {"zh":"<中文讲透,含完整LaTeX公式和例题>","en":"<English>"}.')

async def synth_one(cli, chapter, item, sem):
    intro = chapter[:1000]
    p = item.get('pos', 0)
    # ★扩大窗口至 20000 字, 确保捕获定理后的例题
    section = chapter[max(0, p - 300): p + 20000]
    prompt = (f"本章开头(记号约定):\n{intro}\n\n该知识点所在小节:\n{section}\n\n"
              f"为知识点「{item['label'] or item['id']}」({item['type']}型)合成讲透KU。\n"
              f"面: {facets(item['type'])}\n"
              f"★若该知识点后文有例1/例2等例题, 请完整纳入(含解题过程)。\n"
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

async def main():
    TEXT = MD.read_text(encoding='utf-8', errors='replace')

    # ═══ 5条超时缺失: 从should-have取元数据, 合成后追加 ═══
    MISSING = [(1,'区间与邻域'), (3,'定理3.13'), (3,'无穷大量'), (4,'定理4.12'), (9,'定义3')]
    # ═══ 13条真缺例子: 重合成(替换) ═══
    TRUE_LACKING = [
        (10,'定理10.1'),(11,'定理11.6'),(11,'定理11.7'),(11,'定理11.8'),
        (2,'定理2.6'),(3,'定理3.6'),(3,'定理3.12'),
        (6,'定理6.3'),(6,'定理6.11'),(6,'定理6.17'),
        (8,'定理8.4'),(9,'定理9.7'),(9,'定理9.13'),
    ]

    sem = asyncio.Semaphore(6)

    async with httpx.AsyncClient(trust_env=False, timeout=90) as cli:
        # — 超时缺失 —
        for ch, pt in MISSING:
            print(f'\n=== 补齐 Ch{ch} [{pt}] ===', flush=True)
            chapter = slice_chapter(TEXT, ch)
            should = extract(chapter)
            item = next((it for it in should if it['id'] == pt), None)
            if not item:
                print(f'  ★should-have中未找到 [{pt}]', flush=True)
                continue
            j = await synth_one(cli, chapter, item, sem)
            if not j:
                print(f'  ★合成失败', flush=True)
                continue
            zh = clean_math(j.get('zh','')); en = clean_math(j.get('en',''))
            has_latex = bool(re.search(r'\\(frac|lim|int|sqrt|prime|partial)|\$', zh))
            content_ok = any(kt in zh for kt in item['key_terms'])
            fissues = facet_check(item['id'], zh)
            ku = {'point': item['id'], 'type': item['type'], 'label': item['label'],
                  'key_terms': item['key_terms'], 'zh': zh, 'en': en,
                  'has_formula': has_latex, 'zh_len': len(zh),
                  'content_match': content_ok, 'facet_issues': fissues, 'chapter': ch}
            chf = OUTDIR / f'ch{ch}.json'
            kus = json.loads(chf.read_text())
            if any(k['point'] == pt for k in kus):
                print(f'  ★已存在, 跳过', flush=True)
            else:
                kus.append(ku)
                chf.write_text(json.dumps(kus, ensure_ascii=False, indent=1))
                print(f'  ✓ 追加成功: content_match={content_ok} facet_issues={fissues}', flush=True)

        # — 真缺例子重合成 —
        for ch, pt in TRUE_LACKING:
            print(f'\n=== 重合成 Ch{ch} [{pt}] ===', flush=True)
            chf = OUTDIR / f'ch{ch}.json'
            kus = json.loads(chf.read_text())
            existing = next((k for k in kus if k['point'] == pt), None)
            if not existing:
                print(f'  ★不存在', flush=True)
                continue
            # 从should-have获取item元数据(pos等)
            chapter = slice_chapter(TEXT, ch)
            should = extract(chapter)
            item = next((it for it in should if it['id'] == pt), None)
            if not item:
                # fallback: 用existing中pos=0
                item = {'id': pt, 'type': existing['type'], 'label': existing['label'],
                        'key_terms': existing['key_terms'], 'pos': 0}
            j = await synth_one(cli, chapter, item, sem)
            if not j:
                print(f'  ★合成失败', flush=True)
                continue
            zh = clean_math(j.get('zh','')); en = clean_math(j.get('en',''))
            has_latex = bool(re.search(r'\\(frac|lim|int|sqrt|prime|partial)|\$', zh))
            content_ok = any(kt in zh for kt in item['key_terms'])
            fissues = facet_check(item['id'], zh)
            # 替换
            for k in kus:
                if k['point'] == pt:
                    old_issues = k.get('facet_issues', [])
                    k['zh'] = zh; k['en'] = en; k['has_formula'] = has_latex
                    k['zh_len'] = len(zh); k['content_match'] = content_ok
                    k['facet_issues'] = fissues
                    k['key_terms'] = item['key_terms']
                    if k.get('facet_exempt'):
                        for ex in k['facet_exempt']:
                            if ex in k['facet_issues']:
                                k['facet_issues'].remove(ex)
                    print(f'  ✓ 替换: facet_issues {old_issues} → {k["facet_issues"]}', flush=True)
                    break
            chf.write_text(json.dumps(kus, ensure_ascii=False, indent=1))

    print('\n\n=== 全部完成 ===')

if __name__ == '__main__':
    asyncio.run(main())
