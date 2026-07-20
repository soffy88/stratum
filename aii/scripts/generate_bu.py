import asyncio, asyncpg, os, json, httpx
from dotenv import load_dotenv

load_dotenv("aii/.env", override=True)
SUB = os.getenv("SUBSTRATE", "microecon_en_full_v2")
KEY = os.getenv("DEEPSEEK_API_KEY")


# ────────────────────────────────────────────────────────────────────
# 论文分支(2026-07-16, 6篇跨类型实证 → docs/PAPER_BU_SCHEMA)
# 论文≠教材: 不逐章讲透堆概念, 而是产两层——「1」论文理解(人读) + 「skill」agent可调用对象。
# 概念一律只存指针(references_concepts), 通用概念绝不复述; 只内联本篇新造术语(coined_terms)。
# 教材路径完全不走这里(go() 里靠 doc_type:paper frontmatter 早返回)。
# ────────────────────────────────────────────────────────────────────
def _strip_frontmatter(md: str) -> str:
    if md.startswith("---"):
        end = md.find("\n---", 3)
        if end != -1:
            return md[end + 4 :]
    return md


def _condense_paper(md: str, head: int = 30000, tail: int = 11000) -> str:
    body = _strip_frontmatter(md).strip()
    headings = "\n".join(l for l in body.splitlines() if l.lstrip().startswith("#"))[:4000]
    core = body if len(body) <= head + tail else body[:head] + "\n\n[……中略……]\n\n" + body[-tail:]
    return f"【节标题一览】\n{headings}\n\n【正文(首尾,方法/结论/局限多在此)】\n{core}"


_PAPER_SYS = (
    "你把一篇学术论文提炼成结构化记录, 供人查阅和 agent 调用。论文不是教材: 不复述通用概念(教材里就有的、"
    "参考文献里找得到的), 只抓这篇独有的**方法、结论、整体用途**。\n"
    "★★质量红线(最重要): 每个字段的内容必须**具体、有实际用处**——要能让一个 agent 真的据此判断'该不该用'"
    "和'怎么用'。**严禁**: 占位符(如 ±、-\\$、N/A)、空泛套话、无意义乱码或中英混杂的残句。**宁可字段留空, "
    "也不填没信息量的内容**。有数字就写数字, 有条件就写清条件, 保留论文原文的公式/符号/命题编号。忠实不编造。只输出 JSON。\n"
    "字段:\n"
    "  overview_oneline: 一句话这论文干嘛(具体, 不要'本文研究了X'式套话).\n"
    "  problem_statement: 解决什么问题 + 已有方法的缺口.\n"
    "  key_findings: [关键结论/定理, 每条**带成立条件**, 写成一句实在的话].\n"
    "  limitations: [作者自陈的局限/失效边界].\n"
    "  relation_to_prior: 扩展/反驳/涵盖了谁(具体到人名年份或方法名).\n"
    "  contribution_type: 五选一 = method | empirical | impossibility | framework | survey. "
    "★防误用第一闸: impossibility(不可能性/负面)类不能被当'我因此获得了保证'.\n"
    "  method: {approach:总思路, steps:[可执行步骤/配方], inputs:[需要什么输入/数据], outputs:[产出什么]}.\n"
    "  preconditions: [{assumption:前置假设, failure_if_violated:违背会**具体**怎样}] —— 该不该用的硬门.\n"
    "  use_when: [遇到什么任务该想起这篇, 任务形状短语]. do_not_use_when: [硬性排除/别用于什么].\n"
    "  boundary_conditions: [{claim:哪条结论(带命题/定理编号如'Prop3'), direction:方向/符号, "
    "holds_when:**具体**成立条件, reverses_when:**具体**反转/失效条件}]. "
    "★论文的**条件性结论是它最值钱的部分**, 尽量抓全(通常有 3~8 条), 别只敷衍一条; 用论文真实的参数/命题.\n"
    "  key_results: [{metric:测的什么, value:**具体数值或明确定性结论**(如'高估约30%'、'σ_E低时排放反增'), "
    "baseline:对照, dataset:数据/参数设定, condition:在什么条件下}]. 论文给了数字就填数字, 给不出数字就写明确的定性结论+条件; "
    "尽量抓全(3~8 条), 禁止填无信息占位.\n"
    "  reusable_artifacts: [{name:命名, what:可单独复用的技术/公式/招数, where:代码URL或公式/章节位置}].\n"
    "  dependencies: [跑这方法/复现要的前置组件或方法].\n"
    "  references_concepts: [这篇用到的**通用概念名**, 只列名字做指针, 绝不在这里定义它们].\n"
    "  coined_terms: [{term:本篇新造/重定义的术语, definition:本篇给的定义}] —— 只放这篇原创的.\n"
    "  source_excerpts: [{excerpt:支撑核心方法/结论的**原文逐字摘录**(≤150字/≤100词), where:章节/位置}] "
    "—— 供核对忠实性, 只摘真正关键的 3~6 条, 逐字不改写.\n"
    "  application_cases: [{problem:解决什么具体问题, how:怎么用这方法/结论, outcome:结果/效果}] "
    "—— 论文自己给的应用实例(数值实验、案例). 没有就空数组.\n"
    "  test_prompts: {should_invoke:[2~3条**应该**命中这篇技能的任务描述], "
    "should_not_invoke:[2~3条相邻领域但**不该**命中的诱饵任务描述]} —— 供验证检索不误触发.\n"
    "  authors: 作者. venue_year: 出处/年份(可辨则填, 否则空串).\n"
    "★输出**扁平** JSON: 以上字段名都是**顶层键**, 禁止分组塞进 '1'/'skill' 等外层对象。"
)


async def _go_paper(md: str):
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    title = (
        await c.fetchval("SELECT title FROM aii.ingested_substrate WHERE substrate_id=$1", SUB)
        or SUB
    )
    await c.close()

    from aii.api._provider import register_providers
    from obase import ProviderRegistry

    register_providers()
    llm = ProviderRegistry.get().llm("default")
    body = f"论文标题: {title}\n\n{_condense_paper(md)}"
    raw = None
    for attempt in range(3):  # deepseek 偶发坏 JSON(字段多时更易), 重试即好
        try:
            raw = json.loads(llm.call_sync(_PAPER_SYS + "\n\n" + body))
            break
        except json.JSONDecodeError as e:
            if attempt == 2:
                raise
            print(f"  论文卡 JSON 解析失败(重试 {attempt + 1}/2): {e}", flush=True)
    # 防御: LLM 偶尔把字段分组进 '1'/'skill' 外层 → 拍平到顶层
    j = {}
    for k, v in raw.items():
        if k in ("1", "skill", "「1」", "「skill」", "人读", "agent") and isinstance(v, dict):
            j.update(v)
        else:
            j[k] = v
    j["_paper"] = True

    import pathlib

    pathlib.Path("econ_pipeline").mkdir(exist_ok=True)
    pathlib.Path(f"econ_pipeline/bu_{SUB}.json").write_text(
        json.dumps(j, ensure_ascii=False, indent=2)
    )
    print(f"【论文BU】{j.get('overview_oneline', '(缺)')}")
    print(
        f"  贡献类型={j.get('contribution_type')} | 方法步骤={len((j.get('method') or {}).get('steps', []))} "
        f"| use_when={len(j.get('use_when', []))} | key_results={len(j.get('key_results', []))} "
        f"| 概念指针={len(j.get('references_concepts', []))} | 新造术语={len(j.get('coined_terms', []))}"
    )


async def go():
    # ★论文分支: AII_MD_FILE 带 doc_type:paper frontmatter → 走论文范式, 早返回, 不碰下方教材逻辑
    _mdp = os.getenv("AII_MD_FILE")
    if _mdp and os.path.exists(_mdp):
        _md = open(_mdp, encoding="utf-8", errors="replace").read()
        if "doc_type:paper" in _md[:600].lower().replace(" ", ""):
            await _go_paper(_md)
            return
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    kcs = await c.fetch(
        "SELECT community_label FROM aii.kc_onto WHERE substrate_id=$1 AND synthesis_marker='AII章节KC' ORDER BY level",
        SUB,
    )
    hubs = await c.fetch(
        """SELECT cc.name, count(*) d FROM aii.ku_concept_onto kc JOIN aii.concept_onto cc ON kc.concept_id=cc.concept_id
        JOIN aii.ku_onto k ON kc.ku_id=k.ku_id WHERE k.substrate_id=$1 GROUP BY 1 ORDER BY 2 DESC LIMIT 12""",
        SUB,
    )
    # sample KU essences (titles span breadth)
    booktitle = (
        await c.fetchval("SELECT title FROM aii.ingested_substrate WHERE substrate_id=$1", SUB)
        or SUB
    )
    samp = await c.fetch(
        f"SELECT title FROM aii.ku_onto WHERE substrate_id='{SUB}' ORDER BY random() LIMIT 30"
    )
    claims_src = await c.fetch(
        "SELECT ku_id, title, natural_text_zh, natural_text, stance_holder, opposing_stance, grade "
        "FROM aii.ku_onto WHERE substrate_id=$1 AND knowledge_type='positional' ORDER BY created_at LIMIT 20",
        SUB,
    )
    await c.close()

    if not samp:
        # ★2026-07-09 实测: samp(=该substrate下ku_onto全部标题采样)为空即该书0条真实KU——
        # 之前不管有没有数据都照样调LLM, LLM会无视"STRICT不许编"直接用书名编出一段看起来
        # 像真的通用废话(比如"经济学的本质是理解人类行为和决策的科学"), bu_onto存的是纯虚构
        # 内容。0数据时代码侧直接短路, 不给LLM编的机会——诚实标"数据不足", 不伪装成真实理解。
        j = {
            "soul": "[数据不足] 该书暂无可用的知识抽取数据(0条KU), 尚无法生成书级理解",
            "positioning": "",
            "question": "",
            "skeleton": "",
            "thinking": "",
            "for_whom": "",
            "boundary": "",
            "main_claims": [],
            "argument_structure": [],
        }
        import pathlib

        pathlib.Path("econ_pipeline").mkdir(exist_ok=True)
        pathlib.Path(f"econ_pipeline/bu_{SUB}.json").write_text(
            json.dumps(j, ensure_ascii=False, indent=2)
        )
        print(f"\n【①一句话灵魂】\n{j['soul']}")
        return

    topics = "\n".join("- " + k["community_label"] for k in kcs)
    hubtxt = ", ".join(f"{h['name']}({h['d']})" for h in hubs)
    samptxt = ", ".join(s["title"] for s in samp)
    SYS = (
        "You synthesize a BOOK UNDERSTANDING (BU) — the highest-level grasp of a book — by ABSTRACTING from its "
        "knowledge structure (NOT retelling/summarizing chapters). ★STRICT: every claim must be derivable from the "
        "given topics/concepts/KUs. Do NOT fabricate. For 思维方式(way of thinking) and 诚实边界(honest boundaries) "
        "— the most over-reach-prone — assert ONLY what the structure actually shows; if unsure, hedge. "
        "知识骨架 MUST use the data-computed hub concepts given. Output JSON with 7 fields (简体中文): "
        '{"soul":"一句话灵魂","positioning":"背景定位","question":"根本问题","skeleton":"知识骨架(用枢纽概念)",'
        '"thinking":"思维方式","for_whom":"适合谁能干什么","boundary":"诚实边界(不讲什么)"}.'
    )
    body = (
        f"Book: {booktitle}\n\n"
        f"主题KC(知识结构):\n{topics}\n\n"
        f"★数据算出的枢纽概念(度中心, 括号=涉及KU数)= 知识骨架支柱:\n{hubtxt}\n\n"
        f"KU样本(覆盖广度): {samptxt}"
    )

    if claims_src:
        SYS += (
            " Also output 2 more fields grounded ONLY in the given 立场KU列表 below (each already tagged "
            "with a real ku_id) — do NOT invent claims beyond this list, do NOT include a grade field "
            "(grade is filled in by code afterward, not by you): "
            '{"main_claims":[{"ku_id":"(copy from list)","claim":"(compress natural_text into ONE faithful '
            'sentence, no exaggeration)","stance":"(copy given stance_holder verbatim)",'
            '"stance_marker":"(copy given opposing_stance verbatim, or empty)"}],'
            '"argument_structure":[{"ku_id":"(copy from list)","point":"(the reasoning/logic behind the '
            'claim, faithfully distilled from natural_text)","boundary":"(what this claim does NOT cover / '
            'where opposing_stance disagrees, faithfully distilled)","evidence":[{"text":"(verbatim excerpt '
            "<=30 chars from natural_text supporting point, quote don't paraphrase)\"}]}]}."
        )
        claimstxt = "\n".join(
            f"- ku_id={r['ku_id']} | stance_holder={r['stance_holder']} | opposing_stance={r['opposing_stance']} | "
            f"text={(r['natural_text_zh'] or r['natural_text'])[:500]}"
            for r in claims_src
        )
        body += f"\n\n立场KU列表(用于main_claims/argument_structure, 只能从这里面选, 不许编):\n{claimstxt}"

    # ★走 ProviderRegistry: ECON_LLM_PROVIDER=ollama → gemma4(本地); 否则 DeepSeek. call_sync=JSON mode.
    from aii.api._provider import register_providers
    from obase import ProviderRegistry

    register_providers()
    llm = ProviderRegistry.get().llm("default")
    j = json.loads(llm.call_sync(SYS + "\n\n" + body))

    if claims_src:
        grade_by_id = {r["ku_id"]: r["grade"] for r in claims_src}
        main_claims = []
        for c_ in j.get("main_claims") or []:
            g = grade_by_id.get(c_.get("ku_id"))
            if g is None:
                print(f"⚠ main_claims: 丢弃未知ku_id={c_.get('ku_id')!r}(无法回填真实grade)")
                continue
            main_claims.append(
                {
                    "claim": c_.get("claim", ""),
                    "stance": c_.get("stance", ""),
                    "stance_marker": c_.get("stance_marker", ""),
                    "claim_grade": g,
                }
            )
        argument_structure = []
        for a_ in j.get("argument_structure") or []:
            g = grade_by_id.get(a_.get("ku_id"))
            if g is None:
                print(f"⚠ argument_structure: 丢弃未知ku_id={a_.get('ku_id')!r}(无法回填真实grade)")
                continue
            evidence = [
                {"text": e.get("text", "") if isinstance(e, dict) else str(e), "grade": g}
                for e in (a_.get("evidence") or [])
            ]
            argument_structure.append(
                {
                    "point": a_.get("point", ""),
                    "boundary": a_.get("boundary", ""),
                    "evidence": evidence,
                }
            )
        j["main_claims"] = main_claims
        j["argument_structure"] = argument_structure
    else:
        j["main_claims"] = []
        j["argument_structure"] = []

    import pathlib

    pathlib.Path("econ_pipeline").mkdir(exist_ok=True)
    pathlib.Path(f"econ_pipeline/bu_{SUB}.json").write_text(
        json.dumps(j, ensure_ascii=False, indent=2)
    )
    labels = [
        ("①一句话灵魂", "soul"),
        ("②背景定位", "positioning"),
        ("③根本问题", "question"),
        ("④知识骨架", "skeleton"),
        ("⑤思维方式", "thinking"),
        ("⑥适合谁/能干什么", "for_whom"),
        ("⑦诚实边界", "boundary"),
    ]
    for lab, k in labels:
        print(f"\n【{lab}】\n{j.get(k, '(缺)')}")


asyncio.run(go())
