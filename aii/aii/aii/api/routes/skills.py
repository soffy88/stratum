"""论文技能检索 —— 「agent 用 skill」落地。

agent 用一句任务描述检索相关论文的可调用技能(方法/前置/边界/结论), 决定"该不该用+怎么用"。
检索基于 doc_type='paper' 的 BU 向量(overview+problem+use_when+do_not_use_when 的 BGE-M3 嵌入)。
可选 contribution_type 过滤(如只要 method、排除 impossibility)。
返回每篇的可调用卡片(agent_skill 全字段 + overview/problem/出处 + 相似度)。
"""

import json

from fastapi import APIRouter, Body

from aii.api._dependencies import backend
from aii.api._envelope import error_response, success_response
from oprim import vector_encode

router = APIRouter()

_VALID_CT = {"method", "empirical", "impossibility", "framework", "survey"}

# 论文类型 → agent 使用心智(比 cangjie 多一层"防误用"语义)
_CT_HINT = {
    "method": "提供可复用的方法/算法, 可照 E 执行步骤套用",
    "empirical": "提供实证发现, 结论受数据/参数条件约束(见 B), 别当普适定律",
    "impossibility": "⚠不可能性/负面结论——**不能**当'我因此获得了保证'来用, 只作反驳/警示",
    "framework": "提供统一框架/视角, 用于组织理解或归类既有工作",
    "survey": "综述性梳理, 用于快速了解领域全貌与文献坐标",
}


def _slugify(text: str, n: int = 48) -> str:
    import re

    s = re.sub(r"[^\w一-鿿]+", "-", (text or "").strip())[:n].strip("-")
    return s or "paper-skill"


def _fmt_list(items, bullet="- "):
    out = []
    for it in items or []:
        if isinstance(it, dict):
            out.append(bullet + " | ".join(f"{k}: {v}" for k, v in it.items() if v))
        else:
            out.append(bullet + str(it))
    return "\n".join(out) or "—"


def render_skill_md(row: dict) -> str:
    """把一篇论文 BU(bu_onto 行)渲染成原生 Claude Code SKILL.md(RIA++ 增强版)。
    比 cangjie 多: contribution_type 防误用闸 / preconditions 违背后果 / key_results 数值 / boundary 反转条件。"""
    skill = _as_obj(row.get("agent_skill"))
    method = _as_obj(skill.get("method"))
    ct = skill.get("contribution_type") or "method"
    overview = row.get("overview_oneline") or ""
    use_when = skill.get("use_when") or []
    dont = skill.get("do_not_use_when") or []
    src = " ".join(x for x in [row.get("authors"), row.get("venue_year")] if x) or "—"
    tags = (skill.get("references_concepts") or [])[:6]

    # description = A2 触发信号(Claude Code 靠它自动调用)
    desc = f"当遇到以下任务时调用: {'; '.join(use_when)}。"
    if dont:
        desc += f" 不适用于: {'; '.join(dont)}。"
    desc += f" 类型={ct}({_CT_HINT.get(ct, '')})。"

    fm = [
        "---",
        f"name: {_slugify(overview or row.get('substrate_id'))}",
        "description: |",
        "  " + desc.replace("\n", " ")[:600],
        f"source: {src}",
        f"substrate_id: {row.get('substrate_id')}",
        f"contribution_type: {ct}",
        f"tags: [{', '.join(tags)}]",
        "related_skills: []",
        "---",
    ]
    body = [
        f"\n# {overview}\n",
        "## R · 原文依据(可核对来源)",
        _fmt_list(skill.get("source_excerpts")),
        "\n## I · 方法框架",
        f"{method.get('approach', '')}",
        f"\n**要解决的问题**: {row.get('problem_statement', '')}",
        "\n## A1 · 应用案例(论文中的实例)",
        _fmt_list(skill.get("application_cases")),
        "\n## A2 · 何时调用 / 何时不用",
        "**调用**:\n" + _fmt_list(use_when),
        "\n**不用**:\n" + _fmt_list(dont),
        "\n## E · 执行步骤",
        _numbered(method.get("steps")),
        f"\n输入: {', '.join(method.get('inputs') or []) or '—'}  →  输出: {', '.join(method.get('outputs') or []) or '—'}",
        "\n## B · 边界与前提(防误用)",
        "**结论的成立/反转条件**:\n" + _fmt_list(skill.get("boundary_conditions")),
        "\n**前置假设(违背后果)**:\n" + _fmt_list(skill.get("preconditions")),
        "\n**作者自陈局限**:\n"
        + _fmt_list(
            _as_obj(row.get("limitations"))
            if isinstance(row.get("limitations"), str)
            else row.get("limitations")
        ),
        "\n## 关键结果(可复用量化锚点)",
        _fmt_list(skill.get("key_results")),
        "\n## 依赖(要用需先有)",
        _fmt_list(skill.get("dependencies")),
        "\n## 本篇新造术语",
        _fmt_list(skill.get("coined_terms")),
        _render_audit(skill),
        f"\n---\n*substrate_id={row.get('substrate_id')} · 蒸馏自论文 BU · 通用概念只引用不复述*",
    ]
    return "\n".join(fm) + "\n".join(body)


def _render_audit(skill: dict) -> str:
    """Audit 段: V3 排他性 + 检索测试题(比 cangjie 多把这两块显式落进 SKILL.md)。"""
    v3 = _as_obj(skill.get("v3"))
    tp = _as_obj(skill.get("test_prompts"))
    if not v3 and not tp:
        return ""
    lines = ["\n## Audit · 排他性与检索校验"]
    if v3:
        fv = v3.get("findings") or []
        excl = sum(1 for f in fv if f.get("exclusive"))
        lines.append(
            f"- **V3 排他性**: worth_as_skill={v3.get('worth_as_skill')}; "
            f"非常识 findings {excl}/{len(fv)}; {v3.get('novelty_note', '')}"
        )
        weak = [f.get("finding") for f in fv if not f.get("exclusive")]
        if weak:
            lines.append("  - ⚠常识级(非本篇独有): " + "; ".join(w for w in weak if w)[:200])
    if tp:
        if tp.get("should_invoke"):
            lines.append("- **应命中**: " + " / ".join(tp["should_invoke"]))
        if tp.get("should_not_invoke"):
            lines.append("- **诱饵(不该命中)**: " + " / ".join(tp["should_not_invoke"]))
    return "\n".join(lines)


def _numbered(items):
    if not items:
        return "—"
    return "\n".join(f"{i + 1}. {s}" for i, s in enumerate(items))


def _as_obj(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return {}
    return v or {}


@router.post("/skills/search")
async def search_skills(
    task: str = Body(..., description="任务描述: agent 现在要做什么"),
    top_k: int = Body(5),
    contribution_type: "str | list[str] | None" = Body(
        None, description="过滤论文类型: method|empirical|impossibility|framework|survey"
    ),
    min_score: float = Body(
        0.0,
        description="相关度阈值(防误触发): 低于此分丢弃。test_prompts 压测显示真匹配~0.70+、相邻诱饵~0.55, 传0.6可挡诱饵",
    ),
):
    try:
        ct = contribution_type
        if isinstance(ct, str):
            ct = ct if ct in _VALID_CT else None
        elif isinstance(ct, list):
            ct = [c for c in ct if c in _VALID_CT] or None

        qv = vector_encode(texts=[task], provider="default")[0]
        rows = await backend.search_paper_skill_by_vector(
            [float(x) for x in qv], limit=top_k, contribution_type=ct
        )

        out = []
        for r in rows:
            score = round(1.0 - r.get("distance", 1.0), 4)
            if score < min_score:  # 防误触发: 低相关度丢弃
                continue
            skill = _as_obj(r.get("agent_skill"))
            out.append(
                {
                    "substrate_id": r["substrate_id"],
                    "overview": r.get("overview_oneline"),
                    "problem": r.get("problem_statement"),
                    "authors": r.get("authors"),
                    "venue_year": r.get("venue_year"),
                    # 「skill」可调用字段 —— agent 据此判断该不该用 + 怎么用
                    "contribution_type": skill.get("contribution_type"),
                    "use_when": skill.get("use_when"),
                    "do_not_use_when": skill.get("do_not_use_when"),
                    "preconditions": skill.get("preconditions"),
                    "method": skill.get("method"),
                    "boundary_conditions": skill.get("boundary_conditions"),
                    "key_results": skill.get("key_results"),
                    "reusable_artifacts": skill.get("reusable_artifacts"),
                    "dependencies": skill.get("dependencies"),
                    "coined_terms": skill.get("coined_terms"),
                    "limitations": _as_obj(r.get("limitations")) or None,
                    "score": score,
                }
            )
        return success_response(out)
    except Exception as e:
        return error_response("SKILL_SEARCH_ERROR", str(e))


@router.post("/skills/export")
async def export_skill(
    substrate_id: str = Body(..., embed=True, description="要导出为 SKILL.md 的论文 substrate_id"),
):
    """把一篇论文技能导出成原生 Claude Code SKILL.md(RIA++ 增强版)。
    agent 检索到某篇后, 用它把技能'安装'成可原生调用的 skill 文件。"""
    try:
        row = await backend.get_paper_bu(substrate_id)
        if not row:
            return error_response("NOT_FOUND", f"无 doc_type=paper 的 BU: {substrate_id}")
        return success_response({"substrate_id": substrate_id, "skill_md": render_skill_md(row)})
    except Exception as e:
        return error_response("SKILL_EXPORT_ERROR", str(e))
