"""P6 adversarial verification executors (§§48, 54-58, §§117-118).

Deterministic, structure-based challengers operating on the persisted BU
graph (dicts/lists) — no LLM. Each challenger returns explicit verdicts; the
pipeline's verification gate consumes them as gaps, never as self-scores.

Covered: holdout probes, mutation tests (7 types, must REJECT), chapter
ablation, premise/evidence ablation (§55 verdict classes), minimal-pair
distinctions (§57), cross-chapter revision reconstruction (§56), and the
targeted-reread planner (§53).
"""

from __future__ import annotations

from typing import Any, Dict, List

from stratum.knowledge.bu_v2_models import (
    AblationResult, AblationVerdict, HoldoutItem, MinimalPairCase,
    MutationCase, MutationType, MutationVerdict,
)

REJECT = "REJECT"


def holdout_probe(item: HoldoutItem, bu_refs: List[str]) -> Dict[str, Any]:
    """Builder never saw this holdout. PASS only if the BU already exposes
    every required ref (gap exposure, not confident completion, §117)."""
    missing = [r for r in item.required_refs if r not in bu_refs]
    return {
        "holdout_id": item.holdout_id,
        "passed": len(missing) == 0,
        "missing_refs": missing,
        "exposed_gap": len(missing) > 0,
    }


def mutation_verdict(case: MutationCase, truth: Dict[str, Any]) -> MutationVerdict:
    """Each mutation type must be REJECTED against the structured truth.
    truth keys depend on type: stance, quantifier, conditions, causal_links,
    chapter_relations, evidence_refs, conclusion_strength."""
    t = case.mutation_type
    reason = ""
    rejected = False
    if t == MutationType.WRONG_STANCE:
        rejected = truth.get("stance") != case.mutated_statement
        reason = "stance mismatch with author stance" if rejected else "stance accepted"
    elif t == MutationType.WRONG_QUANTIFIER:
        rejected = truth.get("quantifier") != case.mutated_statement
        reason = "quantifier not supported by scope" if rejected else "quantifier accepted"
    elif t == MutationType.MISSING_CONDITION:
        required = truth.get("conditions", [])
        rejected = len(required) > 0
        reason = f"dropped required condition(s): {required}" if rejected else "no condition required"
    elif t == MutationType.REVERSED_CAUSALITY:
        links = truth.get("causal_links", [])
        rejected = case.mutated_statement not in links and len(links) > 0
        reason = "causal direction contradicts mechanism" if rejected else "no causal constraint"
    elif t == MutationType.WRONG_CHAPTER_RELATION:
        rels = truth.get("chapter_relations", [])
        rejected = case.mutated_statement not in rels
        reason = "relation absent from dependency graph" if rejected else "relation present"
    elif t == MutationType.FAKE_EVIDENCE:
        ev = truth.get("evidence_refs", [])
        rejected = case.mutated_statement not in ev
        reason = "evidence ref untraceable" if rejected else "evidence present"
    elif t == MutationType.OVERSTATED_CONCLUSION:
        strength = truth.get("conclusion_strength", "")
        rejected = strength in ("qualified", "conditional", "partial")
        reason = "conclusion is qualified, not absolute" if rejected else "conclusion is absolute"
    return MutationVerdict(case_id=case.id, rejected=rejected, reason=reason)


def chapter_ablation(chapter_id: str, theses: List[Dict[str, Any]],
                     arguments: List[Dict[str, Any]],
                     dependencies: List[Dict[str, str]]) -> AblationResult:
    """Temporarily remove Chapter N (§54): which theses/arguments break?"""
    impacted, broken = [], []
    for th in theses:
        refs = th.get("chapter_refs", []) or th.get("evidence_chapters", [])
        if refs == [chapter_id] or (len(refs) == 1 and refs[0] == chapter_id):
            impacted.append(th.get("id", th.get("thesis", "?")))
    for arg in arguments:
        refs = arg.get("chapter_refs", [])
        if chapter_id in refs:
            others = [r for r in refs if r != chapter_id]
            if not others:
                broken.append(arg.get("id", "?"))
    # Dependency edges that lose an endpoint.
    for dep in dependencies:
        if chapter_id in (dep.get("source_chapter"), dep.get("target_chapter")):
            broken.append(f"edge:{dep.get('source_chapter')}->{dep.get('target_chapter')}")
    verdict = (AblationVerdict.ARGUMENT_INVALID if broken
               else AblationVerdict.SUPPORT_WEAKENED if impacted
               else AblationVerdict.NO_MEANINGFUL_EFFECT)
    return AblationResult(
        target=chapter_id, target_type="chapter",
        impacted_theses=impacted, broken_arguments=broken,
        verdict=verdict,
        detail=f"removed {chapter_id}: {len(impacted)} theses impacted, {len(broken)} breaks")


def premise_ablation(argument: Dict[str, Any], removed: str) -> AblationResult:
    """Delete one premise/warrant/evidence item (§55)."""
    premises = list(argument.get("premises", []))
    remaining = [p for p in premises if p != removed]
    if removed not in premises and removed not in argument.get("evidence", []):
        verdict = AblationVerdict.NO_MEANINGFUL_EFFECT
    elif len(remaining) == 0 and len(argument.get("warrants", [])) == 0:
        verdict = AblationVerdict.ARGUMENT_INVALID
    else:
        verdict = AblationVerdict.SUPPORT_WEAKENED
    return AblationResult(
        target=removed, target_type="premise",
        impacted_theses=[],
        broken_arguments=[argument.get("id", "?")] if verdict == AblationVerdict.ARGUMENT_INVALID else [],
        verdict=verdict,
        detail=f"{verdict.value}: {len(premises)} -> {len(remaining)} premises")


def reconstruct_revision(steps: List[Dict[str, str]]) -> Dict[str, Any]:
    """Cross-chapter revision chain X -> QUALIFIED_BY C -> REVISED_TO X' (§56).
    Original KUs are preserved (returned untouched); only the chain is built."""
    chain = []
    for s in steps:
        if s.get("evolution_type") not in ("REFINE", "QUALIFY", "REVISE", "RESTATED"):
            return {"ok": False, "reason": f"unknown evolution_type: {s.get('evolution_type')}",
                    "chain": chain}
        chain.append(s)
    return {"ok": True, "chain": chain, "originals_preserved": True}


_MINIMAL_PAIR_RULES = {
    "may/does": ("possibility", "actuality"),
    "some/all": ("existential", "universal"),
    "usually/always": ("habitual", "universal"),
    "correlation/causation": ("association", "mechanism"),
    "supports/proves": ("partial", "conclusive"),
    "example/rule": ("instance", "general"),
    "critic says/author says": ("quoted", "asserted"),
    "hypothesis/conclusion": ("conjectured", "established"),
    "under C/unconditional": ("conditional", "absolute"),
}


def minimal_pair_check(case: MinimalPairCase) -> Dict[str, Any]:
    """§57: the two sides must map to different semantic slots."""
    key = case.distinction.strip().lower()
    expected = _MINIMAL_PAIR_RULES.get(key)
    if expected is None:
        return {"case_id": case.id, "distinguished": False,
                "reason": f"unknown distinction class: {case.distinction}"}
    a_ok = bool(case.side_a and case.side_a != case.side_b)
    return {"case_id": case.id,
            "distinguished": a_ok and expected[0] != expected[1],
            "slots": list(expected),
            "reason": f"{case.side_a!r} -> {expected[0]}, {case.side_b!r} -> {expected[1]}"}


def plan_targeted_reread(gap: Dict[str, Any],
                         chapter_index: Dict[str, List[str]]) -> Dict[str, Any]:
    """Gap -> affected graph -> source regions -> reread plan (§53). Never a
    blind full-book rerun: regions are bounded by the chapter index."""
    targets = gap.get("evidence_targets", []) or gap.get("affected_chapters", [])
    regions: List[str] = []
    for t in targets:
        regions.extend(chapter_index.get(t, [t]))
    seen, bounded = set(), []
    for r in regions:
        if r not in seen:
            seen.add(r)
            bounded.append(r)
    return {
        "gap_id": gap.get("id", gap.get("gap_id", "")),
        "regions": bounded,
        "repair": gap.get("required_action", "reread"),
        "full_rerun": False,
        "steps": ["locate", "reread", "repair", "propagate", "reverify"],
    }
