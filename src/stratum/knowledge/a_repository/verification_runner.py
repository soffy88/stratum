"""A Repository P3 — verification runner.

Applies the P3 verification stage to the frozen P1/P2 baseline.
Deterministic, resumable, idempotent. No DB mutation.

Run: PYTHONPATH=src python3 -m stratum.knowledge.a_repository.verification_runner
"""

from __future__ import annotations

import json
from typing import Dict

from . import pilot_corpus as C
from .quality_runner import build_quality_baseline
from .verification import VERIFIER_VERSION, AVerificationPipeline


def build_verification_baseline() -> Dict:
    """P2 chain + P3 verification decisions."""
    upstream = build_quality_baseline()
    base, quality_pipeline = upstream["base"], upstream["quality"]
    vp = AVerificationPipeline(base["pipeline"], quality_pipeline)
    candidate_ids = [base["candidate_ids"][item["key"]]
                     for item in sorted(C.KU_CANDIDATES,
                                        key=lambda i: i["key"])]
    vp.verify_all(candidate_ids)
    return {"base": base, "quality": quality_pipeline, "verification": vp}


def report(result: Dict) -> Dict:
    vp: AVerificationPipeline = result["verification"]
    pipeline = result["base"]["pipeline"]
    run_id = result["base"]["reading_run_id"]
    by_id = {cid: key for key, cid
             in result["base"]["candidate_ids"].items()}

    rejections = {
        by_id[v.candidate_id]: v.verification_trace.get("failed_rules", [])
        for v in vp.store.verifications.values()
        if v.verification_status == "REJECTED"
    }
    return {
        "run_id": run_id,
        "book": f"{C.BOOK_TITLE} {C.BOOK_EDITION}",
        "candidate_count": pipeline.candidate_count(run_id),
        "verification_count": vp.verification_count(run_id),
        "verified": vp.verified_count(run_id),
        "rejected": vp.rejected_count(run_id),
        "status_breakdown": vp.status_breakdown(run_id),
        "rejection_reasons": dict(sorted(rejections.items())),
        "orphan_verifications": vp.orphan_verifications(),
        "traceability": vp.traceability(run_id),
        "verifier_version": VERIFIER_VERSION,
    }


def main() -> None:
    print(json.dumps(report(build_verification_baseline()),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()