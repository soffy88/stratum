"""用 NVIDIA NIM 对 /books/MD 根目录里"其它"堆积的 MD 做 LLM 学科分类,
把 经济/数学 且有章节结构(飞轮能逐章处理)的搬进对应子文件夹。

    python reclassify_md_llm.py          # dry-run(只报告会搬哪些)
    python reclassify_md_llm.py --apply  # 执行移动

学科判定交给 LLM(不受关键词表/繁简/语言/公式密度限制);
章节结构用 Markdown 标题检测(飞轮按 # 章节处理,无标题的扁平书搬进去也啃不动 → 留在根)。
"""

import os, re, sys, glob, json, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

ROOT = "/home/soffy/books/MD"
APPLY = "--apply" in sys.argv
SUBDIRS = {"经济学", "中文数学", "英文数学"}

# NIM key(与中文数学飞轮共用)
try:
    keys = json.load(open("/data/soffy/projects/stratum/aii/.pipeline_keys.json"))
    os.environ.setdefault("NVIDIA_NIM_API_KEY", keys.get("math_zh", ""))
except Exception as e:
    print(f"⚠ 读 key 失败: {e}", file=sys.stderr)

from oprim.llm.llm_call import llm_call
from oprim.errors import LLMRateLimitError

# 章节结构 = Markdown 标题里像"章"的数量(飞轮逐章处理要这个;扁平书=0)
_CH = re.compile(
    r"(?im)^#{1,4}\s*\*{0,2}\s*(chapter\s+\d+|第\s*[一二三四五六七八九十百千0-9]+\s*[章講]|lecture\s+\d+|part\s+\d+)"
)


def chapter_count(text):
    return len(set(m.lower().strip() for m in re.findall(_CH, text)))


PROMPT = """判断这本书的学科归属。只依据标题和正文样本,返回 JSON,不加解释。

标题: {title}

正文样本:
{sample}

返回格式(严格 JSON):
{{"subject": "经济学|数学|其它", "lang": "zh|en", "is_textbook": true/false, "reason": "简短理由"}}

- subject: 是经济/金融类教材填"经济学";是数学类教材填"数学";其它学科(哲学/心理/历史/纯论文等)填"其它"
- lang: 正文主要语言
- is_textbook: 是系统性教材/讲义(而非论文、随笔、科普故事)填 true"""


def classify_one(path):
    name = Path(path).stem
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except Exception as e:
        return (name, path, {"subject": "其它", "reason": f"读取失败{e}"}, 0)
    ch = chapter_count(text)
    # 跳过封面/版权/目录/广告等前置页,从正文深处取两段(12% 与 45% 处)
    n = len(text)
    if n < 6000:
        sample = text
    else:
        s1 = text[int(n * 0.12) : int(n * 0.12) + 2400]
        s2 = text[int(n * 0.45) : int(n * 0.45) + 2000]
        sample = s1 + "\n……\n" + s2
    prompt = PROMPT.format(title=name, sample=sample)
    for attempt in range(4):
        try:
            r = llm_call(
                prompt=prompt,
                provider="nvidia_nim",
                model="meta/llama-3.1-70b-instruct",
                temperature=0,
            )
            raw = r.text.strip()
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            j = json.loads(m.group(0)) if m else {"subject": "其它", "reason": "无JSON"}
            return (name, path, j, ch)
        except LLMRateLimitError:
            time.sleep(3 + attempt * 2)
        except Exception as e:
            return (name, path, {"subject": "其它", "reason": f"LLM失败:{type(e).__name__}"}, ch)
    return (name, path, {"subject": "其它", "reason": "限流重试耗尽"}, ch)


def route(j, ch, is_zh_guess):
    """→ 目标子文件夹 或 None(留根)。要求:econ/math 学科 + 是教材 + 有≥3章标题。"""
    subj = (j.get("subject") or "").strip()
    if not j.get("is_textbook"):
        return None, "非教材"
    if ch < 3:
        return None, f"无章节结构(ch{ch}),飞轮啃不动"
    if subj == "经济学":
        return "经济学", f"econ 教材 ch{ch}"
    if subj == "数学":
        lang = (j.get("lang") or "").lower()
        return ("中文数学" if lang == "zh" else "英文数学"), f"math 教材 ch{ch} {lang}"
    return None, f"其它学科({subj})"


files = sorted(glob.glob(f"{ROOT}/*.md"))
print(f"待分类 {len(files)} 本(NIM 分类中,约 {len(files) * 1.5 // 60 + 1} 分钟)…", file=sys.stderr)
results = []
with ThreadPoolExecutor(max_workers=4) as ex:
    for i, res in enumerate(ex.map(classify_one, files)):
        results.append(res)
        if (i + 1) % 20 == 0:
            print(f"  …{i + 1}/{len(files)}", file=sys.stderr)

plan = {"经济学": [], "中文数学": [], "英文数学": [], "留在根": []}
for name, path, j, ch in results:
    tgt, why = route(j, ch, False)
    if tgt:
        plan[tgt].append((name, path, why))
    else:
        plan["留在根"].append((name, path, f"{why} [{j.get('subject', '?')}]"))

for k in ["经济学", "中文数学", "英文数学"]:
    v = plan[k]
    print(f"\n=== → 【{k}】 {len(v)} 本 ===")
    for name, _, why in v:
        print(f"   [{why}] {name[:56]}")
print(f"\n=== 留在根(非教材/其它学科/无结构): {len(plan['留在根'])} 本 ===")
for name, _, why in plan["留在根"][:20]:
    print(f"   [{why}] {name[:52]}")
if len(plan["留在根"]) > 20:
    print(f"   … 还有 {len(plan['留在根']) - 20} 本")

if APPLY:
    import shutil

    moved = 0
    for k in ["经济学", "中文数学", "英文数学"]:
        d = f"{ROOT}/{k}"
        os.makedirs(d, exist_ok=True)
        for name, path, _ in plan[k]:
            dst = f"{d}/{Path(path).name}"
            if os.path.exists(dst):
                continue
            shutil.move(path, dst)
            moved += 1
    print(f"\n✓ 已搬 {moved} 本进子文件夹。留根 {len(plan['留在根'])} 本未动。")
else:
    total = sum(len(plan[k]) for k in ["经济学", "中文数学", "英文数学"])
    print(f"\n[dry-run] 会搬 {total} 本。加 --apply 执行。")
