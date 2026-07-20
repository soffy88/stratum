import asyncio, asyncpg, os, json, httpx
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
from dotenv import load_dotenv

load_dotenv(ROOT / "aii" / ".env", override=True)
SUB = os.getenv("SUBSTRATE", "microecon_en_full_v2")
KEY = os.getenv("DEEPSEEK_API_KEY")


_SKILL_KEYS = [
    "contribution_type",
    "method",
    "preconditions",
    "use_when",
    "do_not_use_when",
    "boundary_conditions",
    "key_results",
    "reusable_artifacts",
    "dependencies",
    "references_concepts",
    "coined_terms",
    "source_excerpts",
    "application_cases",
    "test_prompts",
]


async def _persist_paper(bu: dict):
    """论文向 BU 入库(doc_type=paper): 「1」人读字段 + 「skill」agent_skill 对象。教材路径不走这里。"""
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    try:
        from pgvector.asyncpg import register_vector

        await register_vector(c)  # 让 embedding vector 列能收 Python list
    except Exception:
        pass
    for col, typ in [
        ("agent_skill", "jsonb"),
        ("limitations", "jsonb"),
        ("authors", "text"),
        ("venue_year", "text"),
    ]:
        await c.execute(f"ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS {col} {typ}")
    await c.execute("DELETE FROM aii.bu_onto WHERE substrate_id=$1", SUB)
    nkc = await c.fetchval("SELECT count(*) FROM aii.kc_onto WHERE substrate_id=$1", SUB)
    skill = {k: bu.get(k) for k in _SKILL_KEYS if bu.get(k) not in (None, [], {}, "")}
    main_claims = [{"claim": f} for f in (bu.get("key_findings") or []) if f]

    def _asstr(v):  # LLM 偶尔把 authors/venue 返回成 list → 拼成 text
        if isinstance(v, list):
            return ", ".join(str(x) for x in v) or None
        return v or None

    await c.execute(
        """INSERT INTO aii.bu_onto(substrate_id,doc_type,overview_oneline,problem_statement,
        main_claims,limitations,positional_summary,agent_skill,authors,venue_year,grade,synthesis_marker)
        VALUES($1,'paper',$2,$3,$4,$5,$6,$7,$8,$9,'unverified','AII论文理解-方法/结论/用途, 概念只指针')""",
        SUB,
        bu.get("overview_oneline", ""),
        bu.get("problem_statement", ""),
        json.dumps(main_claims, ensure_ascii=False),
        json.dumps(bu.get("limitations") or [], ensure_ascii=False),
        json.dumps({"relation_to_prior": bu.get("relation_to_prior", "")}, ensure_ascii=False),
        json.dumps(skill, ensure_ascii=False),
        _asstr(bu.get("authors")),
        _asstr(bu.get("venue_year")),
    )
    # 技能检索向量: overview+problem+use_when+do_not_use_when → agent 按任务意图检索(/api/skills/search)。
    # 非致命: embed 服务挂了不拦入库, 只是这篇暂不可被技能检索命中(下次重跑补)。
    try:
        rtext = "。".join(
            [bu.get("overview_oneline", ""), bu.get("problem_statement", "")]
            + list(skill.get("use_when", []) or [])
            + list(skill.get("do_not_use_when", []) or [])
        ).strip()
        if rtext:
            from aii.api._provider import register_providers
            from oprim import vector_encode

            register_providers()  # 注册 embedding provider(AiiRemoteEmbedder→aii-embed), 否则回退128维桩
            vec = vector_encode(texts=[rtext], provider="default")[0]
            await c.execute(
                "UPDATE aii.bu_onto SET embedding=$2 WHERE substrate_id=$1",
                SUB,
                [float(x) for x in vec],
            )
            print("  技能检索向量 ✓")
    except Exception as e:
        print(f"  ⚠ 技能检索向量跳过(非致命): {e}")
    await c.close()
    ct = skill.get("contribution_type")
    print(
        f"论文BU入库 ✓ doc_type=paper (关联 {nkc} KC) | 贡献类型={ct} "
        f"| use_when={len(skill.get('use_when', []))} | key_results={len(skill.get('key_results', []))} "
        f"| 概念指针={len(skill.get('references_concepts', []))} | 新造术语={len(skill.get('coined_terms', []))}"
    )


async def go():
    bu = json.loads(Path(f"econ_pipeline/bu_{SUB}.json").read_text())
    if bu.get("_paper"):
        # 防御拍平: 兼容 LLM 把字段分组进 '1'/'skill' 外层(与 generate_bu 一致)
        flat = {}
        for k, v in bu.items():
            if k in ("1", "skill", "「1」", "「skill」", "人读", "agent") and isinstance(v, dict):
                flat.update(v)
            else:
                flat[k] = v
        await _persist_paper(flat)
        return
    # 边界用生成版(忠实校验在 generate 阶段做; 不再硬编码 microecon 边界)
    zh = {
        k: bu[k]
        for k in ["soul", "positioning", "question", "skeleton", "thinking", "for_whom", "boundary"]
    }
    # ★2026-07-09: generate_bu.py 在0-KU时直接短路输出"[数据不足]"占位(其余6字段空字符串),
    # 不是真内容——这里跟着短路,不为占位文本浪费一次翻译LLM调用,grade写'pending'(数据待收集,
    # 不是'unverified'那种"有内容但未核实"的语义)。
    insufficient = not any(
        zh[k] for k in ["positioning", "question", "skeleton", "thinking", "for_whom", "boundary"]
    )
    if insufficient:
        en = {k: zh[k] for k in zh}
    else:
        SYS = "Translate each JSON value to concise English. Output JSON same keys, English values only."
        # ★走 ProviderRegistry: ECON_LLM_PROVIDER=ollama → gemma4(本地); 否则 DeepSeek. call_sync=JSON mode.
        from aii.api._provider import register_providers
        from obase import ProviderRegistry

        register_providers()
        llm = ProviderRegistry.get().llm("default")
        en = json.loads(llm.call_sync(SYS + "\n\n" + json.dumps(zh, ensure_ascii=False)))
    c = await asyncpg.connect(os.getenv("DATABASE_URL"))
    await c.execute("ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS facets_zh jsonb")
    await c.execute("ALTER TABLE aii.bu_onto ADD COLUMN IF NOT EXISTS facets_en jsonb")
    await c.execute("DELETE FROM aii.bu_onto WHERE substrate_id=$1", SUB)
    nkc = await c.fetchval("SELECT count(*) FROM aii.kc_onto WHERE substrate_id=$1", SUB)
    grade = "pending" if insufficient else "unverified"
    await c.execute(
        """INSERT INTO aii.bu_onto(substrate_id,doc_type,overview_oneline,problem_statement,learning_thread,
        facets_zh,facets_en,main_claims,argument_structure,grade,synthesis_marker)
        VALUES($1,'textbook',$2,$3,$4,$5,$6,$7,$8,$9,'AII综合-书级理解,非原文断言')""",
        SUB,
        zh["soul"],
        zh["question"],
        zh["thinking"],
        json.dumps(zh, ensure_ascii=False),
        json.dumps(en, ensure_ascii=False),
        json.dumps(bu.get("main_claims", []), ensure_ascii=False),
        json.dumps(bu.get("argument_structure", []), ensure_ascii=False),
        grade,
    )
    print(
        f"BU入库(校验版) + 双语 ✓ (关联 {nkc} KC, {len(bu.get('main_claims', []))} main_claims, "
        f"{len(bu.get('argument_structure', []))} argument_structure)"
    )
    print("boundary_zh:", zh["boundary"][:60])
    print("soul_en:", en.get("soul", "")[:80])
    await c.close()


asyncio.run(go())
