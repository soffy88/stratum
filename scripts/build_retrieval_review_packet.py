#!/usr/bin/env python3
"""Build a deterministic human-review packet from retrieval gold candidates.

The packet makes proposed substrate mappings easy to inspect while keeping
their candidate status explicit. It never confirms relevance, invents a
reviewer, or changes the source manifest.

Usage::

    python scripts/build_retrieval_review_packet.py \
      --manifest /tmp/retrieval-gold-candidate.json \
      --output /tmp/retrieval-review-packet.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.eval_retrieval import validate_golden_set
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from eval_retrieval import validate_golden_set


def build_review_packet(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a review packet without modifying candidate mappings."""
    packet_cases = [
        {
            "query_id": case.get("query_id"),
            "query": case["query"],
            "source_ref": case.get("source_ref"),
            "reviewer": case.get("reviewer"),
            "review_status": case.get("review_status"),
            "rationale": case.get("rationale"),
            "proposed_relevant_substrate_ids": list(case["relevant_substrate_ids"]),
            "mapping_review_required": True,
        }
        for case in cases
    ]
    return {
        "schema_version": 1,
        "packet_type": "retrieval_human_review",
        "review_required": True,
        "annotations_unchanged": True,
        "cases": packet_cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    cases = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = validate_golden_set(cases, min_queries=1)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2
    packet = build_review_packet(cases)
    args.output.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(packet['cases'])} retrieval review cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
