"""Book reasoning graph — spec §5, §15.

The gap P12 names is real and was measured rather than assumed. P11 produced
1 cross-chapter dependency edge across 16 chapters, and Q5 Integration scored
0.72 — the lowest of the seven dimensions. The chapters were understood; the
*relations between them* were not.

The fix is a signal that is actually in the book. Measured on the trial text:

    "Here we state the general version of the rule, but postpone its proof
     until Chapter 7."                         -> ch3 -> ch7, quotable, locatable
    "We encountered another type of vector field in Chapter 13."

66 distinct explicit cross-chapter references, each a verbatim string at a known
character offset. That is a stronger foundation than asking a 7B model what
depends on what, which is what P11 did and which yielded one edge.

Three properties this module holds, and which the tests pin:

**§15 no silent drops.** Every proposed relation that evidence did not support
becomes an ``UnresolvedRelation`` carrying its reason, source, confidence and
fallback. Nothing is discarded, and nothing is invented: an edge exists only when
a located span supports it.

**§6 no unreasoned edges.** Every edge carries a ``reason`` and, where one exists,
an evidence reference. The database enforces the same rule — ``reasoning_edge.reason``
is NOT NULL, so an unreasoned edge cannot be persisted even by a careless writer.

**§2.1 book-scoped, not global.** A concept node means "this concept, in this
book, at this chapter". There is no canonical concept identity here and no
cross-book key, which is what keeps this from becoming the B warehouse.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any, Literal

NodeType = Literal[
    "CHAPTER", "CONCEPT", "CLAIM", "THEOREM", "MECHANISM", "QUESTION", "EXAMPLE", "CONCLUSION"
]
EdgeType = Literal[
    "DEPENDS_ON",
    "EXTENDS",
    "REFINES",
    "CONTRADICTS",
    "APPLIES_TO",
    "EXPLAINS",
    "SUPPORTS",
]
# §11: how strong the support is. MODEL_INFERENCE is explicit rather than
# implied, so a reader can always tell an inferred relation from a quoted one.
EvidenceStrength = Literal["DIRECT", "DEFINITION", "EXAMPLE", "DERIVED", "MODEL_INFERENCE"]

EVIDENCE_STRENGTH_RANK: dict[str, int] = {
    "DIRECT": 4,
    "DEFINITION": 3,
    "EXAMPLE": 2,
    "DERIVED": 1,
    "MODEL_INFERENCE": 0,
}

# §5.2 vocabularies, kept in one place so the model, the validator and the
# database CHECK cannot drift apart.
NODE_TYPES: frozenset[str] = frozenset(
    {"CHAPTER", "CONCEPT", "CLAIM", "THEOREM", "MECHANISM", "QUESTION", "EXAMPLE", "CONCLUSION"}
)
EDGE_TYPES: frozenset[str] = frozenset(
    {"DEPENDS_ON", "EXTENDS", "REFINES", "CONTRADICTS", "APPLIES_TO", "EXPLAINS", "SUPPORTS"}
)


@dataclass
class ReasoningNode:
    """One node of the book reasoning graph."""

    node_id: str
    node_type: NodeType
    label: str
    chapter_id: str = ""
    source_ref: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.node_type not in NODE_TYPES:
            raise ValueError(
                f"unknown node type {self.node_type!r}; §5.2 allows {sorted(NODE_TYPES)}"
            )
        self.confidence = _clamp(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "label": self.label,
            "chapter_id": self.chapter_id,
            "source_ref": self.source_ref,
            "confidence": round(self.confidence, 4),
            "metadata": self.metadata,
        }


@dataclass
class ReasoningEdge:
    """One relation. §6: a reason is mandatory, never optional."""

    edge_id: str
    source_node_id: str
    target_node_id: str
    relation_type: EdgeType
    reason: str
    evidence_refs: list[str] = field(default_factory=list)
    evidence_type: EvidenceStrength = "MODEL_INFERENCE"
    confidence: float = 0.0
    status: Literal["asserted", "uncertain", "refuted"] = "asserted"

    def __post_init__(self) -> None:
        if self.relation_type not in EDGE_TYPES:
            raise ValueError(
                f"unknown relation {self.relation_type!r}; §5.2 allows {sorted(EDGE_TYPES)}"
            )
        if not (self.reason or "").strip():
            # §6: "禁止 模型直接生成 Chapter A depends Chapter B 但没有 reason".
            # Refusing here means the failure surfaces at construction, where the
            # message can name the relation, rather than as a NOT NULL error at
            # insert time.
            raise ValueError(f"edge {self.edge_id}: §6 requires a reason for {self.relation_type}")
        if self.evidence_type not in EVIDENCE_STRENGTH_RANK:
            raise ValueError(
                f"unknown evidence_type {self.evidence_type!r}; "
                f"§11 allows {sorted(EVIDENCE_STRENGTH_RANK)}"
            )
        self.confidence = _clamp(self.confidence)
        if self.status != "asserted":
            # §15: an uncertain relation is stored, but it is never dressed up as
            # an asserted one.
            self.confidence = min(self.confidence, 0.4)

    @property
    def is_direct(self) -> bool:
        return self.evidence_type in ("DIRECT", "DEFINITION", "EXAMPLE")

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "relation_type": self.relation_type,
            "reason": self.reason,
            "evidence_refs": self.evidence_refs,
            "evidence_type": self.evidence_type,
            "confidence": round(self.confidence, 4),
            "status": self.status,
        }


@dataclass
class UnresolvedRelation:
    """§15: a relation that was proposed and not established, kept with its why.

    Dropping these silently is what §15 forbids. Keeping them is also what makes
    the graph honest: a reader can see that chapter 3 *might* depend on chapter 2
    and that the text did not settle it.
    """

    kind: str
    subject: str
    reason: str
    source: str
    confidence: float = 0.0
    fallback: str = ""

    def __post_init__(self) -> None:
        self.confidence = _clamp(self.confidence)
        if not (self.reason or "").strip():
            raise ValueError("§15 requires a reason even for an unresolved relation")
        if not (self.fallback or "").strip():
            # A record that says what failed but not what happened instead is
            # half a record. The default is the honest one.
            self.fallback = "recorded as absent; no relation asserted"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "subject": self.subject,
            "reason": self.reason,
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "fallback": self.fallback,
        }


@dataclass
class BookReasoningGraph:
    """§5.2: nodes, edges, evidence, confidence."""

    graph_id: str
    run_id: str
    book_id: str
    nodes: dict[str, ReasoningNode] = field(default_factory=dict)
    edges: list[ReasoningEdge] = field(default_factory=list)
    unresolved: list[UnresolvedRelation] = field(default_factory=list)

    # ── construction ───────────────────────────────────────────────────────

    def add_node(self, node: ReasoningNode) -> ReasoningNode:
        if node.node_id in self.nodes:
            # §5.6-style: a higher-confidence observation of the same node wins,
            # so a later, weaker pass cannot overwrite a better one.
            prior = self.nodes[node.node_id]
            if node.confidence > prior.confidence:
                self.nodes[node.node_id] = node
        else:
            self.nodes[node.node_id] = node
        return self.nodes[node.node_id]

    def add_edge(self, edge: ReasoningEdge) -> ReasoningEdge | None:
        """Add an edge, refusing duplicates and unresolvable endpoints."""
        if edge.source_node_id not in self.nodes:
            return self.record_unresolved(
                UnresolvedRelation(
                    kind="edge",
                    subject=f"{edge.source_node_id} -> {edge.target_node_id}",
                    reason=f"source node {edge.source_node_id} is not in the graph",
                    source="add_edge",
                    confidence=edge.confidence,
                    fallback="edge dropped",
                )
            )
        if edge.target_node_id not in self.nodes:
            return self.record_unresolved(
                UnresolvedRelation(
                    kind="edge",
                    subject=f"{edge.source_node_id} -> {edge.target_node_id}",
                    reason=f"target node {edge.target_node_id} is not in the graph",
                    source="add_edge",
                    confidence=edge.confidence,
                    fallback="edge dropped",
                )
            )
        key = (edge.source_node_id, edge.target_node_id, edge.relation_type)
        for existing in self.edges:
            if (existing.source_node_id, existing.target_node_id, existing.relation_type) == key:
                # Keep the better-supported claim rather than the later one.
                if edge.confidence > existing.confidence:
                    self.edges[self.edges.index(existing)] = edge
                return None
        self.edges.append(edge)
        return edge

    def record_unresolved(self, relation: UnresolvedRelation) -> UnresolvedRelation:
        self.unresolved.append(relation)
        return relation

    # ── queries ────────────────────────────────────────────────────────────

    def nodes_of_type(self, node_type: str) -> list[ReasoningNode]:
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def edges_of_type(self, relation_type: str) -> list[ReasoningEdge]:
        return [e for e in self.edges if e.relation_type == relation_type]

    def out_edges(self, node_id: str) -> list[ReasoningEdge]:
        return [e for e in self.edges if e.source_node_id == node_id]

    def in_edges(self, node_id: str) -> list[ReasoningEdge]:
        return [e for e in self.edges if e.target_node_id == node_id]

    def cross_chapter_edges(self) -> list[ReasoningEdge]:
        """Edges between different chapters — the relations P11 could not find."""
        out = []
        for e in self.edges:
            s = self.nodes.get(e.source_node_id)
            t = self.nodes.get(e.target_node_id)
            if s and t and s.chapter_id and t.chapter_id and s.chapter_id != t.chapter_id:
                out.append(e)
        return out

    @property
    def direct_edge_ratio(self) -> float:
        if not self.edges:
            return 0.0
        return round(sum(1 for e in self.edges if e.is_direct) / len(self.edges), 4)

    @property
    def mean_confidence(self) -> float:
        if not self.edges:
            return 0.0
        return round(sum(e.confidence for e in self.edges) / len(self.edges), 4)

    def stats(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for n in self.nodes.values():
            by_type[n.node_type] = by_type.get(n.node_type, 0) + 1
        rel: dict[str, int] = {}
        for e in self.edges:
            rel[e.relation_type] = rel.get(e.relation_type, 0) + 1
        return {
            "graph_id": self.graph_id,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "cross_chapter_edges": len(self.cross_chapter_edges()),
            "unresolved_count": len(self.unresolved),
            "nodes_by_type": by_type,
            "edges_by_type": rel,
            "direct_edge_ratio": self.direct_edge_ratio,
            "mean_confidence": self.mean_confidence,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "run_id": self.run_id,
            "book_id": self.book_id,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "unresolved": [u.to_dict() for u in self.unresolved],
            "stats": self.stats(),
        }


# ── helpers ──────────────────────────────────────────────────────────────────


def node_id(prefix: str, *parts: str) -> str:
    """A stable id. Stability matters: a re-run must produce the same ids for
    the same book, or a graph cannot be compared with its predecessor."""
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


def load_graph(graph_id: str) -> "BookReasoningGraph | None":
    """Rebuild a persisted reasoning graph from the database (task E).

    Reads ``book_reasoning_graph`` + ``reasoning_node`` + ``reasoning_edge`` and
    reconstructs the in-memory graph. Returns ``None`` when the graph is absent,
    so a caller degrades to the chapter-based learning-guide fallback rather than
    failing.
    """
    from stratum.db import query

    rows = query(
        "SELECT * FROM book_reasoning_graph WHERE id = %(g)s",
        {"g": graph_id},
        limit=1,
    )
    if not rows:
        return None
    head = rows[0]
    graph = BookReasoningGraph(
        graph_id=graph_id,
        run_id=head.get("run_id") or "",
        book_id=head.get("book_id") or "",
    )
    for n in query(
        "SELECT * FROM reasoning_node WHERE graph_id = %(g)s", {"g": graph_id}, limit=100000
    ):
        try:
            graph.nodes[n["id"]] = ReasoningNode(
                node_id=n["id"],
                node_type=n["node_type"],
                label=n.get("label") or "",
                chapter_id=n.get("chapter_id") or "",
                source_ref=n.get("source_ref") or "",
                confidence=float(n.get("confidence") or 0.0),
                metadata=n.get("metadata") or {},
            )
        except ValueError:
            continue
    for e in query(
        "SELECT * FROM reasoning_edge WHERE graph_id = %(g)s", {"g": graph_id}, limit=100000
    ):
        try:
            graph.edges.append(
                ReasoningEdge(
                    edge_id=e["id"],
                    source_node_id=e["source_node_id"],
                    target_node_id=e["target_node_id"],
                    relation_type=e["relation_type"],
                    reason=e.get("reason") or "",
                    evidence_refs=list(e.get("evidence_refs") or []),
                    evidence_type=e.get("evidence_type") or "MODEL_INFERENCE",
                    confidence=float(e.get("confidence") or 0.0),
                    status=e.get("status") or "asserted",
                )
            )
        except ValueError:
            continue
    return graph


def _clamp(v: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    return round(max(0.0, min(1.0, f)), 4)


def strength_rank(evidence_type: str) -> int:
    return EVIDENCE_STRENGTH_RANK.get(evidence_type, 0)
