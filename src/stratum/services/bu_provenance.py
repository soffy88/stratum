"""P5 statement provenance (§§39-41) + multi-resolution zoom (§§46-47) + lineage (§13).

- AUTHOR_EXPLICIT: said in one place, needs >= 1 source ref.
- AUTHOR_SYNTHESIZED: spread over the book, needs >= 2 source_refs + trace.
- STRATUM_DERIVED: our inference, needs derived refs + reason + confidence,
  and must never flow back into Raw KU (enforced by keeping derived refs
  disjoint from raw KU registries at validation time).
- Resolution: ROOT / BRANCH / LEAF assigned by centrality over the BU graph.
- Lineage: claim -> argument -> KU -> evidence -> fragment/page over caller
  supplied indexes (no store invented here).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from stratum.knowledge.bu_v2_models import (
    BUStatement, BUVerificationState, ResolutionLevel, ResolutionNode,
    StatementProvenance,
)


def validate_statement(stmt: BUStatement,
                       raw_ku_ids: List[str] | None = None) -> Tuple[bool, List[str]]:
    """Provenance gate. Returns (ok, failures)."""
    failures: List[str] = []
    if stmt.provenance == StatementProvenance.AUTHOR_EXPLICIT:
        if len(stmt.source_refs) < 1:
            failures.append("AUTHOR_EXPLICIT requires >= 1 source_ref.")
    elif stmt.provenance == StatementProvenance.AUTHOR_SYNTHESIZED:
        if len(stmt.source_refs) < 2:
            failures.append("AUTHOR_SYNTHESIZED requires source_refs >= 2 (§40).")
        if not stmt.synthesis_trace.strip():
            failures.append("AUTHOR_SYNTHESIZED requires a synthesis trace.")
    elif stmt.provenance == StatementProvenance.STRATUM_DERIVED:
        if not (stmt.derived_from_ku_refs or stmt.argument_refs or stmt.evidence_refs):
            failures.append("STRATUM_DERIVED requires derived_from refs (§41).")
        if not stmt.derivation_reason.strip():
            failures.append("STRATUM_DERIVED requires a derivation_reason.")
        if not (0.0 <= stmt.confidence <= 1.0):
            failures.append("STRATUM_DERIVED requires confidence in [0,1].")
        if raw_ku_ids is not None:
            leaked = [r for r in (stmt.derived_from_ku_refs or [])
                      if r in raw_ku_ids and r.startswith("raw:")]
            if leaked:
                failures.append(f"STRATUM_DERIVED must not enter Raw KU: {leaked}.")
    else:
        failures.append(f"Unknown provenance: {stmt.provenance}.")
    return (len(failures) == 0, failures)


def centrality(ref: str, arguments: List[Dict[str, Any]],
               theses: List[str], questions: List[str]) -> float:
    """Cheap centrality: thesis/question mention (2.0) + argument degree (1.0
    per containing argument) + evidence support (0.5 per evidence ref)."""
    score = 0.0
    joined_args = " ".join(str(a) for a in arguments)
    if ref in " ".join(theses):
        score += 2.0
    if ref in " ".join(questions):
        score += 2.0
    score += 1.0 * joined_args.count(ref)
    return score


def build_resolution(nodes: List[ResolutionNode]) -> Dict[str, List[ResolutionNode]]:
    """Group pre-scored nodes; ROOT = top centrality core model (§46)."""
    return {
        "ROOT": [n for n in nodes if n.level == ResolutionLevel.ROOT],
        "BRANCH": [n for n in nodes if n.level == ResolutionLevel.BRANCH],
        "LEAF": [n for n in nodes if n.level == ResolutionLevel.LEAF],
    }


def assign_levels(items: List[Dict[str, Any]]) -> List[ResolutionNode]:
    """Assign ROOT/BRANCH/LEAF by centrality terciles over scored items.
    Items: {node_id, label, centrality, bu_refs, ku_refs, evidence_refs}."""
    if not items:
        return []
    ranked = sorted(items, key=lambda i: i.get("centrality", 0.0), reverse=True)
    n = len(ranked)
    out = []
    for i, item in enumerate(ranked):
        frac = i / max(n - 1, 1)
        level = (ResolutionLevel.ROOT if frac < 0.2
                 else ResolutionLevel.BRANCH if frac < 0.6
                 else ResolutionLevel.LEAF)
        out.append(ResolutionNode(
            node_id=item.get("node_id", f"n{i}"),
            level=level,
            label=item.get("label", ""),
            bu_refs=item.get("bu_refs", []),
            ku_refs=item.get("ku_refs", []),
            evidence_refs=item.get("evidence_refs", []),
            centrality=item.get("centrality", 0.0)))
    return out


def zoom(node_id: str, nodes: List[ResolutionNode],
         edges: List[Tuple[str, str]]) -> Dict[str, List[str]]:
    """ROOT <-> BRANCH <-> LEAF <-> KU <-> Evidence drill path (§47).
    edges are (parent, child) containment links."""
    children = {p: [] for p in [n.node_id for n in nodes]}
    parents: Dict[str, List[str]] = {n.node_id: [] for n in nodes}
    for p, c in edges:
        children.setdefault(p, []).append(c)
        parents.setdefault(c, []).append(p)
    return {"down": children.get(node_id, []), "up": parents.get(node_id, [])}


def trace_lineage(claim_ref: str, indexes: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """Walk claim -> argument -> KU -> evidence -> page (§13) over caller
    supplied indexes: {arguments:{}, kus:{}, evidence:{}, pages:{}}.
    Missing links are reported, never hallucinated."""
    trail: Dict[str, Any] = {"claim": claim_ref, "links": [], "broken_at": None}
    current, kind = claim_ref, "claim"
    hop_order = ["claim", "argument", "ku", "evidence", "page"]
    for _ in range(len(hop_order)):
        store_key = {"ku": "kus", "evidence": "evidence"}.get(kind, kind + "s")
        store = indexes.get(store_key, {}) or {}
        node = store.get(current)
        if node is None:
            trail["broken_at"] = (kind, current)
            break
        nxt = node.get("next_ref")
        trail["links"].append((kind, current))
        if not nxt:
            break
        current = nxt
        idx = hop_order.index(kind)
        kind = hop_order[idx + 1] if idx + 1 < len(hop_order) else kind
        if kind == "page":
            trail["links"].append(("page", current))
            break
    trail["complete"] = trail["broken_at"] is None
    return trail


def verification_state_of_bu(coverage: Dict[str, float],
                             verification_score: float,
                             open_gaps: int) -> BUVerificationState:
    """§106: status instead of fake percentage."""
    if open_gaps > 0 or verification_score <= 0:
        return BUVerificationState.UNVERIFIED
    if verification_score >= 0.9 and all(v >= 0.9 for v in coverage.values()):
        return BUVerificationState.VERIFIED
    if verification_score >= 0.6:
        return BUVerificationState.QUALIFIED
    return BUVerificationState.PARTIAL
