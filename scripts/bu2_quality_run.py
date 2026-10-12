"""Task G: run BU2 for a book against the freellmapi gateway, with KU anchoring.

Usage:
    python scripts/bu2_quality_run.py <substrate_id> [--model M] [--chapters N] [--persist]

Reads the gateway base URL / key from the environment (PPT_LLM_*), which the
operator sources from ~/.config/keys/.env. Never prints the key.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, "src")


def build_provider(model: str):
    from stratum.services.bu_v2_provider import resolve_provider

    base = os.environ.get("PPT_LLM_BASE_URL") or "http://172.19.0.1:3001/v1"
    key = os.environ.get("PPT_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY") or ""
    if not key:
        raise SystemExit("no gateway key in PPT_LLM_API_KEY")
    return resolve_provider("openai", model=model, base_url=base, api_key=key)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("substrate_id")
    ap.add_argument(
        "--model", default=os.environ.get("PPT_LLM_MODEL") or "deepseek-ai/DeepSeek-V3.2"
    )
    ap.add_argument("--chapters", type=int, default=None)
    ap.add_argument("--persist", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument(
        "--judge-model",
        default=os.environ.get("BU2_JUDGE_MODEL"),
        help="a different model for the accuracy dimension",
    )
    ap.add_argument("--out", default=None, help="write the run JSON here")
    args = ap.parse_args(argv)

    from stratum.services.bu_v2_entrypoint import BU2Runner

    runner = BU2Runner(
        provider=build_provider(args.model),
        persist=args.persist,
        chapter_limit=args.chapters,
        use_ku_anchor=True,
        use_accuracy_judge=not args.no_judge,
        judge_provider=build_provider(args.judge_model) if args.judge_model else None,
    )
    result = runner.execute(args.substrate_id)

    payload = {
        "run_id": result.run_id,
        "substrate_id": result.substrate_id,
        "model": args.model,
        "chapters": len(result.chapters),
        "evidence": len(result.evidence),
        "bu_status": result.bu.status.value if result.bu else None,
        "governing_questions": list(result.bu.governing_questions) if result.bu else [],
        "central_theses": list(result.bu.central_theses) if result.bu else [],
        "concept_count": len((result.bu.concept_system or {}).get("concepts", {}))
        if result.bu
        else 0,
        "concepts_introduced": sum(len(c.concepts_introduced_refs) for c in result.chapters),
        "evidence_with_quote": sum(1 for e in result.evidence if getattr(e, "quote", "")),
        "arguments_complete": getattr(result.p12.get("argument"), "complete_chains", 0)
        if result.p12
        else 0,
        "graph_stats": result.p12["dependency"].graph.stats() if result.p12 else {},
        "hard_gates": result.hard_gates.to_dict() if result.hard_gates else None,
        "claim_verification": result.claim_verification.to_dict()
        if result.claim_verification
        else None,
        "reconstructed_arguments": sum(len(c.arguments_refs) for c in result.chapters),
        "learning_guide_steps": len(result.learning_guide.steps) if result.learning_guide else 0,
        "failures": result.failures,
    }
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0 if (result.bu and result.bu.status.value == "VERIFIED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
