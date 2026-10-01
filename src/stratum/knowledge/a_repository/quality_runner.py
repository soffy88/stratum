"""A Repository P2 — quality runner.

Applies the P2 quality + classification stage to the frozen P1 Chapter 1
baseline. Deterministic, resumable, idempotent. No DB mutation.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.quality_runner
"""

from __future__ import annotations

import json
from typing import Dict

from . import pilot_corpus as C
from .freeze_runner import build_baseline
from .quality import EvidenceQualityPipeline, deterministic_id


def build_quality_baseline() -> Dict:
    """P1 chain + P2 quality rows + P2 classification."""
    base = build_baseline()
    p = base["pipeline"]
    qp = EvidenceQualityPipeline(p)
    run_id = base["reading_run_id"]

    for item in C.EVIDENCE:
        ev_id = base["evidence_ids"][item["key"]]
        if qp.has_quality(ev_id):
            continue
        qp.score_evidence(
            evidence_id=ev_id,
            locator=p.store.evidence[ev_id].locator,
            quality_id=deterministic_id("eq", ev_id, "p2-v1"),
        )

    for item in sorted(C.KU_CANDIDATES, key=lambda i: i["key"]):
        kc_id = base["candidate_ids"][item["key"]]
        if getattr(p.store.ku_candidates[kc_id], "classification", None):
            continue
        qp.classify_candidate(kc_id)

    return {"base": base, "quality": qp}


def report(result: Dict) -> Dict:
    qp: EvidenceQualityPipeline = result["quality"]
    run_id = result["base"]["reading_run_id"]
    p = result["base"]["pipeline"]

    by_class: Dict[str, int] = {}
    for kc in p.store.ku_candidates.values():
        if kc.classification:
            by_class[kc.classification.value] = by_class.get(
                kc.classification.value, 0) + 1

    return {
        "run_id": run_id,
        "evidence_count": p.evidence_count(run_id),
        "quality_count": qp.quality_count(run_id),
        "classification_count": qp.classification_count(run_id),
        "unclassified": qp.unclassified_candidates(run_id),
        "orphan_quality": qp.orphan_quality(),
        "overall_quality": qp.overall_quality(run_id),
        "classification_breakdown": dict(sorted(by_class.items())),
        "quality_version": "p2-v1",
    }


def main() -> None:
    print(json.dumps(report(build_quality_baseline()),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()