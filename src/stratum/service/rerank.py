"""Layer-4 retrieval enhancers: LLM query expansion + LLM judge rerank.

Both wrap 主库 primitives without modifying them (§20):
  - oprim.llm_query_expand.llm_query_expand
  - oprim.llm_judge_rerank.llm_judge_rerank

They are opt-in via the /search `expand` / `rerank` flags, which the API
accepted but ignored before this module existed. When the LLM/oprim path is
unavailable (tests, missing keys), every function degrades to a safe no-op so
search never hard-fails on the enhancement path.

The DashScope output-parsing patch lives in the agents router bootstrap and is
applied process-wide on import, so the shared ``oprim.llm.llm_call`` path works
in the running app.
"""
from __future__ import annotations

import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)

_PROVIDER = os.environ.get("STRATUM_LLM_PROVIDER", "qwen3_dashscope")
_MODEL = os.environ.get("STRATUM_LLM_MODEL", "qwen-plus")


def _default_llm() -> Optional[Callable]:
    """Build a messages-style LLM caller -> {"content": str}.

    Mirrors agents._make_oprim_llm_adapter. Returns None if oprim.llm is
    unavailable so callers degrade to no-op.
    """
    try:
        from oprim.llm.llm_call import llm_call
    except Exception as e:  # pragma: no cover - env without oprim
        logger.warning("rerank: oprim llm_call unavailable: %s", e)
        return None

    def _caller(*, messages: list, max_tokens: int = 1024, **_) -> dict:
        prompt = "\n".join(
            m.get("content", "") for m in messages if m.get("role") == "user"
        )
        result = llm_call(
            prompt=prompt, provider=_PROVIDER, model=_MODEL, max_tokens=max_tokens
        )
        return {"content": result.text}

    return _caller


_EXPAND_PROMPT = (
    "为下面的检索查询生成 {n} 个改写，使用同义词、相关概念或不同措辞以提升召回。\n"
    "每行只输出一个改写，不要编号、不要解释。\n\n原始查询: {q}"
)


def _inline_expand(query: str, num_variants: int, llm: Callable) -> list[str]:
    """Layer-4 fallback for query expansion (oprim.llm_query_expand is currently
    broken upstream by a bad relative import — §20: can't patch it)."""
    resp = llm(messages=[{"role": "user",
                          "content": _EXPAND_PROMPT.format(n=num_variants, q=query)}])
    content = (resp.get("content", "") if isinstance(resp, dict) else str(resp)) or ""
    variants = [ln.strip() for ln in content.splitlines() if ln.strip()]
    return [query] + variants[:num_variants]


def expand_query(query: str, *, num_variants: int = 3, llm: Optional[Callable] = None) -> list[str]:
    """Return [original] + LLM-generated variants. Falls back to [query] on any error."""
    if not query or not query.strip():
        return [query] if query else []
    llm = llm or _default_llm()
    if llm is None:
        return [query]
    try:
        import oprim
        variants = oprim.llm_query_expand(query=query, llm=llm, num_variants=num_variants)
    except Exception:
        # oprim's llm_query_expand is broken upstream; use the inline equivalent.
        try:
            variants = _inline_expand(query, num_variants, llm)
        except Exception as e:
            logger.warning("rerank: query expand failed: %s", e)
            return [query]
    # De-dup while preserving order (LLM may echo the original).
    seen: set[str] = set()
    out: list[str] = []
    for v in variants:
        key = (v or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(v)
    return out or [query]


def rerank_results(query: str, results: list, *, top_k: Optional[int] = None,
                   llm: Optional[Callable] = None) -> list:
    """Reorder result objects via LLM judge on (title + highlight).

    ``results`` items expose ``.title`` and ``.highlight``. Items the judge omits
    are appended after judged ones so nothing is silently dropped. Falls back to
    the original order (sliced to top_k) on any error.
    """
    if not results:
        return results
    llm = llm or _default_llm()
    if llm is None:
        return results[:top_k] if top_k else results

    docs = [
        f"{getattr(r, 'title', '') or ''}\n{getattr(r, 'highlight', '') or ''}".strip()
        for r in results
    ]
    try:
        import oprim

        ranked = oprim.llm_judge_rerank(query=query, documents=docs, llm=llm, top_k=top_k)
    except Exception as e:
        logger.warning("rerank: judge rerank failed: %s", e)
        return results[:top_k] if top_k else results

    reordered: list = []
    used: set[int] = set()
    for r in ranked:
        idx = r.original_index
        if 0 <= idx < len(results) and idx not in used:
            reordered.append(results[idx])
            used.add(idx)
    # Defensive: append any candidate the judge dropped, original order preserved.
    for i, r in enumerate(results):
        if i not in used:
            reordered.append(r)
    return reordered[:top_k] if top_k else reordered
