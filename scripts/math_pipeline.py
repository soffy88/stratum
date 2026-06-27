"""数学专门管道(试 Ch2): 应有清单(定义/定理/概念)驱动讲透→数学打磨→完整性自检→质量门. 不入正式库, 出实物.
★关键: 讲透由确定性应有清单驱动(每知识点一KU), 不靠LLM规划(那会漏). 公式完整=命门."""
import asyncio, os, json, re, sys, httpx
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]; load_dotenv(ROOT/"aii"/".env", override=True)
sys.path.insert(0, str(ROOT/"scripts"))
from chapter_ingest import slice_chapter, SM
from math_should_have import extract
KEY = os.getenv('DEEPSEEK_API_KEY')
# 数学杂乱词(打磨): 含这些的句删
_MATHNONCOV = re.compile(r"未涉及|未覆盖|未出现|未给出|未提及|未定义|未讨论|需查阅|其他资料|建议参考|不在本(章|节)|超出本(章|节)")
def clean_math(t):
    if not t: return ""
    t = re.sub(r"\s*[\[【]\s*第?\s*\d+[-–]?\d*\s*页\s*[\]】]", "", t)  # 去页码溯源
    t = re.sub(r"^\s*(KU|知识单元|类型|概念)\s*[:：].*$", "", t, flags=re.M)  # 去元标记行
    t = t.replace("**", "").replace("##", "")
    kept = [s for s in re.split(r"(?<=[。.！？\n])", t) if s.strip() and not _MATHNONCOV.search(s)]
    return re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()
def facets(typ):
    return {'定义': "定义内容 / 直观含义 / 与相关概念的区别 / 用途",
            '定理': "条件 / 结论 / 证明思路 / 适用场景 / 例子",
            '概念': "是什么 / 核心公式或方法 / 适用条件 / 应用",
            '小节': "该小节核心知识点概述"}.get(typ, "是什么 / 为什么 / 怎么用")
SYS=("你为数学教材合成一个讲透知识单元(KU), 严格只用本章内容、整合非创作。"
     "★数学公式必须完整保留(LaTeX原样, 如 \\frac \\lim), 公式残缺=不合格。"
     "中文主显(简体), 之后附English。书没讲的面直接不写(不要写'未涉及')。"
     'Output JSON {"zh":"<中文讲透,含完整LaTeX公式>","en":"<English>"}.')
async def synth(cli, chapter, item):
    prompt=f"本章内容:\n{chapter[:75000]}\n\n为知识点「{item['label'] or item['id']}」({item['type']}型)合成讲透KU。\n面: {facets(item['type'])}\n中文讲透(公式完整)+English。"
    for _ in range(3):
        try:
            r=await cli.post("https://api.deepseek.com/chat/completions",headers={"Authorization":"Bearer "+KEY},
                json={"model":"deepseek-v4-flash","response_format":{"type":"json_object"},
                      "messages":[{"role":"system","content":SYS},{"role":"user","content":prompt}]})
            j=json.loads(r.json()["choices"][0]["message"]["content"]); return j
        except Exception: await asyncio.sleep(2)
    return None
async def main():
    ch_n = int(sys.argv[1]) if len(sys.argv)>1 else 2
    chapter = slice_chapter(SM.read_text(encoding='utf-8',errors='replace'), ch_n)
    sh = extract(chapter)
    print(f"应有清单: {len(sh)} 知识点", flush=True)
    sem = asyncio.Semaphore(6)
    async with httpx.AsyncClient(trust_env=False, timeout=60) as cli:
        async def one(item):
            async with sem:
                j = await synth(cli, chapter, item)
                if not j: return None
                zh = clean_math(j.get('zh','')); en = clean_math(j.get('en',''))
                has_latex = bool(re.search(r'\\(frac|lim|int|sqrt|prime|partial)|\$', zh))
                return {'point': item['id'], 'type': item['type'], 'label': item['label'],
                        'zh': zh, 'en': en, 'has_formula': has_latex, 'zh_len': len(zh)}
        kus = [k for k in await asyncio.gather(*(one(it) for it in sh)) if k]
    Path(f"{ROOT}/../tmp_math_ch{ch_n}.json").write_text(json.dumps(kus, ensure_ascii=False, indent=1))
    Path("/tmp/claude-1000/-home-soffy-projects-AII/bebc9349-7f09-4086-abef-c4c9a94f4c0c/scratchpad/math_ch2.json").write_text(json.dumps(kus,ensure_ascii=False,indent=1))
    print(f"讲透 {len(kus)} KU (应有{len(sh)})", flush=True)
asyncio.run(main())
