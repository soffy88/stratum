"""B 接入版:程序抠数学 KU + 规划审核 → 输出 math_ingest 可用的 staging.
- 内容:程序(0 LLM)——行首标记切"陈述+证明",忠实逐字, 抠出来的文本一字不改。
- 规划审核:每章 1 次 LLM 审核候选标记是否为"真概念"(唯一的LLM用途,~1call/章)——
  正则只管找到"Definition/Theorem/Example N"这类标记, 不管语义; 有的标记是引用
  别处定义的交叉引用、边界切错的半截碎片、或重复项, 这些该在真正抽取内容前就
  被筛掉, 而不是等抠出一堆内容后再去评判(那时已经晚了, 见2026-07-07对话)。
  LLM 只做"留/弃"取舍, 不改写、不生成内容——内容仍是程序逐字忠实抠取。
  无key(NVIDIA_NIM_API_KEY未设)→ fail-open全保留, 退化成纯0LLM版本。
- 命名:程序(0 LLM)——抠书自带括号名, 无则摘首句, 见 name_kus()(实测优于LLM命名)。
- 输出:staging <dir>/ch{N}.json,字段对齐 math_ingest(point/label/type/zh/en/chapter)。
用法: python scripts/math_program_ingest.py <源MD> <substrate_id> [--only-chapter N] [--staging DIR]
之后: python scripts/math_ingest.py --substrate <substrate_id> --staging DIR
"""

import asyncio
import json
import os
import re
import sys
import time
from pathlib import Path

MD = sys.argv[1]
SUBSTRATE = sys.argv[2]
ONLY = int(sys.argv[sys.argv.index("--only-chapter") + 1]) if "--only-chapter" in sys.argv else 0
STAGING = (
    Path(sys.argv[sys.argv.index("--staging") + 1])
    if "--staging" in sys.argv
    else Path(f"scripts/_staging/math_prog/{SUBSTRATE}")
)

MARK = re.compile(
    r"(?m)^\s{0,3}(?:#{1,4}\s*)?(?:\*\*)?\s*"
    r"(Definition|Theorem|Lemma|Proposition|Corollary|Example|定义|定理|引理|推论|命题|例题|例)"
    r"\s*(\d+(?:\.\d+)*)"
)
# ★内容边界止损: 两类MARK识别不了的边界, 不加这些的话最后一个Example/Theorem会把
#   后面不相干的内容全吞掉(直到MAX_LEN硬顶): ①章末收尾段(Summary/Exercises/习题等)
#   和无解的Problem习题; ②普通编号小节标题(如"12.3 Ridge Regression")——新小节开始,
#   哪怕它不是以Definition/Theorem/Example起头(比如先来一段散文+一张图), 也该算作
#   上一条的内容边界(实测吞过下一小节的图注).
STOP = re.compile(
    r"(?m)^\s{0,3}(?:#{1,4}\s*)?(?:\*\*)?\s*"
    r"(?:\d+\.\d+\s+(?:[A-Z]|[一-鿿])"  # 编号小节标题起笔即可: "12.3 Ridge..." / "8.5 摘要"
    r"|(?:\d+\.\d+\s+)?(?:Summary|Further Reading|Exercises?|References?)\b"
    r"|Problem\s+\d+(?:\.\d+)*\b"
    r"|(?:本章小结|小结|习题|练习|参考文献|拓展阅读))"
)


def _stop_before(text, start, hard_end):
    """[start, hard_end) 内第一个 STOP 命中位置; 没有则返回 hard_end."""
    m = STOP.search(text, start, hard_end)
    return m.start() if m else hard_end


_TYPE_ZH = {
    "Definition": "定义",
    "Theorem": "定理",
    "Lemma": "引理",
    "Proposition": "命题",
    "Corollary": "推论",
    "Example": "例子",
}
MAX_LEN = 8000

_KEY = os.getenv("NVIDIA_NIM_API_KEY", "")
_LLM = None
if _KEY:
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT / "aii"))
    from aii.api._provider import register_providers
    from obase import ProviderRegistry

    register_providers()
    _LLM = ProviderRegistry.get().llm("default")

PLAN_AUDIT_SYS = (
    "You audit candidate knowledge units that were mechanically extracted VERBATIM (by regex marker, "
    "no LLM involved) from a math/stats textbook chapter. Each candidate is labeled Definition/Theorem/"
    "Lemma/Proposition/Corollary/Example — ALL SIX of these marker types are, by this pipeline's "
    "design, equally valid standalone knowledge units. A worked Example is NOT 'less conceptual' than "
    "a Definition — it is kept on purpose, as procedural knowledge (it demonstrates HOW to apply a "
    "method). Do NOT drop something just because it is an Example, or because it looks like an "
    "illustration rather than an abstract statement — that is exactly the kind of content this "
    "pipeline wants. "
    "Your job has TWO parts for each candidate: (1) decide keep/drop, (2) give it a short display name.\n\n"
    "PART 1 — keep/drop: catch REGEX BOUNDARY-DETECTION MISTAKES only, not re-judging what counts as "
    "worth knowing. DROP a candidate ONLY if it is clearly a mechanical extraction error: "
    "(a) the marker text is a cross-reference/citation to a definition or theorem stated elsewhere "
    "(e.g. 'as shown in Theorem 3.2' with no actual restatement here) — NOT a case where the item "
    "restates or applies something from elsewhere while still presenting real content of its own; "
    "(b) the excerpt is truly empty of mathematical content — cut off mid-sentence with nothing "
    "substantive, not just short; "
    "(c) it is an exact or near-exact duplicate of another candidate in the list (same statement, "
    "same numbers). "
    "When in doubt, KEEP it. Expect to keep the large majority — this pipeline's whole point is "
    "faithful, complete extraction, and this audit exists only to catch clear extraction accidents, "
    "not to curate 'better' content.\n\n"
    "PART 2 — name (only for items you keep): a short display title (≤20 characters), TYPE-APPROPRIATE:\n"
    "★★LANGUAGE (frequently gotten wrong — follow exactly): the name MUST be in the SAME language as "
    "the candidate's own content shown below. If the candidate text is Chinese, the name MUST be "
    "Chinese — do NOT translate it to English even though these instructions are in English. Only use "
    "English for a name if the candidate's own text is English.\n"
    "• Definition → the TERM/CONCEPT being defined itself (e.g. '反正弦函数', 'Convex Function') — "
    "not a sentence.\n"
    "• Theorem/Lemma/Proposition/Corollary → the theorem's own name if the book gives one (e.g. "
    "'勾股定理', 'Jensen不等式'); otherwise a concise label for WHAT it asserts (e.g. '直角三角形边长关系'), "
    "NOT the full statement/proof verbatim.\n"
    "• Example → a concise label for WHAT is being computed/demonstrated (e.g. '反三角函数复合求值'), "
    "NOT the raw problem text copied verbatim — that produces unreadable LaTeX-cluttered titles.\n"
    "★Only summarize/label using terms already present in the content — do NOT invent facts or results "
    "not in the text; this is a labeling task, not creative writing.\n\n"
    'Output JSON only: {"items": [{"label": "<original label>", "keep": bool, "name": "<display name, '
    'only meaningful if keep=true>"}, ...]} — one entry per candidate given, in any order.'
)


async def _call_with_retry(retries=4, base_delay=8, **kwargs):
    for attempt in range(retries):
        try:
            return await _LLM(**kwargs)
        except Exception as e:
            if attempt == retries - 1:
                raise
            msg = str(e)
            if "429" not in msg and "timed out" not in msg.lower() and "timeout" not in msg.lower():
                raise
            await asyncio.sleep(base_delay * (2**attempt))


async def audit_plan(kus, chapter_n):
    """规划审核: 候选标记里筛掉非真概念(交叉引用/半截碎片/重复); 顺带给类型合适的展示名
    (概念→概念名, 定理→定理名/断言概括, 例子→题目概括——不是逐字摘录整句). 不改内容本身,
    只影响label/是否保留. fail-open."""
    if not _LLM or not kus:
        return kus
    # ★不用方括号包label(如"- [1.1 例 1]: ..."): 实测LLM会把方括号原样抄进返回的label字段
    # (变成"[1.1 例 1]"), 跟真实label对不上, 导致keep交集算成0→安全阀误判"100%丢弃"全回退。
    items = "\n".join(f"- {k['label']}: {k['en'][:180].replace(chr(10), ' ')}" for k in kus)
    content = (
        f"Chapter {chapter_n} candidates ({len(kus)} total):\n{items}\n\n"
        "For each: keep/drop + a type-appropriate display name (see rules)."
    )
    try:
        r = await _call_with_retry(
            messages=[{"role": "user", "content": content}],
            system=PLAN_AUDIT_SYS,
            # ★每条要输出label+keep+name三个字段, 比老版本(只输出keep的label列表)长得多;
            #   固定4000在候选多的章节(48条实测)会截断JSON→解析失败. 按候选数动态给, 留余量.
            max_tokens=min(8000, 800 + 120 * len(kus)),
        )
        t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", t, re.DOTALL)
        parsed = json.loads(m.group(0)).get("items") if m else None
    except Exception as e:
        print(f"  ⚠ ch{chapter_n} 规划审核调用失败(不拦截, 全部保留): {e}", flush=True)
        return kus
    if not parsed:  # 解析失败/空 → fail-open 全保留, 不因判官抽风丢数据
        return kus
    # ★防御性剥离: 万一LLM仍把方括号/引号原样抄进label(见上面注释), 这里兜底清一次.
    by_label = {
        it["label"].strip().strip("[]").strip(): it
        for it in parsed
        if isinstance(it, dict) and it.get("label")
    }
    keep = {lbl for lbl, it in by_label.items() if it.get("keep")}
    # ★安全阀: 单次调用丢弃比例过高(>40%)不可信(实测偶发"对长列表偷懒瞎选"的坏
    #   response, 见2026-07-07: 30条全是干净Definition/Theorem/Example却丢了28条)——
    #   真实0LLM抽取里交叉引用/半截碎片本该是少数, 大规模丢弃更可能是判官抽风,
    #   不是真的抽取质量问题. 回退成全保留, 而不是让一次坏调用吞掉一整章内容.
    drop_ratio = 1 - len(keep & {k["label"] for k in kus}) / len(kus)
    if drop_ratio > 0.4:
        print(
            f"  ⚠ ch{chapter_n} 规划审核丢弃比例异常({drop_ratio:.0%}, 疑似判官抽风)"
            f", 不可信, 回退全保留",
            flush=True,
        )
        return kus
    dropped = [k for k in kus if k["label"] not in keep]
    if dropped:
        print(
            f"  ch{chapter_n} 规划审核: 丢弃{len(dropped)}条非真概念 → "
            + ", ".join(k["label"] for k in dropped[:5]),
            flush=True,
        )
    kept = [k for k in kus if k["label"] in keep]
    for k in kept:
        nm = (by_label.get(k["label"]) or {}).get("name", "").strip()
        if nm:
            k["llm_name"] = nm  # ★name_kus() 优先用书自带括号名, 其次这个, 最后才摘首句
    return kept


def _clean(s):
    s = s.replace("\x00", "")  # PDF抽取偶发NUL字节, postgres text字段直接拒绝插入(非法UTF8)
    out = []
    for ln in s.split("\n"):
        t = ln.strip()
        if re.fullmatch(r"\d{1,4}", t) or re.fullmatch(r"#{1,4}\s*\d*", t):
            continue
        if re.fullmatch(r"(CHAPTER \d+\.?.*|\d+\.\d+\.?\s+[A-Z][A-Z ,\'-]{2,})", t):
            continue
        if re.fullmatch(r"[*_\s]+", t):  # 只剩 **/*/_ 的残留行
            continue
        if re.fullmatch(
            r"#{1,4}\s+\*{0,2}[A-Za-z][^\n]{0,45}", t
        ):  # markdown 页眉/小标题(EXAMPLE 2.16…)
            continue
        out.append(ln)
    txt = re.sub(r"\n{2,}", "\n", "\n".join(out)).strip()
    return txt.replace("**", "").strip()  # 去 markdown 粗体残留(数学用 $/LaTeX 不用 **)


def split_chapters(text):
    """按 'Chapter N' 行首切章;返回 {n: chapter_text}."""
    marks = [
        (int(m.group(1)), m.start())
        for m in re.finditer(r"(?m)^\s*(?:#+\s*)?Chapter\s+(\d+)\b", text)
    ]
    chapters = {}
    for i, (n, pos) in enumerate(marks):
        end = marks[i + 1][1] if i + 1 < len(marks) else len(text)
        if n not in chapters:
            chapters[n] = text[pos:end]
    return chapters


def extract_chapter(ch_text, chapter_n):
    marks = list(MARK.finditer(ch_text))
    kus, seen = [], set()
    for i, m in enumerate(marks):
        typ, num = m.group(1), m.group(2)
        label = f"{typ} {num}"
        if label in seen:
            continue
        seen.add(label)
        start = m.start(1)
        hard_end = min(
            marks[i + 1].start(1) if i + 1 < len(marks) else len(ch_text), start + MAX_LEN
        )
        end = _stop_before(ch_text, start, hard_end)
        content = _clean(ch_text[start:end])
        if len(content) < 15:
            continue
        kus.append(
            {
                "type": _TYPE_ZH.get(typ, typ),
                "label": label,
                "point": label,
                "en": content,
                "zh": "",
                "chapter": chapter_n,
                "key_terms": [],
            }
        )
    return kus


# 名字合法性:首字母大写(或多词)+ 只字母/空格/常见标点,≥3字(排除公式括号如 (A∨B))
_NAME_OK = re.compile(r"^[A-Za-z][A-Za-z ,.\-'’&]+$")
# 中文书自带名(如"阿基米德，来自《圆的度量》"): 含中文字符, 只由中文/字母数字/常见中文标点/书名号组成
_NAME_OK_ZH = re.compile(r"^[一-鿿A-Za-z0-9，,、·（）()《》\-\s]{2,45}$")


def _is_name(s):
    s = s.strip()
    if len(s) < 3:
        return False
    if _NAME_OK.match(s):
        return s[0].isupper() or " " in s
    return bool(_NAME_OK_ZH.match(s) and re.search(r"[一-鿿]", s))


_MARKER_PREFIX = re.compile(
    r"^\s*(?:Definition|Theorem|Lemma|Proposition|Corollary|Example|定义|定理|引理|推论|命题|例题|例)"
    r"\s*[\d.]+\.?\s*"
)


def _fallback_label(body: str, cap: int = 80) -> str:
    """无书自带括号名时, 用陈述本身开头一句逐字摘录当label(仍是0 LLM, 不是编的)。
    比裸标记"Example 8.11"更能让人一眼看出这条讲什么。"""
    body = body.strip()
    if not body:
        return ""
    m = re.match(r"[^.!?。！？\n]{8,%d}[.!?。！？]" % cap, body)
    if m:
        return m.group(0).strip()
    return (body[:cap].strip() + "…") if len(body) > cap else body


def name_kus(kus):
    """命名优先级: ①书自带括号名(0 LLM, 过滤公式括号, 中英文括号都认, 最可信)→
    ②规划审核阶段LLM给的类型合适展示名(audit_plan()写入的k['llm_name']——概念给概念名/
    定理给定理名或断言概括/例子给题目概括, 不是逐字摘录整句; 无key/调用失败时该字段不存在,
    自然跳过不影响) → ③无书自带名也没LLM名时, 摘首句(仍是0 LLM, 不是编的)。
    ★纯0LLM摘首句对Example类尤其容易抠出一整段带LaTeX的题干, 读起来乱七八糟(2026-07-07
    实例: "求(a) sin^{-1}(1/2)和(b) tan(arcsin 1/3)的值"当了标题)——②就是为解决这个加的。"""
    for k in kus:
        k["point"] = k["label"]  # 标记(Theorem X.Y)留 provenance
        en = k["en"].strip()
        m = re.match(
            r"^(?:Definition|Theorem|Lemma|Proposition|Corollary|Example|定义|定理|引理|推论|命题|例题|例)"
            r"\s*[\d.]+\.?\s*[\(（]([^)）]{2,45})[\)）]",
            en,
        )
        if m and _is_name(m.group(1)):
            k["label"] = m.group(1).strip()  # 书自带名: Urysohn / Metric Completion...
        elif k.get("llm_name") and _is_name(k["llm_name"]):
            k["label"] = k["llm_name"]  # 规划审核阶段LLM给的类型合适展示名
        else:
            fb = _fallback_label(_MARKER_PREFIX.sub("", en))
            if fb:
                k["label"] = fb  # 无书自带名也无LLM名 → 陈述开头一句(逐字摘录, 不是编的)
            # 连首句都抠不出(极短/空)才真正保留裸标记(书自己的编号,忠实)


def _headers(text):
    """章头(第N章 / Chapter N)与节头(N.N 标题)的位置, 供扁平编号书按位置定位.
    返回 (chaps=[(pos,章号)], secs=[(pos,'N.N')])."""
    chaps, secs = [], []
    for m in re.finditer(r"(?m)^\s*(?:#+\s*)?(?:Chapter\s+(\d+)|第\s*(\d+)\s*章)", text):
        chaps.append((m.start(), int(m.group(1) or m.group(2))))
    for m in re.finditer(r"(?m)^\s*(?:#+\s*)?(\d+\.\d+)\s+\S", text):
        secs.append((m.start(), m.group(1)))
    return chaps, secs


def _before(items, pos, default=None):
    r = default
    for p, v in items:
        if p <= pos:
            r = v
        else:
            break
    return r


def extract_all(text):
    """整本抽取, 跨标记切、证明全收。兼容两类编号:
    - 层级编号(Theorem 1.3.1, 含'.'): 章号取首位, 全局唯一→按 label 去重(正式书).
    - 扁平编号(例 1, 每节重置): 按'第N章'定章、label 冠以'N.N'节号→同章不同节的"例1"各成一KU
      且 ku_id(sub::章::point) 不撞. 这是中文本科教材(斯图/同济)的形态."""
    # 中文教材定义/定理常用"页边码在前"格式 "5 定义 …"; 翻成 "定义 5" 让 MARK(词在前)命中.
    # 放在抽取器内, 任何来源的 MD(经或未经组装器)都兼容, 不再依赖上游翻转.
    text = re.sub(r"(?m)^(\d+)[ \t]+(定义|定理|引理|推论|命题)(?=[ \t　])", r"\2 \1", text)
    marks = list(MARK.finditer(text))
    chaps, secs = _headers(text)
    kus, seen = [], set()
    for i, m in enumerate(marks):
        typ, num = m.group(1), m.group(2)
        hierarchical = "." in num and num.split(".")[0].isdigit()
        if hierarchical:
            ch = int(num.split(".")[0])
            label = f"{typ} {num}"
        else:
            sec = _before(secs, m.start())
            if sec:
                label = f"{sec} {typ} {num}"
                ch = int(sec.split(".")[0])  # 章号取自节号首位, 与 label 一致
            else:
                ch = _before(chaps, m.start(), 0)  # 无节号时回退'第N章'位置
                # ★没有"N.N小节标题"可用时(如本书只有"第N章", 没有细分小节),
                #   不冠章号会让不同章重置计数的"命题1"们撞进同一个label被去重丢掉
                #   (实测: 一本书238处标记, 180处因此误判"重复"丢失). 冠章号防撞.
                label = f"第{ch}章 {typ} {num}" if ch else f"{typ} {num}"
        if label in seen:
            continue
        seen.add(label)
        start = m.start(1)
        hard_end = min(marks[i + 1].start(1) if i + 1 < len(marks) else len(text), start + MAX_LEN)
        end = _stop_before(text, start, hard_end)
        content = _clean(text[start:end])
        # ★去掉标记本身后须有实质内容(丢 "Theorem 4.6" 这种空标记)
        body = re.sub(
            r"^\s*(?:Definition|Theorem|Lemma|Proposition|Corollary|Example|定义|定理|引理|推论|命题|例题|例)\s*[\d.]+\s*",
            "",
            content,
        )
        if len(body.strip()) < 10:
            continue
        if ch == 0:
            continue  # 前言/预备页 N.N 误命中(如"0.5 例")→ 无真实章号, 丢弃噪音
        kus.append(
            {
                "type": _TYPE_ZH.get(typ, typ),
                "label": label,
                "point": label,
                "en": content,
                "zh": "",
                "chapter": ch,
                "key_terms": [],
            }
        )
    return kus


from collections import Counter, defaultdict


def strip_running_lines(text, min_repeats=12):
    """★去逐页页脚/版权声明: 这类行在全书里逐页重复出现(动辄几十上百次), 真实
    正文几乎不会逐字重复这么多次。PDF→MD转换常把它们拍扁进正文中间(如
    "©2024 ... Cambridge University Press" 出现在一条 Example 的推导里), 0LLM
    抽取会原样忠实保留、污染KU内容——按全书重复频次去重, 不是给某本书写死正则。"""
    lines = text.split("\n")
    cnt = Counter(ln.strip() for ln in lines if 5 <= len(ln.strip()) <= 250)
    noisy = {ln for ln, c in cnt.items() if c >= min_repeats}
    if not noisy:
        return text
    return "\n".join(ln for ln in lines if ln.strip() not in noisy)


text = Path(MD).read_text(encoding="utf-8", errors="replace")
text = strip_running_lines(text)
by_ch = defaultdict(list)
for k in extract_all(text):
    by_ch[k["chapter"]].append(k)
STAGING.mkdir(parents=True, exist_ok=True)
total = 0
for n in sorted(by_ch):
    if ONLY and n != ONLY:
        continue
    kus = by_ch[n]
    if _LLM:
        kus = asyncio.run(audit_plan(kus, n))
        time.sleep(1.8)  # NIM 限流
    name_kus(kus)
    (STAGING / f"ch{n}.json").write_text(
        json.dumps(kus, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    total += len(kus)
    print(
        f"  ch{n}: {len(kus)} KU → 命名样例: "
        + " / ".join(f"{k['label']}={k['point']}" for k in kus[:3])
    )
print(f"★ 完成: {total} KU → {STAGING}  (规划审核LLM调用={'0(无key)' if not _LLM else '章数'})")
