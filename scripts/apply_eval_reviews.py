#!/usr/bin/env python3
"""Apply explicit human review decisions to a copied eval manifest.

The source manifest is never modified. By default every source case must have
exactly one reviewed decision; ``--allow-partial`` is available only for local
preparation and leaves undecided cases in ``candidate`` status.

Parser review decision::

    {"id": "case-1", "reviewer": "alice", "review_status": "reviewed",
     "layout": "single_column", "language": "en",
     "structure_elements": ["heading"], "required_markers": ["Results"]}

Retrieval review decision::

    {"query_id": "q-1", "reviewer": "alice", "review_status": "reviewed",
     "relevant_substrate_ids": ["substrate-1"], "rationale": "..."}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal

try:
    from scripts.eval_parser_benchmark import validate_manifest
    from scripts.eval_retrieval import validate_golden_set
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from eval_parser_benchmark import validate_manifest
    from eval_retrieval import validate_golden_set

Kind = Literal["parser", "retrieval"]


def _key(case: dict[str, Any], kind: Kind) -> str:
    if kind == "parser":
        return str(case.get("id", ""))
    return str(case.get("query_id") or f"query:{case.get('query', '')}")


def _review_map(reviews: object, kind: Kind) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(reviews, list):
        return {}, ["review decisions must be a JSON array"]
    mapped: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for index, review in enumerate(reviews):
        if not isinstance(review, dict):
            errors.append(f"review[{index}] must be an object")
            continue
        key = _key(review, kind)
        if not key or key.endswith("query:"):
            errors.append(
                f"review[{index}] is missing its {'id' if kind == 'parser' else 'query_id/query'}"
            )
            continue
        if key in mapped:
            errors.append(f"review[{index}] duplicates case {key}")
            continue
        mapped[key] = review
    return mapped, errors


def _review_common(review: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    if review.get("review_status") != "reviewed":
        errors.append(f"{prefix}.review_status must be 'reviewed'")
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        errors.append(f"{prefix}.reviewer must be a non-empty string")
    return errors


def apply_reviews(
    manifest: object,
    reviews: object,
    *,
    kind: Kind,
    allow_partial: bool = False,
) -> list[dict[str, Any]]:
    """Return a new manifest with only explicit review decisions applied."""
    if not isinstance(manifest, list):
        raise ValueError("source manifest must be a JSON array")
    if kind == "parser":
        source_errors = validate_manifest(manifest, min_cases=1)
    else:
        source_errors = validate_golden_set(manifest, min_queries=1)
    if source_errors:
        raise ValueError("source manifest is invalid: " + "; ".join(source_errors))
    review_map, errors = _review_map(reviews, kind)
    if errors:
        raise ValueError("; ".join(errors))

    cases = [dict(case) for case in manifest]
    source_keys = {_key(case, kind) for case in cases}
    unknown = sorted(set(review_map) - source_keys)
    if unknown:
        raise ValueError(f"review contains unknown case(s): {', '.join(unknown)}")
    missing = sorted(source_keys - set(review_map))
    if missing and not allow_partial:
        raise ValueError(f"review is missing case(s): {', '.join(missing)}")

    result: list[dict[str, Any]] = []
    for case in cases:
        review = review_map.get(_key(case, kind))
        if review is None:
            result.append(case)
            continue
        errors = _review_common(review, f"review[{_key(case, kind)}]")
        if kind == "parser":
            required = ("layout", "language", "structure_elements", "required_markers")
            errors.extend(
                f"review[{_key(case, kind)}].{field} is required"
                for field in required
                if field not in review
            )
            allowed = (
                "layout",
                "language",
                "structure_elements",
                "required_markers",
                "source_ref",
                "reviewer",
                "review_status",
                "notes",
            )
        else:
            if "relevant_substrate_ids" not in review:
                errors.append(f"review[{_key(case, kind)}].relevant_substrate_ids is required")
            if not isinstance(review.get("rationale"), str) or not review["rationale"].strip():
                errors.append(f"review[{_key(case, kind)}].rationale must be a non-empty string")
            allowed = (
                "relevant_substrate_ids",
                "source_ref",
                "reviewer",
                "review_status",
                "rationale",
            )
        if errors:
            raise ValueError("; ".join(errors))
        updated = dict(case)
        updated.update({field: review[field] for field in allowed if field in review})
        result.append(updated)

    if kind == "parser":
        errors = validate_manifest(result, min_cases=1, require_provenance=not allow_partial)
    else:
        errors = validate_golden_set(result, min_queries=1, require_provenance=not allow_partial)
    if errors:
        raise ValueError("; ".join(errors))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("parser", "retrieval"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--reviews", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        reviews = json.loads(args.reviews.read_text(encoding="utf-8"))
        result = apply_reviews(manifest, reviews, kind=args.kind, allow_partial=args.allow_partial)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 2
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(result)} reviewed eval records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
