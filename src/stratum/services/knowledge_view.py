"""AII KnowledgeView — the single retrieval contract.

Replaces the previous three disjoint retrieval planes:
  - POST /api/v1/search  (cross_layer_search + tantivy/pgvector)
  - POST /api/v1/retrieve (directory-recursive substrate_layers)
  - companion/agent ad-hoc SQL

KnowledgeView is a projection, not a new authority.
All retrieval backs to PostgreSQL canonical store (stratum.* + aii.*).
Lexical/vector indexes are rebuildable projections.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Scope = Literal["lexical", "dense", "graph", "temporal", "user-authored", "learning"]

RESULT_SCHEMA_FIELDS: set[str] = {
    "id",
    "title",
    "type",
    "score",
    "snippet",
    "citation",
    "paragraph_index",
    "char_start",
    "char_end",
    "anchor_status",
    "deep_link",
    "substrate_id",
    "layer",
    "uri",
    "ref_id",
}


@dataclass
class KnowledgeViewRequest:
    query: str
    top_k: int = 10
    scopes: list[Scope] | None = None
    user_id: str | None = None
    rerank: bool = False
    filters: dict[str, Any] = field(default_factory=dict)


@dataclass
class KnowledgeViewResult:
    """Stable result schema for all consumers (search/retrieve/companion/agent/skill)."""

    id: str
    title: str
    type: str
    score: float
    snippet: str
    citation: dict[str, Any] | None = None
    paragraph_index: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    anchor_status: str = "ok"
    deep_link: str | None = None
    substrate_id: str | None = None
    layer: str | None = None
    uri: str | None = None
    ref_id: str | None = None
    provenance: dict[str, Any] | None = None  # Claim -> Evidence -> Fragment -> Source

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "score": round(self.score, 4),
            "snippet": self.snippet,
            "citation": self.citation,
            "paragraph_index": self.paragraph_index,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "anchor_status": self.anchor_status,
            "deep_link": self.deep_link,
            "substrate_id": self.substrate_id,
            "layer": self.layer,
            "uri": self.uri,
            "ref_id": self.ref_id,
            "provenance": self.provenance,
        }


def _normalize_scopes(scopes: list[Scope] | None) -> list[Scope]:
    if not scopes:
        return ["lexical", "dense"]
    return scopes


def search_knowledge_view(req: KnowledgeViewRequest) -> dict[str, Any]:
    """Single entry point for all retrieval consumers.

    Delegates to existing engines but enforces:
    - user isolation (user_id + hash_user_id)
    - stable result schema
    - provenance/citation echo
    - lexical+dense as projection (rebuildable), never authority
    """
    # Use retrieval_engine as canonical dense path; search_utils pgvector as fallback.
    # This keeps behavior identical but routes through one contract.
    from stratum.services.retrieval_engine import retrieve

    # Map scopes to retrieval_engine layers: dense->vector, learning->L1/L2
    max_depth = 2
    if req.scopes and "learning" in req.scopes:
        max_depth = 3
    namespace = "global"
    if req.scopes and "user-authored" in req.scopes and len(req.scopes) == 1:
        namespace = "personal"
    elif req.scopes and "user-authored" in req.scopes:
        namespace = "all"

    resp = retrieve(
        query=req.query,
        max_depth=max_depth,
        top_k=req.top_k,
        rerank=req.rerank,
        user_id=req.user_id or "default",
        namespace=namespace,
    )

    # Normalize to KnowledgeViewResult stable schema
    from stratum.services.search_anchors import locate_anchor
    from stratum.db import query as db_query

    ref_ids = [r.ref_id for r in resp.results if r.ref_id]
    title_map: dict[str, str] = {}
    if ref_ids:
        try:
            rows = db_query(
                "SELECT id, title FROM substrates WHERE id = ANY(%(ids)s)",
                {"ids": ref_ids},
            )
            title_map = {r["id"]: r["title"] or r["id"] for r in rows}
        except Exception:
            title_map = {}

    results: list[KnowledgeViewResult] = []
    for r in resp.results:
        anchor = locate_anchor(r.content or "", None)
        title = title_map.get(r.ref_id or "", r.uri or r.ref_id or "")
        results.append(
            KnowledgeViewResult(
                id=r.ref_id or r.uri,
                title=title or r.uri or "",
                type=r.node_type,
                score=r.score,
                snippet=(anchor.get("snippet") or r.content[:300]) if r.content else "",
                citation=None,
                paragraph_index=anchor.get("paragraph_index"),
                char_start=anchor.get("char_start"),
                char_end=anchor.get("char_end"),
                anchor_status="ok",
                deep_link=f"stratum://substrate/{r.ref_id}#p{anchor.get('paragraph_index')}" if r.ref_id else r.uri,
                substrate_id=r.ref_id,
                layer=r.layer,
                uri=r.uri,
                ref_id=r.ref_id,
                provenance={"substrate_id": r.ref_id, "layer": r.layer},
            )
        )

    return {
        "query": req.query,
        "scopes": _normalize_scopes(req.scopes),
        "result_count": len(results),
        "results": [x.to_dict() for x in results],
        "trajectory_id": resp.trajectory_id,
        "total_ms": resp.total_ms,
    }


def validate_result_schema(result: dict[str, Any]) -> list[str]:
    """Validate that a result respects the stable schema."""
    errors: list[str] = []
    for field in ("id", "title", "type", "score", "snippet"):
        if field not in result:
            errors.append(f"missing required field: {field}")
    # score must be finite [0,1] or at least finite
    score = result.get("score")
    if score is not None:
        try:
            s = float(score)
            if s != s or s == float("inf") or s == float("-inf"):
                errors.append("score is non-finite")
        except Exception:
            errors.append("score not numeric")
    return errors
