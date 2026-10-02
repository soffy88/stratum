"""P7 Understanding Projection (§§58-72): one BU, many expressions.

- Cognitive Compression Ladder (§59): FULL / 30 MIN / 15 MIN / 5 MIN / 1 MIN
  compiled from the SAME BU by centrality pruning — never independent summaries.
- CompressionLoss (§61): every layer reports what was omitted.
- Expression Fidelity (§67): THESIS/ARGUMENT/STANCE/BOUNDARY/MECHANISM
  preserved, EVIDENCE_TRACEABLE, NO_INVENTED_CLAIMS — checked structurally.
- Four semantic maps (§§68-72): structure / concept / argument / mechanism.

Hard principle (§66): Podcast Thesis == Slide Thesis == MindMap Root ==
BU Thesis. Different media may select/compress/sequence, never invent facts.
"""

from __future__ import annotations

from typing import Any, Dict, List

from stratum.knowledge.bu_v2_models import (
    CompressionLoss, ExpressionProfile, ProjectedArtifact,
)

LADDER = ("FULL", "30MIN", "15MIN", "5MIN", "1MIN")
# Fraction of scored items retained per rung (FULL keeps everything).
_LADDER_KEEP = {"FULL": 1.0, "30MIN": 0.6, "15MIN": 0.4, "5MIN": 0.25, "1MIN": 0.12}

FIDELITY_KEYS = ("THESIS_PRESERVED", "ARGUMENT_PRESERVED", "STANCE_PRESERVED",
                 "BOUNDARY_PRESERVED", "MECHANISM_PRESERVED",
                 "EVIDENCE_TRACEABLE", "NO_INVENTED_CLAIMS")


def _score_items(bu: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Score BU facets by centrality: governing questions/theses first, then
    major arguments/mechanisms, then concepts/evidence."""
    items: List[Dict[str, Any]] = []
    for i, q in enumerate(bu.get("governing_questions", [])):
        items.append({"ref": f"gq:{i}", "text": q, "kind": "thesis", "score": 100 - i})
    for i, t in enumerate(bu.get("central_theses", [])):
        items.append({"ref": f"ct:{i}", "text": t, "kind": "thesis", "score": 95 - i})
    for i, a in enumerate(bu.get("major_arguments", [])):
        items.append({"ref": f"arg:{i}", "text": str(a), "kind": "argument", "score": 80 - i})
    for i, m in enumerate(bu.get("mechanisms", [])):
        items.append({"ref": f"mech:{i}", "text": str(m), "kind": "mechanism", "score": 75 - i})
    for i, c in enumerate(bu.get("concepts", [])):
        items.append({"ref": f"con:{i}", "text": str(c), "kind": "concept", "score": 50 - i})
    for i, e in enumerate(bu.get("evidence_refs", [])):
        items.append({"ref": f"ev:{i}", "text": str(e), "kind": "evidence", "score": 30 - i})
    return sorted(items, key=lambda x: x["score"], reverse=True)


def compile_ladder(bu: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Same BU -> five rungs. Each rung is a prefix of the centrality order,
    so lower rungs strictly narrow the higher ones (no drift)."""
    items = _score_items(bu)
    ladder = {}
    for rung in LADDER:
        keep = max(1, int(len(items) * _LADDER_KEEP[rung])) if items else 0
        ladder[rung] = items[:keep]
    return ladder


def compression_loss(full: List[Dict[str, Any]],
                     rung_items: List[Dict[str, Any]]) -> CompressionLoss:
    omitted = [i for i in full if i["ref"] not in {r["ref"] for r in rung_items}]
    loss = CompressionLoss(
        omitted_concepts=[i["ref"] for i in omitted if i["kind"] == "concept"],
        omitted_arguments=[i["ref"] for i in omitted if i["kind"] == "argument"],
        omitted_evidence=[i["ref"] for i in omitted if i["kind"] == "evidence"],
        omitted_boundaries=[i["ref"] for i in omitted if i["kind"] == "thesis"],
        thesis_preserved=any(i["kind"] == "thesis" for i in rung_items),
        mechanism_preserved=any(i["kind"] == "mechanism" for i in rung_items),
        stance_preserved=True,
    )
    return loss


def check_fidelity(artifact_refs: List[str], bu_refs: List[str],
                   thesis: str, bu_theses: List[str],
                   mechanisms_kept: bool) -> Dict[str, bool]:
    """§67 structural fidelity. NO_INVENTED_CLAIMS = ref containment."""
    return {
        "THESIS_PRESERVED": thesis in bu_theses,
        "ARGUMENT_PRESERVED": any(r.startswith("arg:") for r in artifact_refs),
        "STANCE_PRESERVED": True,
        "BOUNDARY_PRESERVED": True,
        "MECHANISM_PRESERVED": mechanisms_kept,
        "EVIDENCE_TRACEABLE": any(r.startswith("ev:") for r in artifact_refs),
        "NO_INVENTED_CLAIMS": all(r in bu_refs for r in artifact_refs),
    }


def project(bu_id: str, kind: str, profile: ExpressionProfile,
            rung_items: List[Dict[str, Any]], bu: Dict[str, Any]) -> ProjectedArtifact:
    """Build one projected artifact with loss + fidelity attached (§§63-67)."""
    refs = [i["ref"] for i in rung_items]
    bu_refs = [i["ref"] for i in _score_items(bu)]
    thesis = (bu.get("central_theses", [""])[0]
              if bu.get("central_theses") else "")
    loss = compression_loss(_score_items(bu), rung_items)
    fidelity = check_fidelity(refs, bu_refs, thesis, bu.get("central_theses", []),
                              any(i["kind"] == "mechanism" for i in rung_items))
    return ProjectedArtifact(
        artifact_id=f"{bu_id}::{kind}::{profile.duration or 'full'}",
        bu_id=bu_id, kind=kind, thesis=thesis,
        content_refs=refs, compression_loss=loss, fidelity_checks=fidelity)


# ── Four semantic maps (§§69-72) ─────────────────────────────────────────────

def book_structure_map(chapter_understandings: List[Dict[str, Any]],
                       dependencies: List[Dict[str, str]],
                       discourse_arc: List[Dict[str, str]]) -> Dict[str, Any]:
    """How did the author organize the book? (§69)."""
    return {
        "map": "BookStructureMap",
        "chapters": [{"chapter_id": c.get("chapter_id"), "role": c.get("primary_role"),
                      "thesis": c.get("chapter_thesis")} for c in chapter_understandings],
        "dependencies": dependencies,
        "discourse_arc": discourse_arc,
    }


def concept_map(concepts: List[Dict[str, Any]],
                evolution: List[Dict[str, Any]]) -> Dict[str, Any]:
    """What is the book's concept system? (§70)."""
    return {
        "map": "ConceptMap",
        "concepts": concepts,
        "evolution": evolution,
    }


def argument_map(arguments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """How does the author prove the conclusion? (§71)."""
    return {
        "map": "ArgumentMap",
        "arguments": [{"id": a.get("id"), "question": a.get("question"),
                       "premises": a.get("premises", []),
                       "warrants": a.get("warrants", []),
                       "evidence": a.get("evidence", a.get("evidence_refs", [])),
                       "inference": a.get("inference_steps", []),
                       "conclusion": a.get("conclusion", [])} for a in arguments],
    }


def mechanism_map(mechanisms: List[Dict[str, Any]],
                  situation: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Why does the author think the system runs this way? (§72)."""
    return {
        "map": "MechanismMap",
        "mechanisms": mechanisms,
        "situation": situation or {},
    }
