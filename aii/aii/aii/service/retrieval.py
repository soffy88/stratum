"""AII 检索层(共享): 混合检索的重排与查询理解辅助.

- llm_rerank: LLM 列表式重排(离线无 cross-encoder 时的现实选择; 有 bge-reranker 可平替).
- 设计: 后端 search_ku_hybrid 已做 dense+lexical RRF 融合; 本模块在其上做精排.
"""
from __future__ import annotations
import json
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _ku_snippet(ku: dict, n: int = 220) -> str:
    """候选 KU 的紧凑表示(标题 + 英文要义), 喂给重排 LLM."""
    title = (ku.get("title") or ku.get("ku_id") or "").strip()
    body = (ku.get("natural_text") or ku.get("natural_text_zh") or "").strip()
    body = re.sub(r"\s+", " ", body)[:n]
    return f"{title} — {body}" if title else body


async def llm_rerank(llm, query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """列表式重排: 让 LLM 按"对 query 的相关度"对候选打分排序.
    - 不改候选内容/grade, 只重排序(命门: 重排是排序问题, 不得改写知识).
    - LLM 失败/返回不可解析 → 原样返回前 top_k(降级安全).
    - 返回带 rerank_score 的候选(降序), 截断 top_k.
    """
    if not candidates:
        return []
    if len(candidates) == 1:
        return candidates[:top_k]
    items = "\n".join(f"[{i}] {_ku_snippet(c)}" for i, c in enumerate(candidates))
    prompt = (
        f"Query: {query}\n\n"
        f"Candidate knowledge units:\n{items}\n\n"
        f"Rank the candidates by how directly and completely each ANSWERS the query. "
        f"Return ONLY JSON: {{\"ranking\":[{{\"id\":<int>,\"score\":<0-10>}}]}} "
        f"with the most relevant first. Include only genuinely relevant ids."
    )
    try:
        r = await llm(
            messages=[{"role": "user", "content": prompt}],
            system="You are a precise retrieval re-ranker. Output valid JSON only.",
            max_tokens=400,
        )
        t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", t, re.DOTALL)
        ranking = json.loads(m.group(0)).get("ranking", []) if m else []
    except Exception as e:
        logger.warning("llm_rerank failed, falling back to fusion order: %s", e)
        return candidates[:top_k]

    seen, out = set(), []
    for entry in ranking:
        try:
            idx = int(entry["id"])
        except (KeyError, ValueError, TypeError):
            continue
        if 0 <= idx < len(candidates) and idx not in seen:
            c = dict(candidates[idx])
            c["rerank_score"] = float(entry.get("score", 0))
            out.append(c)
            seen.add(idx)
    # 补回未被 LLM 列出的候选(保底, 排在已排序之后)
    for i, c in enumerate(candidates):
        if i not in seen:
            out.append(c)
    return out[:top_k]
