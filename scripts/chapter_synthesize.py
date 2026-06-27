"""新范式章节合成(讲透 + 防漏): 按章切 → 规划知识点 → 每点讲透合成(双语+溯源) → 完整性校验防漏 → 补漏.
★规划喂全章(不截断), 合成改定向窗口+程序骨架混合:
  - 程序骨架(多策略): 格式定义框→is/means句式→首次出现句; 例子: EXAMPLE块+数字句+for example
  - 窗口按章节边界截断(治本防污染): 跳过近距离同主题小节, 在第一个≥4000chars的节边界或章末截断
  - LLM只看WHY窗口; 节省~49%/call
  - 无骨架: 标准定向窗口 intro[:1000]+section[pos-WIN_PRE:pos+WIN_POST]
★防漏: 用 planning_completeness(确定性)对照"应有黑体术语/小节"查漏, 漏的补抽.
Usage: chapter_synthesize.py <chapter_n>
"""
import asyncio, json, re, sys
from pathlib import Path
from dotenv import load_dotenv
ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / "aii" / ".env", override=True)
sys.path.insert(0, str(ROOT / "scripts"))
from chapter_ingest import slice_chapter, SM
from aii.api._provider import register_providers
from aii.service.planning_completeness import check_completeness
from obase import ProviderRegistry

# _plan 仍用全章分块喂(规划不截断, 不影响 token).
_CTX = 130000
# ★定向窗口参数 — 每个 KU 合成只喂知识点所在小节, 不喂整章.
_WIN_PRE        = 500    # 知识点 pos 前的 chars(标准路径)
_WIN_POST       = 20000  # 知识点 pos 后的 chars(标准路径)
_WIN_FALLBACK   = 40000  # pos 未找到时 fallback
# ★混合路径参数 — 程序提取了WHAT骨架后, LLM看WHY窗口
# 注意: 不跳过定义区(避免引入段被截断); 节省来自省去 intro[:1000]+pre-pos 500 + 缩短 20K→9K
_WIN_SKEL_DEF   = 0      # 从 pos 开始读(不跳过定义区, 防止"Let bygones"等引入段丢失)
_WIN_POST_HYBRID = 9000  # 从 pos 起读 9K chars(比标准 20K 更小)

PLAN_SYS = ("You identify the knowledge points a textbook chapter DIRECTLY AND SUBSTANTIVELY teaches. "
            "Output valid JSON only.")
SYN_SYS = ("You synthesize ONE thorough KU by INTEGRATING the chapter's material. Use ONLY the chapter text. "
           "Cite [Ch{n}]. Write ONLY what IS substantively covered — skip any facet absent from this chapter "
           "(do NOT write placeholder text like 'not covered'). Integration not creation. Bilingual EN+中文. "
           "★ The Chinese MUST be Simplified Chinese (简体中文) only — NEVER Traditional characters (禁止繁体字).")


# ── 章节边界检测(模块级编译, 治本防污染) ──
_HARD_BOUNDARY_RE = re.compile(
    r'(?mi)^(?:#{1,4}\s+)?(?:\*\*)?'
    r'(?:KEY\s+TERMS?|WHAT\s+YOU\s+SHOULD|QUESTIONS?\s+AND\s+PROBLEMS?'
    r'|REVIEW\s+QUESTIONS?|EXERCISES?|APPENDIX'
    r'|习题|练习题|本章小结|思考题|复习题|关键术语)'
    r'(?:\*\*)?\b'
)
_SOFT_BOUNDARY_RE = re.compile(r'(?m)^#{1,4}\s+')


def _section_end(text: str, after: int, min_dist: int = 4000) -> int:
    """after 之后的实质性节边界(用于截断WHY窗口).
    ★策略: 跳过 <min_dist 的近距离节头(同主题小节); 找第一个 ≥min_dist 的## 或硬边界.
    硬边界(习题/小结等)无视距离直接截断."""
    # 硬边界: 章末/习题区, 无论距离
    mh = _HARD_BOUNDARY_RE.search(text, after + 50)
    hard = mh.start() if mh else len(text)
    # 软边界: 第一个距离 ≥ min_dist 的 ## 标题
    search_from = after + 100
    soft = len(text)
    while True:
        ms = _SOFT_BOUNDARY_RE.search(text, search_from)
        if not ms:
            break
        if ms.start() - after >= min_dist:
            soft = ms.start()
            break
        search_from = ms.end()
    return min(hard, soft)


def _name_variants(name: str) -> list:
    """生成知识点名称的匹配变体: 大写/Title/原始 × 单/复数形式."""
    u, t = name.upper(), name.title()
    out = []
    for base in [u, t, name]:
        out.append(base)
        if not base.rstrip("sS").endswith("s"):  # 如果原始不以s结尾则加复数
            pass
        # 单复数互补
        if base.endswith("S") or base.endswith("s"):
            out.append(base[:-1])  # Cost ← Costs
        else:
            out.append(base + "s")  # Costs ← Cost
    return list(dict.fromkeys(out))  # 去重保序


def _extract_skeleton(text: str, name: str, pos: int):
    """★升级版程序骨架(多策略):
    定义: A.格式定义框(**TERM** ...) → B.is/means/we mean句式 → C.首次出现句(fallback)
    例子: A.**EXAMPLE**块 → B.含数字计算句 → C.for example/e.g./比如句
    窗口: pos-200:pos+3500 (不依赖边界, 搜定义用小窗已够)
    返回: (def_str, [example_str, ...]) — 均为原文片段."""
    win = text[max(0, pos - 200): min(len(text), pos + 3500)]
    variants = _name_variants(name)

    # ── 定义抽取 ──
    bold_def = ""

    # A: 格式定义框 **TERM** sentence (原有,最可信)
    for term in variants:
        m = re.search(rf'\*\*{re.escape(term)}\*\*\s+[^\n*]{{5,150}}', win, re.I)
        if m:
            bold_def = m.group(0).strip()
            break

    # B: "TERM is/are/means/refers to/we mean/is defined as" 句式
    if not bold_def:
        for term in variants[:4]:
            m = re.search(
                rf'\b{re.escape(term)}\b[^.!?\n]{{0,80}}'
                rf'\b(?:is|are|means?|refers?\s+to|we\s+mean|is\s+defined\s+as|represent)\b'
                rf'[^.!?\n]{{10,200}}[.!?]',
                win, re.I)
            if m:
                sent = m.group(0).strip()
                if 25 < len(sent) < 420:
                    bold_def = sent
                    break

    # C: 位置策略 — 含术语的首个非标题短句(fallback)
    if not bold_def:
        name_lo = name.lower()
        for s in re.split(r'(?<=[.!?])\s+|\n\n', win):
            s = s.strip()
            if (name_lo in s.lower()
                    and not s.startswith('#')
                    and 20 < len(s) < 450):
                bold_def = s
                break

    # ── 例子抽取 (多策略) ──
    seen, examples = set(), []

    def _norm_key(s: str) -> str:
        return re.sub(r'\*\*\w[\w\s]*\*\*\s*', '', s).strip()[:60]

    def _add(frag: str, pri: int):
        frag = re.sub(r'^\*\*[A-Z]+\*\*\s*', '', frag).strip()  # 去掉 **EXAMPLE** 前缀
        key = _norm_key(frag)
        if key not in seen and len(frag) > 20:
            examples.append((pri, frag[:280]))
            seen.add(key)

    # A: **EXAMPLE** 块(最可信)
    for m in re.finditer(r'\*\*EXAMPLE\*\*\s*([^\n*]{20,280})', win):
        _add(m.group(1), 0)

    # B: 含百分比/货币/小数的计算句(抓原文数字例子, 如 0.27/-1.32)
    # ★ (?<=[.!?\n ]) 保证从句首开始, 避免匹配 **EXAMPLE** 块内的 [A-Z]
    for m in re.finditer(
        r'(?:(?<=[.!?\n])\s*)([A-Z][^.!?\n*]{8,}'
        r'(?:\d[\d,]*\.?\d*\s*(?:%|percent)|'
        r'\$\s*[\d,]+(?:\.\d+)?|\bε[a-z]?\s*=\s*[\d.]+|equals?\s+[\d.]+)'
        r'[^.!?\n*]{5,150}[.!?])',
        win, re.M):
        frag = m.group(1)
        if re.search(r'\b[a-zA-Z]{4,}\b', frag):  # 过滤纯数字/公式噪音
            _add(frag, 1)

    # C: for example / for instance / 比如 / 例如 (不含 e.g. — 常嵌在公式中产生噪音)
    for m in re.finditer(
        r'(?:for example|for instance|比如|例如)[,\s：]+([A-Z가-힣][^.!?\n]{25,250}[.!?])',
        win, re.I):
        frag = m.group(1)
        if re.search(r'\b[a-zA-Z]{4,}\b', frag):
            _add(frag, 2)

    ordered = ([e for p, e in examples if p == 0][:3]
             + [e for p, e in examples if p == 1][:2]
             + [e for p, e in examples if p == 2][:1])
    return bold_def, ordered[:5]


def _facets(typ):
    return {"concept": "WHAT(内涵essence/外延boundary/用处use), WHY(why true/important), HOW(how applied)",
            "principle": "WHAT(meaning), WHY(rationale/evidence), IMPLICATION(what follows)",
            "method": "WHAT, WHEN, HOW(steps), WHY"}.get(typ, "WHAT, WHY, HOW")


def _find_pos(text_lo: str, name: str) -> int:
    """在小写章文本中定位知识点名称的首次出现位置. 未找到返回 -1."""
    # 先搜全名(前30字符)
    pos = text_lo.find(name.lower()[:30])
    if pos >= 0:
        return pos
    # 搜最长有意义词(>4字符), 按长度降序
    for word in sorted(name.split(), key=len, reverse=True):
        if len(word) > 4:
            pos = text_lo.find(word.lower())
            if pos >= 0:
                return pos
    return -1


async def _plan(llm, text, n):
    """规划仍喂全章(不截断); 额外为每个知识点定位 pos 供 _synth 用."""
    chunks = [text] if len(text) <= _CTX else [text[i:i + _CTX] for i in range(0, len(text), _CTX)]
    pts = []
    for ck in chunks:
        r = await llm(messages=[{"role": "user", "content":
            f"Chapter {n} text (part):\n\n{ck}\n\n"
            f"List ONLY the concepts this chapter DIRECTLY AND SUBSTANTIVELY teaches — "
            f"concepts with their own definition or ≥2 paragraphs of explanation. "
            f"EXCLUDE concepts merely mentioned in passing, used as 1-sentence examples, "
            f"or previewed/introduced for a later chapter. "
            'JSON: {"points":[{"name":"..","type":"concept|principle|method"}]}'}],
            system=PLAN_SYS, max_tokens=700)
        t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", t, re.DOTALL)
        if m:
            pts += json.loads(m.group(0)).get("points", [])
    # dedup by normalized name (单复数/大小写归一)
    seen, out = set(), []
    for p in pts:
        k = re.sub(r"s\b", "", re.sub(r"\s+", " ", p.get("name", "").strip().lower()))[:40]
        if k and k not in seen:
            seen.add(k); out.append(p)
    # ★为每个知识点定位 pos (供 _synth 定向窗口用)
    text_lo = text.lower()
    for p in out:
        found = _find_pos(text_lo, p.get("name", ""))
        p["pos"] = found if found >= 0 else 0
    return out


async def _synth(llm, text, n, name, typ, pos: int = 0):
    """★定向窗口合成 + 程序骨架混合(hybrid):
    pos>0 且程序能提取定义框/例子 → hybrid: 程序WHAT骨架 + LLM只看WHY后段(小窗口)
    pos>0 无骨架 → 标准定向窗口
    pos=0 → fallback 章首40K"""
    bold_def, examples = _extract_skeleton(text, name, pos) if pos > 0 else ("", [])
    has_skeleton = bool(bold_def or examples)

    if pos > 0 and has_skeleton:
        # ── HYBRID路径: 程序已提取WHAT, LLM只看WHY后段 ──
        intro = text[:500]                                          # 短intro(约束/记号)
        # ★ WHY窗口按章节边界截断(治本防污染): 不超过下一个实质性节边界
        boundary  = _section_end(text, pos)
        why_start = min(len(text), pos + _WIN_SKEL_DEF)
        why_end   = min(len(text), why_start + _WIN_POST_HYBRID, boundary)
        why_section = text[why_start:why_end]
        # 骨架提示(直接放进 prompt, 不多余)
        skel = ""
        if bold_def:  skel += f"Extracted definition: {bold_def}\n"
        if examples:  skel += "Extracted examples:\n" + "\n".join(f"• {e[:200]}" for e in examples)
        context = (f"Chapter {n} opening:\n\n{intro}\n\n"
                   f"Programmatic skeleton for \"{name}\":\n{skel}\n\n"
                   f"Section text (after definition):\n\n{why_section}")
        r = await llm(messages=[{"role": "user", "content":
            f"{context}\n\n"
            f"Synthesize ONE thorough KU for: \"{name}\" (type={typ}). "
            f"Include the WHAT from the skeleton above. "
            f"Focus on WHY (importance/rationale — integrate from section, "
            f"SKIP unrelated paragraphs and end-of-chapter questions). "
            f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets. English then 中文."}],
            system=SYN_SYS.format(n=n), max_tokens=1100)

    elif pos > 0:
        # ── 标准定向窗口 (无骨架) ──
        intro   = text[:1000]
        section = text[max(0, pos - _WIN_PRE): pos + _WIN_POST]
        context = f"Chapter {n} opening (notation/context):\n\n{intro}\n\nRelevant section:\n\n{section}"
        r = await llm(messages=[{"role": "user", "content":
            f"{context}\n\nSynthesize ONE thorough KU for: \"{name}\" (type={typ}). "
            f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets. English then 中文."}],
            system=SYN_SYS.format(n=n), max_tokens=1100)

    else:
        # ── Fallback: pos未找到, 章首40K ──
        context = f"Chapter {n} text (opening):\n\n{text[:_WIN_FALLBACK]}"
        r = await llm(messages=[{"role": "user", "content":
            f"{context}\n\nSynthesize ONE thorough KU for: \"{name}\" (type={typ}). "
            f"Facets: {_facets(typ)}. Each [Ch{n}]-cited; skip absent facets. English then 中文."}],
            system=SYN_SYS.format(n=n), max_tokens=1100)

    return name, "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    register_providers(); llm = ProviderRegistry.get().llm("default")
    text = slice_chapter(SM.read_text(encoding="utf-8", errors="replace"), n)
    print(f"chapter {n}: {len(text)} chars", flush=True)
    points = await _plan(llm, text, n)
    print(f"planned {len(points)} knowledge points", flush=True)
    for p in points:
        print(f"  {p['name']}: pos={p.get('pos', 0)}", flush=True)
    sem = asyncio.Semaphore(8)

    async def s(p):
        async with sem:
            return await _synth(llm, text, n, p["name"], p.get("type", "concept"), p.get("pos", 0))
    kus = await asyncio.gather(*(s(p) for p in points))
    names = [k for k, _ in kus]
    # ★防漏: 完整性校验
    comp = check_completeness(text, names)
    print(f"completeness: {comp['covered_terms']}/{comp['total_terms']} terms; "
          f"complete={comp['complete']} missing={comp['missing_bold_terms']}", flush=True)
    # 补漏: 搜 pos 后再调 _synth
    if comp["missing_bold_terms"]:
        text_lo = text.lower()
        fill_pts = []
        for t in comp["missing_bold_terms"]:
            pos = _find_pos(text_lo, t)
            fill_pts.append({"name": t.title(), "type": "concept", "pos": max(0, pos) if pos >= 0 else 0})
        fill = await asyncio.gather(*(s(p) for p in fill_pts))
        kus = list(kus) + list(fill)
        print(f"backfilled {len(fill)} missing → total {len(kus)} KUs", flush=True)
    import os
    Path(os.getenv("PIPELINE_CKPT_DIR", "/tmp") + f"/ch{n}_synth.md").write_text(
        "\n\n".join(f"### {nm}\n{body}" for nm, body in kus), encoding="utf-8")
    print(f"DONE: {len(kus)} thorough KUs (complete after backfill)", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
