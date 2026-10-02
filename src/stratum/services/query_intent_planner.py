"""Deterministic Query Intent Planner for agentic retrieval.

The planner chooses the three retrieval tools used by A-RAG:
``keyword_search``, ``semantic_search`` and ``chunk_read``.  It is intentionally
heuristic and inspectable so a trained classifier can replace it later without
changing the tool contract.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class QueryPlan:
    intent: str
    tools: tuple[str, ...]
    max_depth: int
    rerank: bool
    rationale: str

    def to_dict(self) -> dict:
        value = asdict(self)
        value["tools"] = list(self.tools)
        return value


_COMPARE = re.compile(r"比较|对比|区别|差异|异同|\bvs\.?\b|versus", re.I)
_EXPLAIN = re.compile(r"为什么|如何|机制|原理|解释|定义|what is|how does|explain", re.I)
_SYNTHESIS = re.compile(r"总结|综合|概括|跨文档|汇总|survey|overview|synthesize", re.I)
_LEARN = re.compile(r"复习|记忆|掌握|练习|学习|忘记|review|learn|practice", re.I)


def plan_query(query: str) -> QueryPlan:
    """Classify a query and choose a transparent retrieval sequence."""
    text = (query or "").strip()
    if not text:
        return QueryPlan(
            intent="lookup",
            tools=("keyword_search",),
            max_depth=1,
            rerank=False,
            rationale="empty query defaults to the smallest safe plan",
        )
    if _LEARN.search(text):
        return QueryPlan(
            intent="learn",
            tools=("semantic_search", "chunk_read"),
            max_depth=2,
            rerank=True,
            rationale="learning questions need semantic recall and readable chunks",
        )
    if _COMPARE.search(text):
        return QueryPlan(
            intent="compare",
            tools=("keyword_search", "semantic_search", "chunk_read"),
            max_depth=3,
            rerank=True,
            rationale="comparison needs broad candidate recall and chunk-level evidence",
        )
    if _SYNTHESIS.search(text):
        return QueryPlan(
            intent="synthesis",
            tools=("keyword_search", "semantic_search", "chunk_read"),
            max_depth=3,
            rerank=True,
            rationale="synthesis needs multi-source recall and evidence reranking",
        )
    if _EXPLAIN.search(text):
        return QueryPlan(
            intent="explain",
            tools=("keyword_search", "semantic_search", "chunk_read"),
            max_depth=2,
            rerank=True,
            rationale="explanation needs lexical anchors plus semantic context",
        )
    return QueryPlan(
        intent="lookup",
        tools=("keyword_search", "semantic_search"),
        max_depth=2,
        rerank=False,
        rationale="factual lookup uses hybrid first-pass retrieval",
    )
