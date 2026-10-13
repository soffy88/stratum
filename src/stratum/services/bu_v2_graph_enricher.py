"""Reasoning-graph enrichment — task C.

``DependencyBuilder`` produces CHAPTER nodes and cross-chapter edges from the
author's own cross-references. That is a real signal, but it is only the spine:
the audit found the graph held 18 CHAPTER nodes and no CONCEPT, CLAIM or THEOREM
node at all, so it could not answer "what does this theorem depend on" or "which
concept does this claim use".

This module adds the missing levels to the same ``BookReasoningGraph``:

  CONCEPT nodes   one per concept the chapters introduce (from the frozen KU
                  anchors where available, else the chapter's concept list)
  THEOREM nodes   one per frozen DEF/THM KU that is a theorem
  CLAIM nodes     one per claim the chapters carry in their evidence program

and the reasoned edges between them:

  CHAPTER --EXPLAINS-->   CONCEPT / THEOREM   a chapter introduces a concept
  CHAPTER --SUPPORTS-->   CLAIM               a chapter states a claim
  CLAIM   --DEPENDS_ON--> CONCEPT             a claim's text uses a concept
  CLAIM   --APPLIES_TO--> THEOREM             a claim invokes a theorem

Every edge carries a ``reason`` (§6) and, where one exists, an evidence ref. The
enricher never invents a node for a concept the book does not have: nodes come
from the run's own extracted concepts and frozen KUs, and an edge is added only
when both endpoints exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stratum.services.bu_v2_concept_filter import is_noise_concept
from stratum.knowledge.bu_v2_models import ChapterUnderstanding
from stratum.services.bu_v2_reasoning_graph import (
    BookReasoningGraph,
    ReasoningEdge,
    ReasoningNode,
    node_id,
)

# A concept shorter than this matches too much to be a useful node.
MIN_CONCEPT_CHARS = 3
# How many claim nodes per chapter to add, to keep the graph legible.
MAX_CLAIMS_PER_CHAPTER = 8


@dataclass
class EnrichmentStats:
    concept_nodes: int = 0
    theorem_nodes: int = 0
    claim_nodes: int = 0
    edges_added: int = 0
    unresolved: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "concept_nodes": self.concept_nodes,
            "theorem_nodes": self.theorem_nodes,
            "claim_nodes": self.claim_nodes,
            "edges_added": self.edges_added,
            "unresolved": self.unresolved,
        }


class ReasoningGraphEnricher:
    """Add CONCEPT/THEOREM/CLAIM nodes and reasoned edges to a reasoning graph."""

    def __init__(self) -> None:
        self.stats = EnrichmentStats()
        self._concept_nodes: dict[str, str] = {}  # normalised label -> node_id
        self._theorem_nodes: dict[str, str] = {}
        self._chapter_node: dict[str, str] = {}
        self._graph: BookReasoningGraph | None = None
        self._run_id = ""

    def enrich(
        self,
        graph: BookReasoningGraph,
        chapters: list[ChapterUnderstanding],
        *,
        run_id: str,
        ku_index: Any = None,
        chapter_text: dict[str, str] | None = None,
    ) -> EnrichmentStats:
        self.stats = EnrichmentStats()
        self._concept_nodes = {}
        self._theorem_nodes = {}
        self._chapter_node = {}
        self._graph = graph
        self._run_id = run_id
        chapter_text = chapter_text or {}

        for cu in chapters:
            cnode = node_id("n", run_id, cu.chapter_id)
            if cnode in graph.nodes:
                self._chapter_node[cu.chapter_id] = cnode

        for cu in chapters:
            self._add_concepts(cu, ku_index)
        for cu in chapters:
            self._add_claims(cu, chapter_text)

        self.stats.unresolved = len(graph.unresolved)
        return self.stats

    # ── nodes ────────────────────────────────────────────────────────────────

    def _add_concepts(self, cu: ChapterUnderstanding, ku_index: Any) -> None:
        cid = cu.chapter_id
        anchors: list[dict[str, Any]] = []
        if ku_index is not None:
            try:
                anchors = ku_index.anchors_for(cid)
            except Exception:
                anchors = []
        for a in anchors:
            name = (a.get("name") or "").strip()
            kind = (a.get("kind") or "").upper()
            if len(name) < MIN_CONCEPT_CHARS or is_noise_concept(name, kind):
                continue
            key = _norm(name)
            if not key or key in self._concept_nodes or key in self._theorem_nodes:
                continue
            ntype = "THEOREM" if kind == "THEOREM" else "CONCEPT"
            self._register_concept(
                cid,
                key,
                name,
                ntype,
                source_ref=a.get("locator") or a.get("ku_id") or "",
                confidence=0.9 if kind in ("DEFINITION", "THEOREM") else 0.7,
                metadata={
                    "ku_id": a.get("ku_id") or "",
                    "kind": kind,
                    "quote": (a.get("quote") or "")[:240],
                },
                evidence=[a.get("locator") or ""],
                evidence_type="DEFINITION" if kind == "DEFINITION" else "DIRECT",
            )
        # The chapter's own concept list covers books without frozen KUs.
        for concept in cu.concepts_introduced_refs:
            name = (concept or "").strip()
            if len(name) < MIN_CONCEPT_CHARS or is_noise_concept(name):
                continue
            key = _norm(name)
            if not key or key in self._concept_nodes or key in self._theorem_nodes:
                continue
            self._register_concept(
                cid,
                key,
                name,
                "CONCEPT",
                source_ref=f"{cid}:concept",
                confidence=0.6,
                metadata={"ku_id": "", "kind": "CONCEPT"},
                evidence=[f"{cid}:concept"],
                evidence_type="MODEL_INFERENCE",
            )

    def _register_concept(
        self,
        cid: str,
        key: str,
        name: str,
        ntype: str,
        *,
        source_ref: str,
        confidence: float,
        metadata: dict[str, Any],
        evidence: list[str],
        evidence_type: str,
    ) -> None:
        assert self._graph is not None
        nid = node_id("cn", self._run_id, cid, key)
        self._graph.add_node(
            ReasoningNode(
                node_id=nid,
                node_type=ntype,  # type: ignore[arg-type]
                label=name[:400],
                chapter_id=cid,
                source_ref=source_ref,
                confidence=confidence,
                metadata=metadata,
            )
        )
        if ntype == "THEOREM":
            self._theorem_nodes[key] = nid
            self.stats.theorem_nodes += 1
        else:
            self._concept_nodes[key] = nid
            self.stats.concept_nodes += 1
        cnode = self._chapter_node.get(cid)
        if cnode:
            self._add_edge(
                cnode,
                nid,
                "EXPLAINS",
                reason=f"{cid} introduces '{name}'",
                evidence=evidence,
                evidence_type=evidence_type,
                confidence=confidence,
            )

    def _add_claims(self, cu: ChapterUnderstanding, chapter_text: dict[str, str]) -> None:
        assert self._graph is not None
        cid = cu.chapter_id
        cnode = self._chapter_node.get(cid)
        for i, ep in enumerate(cu.evidence_program[:MAX_CLAIMS_PER_CHAPTER]):
            claim_label = (ep.claim_ref or "").strip()
            if not claim_label:
                continue
            nid = node_id("an", self._run_id, cid, "claim", str(i))
            self._graph.add_node(
                ReasoningNode(
                    node_id=nid,
                    node_type="CLAIM",
                    label=claim_label[:400],
                    chapter_id=cid,
                    source_ref=(ep.evidence_refs[0] if ep.evidence_refs else ""),
                    confidence=0.7 if ep.is_supported else 0.4,
                    metadata={"is_supported": ep.is_supported},
                )
            )
            self.stats.claim_nodes += 1
            if cnode:
                self._add_edge(
                    cnode,
                    nid,
                    "SUPPORTS",
                    reason=f"{cid} states this claim",
                    evidence=list(ep.evidence_refs),
                    evidence_type="DIRECT" if ep.is_supported else "MODEL_INFERENCE",
                    confidence=0.7 if ep.is_supported else 0.4,
                )
            low = claim_label.lower()
            for key, concept_id in self._concept_nodes.items():
                if len(key) < MIN_CONCEPT_CHARS or key not in low:
                    continue
                self._add_edge(
                    nid,
                    concept_id,
                    "DEPENDS_ON",
                    reason=f"the claim uses the concept '{self._graph.nodes[concept_id].label}'",
                    evidence=list(ep.evidence_refs),
                    evidence_type="DERIVED",
                    confidence=0.5,
                )
            for key, theorem_id in self._theorem_nodes.items():
                if len(key) < MIN_CONCEPT_CHARS or key not in low:
                    continue
                self._add_edge(
                    nid,
                    theorem_id,
                    "APPLIES_TO",
                    reason=f"the claim invokes the theorem '{self._graph.nodes[theorem_id].label}'",
                    evidence=list(ep.evidence_refs),
                    evidence_type="DERIVED",
                    confidence=0.55,
                )

    # ── edges ────────────────────────────────────────────────────────────────

    def _add_edge(
        self,
        source: str,
        target: str,
        relation: str,
        *,
        reason: str,
        evidence: list[str],
        evidence_type: str,
        confidence: float,
    ) -> None:
        assert self._graph is not None
        if source == target or source not in self._graph.nodes or target not in self._graph.nodes:
            return
        edge = ReasoningEdge(
            edge_id=node_id("e", source, target, relation),
            source_node_id=source,
            target_node_id=target,
            relation_type=relation,  # type: ignore[arg-type]
            reason=reason,
            evidence_refs=[e for e in evidence if e],
            evidence_type=evidence_type,  # type: ignore[arg-type]
            confidence=confidence,
        )
        if self._graph.add_edge(edge) is not None:
            self.stats.edges_added += 1


def _norm(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum() or c.isspace()).strip()
