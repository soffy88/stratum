#!/usr/bin/env python3
"""Convert the legacy AII retrieval question set into the Stratum schema.

The legacy file at ``aii/scripts/eval/golden.json`` contains curated questions
and substrate/KU identifiers, but it predates the current provenance contract.
This importer preserves those references and deliberately emits
``review_status=candidate``.  It never invents a reviewer and therefore cannot
make the release gate pass by itself.

Usage::

    python scripts/import_legacy_retrieval_gold.py \
      --input aii/scripts/eval/golden.json \
      --output /tmp/retrieval-gold-candidate.json

Human reviewers must verify each substrate mapping, add a real reviewer and
rationale, then change the status to ``reviewed`` before release evaluation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def convert_legacy_gold(legacy: object, *, source_name: str) -> list[dict[str, Any]]:
    """Convert legacy rows into candidate records without losing provenance."""
    if not isinstance(legacy, list):
        raise ValueError("legacy retrieval gold must be a JSON array")

    converted: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    for index, row in enumerate(legacy):
        if not isinstance(row, dict):
            raise ValueError(f"legacy item[{index}] must be an object")
        query = row.get("query")
        substrate_id = row.get("substrate_id")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"legacy item[{index}].query must be non-empty")
        if query.strip() in seen_queries:
            raise ValueError(f"legacy item[{index}].query is duplicated")
        seen_queries.add(query.strip())
        if not isinstance(substrate_id, str) or not substrate_id.strip():
            raise ValueError(f"legacy item[{index}].substrate_id must be non-empty")

        gold_ku_id = row.get("gold_ku_id")
        source_ref = f"{source_name}#item-{index}"
        if isinstance(gold_ku_id, str) and gold_ku_id.strip():
            source_ref = f"{source_ref};gold_ku_id={gold_ku_id.strip()}"
        converted.append(
            {
                "query_id": f"legacy-aii-{index + 1:03d}",
                "query": query.strip(),
                "relevant_substrate_ids": [substrate_id.strip()],
                "source_ref": source_ref,
                "review_status": "candidate",
                "rationale": (
                    "Imported from the legacy AII evaluation set; verify the substrate "
                    "mapping and annotate a human reviewer before release."
                ),
            }
        )
    return converted


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    legacy = json.loads(args.input.read_text(encoding="utf-8"))
    converted = convert_legacy_gold(legacy, source_name=str(args.input))
    args.output.write_text(
        json.dumps(converted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(converted)} candidate retrieval records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
