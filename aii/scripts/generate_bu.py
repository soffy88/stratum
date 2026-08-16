import asyncio, asyncpg, os, json, httpx
from dotenv import load_dotenv

load_dotenv("aii/.env", override=True)
SUB = os.getenv("SUBSTRATE", "microecon_en_full_v2")
KEY = os.getenv("DEEPSEEK_API_KEY")

from bu_learning_gate import (  # noqa: E402  (脚本同目录, 运行/测试时均在 sys.path)
    evidence_class_for,
    resolve_verbatim,
    validate_bu_facets,
    validate_learning_layer,
)


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


async def _build_learning_layer() -> dict:
    """BU 学习层(2026-08-14, 按 su-learning-map 学习内容标准):
    3~7 条能力转变路径 + 深卡(证据分级由 KU grade 计算; 原文切片由代码从 grounded_by 注入, 逐字不改写)。
    LLM 只写内容字段; 质量门(bu_learning_gate)确定性修剪; 证据底限不过 → 诚实 insufficient_data。"""
    from bu_learning_gate import evidence_class_for, validate_learning_layer

    if os.getenv("AII_BU_LEARNING", "1") != "1":
        return {"learning_paths": [], "deep_cards": [],
                "bu_quality": {"status": "skipped", "checks": [], "dropped": []}}
    ku_meta, _kc_labels, _hub_names = await _fetch_ku_meta()
    eligible = 0
    for kid, m in ku_meta.items():
        if evidence_class_for([m["grade"]]) and m["verbatim"]:
            eligible += 1
    if eligible == 0:
        return {"learning_paths": [], "deep_cards": [],
                "bu_quality": {"status": "insufficient_data",
                               "checks": [{"check": "evidence_floor", "status": "fail",
                                           "detail": f"{len(ku_meta)} KU 采样中 0 条同时满足 grade 门槛与逐字来源(quote/program_extract)"}],
                               "dropped": []}}
    ku_lines = _ku_lines(ku_meta)
    SYS = (
        "你把一本书的已抽知识单元(KU)组织成「书级学习层」: 3~7 条能力转变路径 + 8~12 张深卡。"
        "这是给人学习用的, 不是给 AI 复述用的。\n"
        "★★数据红线(与 KU 管线同一把尺): 内容只能来自给定 KU 的 title/text, 严禁编造清单之外的任何主张; "
        "不要写 quote(原文由代码注入, 你只选 ku_ids); evidence 不用你填(代码按 KU grade 计算)。\n"
        "★★★长度红线(确定性质量门会精确校验, 不足整卡丢弃——宁可写长不要写短): "
        "context≥50字; arguments 3~5条且合计≥100字; source_digest 2~3段且合计≥220字(每段至少写 80 字); "
        "boundary≥40字; practice 必须含动作词(写/列出/找出/举/挑/选/改/算/评/设计/判断/给出/检查/对比/回答)。\n"
        "路径字段: id(如 p1), no(01…), name(★能力转变命名——学完能做什么, 不是原书章节名), "
        "promise(一句话承诺), card_ids[卡id]。3~7 条路径; 每卡恰好属于一条路径; 路径覆盖全部卡。\n"
        "深卡字段:\n"
        "  id: 1..K 整数(唯一); name: 概念名(优先合并 KU 标题); path: 所属路径 id;\n"
        "  ku_ids: [支撑KU的ku_id, 1~4条, 只从清单选];\n"
        "  desc: 一句话定义; context: 原文在回应什么问题(≥50字);\n"
        "  arguments: 3~5 条论证链(每条一句实在话, 合计≥100字);\n"
        "  source_digest: 2~3 段忠实转述所选 KU 内容(合计≥220字);\n"
        "  boundary: 误用边界/成立条件(≥40字);\n"
        "  connections: [其他卡id];\n"
        "  practice: 一道能写出具体答案的练习(挂钩学习者真实场景, 含动作词)。\n"
        "★输出扁平 JSON: {\"learning_paths\":[…], \"deep_cards\":[…]}。"
    )
    from aii.api._provider import register_providers
    from obase import ProviderRegistry

    register_providers()
    llm = ProviderRegistry.get().llm("default")
    body = f"Book: {SUB}\n\nKU 清单(内容唯一依据):\n{ku_lines}"
    raw = None
    for attempt in range(3):
        try:
            raw = json.loads(llm.call_sync(SYS + "\n\n" + body))
            break
        except json.JSONDecodeError as e:
            if attempt == 2:
                raise
            print(f"  学习层 JSON 解析失败(重试 {attempt + 1}/2): {e}", flush=True)
    if not isinstance(raw, dict):
        raw = {}
    j = {}
    for k, v in raw.items():
        if k in ("1", "skill", "「1」", "「skill」", "人读", "agent") and isinstance(v, dict):
            j.update(v)
        else:
            j[k] = v
    cards = j.get("deep_cards") or []
    if isinstance(cards, dict):
        cards = [v for v in cards.values() if isinstance(v, dict)]
    if not isinstance(cards, list):
        cards = []
    # ★路径 id 归一(LLM 可能返回数字 id): 数字 → 'p<N>'; 卡的 path 引用同步
    paths_raw = j.get("learning_paths")
    if isinstance(paths_raw, list):
        for p in paths_raw:
            if isinstance(p, dict) and p.get("id") is not None and not isinstance(p.get("id"), str):
                p["id"] = f"p{p['id']}"
    for cd in cards:
        if cd.get("path") is not None and not isinstance(cd.get("path"), str):
            cd["path"] = f"p{cd['path']}"
    # ★代码注入逐字切片 + evidence(LLM 无权): 每卡取前 2 条 KU 的逐字来源(quote 或 program_extract 原文)
    def _inject(cards_list):
        for cd in cards_list:
            kids = [k for k in (cd.get("ku_ids") or []) if k in ku_meta]
            excerpts = []
            for k in kids[:2]:
                if ku_meta[k]["verbatim"]:
                    v = ku_meta[k]["verbatim"][0]
                    excerpts.append({"text": v["text"], "ku_id": k, "locator": f"{k}::{v['chunk_id']}"})
            cd["ku_ids"] = kids
            cd["source_excerpts"] = excerpts
            cd["excerpt"] = excerpts[0]["text"] if excerpts else ""  # ★门在字段阶段校验 excerpt 非空
        return cards_list

    _inject(cards)
    res = validate_learning_layer(paths_raw, cards, ku_meta)
    # ★修复轮(≤2, 与 KU 管线 narrow 重抽同哲学): 因长度/练习不达标被门丢弃的卡 → 送回 LLM 携逐卡原因重写 → 重入门
    _length_sigs = ("context<", "argument_chain<", "arguments<", "digest<", "boundary<", "practice_short", "practice_not_actionable")
    for _round in range(2):
        fixable = [d for d in res["quality"]["dropped"] if any(s in d["reason"] for s in _length_sigs)]
        if not fixable:
            break
        fix_ids = {d["card"] for d in fixable}
        fix_cards = [c for c in cards if c.get("id") in fix_ids]
        reasons = "\n".join(f"- 卡{d['card']} {d['name']}: {d['reason']}" for d in fixable)
        REPAIR = (
            "以下深卡被确定性质量门丢弃, 原因是内容未达长度/可操作下限。逐张重写并扩充(可合并相邻概念), 逐条满足: "
            "context≥50字; arguments 3~5条且合计≥100字; source_digest 2~3段且合计≥220字(每段至少 80 字); boundary≥40字; "
            "practice 含动作词(写/列出/找出/举/挑/选/改/算/评/设计/判断/给出/检查/对比/回答)且与学习者真实场景挂钩。"
            "保留原 id/path(ku_ids 可微调, 仍只从 KU 清单选)。\n★输出扁平 JSON: {\"deep_cards\":[…]}"
        )
        body2 = (
            f"Book: {SUB}\n\nKU 清单(内容唯一依据):\n{ku_lines}\n\n"
            f"丢弃原因:\n{reasons}\n\n被丢弃的卡:\n{json.dumps(fix_cards, ensure_ascii=False)[:8000]}"
        )
        try:
            raw2 = json.loads(llm.call_sync(REPAIR + "\n\n" + body2))
            if not isinstance(raw2, dict):
                raw2 = {}
            fix_new = raw2.get("deep_cards") or []
            if isinstance(fix_new, dict):
                fix_new = [v for v in fix_new.values() if isinstance(v, dict)]
            if not isinstance(fix_new, list) or not fix_new:
                break
            _inject(fix_new)
            before_n = len(res["cards"])
            merged = [c for c in cards if c.get("id") not in fix_ids] + fix_new
            res2 = validate_learning_layer(paths_raw, merged, ku_meta)
            if res2["ok"] and len(res2["cards"]) > before_n:
                res = res2
                cards = merged
                print(f"  学习层修复轮{_round + 1}: {len(fix_new)} 张重写 → 存活 {len(res2['cards'])} (+{len(res2['cards']) - before_n})", flush=True)
            else:
                print(f"  学习层修复轮{_round + 1}: 重写后无增益, 停止", flush=True)
                break
        except Exception as e:  # noqa: BLE001
            print(f"  学习层修复轮{_round + 1}失败(保留当前结果): {str(e)[:100]}", flush=True)
            break
    return {"learning_paths": res["paths"], "deep_cards": res["cards"], "bu_quality": res["quality"]}


async def _fetch_ku_meta():
    """共享采样器: KU(逐字来源+文本) + KC 主题 + 枢纽概念(单本数据, 不碰B仓)。
    七项证据挂接与学习层共用; 按 KC 覆盖采样(每 KC 至多 8, 总上限 60), 不够再按 grade 顺序补。"""
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        kc_rows = await c.fetch(
            "SELECT community_label, member_ku_ids FROM aii.kc_onto "
            "WHERE substrate_id=$1 AND synthesis_marker='AII章节KC' ORDER BY level",
            SUB,
        )
        kus = await c.fetch(
            """SELECT ku_id, title, natural_text_zh, natural_text, grade, grounded_by
               FROM aii.ku_onto WHERE substrate_id=$1""",
            SUB,
        )
        hubs = await c.fetch(
            """SELECT cc.name, count(*) d FROM aii.ku_concept_onto kc JOIN aii.concept_onto cc ON kc.concept_id=cc.concept_id
            JOIN aii.ku_onto k ON kc.ku_id=k.ku_id WHERE k.substrate_id=$1 GROUP BY 1 ORDER BY 2 DESC LIMIT 12""",
            SUB,
        )
    finally:
        await c.close()
    by_id = {r["ku_id"]: r for r in kus}
    order = {"verified": 0, "high": 1, "moderate": 2, "unverified": 3,
             "pending": 4, "low": 5, "contradicted": 6, "refuted": 7}
    chosen = {}
    for kc in kc_rows:
        for kid in (kc["member_ku_ids"] or [])[:8]:
            if kid in by_id and kid not in chosen:
                chosen[kid] = by_id[kid]
        if len(chosen) >= 60:
            break
    for r in sorted(by_id.values(), key=lambda r: order.get(r["grade"], 9)):
        if len(chosen) >= 60:
            break
        chosen[r["ku_id"]] = r
    ku_meta = {}
    for kid, r in chosen.items():
        gb = r["grounded_by"]
        if isinstance(gb, str):  # asyncpg jsonb → str, 需解析
            try:
                gb = json.loads(gb)
            except json.JSONDecodeError:
                gb = {}
        ku_meta[kid] = {
            "grade": r["grade"],
            "verbatim": resolve_verbatim(gb, r["natural_text_zh"] or r["natural_text"]),
            "title": str(r["title"] or ""),
            "text": str(r["natural_text_zh"] or r["natural_text"] or "")[:500],
        }
    return ku_meta, [str(k["community_label"]) for k in kc_rows], [str(h["name"]) for h in hubs]


def _ku_lines(ku_meta: dict) -> str:
    return "\n".join(
        f"- ku_id={kid} | grade={m['grade']} | title={m['title'][:60]} | "
        f"text={m['text'][:420]} | 逐字提示={m['verbatim'][0]['text'][:60] if m['verbatim'] else '(无)'}"
        for kid, m in ku_meta.items()
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
    booktitle = (
        await c.fetchval("SELECT title FROM aii.ingested_substrate WHERE substrate_id=$1", SUB)
        or SUB
    )
    samp = await c.fetchval("SELECT count(*) FROM aii.ku_onto WHERE substrate_id=$1", SUB)
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
            "learning_paths": [],
            "deep_cards": [],
            "facets_grounded": [],
            "bu_quality": {"status": "insufficient_data", "checks": [], "dropped": []},
        }
        import pathlib

        pathlib.Path("econ_pipeline").mkdir(exist_ok=True)
        pathlib.Path(f"econ_pipeline/bu_{SUB}.json").write_text(
            json.dumps(j, ensure_ascii=False, indent=2)
        )
        print(f"\n【①一句话灵魂】\n{j['soul']}")
        return

    ku_meta_f, kc_labels, hub_names = await _fetch_ku_meta()
    if not ku_meta_f:
        # 与 0-KU 同等处理: 无 KU 数据则不调 LLM(防编造)
        j = {"soul": "[数据不足] 该书暂无可用的知识抽取数据(0条KU), 尚无法生成书级理解",
             "positioning": "", "question": "", "skeleton": "", "thinking": "", "for_whom": "", "boundary": "",
             "main_claims": [], "argument_structure": [], "learning_paths": [], "deep_cards": [],
             "facets_grounded": [],
             "bu_quality": {"status": "insufficient_data", "checks": [], "dropped": []}}
        import pathlib
        pathlib.Path("econ_pipeline").mkdir(exist_ok=True)
        pathlib.Path(f"econ_pipeline/bu_{SUB}.json").write_text(json.dumps(j, ensure_ascii=False, indent=2))
        print(f"\n【①一句话灵魂】\n{j['soul']}")
        return
    topics = "\n".join("- " + t for t in kc_labels)
    hubtxt = ", ".join(hub_names)
    SYS = (
        "你把一本书的已抽知识单元(KU)组织成「书级理解七项」——每项不是口号, 而是**带依据、可核验的判断**。\n"
        "★★数据红线: 判断只能来自给定 KC 主题/枢纽概念/KU 文本, 严禁编造清单之外的任何主张; "
        "不要写 quote(原文由代码注入), 你只选 ku_ids 或引用枢纽概念名。\n"
        "七项(每项输出对象 {\"text\":…,\"basis\":…,\"ku_ids\":[…]}, 简体中文):\n"
        "  soul: 一句话灵魂——这本书最核心的判断(具体, 不要「本书研究了X」式套话)。\n"
        "  positioning: 背景定位——它在什么传统/问题脉络里, 补了什么缺口。\n"
        "  question: 根本问题——驱动全书的那一个问题。\n"
        "  skeleton: 知识骨架——支柱必须是给定枢纽概念名(至少引用2个), 说明它们怎么撐起全书; ku_ids 选支撑 KU。\n"
        "  thinking: 思维方式——结构实际展示的推理习惯; ★无直接证据就写「从结构推断, 未见直接论述」, 禁止脑补。\n"
        "  for_whom: 适合谁能干什么——基于 KU 实际覆盖的内容判断。\n"
        "  boundary: 诚实边界——结构里没有/不讲什么, 不延伸。\n"
        "basis: 2~4句, 写清「这个判断依据哪些 KC/枢纽/KU 的什么内容」(每项必填)。\n"
        "★输出扁平 JSON: {\"soul\":{…},\"positioning\":{…},…,\"boundary\":{…}} —— 每项都是含 text/basis/ku_ids 的对象。"
    )
    body = (
        f"Book: {booktitle}\n\n"
        f"主题KC(知识结构):\n{topics}\n\n"
        f"★数据算出的枢纽概念(度中心)=知识骨架支柱:\n{hubtxt}\n\n"
        f"KU 样本(内容唯一依据):\n{_ku_lines(ku_meta_f)}"
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

    # ★2026-08-14: 七项证据挂接(按 su-learning-map 证据标准): 代码注入逐字切片+证据分级(LLM 无权); 门修剪
    facets_raw = {k: j.get(k) for k in ("soul", "positioning", "question", "skeleton", "thinking", "for_whom", "boundary")
                  if isinstance(j.get(k), dict)}
    for k in ("soul", "positioning", "question", "skeleton", "thinking", "for_whom", "boundary"):
        if isinstance(j.get(k), str) and str(j.get(k)).strip() and k not in facets_raw:
            # 防御: LLM 返回旧扁平字符串 → 无依据, 门会因 basis 过短丢弃(不伪装成有据)
            facets_raw[k] = {"text": str(j[k]), "basis": "", "ku_ids": []}
    for key, f in facets_raw.items():
        kids = [k for k in (f.get("ku_ids") or []) if k in ku_meta_f]
        exs = []
        for k in kids[:2]:
            if ku_meta_f[k]["verbatim"]:
                v = ku_meta_f[k]["verbatim"][0]
                exs.append({"text": v["text"], "ku_id": k, "locator": f"{k}::{v['chunk_id']}"})
        f["ku_ids"] = kids
        f["excerpts"] = exs
    fres = validate_bu_facets(facets_raw, ku_meta_f, hub_names, kc_labels)
    j["facets_grounded"] = fres["facets"]
    for f in fres["facets"]:
        j[f["key"]] = f["text"]  # 兼容旧扁平字段(前端/持久化)
    for k in ("soul", "positioning", "question", "skeleton", "thinking", "for_whom", "boundary"):
        if not isinstance(j.get(k), str):
            j[k] = ""  # 被门丢弃的项: 诚实留白

    # ★2026-08-14: BU 学习层(按 su-learning-map 标准): 能力路径 + 深卡(证据分级/逐字quote/质量门)
    layer = await _build_learning_layer()
    j["learning_paths"] = layer["learning_paths"]
    j["deep_cards"] = layer["deep_cards"]
    j["bu_quality"] = layer["bu_quality"]
    j["bu_quality"]["facets"] = fres["quality"]

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
    print(
        f"\n【学习层】路径 {len(j['learning_paths'])} 条 / 深卡 {len(j['deep_cards'])} 张 / "
        f"状态 {j['bu_quality']['status']} / 丢弃 {len(j['bu_quality'].get('dropped', []))}"
    )
    print(
        f"【七项】证据挂接 {len(j['facets_grounded'])}/7 项存活 / "
        f"丢弃 {len(fres['quality'].get('dropped', []))}"
    )

if __name__ == "__main__":
    asyncio.run(go())
