"""AII 查询理解: LLM 意图路由 + HyDE.

替代脆弱的 7 关键词路由(一个 KU 含'体系'即误路由). 设计:
- route_intent: LLM 分类 global/grounded/chitchat; 失败 → 关键词兜底(保旧行为, 不崩).
- hyde_embed: 低召回时用 LLM 生成假设答案再编码检索(HyDE), 缩小 query-doc 语义差.
"""
from __future__ import annotations
import json
import logging
import re

logger = logging.getLogger(__name__)

# 关键词兜底(LLM 不可用时退回原逻辑)
_GLOBAL_STRONG = ["什么关系", "关系是", "总结", "综述", "概括", "全书", "脉络", "体系"]
_GLOBAL_WEAK = ["之间", "综合", "整体", "全局", "哪些", "族"]
_LOCAL_KW = ["是什么", "怎么", "怎样", "公式", "证明", "怎么样", "能不能", "定义"]


def _keyword_route(message: str) -> str:
    """原 7 关键词路由(兜底)."""
    has_strong = any(k in message for k in _GLOBAL_STRONG)
    has_weak = any(k in message for k in _GLOBAL_WEAK)
    has_local = any(k in message for k in _LOCAL_KW)
    if has_strong or (has_weak and not has_local):
        return "global"
    if has_local or any(k in message for k in ["靠谱吗", "？", "?", "建议"]):
        return "grounded"
    return "chitchat"


_ROUTE_SYS = (
    "You classify a user query's retrieval intent for a knowledge base. Output valid JSON only. "
    "Labels: 'global' (asks for synthesis/overview/relationships across a topic — 综述/体系/脉络/比较), "
    "'grounded' (asks about a specific concept/definition/method/fact — 是什么/怎么/证明), "
    "'chitchat' (greeting/smalltalk, no knowledge needed)."
)


async def route_intent(llm, message: str) -> str:
    """LLM 路由 → global/grounded/chitchat. 失败回退关键词路由."""
    try:
        r = await llm(
            messages=[{"role": "user", "content":
                f'Query: "{message}"\nClassify. JSON: {{"intent":"global|grounded|chitchat"}}'}],
            system=_ROUTE_SYS, max_tokens=60)
        t = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        m = re.search(r"\{.*\}", t, re.DOTALL)
        intent = json.loads(m.group(0)).get("intent", "") if m else ""
        if intent in ("global", "grounded", "chitchat"):
            return intent
    except Exception as e:
        logger.warning("route_intent LLM failed, keyword fallback: %s", e)
    return _keyword_route(message)


async def hyde_embed(llm, embed_fn, message: str) -> list[float] | None:
    """HyDE: 让 LLM 写一段假设答案, 编码它(而非原 query)做检索 — 缩小问答语义差.
    用于低召回回退. 失败返回 None(调用方退回普通 query 编码)."""
    import numpy as np
    try:
        r = await llm(
            messages=[{"role": "user", "content":
                f"Write a concise factual passage (2-3 sentences) that would directly answer: {message}"}],
            system="You write a hypothetical answer passage for retrieval. Output the passage only.",
            max_tokens=200)
        hyp = "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text").strip()
        if len(hyp) < 15:
            return None
        arr = np.array(embed_fn([hyp]), dtype="float32")[0]
        nrm = float(np.linalg.norm(arr))
        return [float(x) / nrm for x in arr] if nrm > 0 else [float(x) for x in arr]
    except Exception as e:
        logger.warning("hyde_embed failed: %s", e)
        return None
