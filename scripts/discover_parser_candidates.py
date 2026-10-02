#!/usr/bin/env python3
"""Inventory local PDFs as parser-benchmark candidate cases.

This command only inventories real files.  It intentionally does not infer
OmniDocBench labels, required markers, or a reviewer: those fields are emitted
as conservative placeholders and every case is marked ``candidate``.  A human
must annotate the dimensions before the manifest can be used for release
evaluation.

Usage::

    python scripts/discover_parser_candidates.py \
      --root experiments/02-batch/samples/pdf \
      --output /tmp/parser-candidates.json \
      --limit 20
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _case_id(relative_path: str) -> str:
    digest = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]
    return f"local-pdf-{digest}"


def discover_candidates(root: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Return deterministic candidate cases for PDFs below ``root``."""
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"root is not a directory: {root}")
    paths = sorted(path for path in root.rglob("*.pdf") if path.is_file())
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be positive")
        paths = paths[:limit]

    cases: list[dict[str, Any]] = []
    for path in paths:
        relative = path.relative_to(root).as_posix()
        cases.append(
            {
                "id": _case_id(relative),
                "path": str(path),
                "layout": "unknown",
                "language": "unknown",
                "structure_elements": [],
                "required_markers": [],
                "min_chars": 40,
                "source_ref": f"local-file:{root.name}/{relative}",
                "review_status": "candidate",
                "notes": (
                    "Inventory-only candidate. Human review must annotate layout, language, "
                    "structure_elements, required_markers, reviewer, and notes."
                ),
            }
        )
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    cases = discover_candidates(args.root, limit=args.limit)
    args.output.write_text(json.dumps(cases, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(cases)} parser candidate cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
