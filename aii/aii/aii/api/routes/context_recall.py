"""C仓(个人判断资产)召回 — AII-KNOWLEDGE-FIRST-SPEC-001 改进三 · 场景B。

SPEC §3.2 场景B 要求: Wiki 提决策问题 → ★必须先查 C仓相似案例/原则/反例 → 主动投递
(呈现判断光谱, 各标来源+grade); C仓无相关判断资产时才用通用知识, 且标注"非你的判断历史"。
★禁止: C仓有相关案例却不召回、直接给通用建议。

在此之前 C仓是【只写不读】的: cx.decision_case / lesson_pattern / methodology 只被
scripts/context_compiler.py INSERT 过, 全仓没有任何一处 SELECT——embedding 灌进去从没被
查过。那正是 SPEC §3.1 说的"白建"在 C仓这侧的实际发生地。本模块补上读的那一半。

只读 cx.*, 不写任何表。

★召回不是判断: 这里只按向量相似度把"你以前怎么判的"摆出来, 不排序成建议、不合成结论、
不替人决定。每条都带 grade(默认 unverified——AI 从归档文件里归纳的, 没被验证过)和
reuse_conditions(CBR 核心: 这条理由在什么情境成立/什么情境反过来)。判断光谱要让人自己看。

★空结果是一等公民: has_assets=false 时明确回 advisory, 告诉调用方"C仓没有相关判断资产,
接下来用通用知识可以, 但必须标注'非你的判断历史'"——不静默返回空数组让调用方自行发挥,
那样就退回"直接给通用建议"了。
"""

import json
import os
import urllib.request

import asyncpg
from fastapi import APIRouter, Query

from aii.api._envelope import success_response, error_response

router = APIRouter()

CONTEXT_DSN = os.getenv(
    "CONTEXT_DATABASE_URL", "postgresql://aii:aii_safe_pass@localhost:5436/aii_context"
)
# 跟 scripts/context_compiler.py 同一个共享嵌入服务(BGE-M3, 1024维)——灌库和召回必须
# 用同一个模型, 否则向量不在一个空间里, 相似度是无意义的数。
EMBED_URL = os.getenv("AII_EMBED_URL", "http://100.68.226.13:8102")

# 没有相关资产时给调用方的行为约束(SPEC §3.2/§3.4: 通用知识只做【显式标注】的兜底)。
_NO_ASSET_ADVISORY = (
    "C仓没有与该问题相关的判断资产。可以用通用知识回答, 但★必须显式标注"
    "'这不是你的判断历史, 来自通用知识, 未经 AII 编译'——不能让它看起来像你以前的判断。"
)
_HAS_ASSET_ADVISORY = (
    "C仓有相关判断资产(见 items)。★必须基于它们回答并标明来源(kind + id + grade), "
    "不允许绕开它们直接给通用建议。grade=unverified 的是 AI 从归档里归纳的、未经验证, "
    "呈现时要如实说明, 不能当成定论。"
)

# ★相关性门槛。没有它 has_assets 恒为 true(向量检索总能返回"最近的那条", 哪怕毫不相干),
# advisory 就会逼着调用方把不相关的案例硬套到问题上——那比不召回更糟。实测(BGE-M3):
# 真正对题的案例 ~0.77, 完全不搭界的 ~0.40, 0.55 落在这条缝里。
# ★这是启发式, 不是客观裁判(原则二): 判断资产多起来之后需要拿真实问题重新校准。所以
# ① 门槛是显式参数, 调用方可以自己调; ② 被门槛挡下的不静默丢弃, 在 near_misses 里如实
# 报出最高相似度, 让人看得见"其实有个 0.52 的擦肩而过", 而不是以为库里空空如也。
_DEFAULT_MIN_SIMILARITY = 0.55


def _embed(text: str) -> list[float]:
    """urllib 不认 no_proxy 的 CIDR, 显式绕代理(同 context_compiler._embed)。"""
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    req = urllib.request.Request(
        f"{EMBED_URL}/embed",
        json.dumps({"texts": [text[:2000]]}).encode(),
        {"Content-Type": "application/json"},
    )
    return json.loads(opener.open(req, timeout=60).read())["embeddings"][0]


def _jsonb(v, default):
    return json.loads(v) if isinstance(v, str) else (v or default)


@router.get("/context/recall")
async def context_recall(
    q: str = Query(..., min_length=1, description="决策问题/情境描述"),
    limit: int = Query(5, ge=1, le=20, description="每类资产各返回几条"),
    min_similarity: float = Query(
        _DEFAULT_MIN_SIMILARITY,
        ge=0.0,
        le=1.0,
        description="相关性下限, 低于它的不算'相关资产'(但会在 near_misses 里如实报出)",
    ),
):
    """按情境召回 C仓判断资产(决策案例 / 教训模式 / 方法论), 三类各取 top-N。

    三类分开返回而不是混排打分: 它们回答的是不同问题(以前怎么判的 / 踩过什么坑 /
    有什么可复用做法), 混成一个榜会把"判断光谱"压成单一建议, 那正是 SPEC 不要的。
    """
    try:
        vec = _embed(q)
    except Exception as e:  # 嵌入服务不可达 → 明确报错, 不退化成"没有资产"
        return error_response(
            "EMBED_UNAVAILABLE",
            f"嵌入服务({EMBED_URL})不可用, 无法召回: {str(e)[:120]}。"
            "★这不等于'C仓没有相关资产'——不要据此改用通用知识回答。",
        )
    vlit = "[" + ",".join(f"{x:.7f}" for x in vec) + "]"

    conn = await asyncpg.connect(CONTEXT_DSN)
    try:
        cases = await conn.fetch(
            """
            SELECT case_id, title, project, situation, alternatives, rationale,
                   reuse_conditions, result, lesson, grade, grounded_in, source_files,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM cx.decision_case
            WHERE embedding IS NOT NULL AND status = 'active'
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            vlit,
            limit,
        )
        patterns = await conn.fetch(
            """
            SELECT pattern_id, statement, trigger_context, evidence_case_ids, grade,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM cx.lesson_pattern
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            vlit,
            limit,
        )
        methods = await conn.fetch(
            """
            SELECT method_id, name, description, applicability, grounded_in, grade,
                   1 - (embedding <=> $1::vector) AS similarity
            FROM cx.methodology
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> $1::vector
            LIMIT $2
            """,
            vlit,
            limit,
        )
    finally:
        await conn.close()

    all_items = {
        "decision_cases": [
            {
                "kind": "decision_case",
                "id": r["case_id"],
                "title": r["title"],
                "project": r["project"],
                # CBR 六件套原样呈现——尤其 reuse_conditions, 它是"这条理由什么时候
                # 成立/什么时候反过来", 缺了它召回出来的案例会被无条件套用。
                "situation": r["situation"],
                "alternatives": _jsonb(r["alternatives"], []),
                "rationale": r["rationale"],
                "reuse_conditions": r["reuse_conditions"],
                "result": r["result"],
                "lesson": r["lesson"],
                "grade": r["grade"],
                "grounded_in": _jsonb(r["grounded_in"], []),
                "source_files": _jsonb(r["source_files"], []),
                "similarity": round(float(r["similarity"]), 4),
            }
            for r in cases
        ],
        "lesson_patterns": [
            {
                "kind": "lesson_pattern",
                "id": r["pattern_id"],
                "statement": r["statement"],
                "trigger_context": r["trigger_context"],
                "evidence_case_ids": _jsonb(r["evidence_case_ids"], []),
                "grade": r["grade"],
                "similarity": round(float(r["similarity"]), 4),
            }
            for r in patterns
        ],
        "methodologies": [
            {
                "kind": "methodology",
                "id": r["method_id"],
                "name": r["name"],
                "description": r["description"],
                "applicability": r["applicability"],
                "grounded_in": _jsonb(r["grounded_in"], []),
                "grade": r["grade"],
                "similarity": round(float(r["similarity"]), 4),
            }
            for r in methods
        ],
    }
    # 按相关性门槛切分。被挡下的不丢——每类留一条最接近的进 near_misses, 让人看得见
    # "库里其实有个 0.52 的擦肩而过", 而不是误以为空空如也(那会导致白白用通用知识答)。
    items = {k: [x for x in v if x["similarity"] >= min_similarity] for k, v in all_items.items()}
    near_misses = [
        {
            "kind": v[0]["kind"],
            "id": v[0]["id"],
            "label": v[0].get("title") or v[0].get("name") or v[0].get("statement"),
            "similarity": v[0]["similarity"],
        }
        for k, v in all_items.items()
        if v and not items[k]
    ]
    total = sum(len(v) for v in items.values())

    return success_response(
        {
            "query": q,
            "items": items,
            "total": total,
            "min_similarity": min_similarity,
            # 低于门槛、因而【没被算作相关资产】的最接近项——如实报出, 不静默隐藏。
            "near_misses": near_misses,
            # ★调用方(学习/决策辅助的经理人)据此决定能不能用通用知识, 以及要不要标注。
            "has_assets": total > 0,
            "advisory": _HAS_ASSET_ADVISORY if total else _NO_ASSET_ADVISORY,
        }
    )
