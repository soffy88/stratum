"""Evidence briefs projected from the canonical KnowledgeView.

This module creates no index, store, or retrieval authority. It only transforms
already validated KnowledgeView results into a compact evidence-first contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from stratum.services.knowledge_view import KnowledgeView, KnowledgeViewRequest

SearchFn = Callable[[KnowledgeViewRequest], dict[str, Any]]


@dataclass(frozen=True)
class EvidenceBriefRequest:
    query: str
    user_id: str
    top_k: int = 10
    rerank: bool = True


class EvidenceBriefInvariantError(RuntimeError):
    """Raised when a KnowledgeView result cannot support an evidence brief."""


def build_evidence_brief(
    req: EvidenceBriefRequest, *, search_fn: SearchFn | None = None
) -> dict[str, Any]:
    """Build an evidence-first brief from the single canonical retrieval facade."""
    if not req.query.strip():
        raise EvidenceBriefInvariantError("query is required")
    if not req.user_id or req.user_id == "default":
        raise EvidenceBriefInvariantError("authenticated user_id is required")
    if req.top_k < 1 or req.top_k > 100:
        raise EvidenceBriefInvariantError("top_k must be between 1 and 100")

    search = search_fn or KnowledgeView.search
    response = search(
        KnowledgeViewRequest(
            query=req.query.strip(),
            top_k=req.top_k,
            user_id=req.user_id,
            rerank=req.rerank,
        )
    )

    items: list[dict[str, Any]] = []
    for rank, result in enumerate(response.get("results") or [], start=1):
        citation = result.get("citation")
        provenance = result.get("provenance")
        source_id = result.get("substrate_id") or result.get("ref_id")
        if not source_id:
            raise EvidenceBriefInvariantError("result missing canonical source id")
        if not isinstance(citation, dict) or citation.get("source_id") != source_id:
            raise EvidenceBriefInvariantError("result missing valid citation")
        if not isinstance(provenance, dict) or provenance.get("source_id") != source_id:
            raise EvidenceBriefInvariantError("result missing valid provenance")

        quote = str(citation.get("quote") or result.get("snippet") or "").strip()
        items.append(
            {
                "rank": rank,
                "title": str(result.get("title") or source_id),
                "score": float(result.get("score") or 0.0),
                "quote": quote,
                "source_id": source_id,
                "fragment_id": result.get("fragment_id") or citation.get("fragment_id"),
                "layer": result.get("layer"),
                "paragraph_index": result.get("paragraph_index"),
                "char_start": result.get("char_start"),
                "char_end": result.get("char_end"),
                "deep_link": result.get("deep_link"),
                "citation": citation,
                "provenance": provenance,
            }
        )

    return {
        "query": response.get("query") or req.query.strip(),
        "result_count": len(items),
        "items": items,
        "trajectory_id": response.get("trajectory_id"),
        "authority": "KnowledgeView",
    }


def render_evidence_brief_markdown(brief: dict[str, Any]) -> str:
    """Render the structured brief without inventing citations or evidence."""
    query = str(brief.get("query") or "").strip()
    lines = [f"# Evidence Brief: {query}", ""]
    for item in brief.get("items") or []:
        rank = int(item.get("rank") or 0)
        title = str(item.get("title") or item.get("source_id") or "Untitled")
        source_id = str(item.get("source_id") or "")
        fragment_id = item.get("fragment_id")
        quote = str(item.get("quote") or "").strip()
        deep_link = item.get("deep_link")
        lines.append(f"## {rank}. {title}")
        if quote:
            lines.append(f"> {quote.replace(chr(10), ' ')}")
        lines.append(f"- source_id: `{source_id}`")
        if fragment_id:
            lines.append(f"- fragment_id: `{fragment_id}`")
        if deep_link:
            lines.append(f"- deep_link: {deep_link}")
        lines.append("")
    return chr(10).join(lines).rstrip() + chr(10)
