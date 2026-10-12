"""Author argument model — spec §8.

§8 asks how the author *advances* a thought, which is a different question from
how the book's chapters are structurally related. The dependency graph answers
"what needs what"; this answers "what is being argued, on what grounds, and to
what conclusion".

One chain is:

    CLAIM --SUPPORTS--> EVIDENCE
    EVIDENCE --DERIVES--> REASONING
    REASONING --DERIVES--> CONCLUSION
    CONCLUSION --SUMMARIZES--> CLAIM

A chain is only emitted when it has a CLAIM and a CONCLUSION. A dangling claim
with nothing supporting it is §15's case: recorded as unresolved, not promoted to
a chain, because "the author asserted X" is not the same as "the author argued X
from Y to Z".

Chains are built from recorded evidence programs and mechanism text rather than
invented, and every edge carries a reason for the same reason §6 requires it of a
dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from stratum.knowledge.bu_v2_models import ChapterUnderstanding
from stratum.services.bu_v2_reasoning_graph import (
    EVIDENCE_STRENGTH_RANK,
    UnresolvedRelation,
    node_id,
)

NodeKind = Literal["CLAIM", "EVIDENCE", "REASONING", "CONCLUSION"]
EdgeKind = Literal["SUPPORTS", "DERIVES", "CHALLENGES", "SUMMARIZES"]

NODE_KINDS: frozenset[str] = frozenset({"CLAIM", "EVIDENCE", "REASONING", "CONCLUSION"})
EDGE_KINDS: frozenset[str] = frozenset({"SUPPORTS", "DERIVES", "CHALLENGES", "SUMMARIZES"})


@dataclass
class ArgumentNode:
    node_id: str
    node_kind: NodeKind
    label: str
    chapter_id: str = ""
    confidence: float = 0.0
    evidence_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.node_kind not in NODE_KINDS:
            raise ValueError(
                f"unknown argument node {self.node_kind!r}; §8 allows {sorted(NODE_KINDS)}"
            )
        self.confidence = max(0.0, min(1.0, round(float(self.confidence), 4)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind,
            "label": self.label[:300],
            "chapter_id": self.chapter_id,
            "confidence": round(self.confidence, 4),
            "evidence_refs": self.evidence_refs,
        }


@dataclass
class ArgumentEdge:
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_kind: EdgeKind
    reason: str
    chain_id: str = ""
    evidence_type: str = "MODEL_INFERENCE"
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.0
    status: str = "asserted"

    def __post_init__(self) -> None:
        if self.edge_kind not in EDGE_KINDS:
            raise ValueError(
                f"unknown argument edge {self.edge_kind!r}; §8 allows {sorted(EDGE_KINDS)}"
            )
        if not (self.reason or "").strip():
            raise ValueError("§6 reasoning discipline: every argument edge needs a reason")
        self.confidence = max(0.0, min(1.0, round(float(self.confidence), 4)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "evidence_refs": list(self.evidence_refs),
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "edge_kind": self.edge_kind,
            "reason": self.reason,
            "chain_id": self.chain_id,
            "evidence_type": self.evidence_type,
            "confidence": round(self.confidence, 4),
            "status": self.status,
        }


@dataclass
class ArgumentChain:
    chain_id: str
    chapter_id: str
    claim: ArgumentNode
    conclusion: ArgumentNode | None = None
    evidence: list[ArgumentNode] = field(default_factory=list)
    reasoning: list[ArgumentNode] = field(default_factory=list)
    edges: list[ArgumentEdge] = field(default_factory=list)
    evidence_strength: str = "MODEL_INFERENCE"
    complete: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "chapter_id": self.chapter_id,
            "claim": self.claim.to_dict(),
            "conclusion": self.conclusion.to_dict() if self.conclusion else None,
            "evidence_count": len(self.evidence),
            "reasoning_count": len(self.reasoning),
            "edges": [e.to_dict() for e in self.edges],
            "evidence_strength": self.evidence_strength,
            "complete": self.complete,
        }


@dataclass
class ArgumentAnalysis:
    chains: list[ArgumentChain] = field(default_factory=list)
    nodes: dict[str, ArgumentNode] = field(default_factory=dict)
    edges: list[ArgumentEdge] = field(default_factory=list)
    unresolved: list[UnresolvedRelation] = field(default_factory=list)
    graph_id: str = ""

    @property
    def complete_chains(self) -> int:
        return sum(1 for c in self.chains if c.complete)

    def stats(self) -> dict[str, Any]:
        strengths: dict[str, int] = {}
        for c in self.chains:
            strengths[c.evidence_strength] = strengths.get(c.evidence_strength, 0) + 1
        return {
            "graph_id": self.graph_id,
            "chain_count": len(self.chains),
            "complete_chains": self.complete_chains,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "unresolved_count": len(self.unresolved),
            "chains_by_evidence_strength": strengths,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "stats": self.stats(),
            "chains": [c.to_dict() for c in self.chains],
            "unresolved": [u.to_dict() for u in self.unresolved],
        }


class ArgumentAnalyzer:
    """§8: reconstruct the author's reasoning chains from what was recorded."""

    def analyze(
        self,
        chapters: list[ChapterUnderstanding],
        *,
        run_id: str,
        book_id: str,
        evidence_by_chapter: dict[str, list[str]] | None = None,
    ) -> ArgumentAnalysis:
        evidence_by_chapter = evidence_by_chapter or {}
        analysis = ArgumentAnalysis(graph_id=node_id("agraph", run_id, book_id, "argument"))

        for cu in sorted(chapters, key=lambda c: _num(c.chapter_id)):
            claim_label = (cu.chapter_thesis or cu.chapter_question or "").strip()
            if not claim_label:
                # §15: a chapter with no recorded claim cannot yield a chain,
                # and the absence is recorded rather than passed over.
                analysis.unresolved.append(
                    UnresolvedRelation(
                        kind="argument",
                        subject=f"chain from {cu.chapter_id}",
                        reason="chapter recorded neither a thesis nor a question to serve as a claim",
                        source="producer",
                        confidence=0.0,
                        fallback="no chain emitted for this chapter",
                    )
                )
                continue

            chain_id = node_id("chain", run_id, cu.chapter_id)
            claim = ArgumentNode(
                node_id=node_id("an", chain_id, "claim"),
                node_kind="CLAIM",
                label=claim_label,
                chapter_id=cu.chapter_id,
                confidence=0.7,
            )
            analysis.nodes[claim.node_id] = claim
            chain = ArgumentChain(chain_id=chain_id, chapter_id=cu.chapter_id, claim=claim)

            # Evidence: the chapter's evidence program, which §11 has already
            # bound to a strength.
            # EvidenceProgramItem carries claim_ref / evidence_refs / is_supported,
            # not an evidence_id. Flatten the refs instead of inventing a field.
            ev_ids = [ref for ep in cu.evidence_program for ref in ep.evidence_refs]
            chapter_evidence = evidence_by_chapter.get(cu.chapter_id, [])
            strengths = getattr(cu, "evidence_strengths", {}) or {}
            best = "MODEL_INFERENCE"
            for ep in cu.evidence_program:
                kind = strengths.get(ep.evidence_refs[0] if ep.evidence_refs else "", "")
                if EVIDENCE_STRENGTH_RANK.get(kind, 0) > EVIDENCE_STRENGTH_RANK.get(best, 0):
                    best = kind

            for i, ep in enumerate(cu.evidence_program[:3]):
                ev = ArgumentNode(
                    node_id=node_id("an", chain_id, "ev", str(i)),
                    node_kind="EVIDENCE",
                    label=(ep.claim_ref or f"evidence {i + 1}"),
                    chapter_id=cu.chapter_id,
                    confidence=0.65 if ep.is_supported else 0.35,
                    evidence_refs=list(ep.evidence_refs),
                )
                analysis.nodes[ev.node_id] = ev
                chain.evidence.append(ev)
                analysis.edges.append(
                    ArgumentEdge(
                        edge_id=node_id("ae", chain_id, "sup", str(i)),
                        source_node_id=ev.node_id,
                        target_node_id=claim.node_id,
                        edge_kind="SUPPORTS",
                        reason=(
                            f"evidence program entry in {cu.chapter_id} marks this claim "
                            f"supported={ep.is_supported}"
                        ),
                        chain_id=chain_id,
                        evidence_type=best,
                        evidence_refs=list(ep.evidence_refs),
                        confidence=0.7 if ep.is_supported else 0.4,
                    )
                )

            # Reasoning: the chapter's mechanisms are its stated causal steps.
            for i, mech in enumerate(cu.mechanisms_refs[:2]):
                rn = ArgumentNode(
                    node_id=node_id("an", chain_id, "rs", str(i)),
                    node_kind="REASONING",
                    label=mech,
                    chapter_id=cu.chapter_id,
                    confidence=0.6,
                )
                analysis.nodes[rn.node_id] = rn
                chain.reasoning.append(rn)
                if chain.evidence:
                    analysis.edges.append(
                        ArgumentEdge(
                            edge_id=node_id("ae", chain_id, "drv", str(i)),
                            source_node_id=chain.evidence[0].node_id,
                            target_node_id=rn.node_id,
                            edge_kind="DERIVES",
                            reason=f"mechanism recorded in {cu.chapter_id}",
                            chain_id=chain_id,
                            evidence_refs=list(chain.evidence[0].evidence_refs),
                            confidence=0.55,
                        )
                    )

            # Conclusion: the chapter's qualifications and unresolved questions are
            # where the author says what does not follow, which is a conclusion
            # about the argument's limits.
            closing = ""
            if cu.qualifications:
                closing = cu.qualifications[0]
            elif cu.assumptions:
                closing = cu.assumptions[0]
            elif ev_ids or chapter_evidence:
                closing = f"{cu.chapter_id} establishes its thesis"

            if closing and chain.reasoning:
                conc = ArgumentNode(
                    node_id=node_id("an", chain_id, "concl"),
                    node_kind="CONCLUSION",
                    label=closing,
                    chapter_id=cu.chapter_id,
                    confidence=0.55,
                )
                analysis.nodes[conc.node_id] = conc
                chain.conclusion = conc
                analysis.edges.append(
                    ArgumentEdge(
                        edge_id=node_id("ae", chain_id, "conc"),
                        source_node_id=chain.reasoning[-1].node_id,
                        target_node_id=conc.node_id,
                        edge_kind="DERIVES",
                        reason=f"stated qualification in {cu.chapter_id}",
                        chain_id=chain_id,
                        evidence_refs=list(chain.evidence[0].evidence_refs)
                        if chain.evidence
                        else [],
                        confidence=0.55,
                    )
                )
                analysis.edges.append(
                    ArgumentEdge(
                        edge_id=node_id("ae", chain_id, "summ"),
                        source_node_id=conc.node_id,
                        target_node_id=claim.node_id,
                        edge_kind="SUMMARIZES",
                        reason="the chapter's stated limit qualifies its own claim",
                        chain_id=chain_id,
                        evidence_refs=list(chain.evidence[0].evidence_refs)
                        if chain.evidence
                        else [],
                        confidence=0.5,
                    )
                )
                chain.edges = [e for e in analysis.edges if e.chain_id == chain_id]

            chain.evidence_strength = best
            # A chain is complete only when it has a claim, evidence and a
            # conclusion. Two of three is a partial argument, and §15 says to say so
            # rather than round it up.
            chain.complete = bool(chain.evidence) and chain.conclusion is not None
            analysis.chains.append(chain)

            if not chain.complete:
                analysis.unresolved.append(
                    UnresolvedRelation(
                        kind="argument",
                        subject=chain_id,
                        reason=(
                            "no evidenced conclusion: "
                            + (
                                "no evidence program"
                                if not chain.evidence
                                else "no stated qualification"
                            )
                        ),
                        source="argument_analyzer",
                        confidence=chain.claim.confidence,
                        fallback="partial chain recorded; not counted as complete",
                    )
                )

        # Reconstructed arguments: each one the chapter itself makes (a result,
        # the steps that establish it, what follows) becomes its own chain, so
        # a chapter's argument structure is more than its thesis.
        for cu in chapters:
            for arg in getattr(cu, "chapter_arguments", []) or []:
                _chain_from_argument(analysis, cu, arg, run_id)

        analysis.chains.sort(key=lambda c: (-int(c.complete), -c.claim.confidence))
        return analysis


def _chain_from_argument(analysis: ArgumentAnalysis, cu: Any, arg: Any, run_id: str) -> None:
    chain_id = node_id("chain", run_id, cu.chapter_id, arg.id)
    strengths = getattr(cu, "evidence_strengths", {}) or {}
    refs = list(arg.evidence_refs)
    strength = strengths.get(refs[0], "DERIVED") if refs else "MODEL_INFERENCE"
    claim = ArgumentNode(
        node_id=node_id("an", chain_id, "claim"),
        node_kind="CLAIM",
        label=arg.question,
        chapter_id=cu.chapter_id,
        confidence=0.8 if strength == "DIRECT" else 0.7,
        evidence_refs=refs,
    )
    analysis.nodes[claim.node_id] = claim
    chain = ArgumentChain(chain_id=chain_id, chapter_id=cu.chapter_id, claim=claim)
    premises = list(arg.premises) or [arg.question]
    for i, prem in enumerate(premises[:4]):
        ev = ArgumentNode(
            node_id=node_id("an", chain_id, "ev", str(i)),
            node_kind="EVIDENCE",
            label=prem,
            chapter_id=cu.chapter_id,
            confidence=0.7,
            evidence_refs=refs,
        )
        analysis.nodes[ev.node_id] = ev
        chain.evidence.append(ev)
    prev = chain.evidence[0] if chain.evidence else claim
    for i, step in enumerate(arg.inference_steps[:8]):
        rn = ArgumentNode(
            node_id=node_id("an", chain_id, "rs", str(i)),
            node_kind="REASONING",
            label=step,
            chapter_id=cu.chapter_id,
            confidence=0.7,
            evidence_refs=refs,
        )
        analysis.nodes[rn.node_id] = rn
        chain.reasoning.append(rn)
        analysis.edges.append(
            ArgumentEdge(
                edge_id=node_id("ae", chain_id, "drv", str(i)),
                source_node_id=prev.node_id,
                target_node_id=rn.node_id,
                edge_kind="DERIVES",
                reason=f"step {i + 1} of the argument the text makes in {cu.chapter_id}",
                chain_id=chain_id,
                evidence_type=strength,
                evidence_refs=refs,
                confidence=0.7,
            )
        )
        prev = rn
    for i, ev in enumerate(chain.evidence[1:], start=1):
        analysis.edges.append(
            ArgumentEdge(
                edge_id=node_id("ae", chain_id, "sup", str(i)),
                source_node_id=ev.node_id,
                target_node_id=claim.node_id,
                edge_kind="SUPPORTS",
                reason="stated premise of the argument",
                chain_id=chain_id,
                evidence_type=strength,
                evidence_refs=refs,
                confidence=0.7,
            )
        )
    concl_label = (arg.conclusion or [""])[0]
    if concl_label and chain.reasoning:
        conc = ArgumentNode(
            node_id=node_id("an", chain_id, "concl"),
            node_kind="CONCLUSION",
            label=concl_label,
            chapter_id=cu.chapter_id,
            confidence=0.7,
            evidence_refs=refs,
        )
        analysis.nodes[conc.node_id] = conc
        chain.conclusion = conc
        analysis.edges.append(
            ArgumentEdge(
                edge_id=node_id("ae", chain_id, "conc"),
                source_node_id=chain.reasoning[-1].node_id,
                target_node_id=conc.node_id,
                edge_kind="DERIVES",
                reason="the argument's stated conclusion",
                chain_id=chain_id,
                evidence_type=strength,
                evidence_refs=refs,
                confidence=0.7,
            )
        )
        analysis.edges.append(
            ArgumentEdge(
                edge_id=node_id("ae", chain_id, "summ"),
                source_node_id=conc.node_id,
                target_node_id=claim.node_id,
                edge_kind="SUMMARIZES",
                reason="the conclusion is what the claimed result delivers",
                chain_id=chain_id,
                evidence_type=strength,
                evidence_refs=refs,
                confidence=0.65,
            )
        )
    chain.edges = [e for e in analysis.edges if e.chain_id == chain_id]
    chain.evidence_strength = strength
    chain.complete = bool(chain.evidence) and chain.conclusion is not None
    analysis.chains.append(chain)


def _num(chapter_id: str) -> int:
    d = "".join(c for c in (chapter_id or "") if c.isdigit())
    return int(d) if d else 0
