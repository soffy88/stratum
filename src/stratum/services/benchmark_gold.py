"""Benchmark gold + primary evaluation (§§113-120).

Gold is structural, never a reference summary (§114): governing questions,
theses, critical KUs, arguments, chapter roles, dependencies, qualifications,
revisions, mechanisms, visual evidence, negative knowledge — plus
ROOT/BRANCH/LEAF sets (§115) and evidence gold (§116).

Scoring functions are pure and structural (no ROUGE, §120). Human-written
reference summaries are not required; P10 real-user qualification (§133)
needs human subjects and is tracked as Needs Human, not implemented here.
"""

from __future__ import annotations

from typing import Any, Dict, List

from stratum.knowledge.bu_v2_models import (
    BaselineKind, BookGold, EvidenceGold, MetricScore, ResolutionGold,
)


def baseline_registry() -> Dict[str, str]:
    """§119 baselines B0-B6 descriptors."""
    return {
        BaselineKind.B0_CHUNK_RAG.value: "vector top-k chunks -> LLM answer",
        BaselineKind.B1_WHOLE_CONTEXT_LLM.value: "whole book in context -> LLM claims understanding",
        BaselineKind.B2_CHAPTER_SUMMARY_BOOK_SUMMARY.value: "summarize(chapter summaries)",
        BaselineKind.B3_PAGE_KU_EXTRACTION.value: "page-level KU extraction, no integration",
        BaselineKind.B4_CURRENT_STRATUM.value: "current production (aii.bu_onto flywheel)",
        BaselineKind.B5_BU_1_1.value: "Book Understanding 1.1",
        BaselineKind.B6_BU_2_0.value: "Book Understanding 2.0 (this spec)",
    }


def _recall(gold_items: List[str], bu_items: List[str]) -> float:
    if not gold_items:
        return 1.0
    hit = sum(1 for g in gold_items if g in bu_items)
    return hit / len(gold_items)


def _precision(pred_items: List[str], gold_items: List[str]) -> float:
    if not pred_items:
        return 1.0
    hit = sum(1 for p in pred_items if p in gold_items)
    return hit / len(pred_items)


def score_book(gold: BookGold, bu: Dict[str, Any],
               argument_ids: List[str] | None = None,
               mechanism_ids: List[str] | None = None) -> List[MetricScore]:
    """§120 structural metrics over refs (no text similarity)."""
    bu_kus = bu.get("major_ku_refs", []) + bu.get("supporting_ku_refs", [])
    quals = bu.get("qualifications", [])
    out = [
        MetricScore(metric="KU_PRECISION",
                    score=_precision(bu_kus, gold.critical_ku_refs)),
        MetricScore(metric="KU_RECALL",
                    score=_recall(gold.critical_ku_refs, bu_kus)),
        MetricScore(metric="QUALIFICATION_RECALL",
                    score=_recall(gold.qualifications, quals)),
        MetricScore(metric="REVISION_RECALL",
                    score=_recall(gold.revisions,
                                  [c.get("claim_ref", "") for c in bu.get("claim_evolution", [])])),
        MetricScore(metric="NEGATIVE_KNOWLEDGE_ACCURACY",
                    score=_recall(gold.negative_knowledge,
                                  bu.get("rejected_claims", []) + bu.get("limitations", []))),
        MetricScore(metric="CHAPTER_ROLE_ACCURACY",
                    score=_chapter_role_accuracy(gold, bu)),
        MetricScore(metric="CROSS_CHAPTER_INTEGRATION",
                    score=_recall(gold.cross_chapter_deps,
                                  [f"{d.get('source_chapter')}->{d.get('target_chapter')}"
                                   for d in bu.get("chapter_dependencies", [])])),
        MetricScore(metric="ARGUMENT_RECONSTRUCTION",
                    score=_recall(gold.major_arguments, argument_ids or [])),
        MetricScore(metric="MECHANISM_RECONSTRUCTION",
                    score=_recall(gold.mechanisms, mechanism_ids or [])),
        MetricScore(metric="VISUAL_GROUNDING",
                    score=_recall(gold.visual_evidence, bu.get("visual_refs", []))),
    ]
    return out


def _chapter_role_accuracy(gold: BookGold, bu: Dict[str, Any]) -> float:
    roles = bu.get("chapter_roles", {})
    if not gold.chapter_roles:
        return 1.0
    hit = sum(1 for ch, role in gold.chapter_roles.items() if roles.get(ch) == role)
    return hit / len(gold.chapter_roles)


def score_resolution(gold: ResolutionGold, got: Dict[str, List[str]]) -> List[MetricScore]:
    """§115: ROOT + BRANCH + LEAF_SAMPLE coverage (§46: leaf distorts most)."""
    return [
        MetricScore(metric="ROOT_COMPREHENSION",
                    score=_recall(gold.root, got.get("ROOT", []))),
        MetricScore(metric="BRANCH_COMPREHENSION",
                    score=_recall(gold.branch, got.get("BRANCH", []))),
        MetricScore(metric="LEAF_COMPREHENSION",
                    score=_recall(gold.leaf_sample, got.get("LEAF", []))),
    ]


def score_trajectory(gold: EvidenceGold, traj: Dict[str, Any]) -> List[MetricScore]:
    """§116 + §49: stage-wise trajectory accuracy, not answer-only."""
    return [
        MetricScore(metric="PAGE_LOCALIZATION",
                    score=_recall([str(p) for p in gold.required_pages],
                                  [str(p) for p in traj.get("source_pages", [])])),
        MetricScore(metric="REGION_GROUNDING",
                    score=_recall(gold.required_regions, traj.get("evidence_regions", []))),
        MetricScore(metric="FACT_EXTRACTION",
                    score=_recall(gold.required_facts, traj.get("extracted_facts", []))),
        MetricScore(metric="EVIDENCE_TRAJECTORY_ACCURACY",
                    score=_recall(gold.required_ku, traj.get("ku_refs", []))),
    ]
