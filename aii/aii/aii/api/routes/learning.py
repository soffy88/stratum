"""AII 学习助手模块 API — AII-LEARNING-COACH-SPEC-001 步骤3/4 实现。

流程: 建档(POST /profiles) → 诊断(生成/提交) → 计划生成 → 学习循环(提交任务→裁判判定→
间隔重复排期) → 监督(卡点库/复习队列)。落 C仓 aii_context 的 cx.learning_* 表。

★原则二落地: 裁判必须是"不能撒谎的信号", 不能靠"LLM说你懂了"放行。
  - derivation(推导/证明提交): LLM严格质疑式裁判(默认怀疑, 找漏洞, 不确定时不通过)——
    不是完美的"不能撒谎", 但通过对抗性prompt降低"看起来对就放行"的风险。
  - code(代码提交): 真实subprocess执行, 不是LLM读代码猜对不对——这是本模块唯一严格意义
    上"不能撒谎"的裁判类型(结果客观, 不看LLM怎么想)。
  grade铁律: 默认unverified/learning, 独立通过裁判才 verified; 没过不放行、不升难度。
"""

import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import httpx
from fastapi import APIRouter, Body, HTTPException
from obase import ProviderRegistry

from aii.api._envelope import success_response

router = APIRouter()

CONTEXT_DSN = os.getenv(
    "CONTEXT_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_context"
)
# B仓(aii_refined)——跨database读 rf.refined_ku.ku_type 做裁判路由。与C仓同容器不同库,
# asyncpg一连接一库, 需单独连。
REFINED_DSN = os.getenv(
    "REFINED_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_refined"
)
# ku_type → 默认裁判类型。procedural→真代码执行(最严); conceptual/rationale→Feynman讲解门
# (判"能否讲清"而非拿证明裁判逐字挑刺, 更契合理解类知识); factual→推导兜底(推荐走托管答案速测)。
_TYPE_TO_JUDGE = {
    "procedural": "code",
    "conceptual": "feynman",
    "rationale": "feynman",
    "factual": "derivation",
}
_VERIFIED_BY = {
    "code": "代码跑通(subprocess真实执行)",
    "derivation": "独立推导(LLM严格质疑式裁判)",
    "feynman": "费曼讲解门(能用简单语言讲清)",
    "quiz": "托管答案速测(出题判分解耦)",
}
# 四型错误分类(吸收 DeepTutor)。判官失败时归类, 驱动对症补救 + 让 lesson_pattern 更可迁移。
_ERROR_TYPES = (
    "knowledge_structural",
    "understanding_deviation",
    "application_error",
    "metacognitive",
)
_ERROR_LABEL = {
    "knowledge_structural": "知识结构缺失",
    "understanding_deviation": "理解偏差",
    "application_error": "应用错误",
    "metacognitive": "元认知",
}
_ERR_INSTR = (
    "★若 pass=false, 额外判定 error_type(四选一): "
    "knowledge_structural(缺前置概念/定义没建立) / understanding_deviation(概念理解错或混淆) / "
    "application_error(概念懂但用错/算错/跳步) / metacognitive(空白/没意识到不会/方法选错); "
    "并给 remediation(针对该类型的一句话补救建议)。pass=true 时两者给 null。"
)
MD_ROOTS = [
    Path("/home/soffy/books/MD/中文数学"),
    Path("/home/soffy/books/MD/英文数学"),
    Path("/home/soffy/books/MD/经济学"),
    Path("/home/soffy/books/MD/其它"),
    Path("/mnt/d/books/高级数学经济专用"),
]


async def _ctx_conn():
    return await asyncpg.connect(CONTEXT_DSN)


async def _resolve_knowledge_type(ku_ids: list) -> str | None:
    """从挂靠的 B仓 KU 解析主知识类型(取众数)。空/查不到→None(裁判回退推导)。"""
    if not ku_ids:
        return None
    try:
        conn = await asyncpg.connect(REFINED_DSN)
    except Exception:
        return None
    try:
        rows = await conn.fetch(
            "SELECT ku_type FROM rf.refined_ku WHERE ku_id = ANY($1::text[])",
            [str(k) for k in ku_ids],
        )
    except Exception:
        return None
    finally:
        await conn.close()
    types = [r["ku_type"] for r in rows if r["ku_type"]]
    if not types:
        return None
    return max(set(types), key=types.count)  # 众数


def _mastery_score(attempts: list) -> float:
    """近因加权掌握分 + 置信上限(吸收 DeepTutor)。取最近≤5次 attempt(pass=1/fail=0),
    越近权重越高; 单次答对封顶0.5、两次封顶0.8——一次/两次答对不给'掌握', 防过早达标(原则二)。"""
    if not attempts:
        return 0.0
    recent = attempts[-5:]
    weights = [0.5, 0.7, 0.85, 0.95, 1.0][-len(recent) :]
    num = sum(w * (1.0 if a.get("passed") else 0.0) for w, a in zip(weights, recent))
    den = sum(weights)
    score = (num / den) if den else 0.0
    cap = {1: 0.5, 2: 0.8}.get(len(attempts), 1.0)
    return round(min(score, cap), 3)


def _row(r, jsonb_fields=()):
    d = dict(r)
    for f in jsonb_fields:
        v = d.get(f)
        if isinstance(v, str):
            d[f] = json.loads(v)
    return d


def _find_textbook_md(main_textbook: str) -> Path | None:
    for root in MD_ROOTS:
        p = root / f"{main_textbook}.md"
        if p.exists():
            return p
    return None


async def _llm_json(system: str, user: str, max_tokens: int = 2500) -> dict:
    """调默认LLM provider, 期望JSON输出, 容错抓花括号块解析(同codebase其它LLM调用惯例)."""
    llm = ProviderRegistry.get().llm("learning")  # 学习助手专用 NIM(未注册自动回落 default)
    r = await llm(
        messages=[{"role": "user", "content": user}], system=system, max_tokens=max_tokens
    )
    text = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise HTTPException(502, f"LLM未返回可解析JSON: {text[:300]}")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise HTTPException(502, f"LLM JSON解析失败: {e}; 原文: {text[:300]}") from e


# ── 建档 ──────────────────────────────────────────────────────────────────


@router.post("/learning/profiles")
async def create_profile(
    subject: str = Body(...),
    main_textbook: str = Body(...),
    goal: str = Body(""),
    deadline: str = Body(""),
    b_repo_domain: str = Body("math"),
):
    conn = await _ctx_conn()
    try:
        row = await conn.fetchrow(
            """INSERT INTO cx.learning_profile (subject, goal, deadline, main_textbook, b_repo_domain)
               VALUES ($1,$2,$3,$4,$5) RETURNING profile_id""",
            subject,
            goal,
            deadline,
            main_textbook,
            b_repo_domain,
        )
        return success_response({"profile_id": row["profile_id"]})
    finally:
        await conn.close()


@router.get("/learning/profiles")
async def list_profiles():
    conn = await _ctx_conn()
    try:
        rows = await conn.fetch(
            "SELECT profile_id, subject, goal, main_textbook, created_at FROM cx.learning_profile ORDER BY created_at DESC"
        )
        return success_response([dict(r) for r in rows])
    finally:
        await conn.close()


@router.get("/learning/profiles/{profile_id}")
async def get_profile(profile_id: int):
    conn = await _ctx_conn()
    try:
        profile = await conn.fetchrow(
            "SELECT * FROM cx.learning_profile WHERE profile_id=$1", profile_id
        )
        if not profile:
            raise HTTPException(404, "profile not found")
        plan = await conn.fetchrow(
            "SELECT * FROM cx.learning_plan WHERE profile_id=$1 ORDER BY plan_id DESC LIMIT 1",
            profile_id,
        )
        progress = await conn.fetch(
            "SELECT * FROM cx.learning_progress WHERE profile_id=$1 ORDER BY point_id", profile_id
        )
        stuck = await conn.fetch(
            "SELECT * FROM cx.learning_stuck WHERE profile_id=$1 AND resolved=false ORDER BY occurrences DESC",
            profile_id,
        )
        return success_response(
            {
                "profile": _row(profile, ["real_starting_point", "gaps"]),
                "plan": _row(plan, ["stages", "capabilities"]) if plan else None,
                "progress": [_row(r, ["b_repo_ku_ids", "attempts"]) for r in progress],
                "stuck": [dict(r) for r in stuck],
            }
        )
    finally:
        await conn.close()


# ── 诊断(2.1): 出题 → 提交判真实起点 ────────────────────────────────────────


@router.post("/learning/profiles/{profile_id}/diagnose/generate")
async def diagnose_generate(profile_id: int):
    conn = await _ctx_conn()
    try:
        profile = await conn.fetchrow(
            "SELECT * FROM cx.learning_profile WHERE profile_id=$1", profile_id
        )
    finally:
        await conn.close()
    if not profile:
        raise HTTPException(404, "profile not found")
    textbook_path = _find_textbook_md(profile["main_textbook"])
    excerpt = (
        textbook_path.read_text(encoding="utf-8", errors="replace")[:15000] if textbook_path else ""
    )
    sys_prompt = (
        "你是学习诊断出题老师。根据教材开头内容(目录+前几章), 出5道诊断题, ★覆盖这本书真正要用到的"
        "前置能力(不是书里内容本身, 是学这本书前应该会的东西——如证明技巧/相关领域基础定义/计算能力)。"
        "题目要能测出'真会不会', 不能靠蒙或查资料答对, 覆盖由浅入深的关键前置点。"
        '只输出JSON: {"questions":[{"id":1,"topic":"考察什么","question":"题干"}]}(恰好5题)'
    )
    data = await _llm_json(
        sys_prompt, f"教材《{profile['subject']}》开头内容:\n{excerpt}", max_tokens=2000
    )
    return success_response(data)


@router.post("/learning/profiles/{profile_id}/diagnose/submit")
async def diagnose_submit(
    profile_id: int,
    questions: list = Body(...),
    answers: dict = Body(...),
):
    judge_sys = (
        "你是严格的学习诊断裁判。★原则: 不信自评, 只看实际展示的能力水平——哪怕答案表面'对'也要"
        "指出概念混淆/跳步/量词用词不严谨等实质问题; 未作答或写'不懂'的题目记为该项能力空白, "
        "不要因为题目本身难就放松判定标准。"
        '只输出JSON: {"per_question":[{"id":1,"level":"展示出的真实水平(如: pre-formal直觉/'
        '能写但有漏洞/无法作答)","issues":"具体问题, 没有就空字符串"}],'
        '"real_starting_point":"一段话客观总结真实水位, 不要照顾情面","gaps":["按重要性列出的具体短板"]}'
    )
    payload = json.dumps({"questions": questions, "answers": answers}, ensure_ascii=False)
    verdict = await _llm_json(judge_sys, payload, max_tokens=2500)
    conn = await _ctx_conn()
    try:
        await conn.execute(
            "UPDATE cx.learning_profile SET real_starting_point=$1, gaps=$2, updated_at=now() WHERE profile_id=$3",
            json.dumps(verdict, ensure_ascii=False),
            json.dumps(verdict.get("gaps", []), ensure_ascii=False),
            profile_id,
        )
    finally:
        await conn.close()
    return success_response(verdict)


# ── 计划生成(2.2) ────────────────────────────────────────────────────────


@router.post("/learning/profiles/{profile_id}/plan/generate")
async def plan_generate(profile_id: int):
    conn = await _ctx_conn()
    try:
        profile = await conn.fetchrow(
            "SELECT * FROM cx.learning_profile WHERE profile_id=$1", profile_id
        )
    finally:
        await conn.close()
    if not profile:
        raise HTTPException(404, "profile not found")
    textbook_path = _find_textbook_md(profile["main_textbook"])
    toc = (
        textbook_path.read_text(encoding="utf-8", errors="replace")[:6000] if textbook_path else ""
    )
    gaps_raw = profile["gaps"]
    gaps = json.loads(gaps_raw) if isinstance(gaps_raw, str) else (gaps_raw or [])
    sys_prompt = (
        "你是学习教练, 按学习科学(刻意练习/测试效应/间隔重复/错误驱动)给出课程计划。"
        "★核心原则: 据真实起点诚实评估可行性和时长, 不能因教材难就降低标准, 也不能盲目乐观估时长——"
        "起点越弱, 早期阶段要拆得越细、给的时间要越长。阶段划分对齐教材实际章节结构, 每阶段必须有"
        "'可检查成果'(推导手稿/代码/自测题, 不是看书看视频)和客观'验收标准'。"
        '只输出JSON: {"reality_check":"目标现实性评估, 含总时长现实估计",'
        '"stages":[{"stage":1,"content":"","tasks":"","deliverable":"","acceptance":"","est_weeks":""}],'
        '"capabilities":[{"capability":"","priority":1,"skippable":false}],'
        '"first_week_plan":"第一周每日安排","tools":"所需工具资源","common_mistakes":"常见错误应对",'
        '"today_task":"今天就能开始做的具体任务"}'
    )
    user_prompt = (
        f"教材: {profile['subject']}\n目标: {profile['goal']}\n"
        f"诊断出的真实起点/短板: {json.dumps(gaps, ensure_ascii=False)}\n"
        f"教材目录/开头:\n{toc}"
    )
    plan_data = await _llm_json(sys_prompt, user_prompt, max_tokens=3500)
    conn = await _ctx_conn()
    try:
        row = await conn.fetchrow(
            "INSERT INTO cx.learning_plan (profile_id, stages, capabilities, status) VALUES ($1,$2,$3,'active') RETURNING plan_id",
            profile_id,
            json.dumps(plan_data.get("stages", []), ensure_ascii=False),
            json.dumps(plan_data.get("capabilities", []), ensure_ascii=False),
        )
    finally:
        await conn.close()
    return success_response({"plan_id": row["plan_id"], **plan_data})


# ── 学习循环(2.3): 知识点 + 提交裁判 ─────────────────────────────────────


@router.post("/learning/profiles/{profile_id}/progress")
async def progress_create(
    profile_id: int, point_name: str = Body(...), b_repo_ku_ids: list = Body([])
):
    # ★建点时解析知识类型: 从挂靠的 B仓 KU 取众数 → 决定这个点默认走哪种裁判(P0.2)。
    knowledge_type = await _resolve_knowledge_type(b_repo_ku_ids)
    conn = await _ctx_conn()
    try:
        row = await conn.fetchrow(
            "INSERT INTO cx.learning_progress (profile_id, point_name, b_repo_ku_ids, knowledge_type) VALUES ($1,$2,$3,$4) RETURNING point_id",
            profile_id,
            point_name,
            json.dumps(b_repo_ku_ids),
            knowledge_type,
        )
    finally:
        await conn.close()
    return success_response({"point_id": row["point_id"], "knowledge_type": knowledge_type})


async def _judge_derivation(point_name: str, submission: str) -> dict:
    sys_prompt = (
        "你是极其严格的数学/逻辑裁判, 任务是找出提交内容里的漏洞, 不是判断'看起来对不对'。"
        "★默认怀疑: 逐步核查每一个推导步骤的逻辑链条是否严密, 有没有跳步/循环论证/量词顺序错误/"
        "边界情况漏掉/定义用错。哪怕结论对, 过程有实质性缺陷也判不通过。不确定时默认不通过(宁严勿松)。"
        '只输出JSON: {"pass":true|false,"issues":["逐条列出发现的问题, 没有就空列表"],'
        '"feedback":"给学习者的具体反馈: 错在哪/为什么错/怎么补","error_type":null,"remediation":null}'
        + _ERR_INSTR
    )
    return await _llm_json(
        sys_prompt, f"知识点: {point_name}\n\n提交内容:\n{submission}", max_tokens=1500
    )


async def _judge_feynman(point_name: str, submission: str) -> dict:
    """费曼讲解门(概念/理据类知识的定性裁判, 吸收 DeepTutor)。判"能否用简单语言讲清"——
    不像证明裁判那样逐字挑量词, 而是查三条: ①核心思想对不对 ②有没有漏掉关键前提/条件/边界
    ③是不是真讲清(用自己的话+直觉/例子), 还是只在背教材定义/堆术语。背定义不算通过。"""
    sys_prompt = (
        "你是费曼讲解门裁判, 判定学习者是否'真懂到能讲清一个概念', 而非能否背出定义。"
        "★不要像证明裁判那样逐字挑量词/找边界漏洞——这里判的是理解, 不是形式严谨。"
        "按三条标准判:①核心思想是否正确(有实质错误→不过);②是否漏掉关键前提/条件/适用边界;"
        "③是否真用简单语言+自己的话/直觉/例子讲清(只堆术语或照背教材定义→不过, 哪怕字面没错)。"
        '只输出JSON: {"pass":true|false,"issues":["不通过的具体原因, 通过则空"],'
        '"feedback":"反馈: 哪里讲清了/哪里还没到/怎么讲更清","error_type":null,"remediation":null}'
        + _ERR_INSTR
    )
    return await _llm_json(
        sys_prompt, f"要讲清的知识点: {point_name}\n\n学习者的讲解:\n{submission}", max_tokens=1500
    )


def _judge_code(code: str, expected_stdout: str | None) -> dict:
    """真实执行, 不是LLM读代码猜对不对——本模块唯一严格意义上'不能撒谎'的裁判类型。
    ★subprocess跑, 有超时+临时文件隔离, 非沙箱级别安全隔离(无网络/资源限制), 仅适合单用户自用场景。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
        f.write(code)
        path = f.name
    try:
        r = subprocess.run(["python3", path], capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return {
            "pass": False,
            "issues": ["执行超时(15s), 检查是否死循环"],
            "feedback": "",
            "error_type": "application_error",
            "remediation": "疑似死循环/复杂度失控: 检查循环终止条件与边界",
            "stdout": "",
            "stderr": "",
        }
    finally:
        os.unlink(path)
    ok = r.returncode == 0
    if ok and expected_stdout is not None:
        ok = r.stdout.strip() == expected_stdout.strip()
    # ★代码失败按确定性规则分型: 崩溃(非零退出)=应用错误(代码写崩了); 输出不符=理解偏差(算法/思路对不上)
    if ok:
        error_type, remediation = None, None
    elif r.returncode != 0:
        error_type, remediation = "application_error", "看 traceback 定位崩溃行, 逐步调试运行时错误"
    else:
        error_type, remediation = (
            "understanding_deviation",
            "代码能跑但结果不对, 重新核对你对该问题的理解与算法",
        )
    return {
        "pass": ok,
        "issues": []
        if ok
        else ([f"退出码{r.returncode}"] if r.returncode != 0 else ["输出跟预期不符"]),
        "feedback": (r.stderr[-800:] if r.returncode != 0 else f"实际输出: {r.stdout[:500]}"),
        "error_type": error_type,
        "remediation": remediation,
        "stdout": r.stdout[:2000],
        "stderr": r.stderr[:2000],
    }


def _next_review_interval(attempt_count: int, passed: bool) -> timedelta:
    """间隔重复排期: 通过按粗化SM-2风格间隔递增(1/3/7/14/30/60天), 不过重置到1天(明天再测)."""
    if not passed:
        return timedelta(days=1)
    schedule = [1, 3, 7, 14, 30, 60]
    return timedelta(days=schedule[min(attempt_count, len(schedule) - 1)])


async def _record_attempt(conn, row, passed: bool, verdict: dict, judge_label: str) -> dict:
    """裁判判定后的统一记账: 间隔重测识别 + 掌握度 + verified铁律 + 卡点/教训沉淀。
    progress_submit 与 quiz-answer 共用, 保证两条提交路径的掌握判定完全一致。"""
    point_id = row["point_id"]
    point_name = row["point_name"]
    attempts_raw = row["attempts"]
    attempts = json.loads(attempts_raw) if isinstance(attempts_raw, str) else (attempts_raw or [])

    now = datetime.now(timezone.utc)
    prior_passes = sum(1 for a in attempts if a.get("passed"))
    # ★P0.1 间隔重测: 只有在上次排定的 next_review_at 已到期后、且此前已有过通过, 再次通过才算
    # 真正的间隔重测, 防同一时段连答两次骗过掌握判定(reward hacking)。
    was_due = row["next_review_at"] is not None and now >= row["next_review_at"]
    is_review = bool(passed and prior_passes >= 1 and was_due)

    attempts.append(
        {
            "ts": now.isoformat(),
            "type": judge_label,
            "passed": passed,
            "is_review": is_review,
            "verdict": verdict,
        }
    )
    mastery = _mastery_score(attempts)
    total_passes = sum(1 for a in attempts if a.get("passed"))
    review_passes = sum(1 for a in attempts if a.get("passed") and a.get("is_review"))
    if passed and total_passes >= 2 and review_passes >= 1:
        new_grade, reason = "verified", "已持续通过(含间隔重测), 判定掌握"
    elif passed and total_passes < 2:
        new_grade, reason = "learning", "本次通过, 但需再独立通过一次(且跨间隔重测)才判定掌握"
    elif passed:
        new_grade, reason = "learning", "已通过多次, 但还差一次'到期后的间隔重测'通过才判定掌握"
    else:
        new_grade, reason = "learning", "未通过, 针对性补后重测"

    next_review = now + _next_review_interval(prior_passes, passed)
    await conn.execute(
        """UPDATE cx.learning_progress SET grade=$1, verified_by=$2, last_tested_at=$3,
           next_review_at=$4, attempts=$5, mastery_score=$6, pending_quiz=NULL,
           updated_at=now() WHERE point_id=$7""",
        new_grade,
        _VERIFIED_BY.get(judge_label, judge_label),
        now,
        next_review,
        json.dumps(attempts, ensure_ascii=False),
        mastery,
        point_id,
    )

    error_type = verdict.get("error_type") if verdict.get("error_type") in _ERROR_TYPES else None
    if not passed:
        existing_stuck = await conn.fetchrow(
            "SELECT stuck_id, occurrences FROM cx.learning_stuck WHERE profile_id=$1 AND point_name=$2 AND resolved=false",
            row["profile_id"],
            point_name,
        )
        first_issue = (verdict.get("issues") or [""])[0]
        if existing_stuck:
            new_occ = existing_stuck["occurrences"] + 1
            await conn.execute(
                "UPDATE cx.learning_stuck SET occurrences=$1, error_type=COALESCE($2, error_type) WHERE stuck_id=$3",
                new_occ,
                error_type,
                existing_stuck["stuck_id"],
            )
            # ★反复卡(>=3次)且还没沉淀过 → 升 cx.lesson_pattern(教训模式化, 学习也产生可复用教训)。
            # 带上错误类型标签, 让沉淀出的教训更可迁移(是知识缺口还是应用失误)。
            if new_occ >= 3:
                already = await conn.fetchval(
                    "SELECT count(*) FROM cx.lesson_pattern WHERE trigger_context = $1",
                    f"学习'{point_name}'相关知识点时",
                )
                if not already:
                    tag = _ERROR_LABEL.get(error_type, "反复卡")
                    await conn.execute(
                        "INSERT INTO cx.lesson_pattern (statement, trigger_context, evidence_case_ids) VALUES ($1,$2,$3)",
                        f"在'{point_name}'反复卡住({new_occ}次, {tag}): {first_issue}",
                        f"学习'{point_name}'相关知识点时",
                        json.dumps([existing_stuck["stuck_id"]]),
                    )
        else:
            await conn.execute(
                "INSERT INTO cx.learning_stuck (profile_id, point_name, stuck_pattern, error_type) VALUES ($1,$2,$3,$4)",
                row["profile_id"],
                point_name,
                first_issue,
                error_type,
            )

    return {
        "passed": passed,
        "grade": new_grade,
        "mastery_score": mastery,
        "reason": reason,
        "error_type": error_type,
        "error_label": _ERROR_LABEL.get(error_type),
        "remediation": verdict.get("remediation"),
        "judge": judge_label,
        "is_review": is_review,
        "verdict": verdict,
        "next_review_at": next_review.isoformat(),
    }


async def _judge_point(conn, row, submission, submission_type=None, expected_stdout=None) -> dict:
    """按知识类型路由裁判 + 记账。progress_submit 与 tutor_turn 共用, 保证判分口径一致。
    ★P0.2: 未显式指定 submission_type 时由挂靠KU的 knowledge_type 决定
    (procedural→代码执行; conceptual/rationale→Feynman讲解门; factual→推导兜底/推荐速测)。"""
    if submission_type is None:
        submission_type = _TYPE_TO_JUDGE.get(row["knowledge_type"], "derivation")
    if submission_type == "code":
        verdict = _judge_code(submission, expected_stdout)
    elif submission_type == "feynman":
        verdict = await _judge_feynman(row["point_name"], submission)
    else:
        submission_type = "derivation"
        verdict = await _judge_derivation(row["point_name"], submission)
    return await _record_attempt(conn, row, bool(verdict.get("pass")), verdict, submission_type)


@router.post("/learning/progress/{point_id}/submit")
async def progress_submit(
    point_id: int,
    submission: str = Body(...),
    submission_type: str | None = Body(None),  # None→按 knowledge_type 自动路由; 显式给则覆盖
    expected_stdout: str | None = Body(None),
):
    conn = await _ctx_conn()
    try:
        row = await conn.fetchrow("SELECT * FROM cx.learning_progress WHERE point_id=$1", point_id)
        if not row:
            raise HTTPException(404, "point not found")
        result = await _judge_point(conn, row, submission, submission_type, expected_stdout)
    finally:
        await conn.close()
    return success_response(result)


# ── 服务端答案托管速测(P1.3): 出题(答案存服务端) → 作答(对照标准答案判分) ────────────


async def _fetch_ku_context(ku_ids: list, limit: int = 8) -> str:
    """取挂靠 B仓 KU 的正文, 作为出题/判分的锚定材料(引证式, 不让LLM凭空出题)。"""
    if not ku_ids:
        return ""
    try:
        conn = await asyncpg.connect(REFINED_DSN)
    except Exception:
        return ""
    try:
        rows = await conn.fetch(
            "SELECT point, natural_text FROM rf.refined_ku WHERE ku_id = ANY($1::text[]) LIMIT $2",
            [str(k) for k in ku_ids],
            limit,
        )
    except Exception:
        return ""
    finally:
        await conn.close()
    return "\n\n".join(f"- {r['point'] or ''}: {(r['natural_text'] or '')[:400]}" for r in rows)


@router.post("/learning/progress/{point_id}/quiz")
async def quiz_pose(point_id: int):
    """LLM 出一道题, 标准答案存服务端(不返回)。出题锚定该点的 B仓 KU。"""
    conn = await _ctx_conn()
    try:
        row = await conn.fetchrow("SELECT * FROM cx.learning_progress WHERE point_id=$1", point_id)
        if not row:
            raise HTTPException(404, "point not found")
        ku_ids = (
            json.loads(row["b_repo_ku_ids"])
            if isinstance(row["b_repo_ku_ids"], str)
            else (row["b_repo_ku_ids"] or [])
        )
        context = await _fetch_ku_context(ku_ids)
        sys_prompt = (
            "你为一个知识点出一道速测题, 用于检验学习者是否真掌握。题目要有唯一/可判定的标准答案, "
            "不能是开放式空谈。★标准答案由你现在一并给出, 但只有'题目'会展示给学习者、'答案'存服务端"
            "供判分——所以答案要写具体、可比对。优先依据给定的知识材料出题。"
            '只输出JSON: {"question":"题干","expected":"标准答案(具体, 可判定)"}'
        )
        user = (
            f"知识点: {row['point_name']}\n\n知识材料(依据):\n{context or '(无, 按知识点名称出题)'}"
        )
        quiz = await _llm_json(sys_prompt, user, max_tokens=900)
        quiz["posed_at"] = datetime.now(timezone.utc).isoformat()
        await conn.execute(
            "UPDATE cx.learning_progress SET pending_quiz=$1, updated_at=now() WHERE point_id=$2",
            json.dumps(quiz, ensure_ascii=False),
            point_id,
        )
    finally:
        await conn.close()
    return success_response({"question": quiz["question"]})  # ★不返回 expected


async def _judge_quiz_answer(question: str, expected: str, answer: str) -> dict:
    """对照服务端标准答案判分。裁判看得到标准答案(有 ground truth), 因此不是'出题模型自己给自己放水'——
    判等价性(允许表述不同但实质一致), 实质不符/漏关键点→不过。"""
    sys_prompt = (
        "你判定学习者的作答是否与标准答案实质等价。★你手里有标准答案, 只需比对: 允许表述、记法、"
        "步骤顺序不同, 但核心结论/关键量必须一致; 缺关键点、结论错、答非所问→不过。宁严勿松。"
        '只输出JSON: {"pass":true|false,"issues":["不符之处, 通过则空"],"feedback":"简短反馈",'
        '"error_type":null,"remediation":null}' + _ERR_INSTR
    )
    user = f"题目:\n{question}\n\n标准答案:\n{expected}\n\n学习者作答:\n{answer}"
    return await _llm_json(sys_prompt, user, max_tokens=1000)


@router.post("/learning/progress/{point_id}/quiz-answer")
async def quiz_answer(point_id: int, answer: str = Body(..., embed=True)):
    conn = await _ctx_conn()
    try:
        row = await conn.fetchrow("SELECT * FROM cx.learning_progress WHERE point_id=$1", point_id)
        if not row:
            raise HTTPException(404, "point not found")
        pq_raw = row["pending_quiz"]
        pq = json.loads(pq_raw) if isinstance(pq_raw, str) else pq_raw
        if not pq:
            raise HTTPException(400, "没有待答的题, 先调用 /quiz 出题")
        verdict = await _judge_quiz_answer(pq["question"], pq["expected"], answer)
        result = await _record_attempt(conn, row, bool(verdict.get("pass")), verdict, "quiz")
    finally:
        await conn.close()
    return success_response(result)


# ── 自动生成可测知识点(P1.2): 从主教材 B仓 KU 拆解, 每点挂靠真实 KU ──────────────


def _parse_toc_sections(md_text: str) -> list:
    """从教材MD解析有序小节: [{"num":"2.4","chapter":2,"title":"EquivalenceRelations"}]。
    dedup保留首次出现——TOC在正文前, 故拿到的是TOC的顺序与标题(正文里的重复出现被跳过)。"""
    seen, order = set(), []
    for line in md_text.splitlines():
        m = re.match(r"^(\d+)\.(\d+)\s+(.+)$", line.strip())
        if not m:
            continue
        num = f"{m.group(1)}.{m.group(2)}"
        if num in seen:
            continue
        title = re.sub(r"[.\s]{3,}.*$", "", m.group(3)).strip().rstrip(".")  # 去点导+页码
        if not title:
            continue
        seen.add(num)
        order.append({"num": num, "chapter": int(m.group(1)), "title": title})
    return order


def _ku_section(contributions) -> str | None:
    """从KU的 raw_ku_id(如 '...::6::Definition 6.1.5')提取所属小节号 '6.1'。"""
    contribs = (
        json.loads(contributions) if isinstance(contributions, str) else (contributions or [])
    )
    for c in contribs:
        label = (c.get("raw_ku_id") or "").split("::")[-1]
        m = re.search(r"(\d+)\.(\d+)", label)
        if m:
            return f"{m.group(1)}.{m.group(2)}"
    return None


@router.post("/learning/profiles/{profile_id}/generate-points")
async def generate_points(profile_id: int, chapters: list = Body(..., embed=True)):
    """★按主教材 MD 的真实章节结构生成学习点(SPEC §1: 主线=主教材章节顺序)。
    对选定章节, 逐小节(按书中顺序)建一个学习点, 把该小节的 B仓 KU 挂上去——KU 挂到相应章节去学,
    不再是把 KU 当无序碎片让 LLM 随便归组。每个点 grounded 在真实抽取知识上。"""
    conn = await _ctx_conn()
    try:
        profile = await conn.fetchrow(
            "SELECT * FROM cx.learning_profile WHERE profile_id=$1", profile_id
        )
    finally:
        await conn.close()
    if not profile:
        raise HTTPException(404, "profile not found")

    md_path = _find_textbook_md(profile["main_textbook"])
    if not md_path:
        raise HTTPException(404, "找不到主教材 MD 文件")
    toc = _parse_toc_sections(md_path.read_text(encoding="utf-8", errors="replace"))
    want_ch = set(int(c) for c in chapters)
    toc = [s for s in toc if s["chapter"] in want_ch]
    if not toc:
        raise HTTPException(404, f"教材 TOC 里没有第 {sorted(want_ch)} 章的小节")

    substrate = "math_prog_" + hashlib.md5(profile["main_textbook"].encode()).hexdigest()[:10]
    rconn = await asyncpg.connect(REFINED_DSN)
    try:
        kus = await rconn.fetch(
            "SELECT ku_id, ku_type, contributions FROM rf.refined_ku WHERE contributions @> $1::jsonb",
            json.dumps([{"book_id": substrate}]),
        )
    finally:
        await rconn.close()
    if not kus:
        raise HTTPException(404, f"B仓没有该教材({substrate})的KU——教材是否已走 A→B 灌库?")

    # KU 按小节号归组
    by_section: dict[str, list] = {}
    for r in kus:
        sec = _ku_section(r["contributions"])
        if sec:
            by_section.setdefault(sec, []).append(r)

    conn = await _ctx_conn()
    created, empty = [], []
    try:
        existing = {
            row["point_name"]
            for row in await conn.fetch(
                "SELECT point_name FROM cx.learning_progress WHERE profile_id=$1", profile_id
            )
        }
        for s in toc:  # ★按书中小节顺序建点
            sec_kus = by_section.get(s["num"], [])
            name = f"§{s['num']} {s['title']}"[:300]
            if not sec_kus:
                empty.append(s["num"])
                continue
            if name in existing:
                continue
            ku_ids = [r["ku_id"] for r in sec_kus]
            types = [r["ku_type"] for r in sec_kus if r["ku_type"]]
            ktype = max(set(types), key=types.count) if types else None
            row = await conn.fetchrow(
                "INSERT INTO cx.learning_progress (profile_id, point_name, b_repo_ku_ids, knowledge_type) VALUES ($1,$2,$3,$4) RETURNING point_id",
                profile_id,
                name,
                json.dumps(ku_ids),
                ktype,
            )
            created.append(
                {
                    "point_id": row["point_id"],
                    "name": name,
                    "knowledge_type": ktype,
                    "ku_count": len(ku_ids),
                }
            )
    finally:
        await conn.close()
    return success_response(
        {"created": created, "count": len(created), "sections_without_kus": empty}
    )


# ── KU 中文显示(§1.4): 本地LLM译+GLOSSARY术语约束+缓存natural_text_zh, 原文永不丢 ────

OLLAMA_BASE = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
TRANSLATE_MODEL = os.getenv("LEARNING_TRANSLATE_MODEL", "qwen2.5vl:7b")
# ★复用 AII-GLOSSARY-001 的锁定术语: 显示层翻译绝不能把这些本体术语用通用机翻毁掉
# (invariant→本性 而非"不变的"; positional→立场性 而非"位置的")。
_GLOSSARY_ZH = {
    "invariant": "本性",
    "invariant concept": "本性概念",
    "invariant-shared": "本性同源",
    "positional": "立场性",
    "conceptual": "概念性",
    "factual": "事实性",
    "procedural": "程序性",
    "explanatory": "解释性",
    "metacognitive": "元认知",
    "appearance": "相",
    "concept co-reference": "概念共指",
    "knowledge unit": "知识单元",
    "knowledge cluster": "知识簇",
}


# prompt 回显/翻译失败的特征串: 命中任一 → 判定这次翻译是废的, 不缓存
_ECHO_MARKERS = ("忠实翻译", "术语对照表", "只输出译文", "→ 本性", "英文原文:", "AII术语")


def _bad_translation(out: str, text_en: str) -> bool:
    """判翻译是否失败(小模型偶发把prompt回显/不翻/输出爆长)。失败则不缓存, 保留英文。"""
    if not out or not out.strip():
        return True
    if any(m in out for m in _ECHO_MARKERS):  # 回显了指令
        return True
    if not re.search(r"[一-鿿]", out):  # 没有中文=没翻
        return True
    if len(out) > max(400, len(text_en) * 4):  # 爆长=多半在瞎扯
        return True
    return False


async def _translate_zh_local(text_en: str) -> str | None:
    """本地 LLM(Ollama) 受控翻译: GLOSSARY术语锁定 + 忠实翻译纪律(翻'相'不改'道')。
    ★零云依赖(不走通用MT API), 术语受控(不被通用机翻毁掉)——见 SPEC §1.4 方案C。
    输出校验: 命中回显/无中文/爆长 → 重试一次, 仍废则返回 None(调用方不缓存, 保留英文)。"""
    glossary = "; ".join(f"{k}={v}" for k, v in _GLOSSARY_ZH.items())
    # ★指令在前、待译文本用清晰分隔符包在最后, 降低小模型把指令回显当输出的概率。
    prompt = (
        "你是翻译器。把 <原文> 里的英文忠实翻译成中文并直接给出译文:\n"
        "- 换语言, 不重新表述、不增删、不解释;\n"
        f"- 锁定术语(左英右中, 出现即用): {glossary};\n"
        "- 数学术语用标准译名(theorem=定理, metric space=度量空间, injective=单射)。\n"
        f"<原文>\n{text_en}\n</原文>\n译文:"
    )
    async with httpx.AsyncClient(timeout=180, trust_env=False) as client:
        for _ in range(2):
            try:
                r = await client.post(
                    f"{OLLAMA_BASE}/api/generate",
                    json={
                        "model": TRANSLATE_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.1},
                    },
                )
                r.raise_for_status()
                out = r.json()["response"].strip()
            except Exception:
                continue
            if not _bad_translation(out, text_en):
                return out
    return None  # 两次都废: 不缓存, 前端显示英文原文


async def _ku_display_rows(ku_ids: list) -> list:
    """取KU用于学习显示: 中文(缺则本地LLM按需翻译+缓存natural_text_zh) + 英文原文 + 多出处。"""
    if not ku_ids:
        return []
    rconn = await asyncpg.connect(REFINED_DSN)
    try:
        rows = await rconn.fetch(
            "SELECT ku_id, point, natural_text, natural_text_zh, zh_grade, contributions FROM rf.refined_ku WHERE ku_id = ANY($1::text[])",
            [str(k) for k in ku_ids],
        )
        out = []
        for r in rows:
            zh, zh_grade = r["natural_text_zh"], r["zh_grade"]
            # ★按需触发: 无中文且有英文 → 本地LLM翻一次, 校验通过才落库缓存(一次翻译永久用)。
            # 翻译失败(回显/无中文/爆长)→ 不缓存垃圾, zh 留空, 前端回退显示英文原文。
            if not zh and r["natural_text"]:
                translated = await _translate_zh_local(r["natural_text"])
                if translated:
                    zh, zh_grade = translated, "unverified"
                    await rconn.execute(
                        "UPDATE rf.refined_ku SET natural_text_zh=$1, zh_grade=$2, updated_at=now() WHERE ku_id=$3",
                        zh,
                        zh_grade,
                        r["ku_id"],
                    )
            contribs = r["contributions"]
            contribs = json.loads(contribs) if isinstance(contribs, str) else (contribs or [])
            sources = sorted(
                {
                    c.get("source_book_id") or c.get("book_id")
                    for c in contribs
                    if c.get("source_book_id") or c.get("book_id")
                }
            )
            out.append(
                {
                    "ku_id": r["ku_id"],
                    "point": r["point"],
                    "natural_text_zh": zh,
                    "natural_text": r["natural_text"],
                    "zh_grade": zh_grade,
                    "sources": sources,
                }
            )
        return out
    finally:
        await rconn.close()


@router.get("/learning/progress/{point_id}/kus")
async def point_kus(point_id: int):
    """一个知识点挂靠的 B仓 KU, 带中文显示(按需翻译+缓存)+英文原文+多出处——学习底座。"""
    conn = await _ctx_conn()
    try:
        row = await conn.fetchrow(
            "SELECT b_repo_ku_ids FROM cx.learning_progress WHERE point_id=$1", point_id
        )
        if not row:
            raise HTTPException(404, "point not found")
        ku_ids = (
            json.loads(row["b_repo_ku_ids"])
            if isinstance(row["b_repo_ku_ids"], str)
            else (row["b_repo_ku_ids"] or [])
        )
    finally:
        await conn.close()
    return success_response(await _ku_display_rows(ku_ids))


@router.post("/learning/kus/{ku_id}/correct-zh")
async def correct_ku_zh(
    ku_id: str, corrected_zh: str = Body(...), note: str = Body("", embed=False)
):
    """Wiki 校对/修正机器译文 → 升 verified。★这条修正本身是一条术语教训 → 沉淀 lesson_pattern。"""
    rconn = await asyncpg.connect(REFINED_DSN)
    try:
        old = await rconn.fetchval("SELECT point FROM rf.refined_ku WHERE ku_id=$1", ku_id)
        if old is None:
            raise HTTPException(404, "ku not found")
        await rconn.execute(
            "UPDATE rf.refined_ku SET natural_text_zh=$1, zh_grade='verified', updated_at=now() WHERE ku_id=$2",
            corrected_zh,
            ku_id,
        )
    finally:
        await rconn.close()
    # 术语/翻译教训沉淀进 C仓 lesson_pattern(学习也产生可复用教训)
    cconn = await _ctx_conn()
    try:
        await cconn.execute(
            "INSERT INTO cx.lesson_pattern (statement, trigger_context) VALUES ($1,$2)",
            f"KU译文修正({ku_id}): {note or '机器译有误, 已人工校对'}",
            "翻译B仓KU中文显示时",
        )
    finally:
        await cconn.close()
    return success_response({"ku_id": ku_id, "zh_grade": "verified"})


# ── 主动督学(2.4/P2.2): 下一步该学什么(状态算出, 非计数器) ────────────────

_ACTION = {
    "procedural": ("code", "写一段代码验证/实现这个知识点, 提交给真实执行裁判"),
    "conceptual": ("feynman", "用简单语言把这个概念讲清(费曼门): 核心思想+关键前提+自己的话/例子"),
    "rationale": ("feynman", "讲清这个'为什么': 用简单语言把背后的道理/推理讲透"),
    "factual": ("quiz", "回答下面这道速测题(标准答案已存服务端, 判分不放水)"),
}
_ACTION_DEFAULT = ("derivation", "独立写出这个知识点的推导/证明, 提交给严格裁判")


@router.get("/learning/profiles/{profile_id}/next")
async def next_objective(profile_id: int):
    """主动督学: 从当前进度状态算出'下一步该做什么'(DeepTutor 的 computed-never-counted 原则)。
    优先级: ①到期的间隔重测 ②没掌握过的新点 ③都在巩固中→等下次复习 ④全 verified→毕业。
    factual 类会顺带把速测题出好(答案存服务端)。"""
    conn = await _ctx_conn()
    try:
        rows = await conn.fetch(
            "SELECT * FROM cx.learning_progress WHERE profile_id=$1 ORDER BY point_id", profile_id
        )
        if not rows:
            return success_response(
                {"done": False, "empty": True, "reason": "还没有知识点, 先自动生成或手动建"}
            )

        now = datetime.now(timezone.utc)
        due = sorted(
            [r for r in rows if r["next_review_at"] is not None and r["next_review_at"] <= now],
            key=lambda r: r["next_review_at"],
        )
        objective, reason = None, ""
        if due:
            objective, reason = due[0], "到期的间隔重测(维持/巩固掌握)"
        else:
            fresh = [r for r in rows if r["grade"] == "unverified"]
            if fresh:
                objective, reason = fresh[0], "推进一个还没检验过的新知识点"
            else:
                unverified = [r for r in rows if r["grade"] != "verified"]
                if not unverified:
                    return success_response(
                        {"done": True, "reason": "全部知识点已 verified, 毕业🎓"}
                    )
                soonest = min(
                    (r for r in rows if r["next_review_at"] is not None),
                    key=lambda r: r["next_review_at"],
                    default=None,
                )
                return success_response(
                    {
                        "done": False,
                        "waiting": True,
                        "reason": "都在巩固中, 暂无到期项——下次间隔重测时间已排定",
                        "next_review_at": soonest["next_review_at"].isoformat()
                        if soonest
                        else None,
                    }
                )

        action, prompt = _ACTION.get(objective["knowledge_type"], _ACTION_DEFAULT)
        result = {
            "done": False,
            "reason": reason,
            "action": action,
            "prompt": prompt,
            "objective": {
                "point_id": objective["point_id"],
                "point_name": objective["point_name"],
                "knowledge_type": objective["knowledge_type"],
                "grade": objective["grade"],
                "mastery_score": objective["mastery_score"],
            },
        }
        # factual → 顺带出题(答案存服务端), 前端拿到就能直接作答
        if action == "quiz":
            ku_ids = (
                json.loads(objective["b_repo_ku_ids"])
                if isinstance(objective["b_repo_ku_ids"], str)
                else (objective["b_repo_ku_ids"] or [])
            )
            context = await _fetch_ku_context(ku_ids)
            sys_prompt = (
                "为知识点出一道有唯一/可判定标准答案的速测题。只有题目展示给学习者, 答案存服务端判分。"
                '只输出JSON: {"question":"题干","expected":"标准答案(具体可判定)"}'
            )
            quiz = await _llm_json(
                sys_prompt,
                f"知识点: {objective['point_name']}\n\n知识材料:\n{context or '(无)'}",
                max_tokens=900,
            )
            quiz["posed_at"] = now.isoformat()
            await conn.execute(
                "UPDATE cx.learning_progress SET pending_quiz=$1, updated_at=now() WHERE point_id=$2",
                json.dumps(quiz, ensure_ascii=False),
                objective["point_id"],
            )
            result["quiz_question"] = quiz["question"]
    finally:
        await conn.close()
    return success_response(result)


# ── 统一学习教练入口(DeepTutor ChatOrchestrator 的等价物) ──────────────────
# 一个入口驱动整个学习循环: 算目标 → _coach_turn 决定对话与动作 → 执行(裁判/推进) → 返回教练回合。
# ★教练对话逻辑放本 Layer-4(§8: HTTP/编排是项目服务层职责), 不塞进 3O 共享包——单项目特性没必要
# 让 AII 去追踪共享包的本地源码(那会丢版本固定、拖累升级)。将来第2个项目也要教练循环时再提升成 oskill。


def _select_objective(rows, now):
    """从进度状态算当前目标(同 next_objective): 到期重测 → 未检验新点 → 都在巩固 → 毕业。"""
    due = sorted(
        [r for r in rows if r["next_review_at"] is not None and r["next_review_at"] <= now],
        key=lambda r: r["next_review_at"],
    )
    if due:
        return due[0], "到期间隔重测"
    fresh = [r for r in rows if r["grade"] == "unverified"]
    if fresh:
        return fresh[0], "推进新知识点"
    if all(r["grade"] == "verified" for r in rows):
        return None, "done"
    return None, "waiting"  # 都在巩固中, 无到期项


_COACH_ACTIONS = ("start", "present", "advance", "remediate", "done")
_COACH_SYSTEM = (
    "你是一位顶尖的私人学习教练, 正带一个学习者按教材逐个知识点学。背后有一套'不能撒谎的裁判'"
    "在判他是否真掌握(独立推导/跑代码/讲清/答对), 所以:\n"
    "【红线】1.绝不直接给出题目/证明/代码的答案(那会让裁判失效=帮他作弊骗自己)。"
    "2.他没通过时给对症引导/提示/追问(基于给你的'补救建议'), 不是把答案递过去。3.鼓励、口语化、"
    "一次聚焦一件事, 用中文。\n"
    "【按状态决定 action 与 message】"
    "phase=start: 欢迎+简述怎么学(逐点、独立作答、裁判判真掌握), action=start; "
    "phase=present: 用'教学材料'把这个知识点讲清关键, 再布置该点任务(概念→用简单话讲清; 程序→写代码/推导; "
    "事实→答速测题), action=present; "
    "phase=judged 且 passed=true: 肯定他、指出好在哪、宣布进入下一个点, action=advance; "
    "phase=judged 且 passed=false: 依据'补救建议'和'错误类型'给一个引导/提示(不给答案)让他再试, 不放行, action=remediate。\n"
    '只输出严格JSON: {"message":"(对学生说的话)","action":"start|present|advance|remediate|done"}'
)


def _coach_leaks(text: str) -> bool:
    low = text.lower()
    return any(s in low for s in ("答案是", "答案为", "the answer is", "正确答案：", "证明如下："))


async def _coach_turn(
    *, phase, objective=None, student_input=None, verdict=None, ku_context=None, history=None
) -> dict:
    """学习教练回合(Layer-4): 给定状态→教练对话+建议动作。用 AII 自己的 default provider,
    不依赖 3O 共享包(单项目特性放项目层, §8)。将来第2个项目也要教练循环时再提升成 oskill。"""
    if phase == "done":
        return {
            "message": "🎓 这一段的知识点你都独立通过了，扎实学完了。要不要挑下一章？",
            "action": "done",
            "revealed_answer": False,
        }
    state = {
        "phase": phase,
        "objective": objective,
        "student_input": student_input,
        "verdict": verdict,
        "teaching_material": (ku_context or "")[:4000],
    }
    msgs = list(history or [])
    msgs.append(
        {"role": "user", "content": "当前状态(JSON):\n" + json.dumps(state, ensure_ascii=False)}
    )
    llm = ProviderRegistry.get().llm("learning")  # 学习助手专用 NIM(未注册自动回落 default)
    r = await llm(messages=msgs, system=_COACH_SYSTEM, max_tokens=900)
    text = "".join(x.get("text", "") for x in r.get("content", []) if x.get("type") == "text")
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        act = (
            "advance" if (verdict or {}).get("passed") else ("remediate" if verdict else "present")
        )
        return {
            "message": (verdict or {}).get("feedback") or "我们继续。",
            "action": act,
            "revealed_answer": False,
        }
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        act = (
            "advance" if (verdict or {}).get("passed") else ("remediate" if verdict else "present")
        )
        return {
            "message": (verdict or {}).get("feedback") or "我们继续。",
            "action": act,
            "revealed_answer": False,
        }
    message = str(data.get("message", "")).strip() or "我们继续。"
    action = data.get("action") if data.get("action") in _COACH_ACTIONS else "present"
    revealed = _coach_leaks(message)
    if revealed:
        message = "我先不把答案给你——那样裁判就白判了。你卡在哪一步？说说你的想法，我顺着引导。"
    return {"message": message, "action": action, "revealed_answer": revealed}


@router.post("/learning/profiles/{profile_id}/tutor/turn")
async def tutor_turn(
    profile_id: int,
    student_input: str | None = Body(None),
    submit_answer: bool = Body(False),  # True=把 student_input 当作答交裁判; False=只对话/呈现
    history: list = Body(default_factory=list),
):
    """统一教练回合。submit_answer=False → 呈现当前目标+教学材料并布置任务; =True → 判分+教练反应。"""
    conn = await _ctx_conn()
    try:
        rows = await conn.fetch(
            "SELECT * FROM cx.learning_progress WHERE profile_id=$1 ORDER BY point_id", profile_id
        )
        if not rows:
            return success_response(
                {
                    "message": "还没有学习点——先在上面按章节自动生成，我就能带你逐点学了。",
                    "action": "need_points",
                    "objective": None,
                }
            )

        now = datetime.now(timezone.utc)
        obj_row, why = _select_objective(rows, now)
        if obj_row is None and why == "done":
            turn = await _coach_turn(phase="done", history=history)
            return success_response(
                {"message": turn["message"], "action": "done", "objective": None, "done": True}
            )
        if obj_row is None:  # waiting: 都在巩固, 无到期
            return success_response(
                {
                    "message": "这一批点都在巩固中，暂无到期重测。要不要生成下一章的学习点，或换个点手动练？",
                    "action": "waiting",
                    "objective": None,
                }
            )

        objective = {
            "point_name": obj_row["point_name"],
            "knowledge_type": obj_row["knowledge_type"],
            "grade": obj_row["grade"],
            "mastery_score": obj_row["mastery_score"],
        }
        verdict = None
        phase = "present"

        if submit_answer and student_input:
            verdict = await _judge_point(conn, obj_row, student_input)  # 判分+记账(共用口径)
            phase = "judged"

        ku_context = None
        if phase == "present":
            ku_ids = (
                json.loads(obj_row["b_repo_ku_ids"])
                if isinstance(obj_row["b_repo_ku_ids"], str)
                else (obj_row["b_repo_ku_ids"] or [])
            )
            rowsku = await _ku_display_rows(ku_ids[:3])  # 只取前几条挂靠KU当教学材料(按需翻译)
            ku_context = "\n\n".join(
                (k["natural_text_zh"] or k["natural_text"] or "") for k in rowsku
            )

        turn = await _coach_turn(
            phase=("start" if (phase == "present" and not history) else phase),
            objective=objective,
            student_input=student_input,
            verdict=verdict,
            ku_context=ku_context,
            history=history,
        )
    finally:
        await conn.close()

    return success_response(
        {
            "message": turn["message"],
            "action": turn["action"],
            "objective": objective,
            "knowledge_type": obj_row["knowledge_type"],
            "verdict": verdict,
            "revealed_answer": turn["revealed_answer"],
            "reason": why,
        }
    )


# ── 监督(2.4): 复习队列 + 卡点库 ─────────────────────────────────────────


@router.get("/learning/profiles/{profile_id}/review-queue")
async def review_queue(profile_id: int):
    conn = await _ctx_conn()
    try:
        rows = await conn.fetch(
            "SELECT * FROM cx.learning_progress WHERE profile_id=$1 AND next_review_at <= now() ORDER BY next_review_at",
            profile_id,
        )
        return success_response([_row(r, ["b_repo_ku_ids", "attempts"]) for r in rows])
    finally:
        await conn.close()


@router.get("/learning/profiles/{profile_id}/stuck")
async def stuck_list(profile_id: int):
    conn = await _ctx_conn()
    try:
        rows = await conn.fetch(
            "SELECT * FROM cx.learning_stuck WHERE profile_id=$1 ORDER BY resolved, occurrences DESC",
            profile_id,
        )
        return success_response([dict(r) for r in rows])
    finally:
        await conn.close()


@router.post("/learning/stuck/{stuck_id}/resolve")
async def stuck_resolve(stuck_id: int):
    conn = await _ctx_conn()
    try:
        await conn.execute("UPDATE cx.learning_stuck SET resolved=true WHERE stuck_id=$1", stuck_id)
    finally:
        await conn.close()
    return success_response({"resolved": True})
