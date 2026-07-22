"""LLM-backed Reranker / QueryExpander adapters matching oskill.hybrid_search's
Protocol contracts (see oskill/hybrid_search.py — rerank(query, documents, top_k)
-> list[obj with .original_index/.score]; expand(query, num_variants) -> list[str]
that REPLACES the query list wholesale, so it must include the original).

Both are sync (hybrid_search calls them without awaiting) and fail open: any LLM
error falls back to identity behavior (original order / no expansion) rather
than raising, since a broken rerank/expand call shouldn't break search itself.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class RerankResult:
    original_index: int
    score: float


def llm_rerank(*, query: str, documents: list[str], top_k: int | None = None) -> list[RerankResult]:
    scores = [1.0] * len(documents)  # fallback: preserve original order
    if documents:
        try:
            from oprim import llm_call

            numbered = "\n".join(f"[{i}] {d[:300]}" for i, d in enumerate(documents))
            prompt = (
                f'Query: "{query}"\n\nCandidate documents:\n{numbered}\n\n'
                "Score each document's relevance to the query from 0.0 (irrelevant) "
                "to 1.0 (perfectly relevant). Respond with ONLY a JSON array of "
                "numbers in document order, e.g. [0.9, 0.2, 0.5]."
            )
            resp = llm_call(prompt=prompt, temperature=0.0, max_tokens=500)
            m = re.search(r"\[[\d.,\s]+\]", resp.text)
            parsed = json.loads(m.group(0)) if m else None
            if isinstance(parsed, list) and len(parsed) == len(documents):
                scores = [float(s) for s in parsed]
        except Exception as e:
            log.warning("llm_rerank failed, falling back to original order: %s", e)

    results = [RerankResult(original_index=i, score=s) for i, s in enumerate(scores)]
    results.sort(key=lambda r: r.score, reverse=True)
    return results[:top_k] if top_k else results


def llm_expand(*, query: str, num_variants: int = 3) -> list[str]:
    try:
        from oprim import llm_call

        prompt = (
            f"Generate {num_variants} alternative phrasings of this search query "
            f'that would help find semantically related documents. Original query: "{query}"\n'
            'Respond with ONLY a JSON array of strings, e.g. ["variant 1", "variant 2"].'
        )
        resp = llm_call(prompt=prompt, temperature=0.7, max_tokens=300)
        m = re.search(r"\[.*\]", resp.text, re.DOTALL)
        variants = json.loads(m.group(0)) if m else []
        variants = [v for v in variants if isinstance(v, str) and v.strip()][:num_variants]
        if variants:
            return [query] + variants
    except Exception as e:
        log.warning("llm_expand failed, skipping expansion: %s", e)
    return []  # falsy -> hybrid_search keeps using the original query alone
