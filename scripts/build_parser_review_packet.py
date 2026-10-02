#!/usr/bin/env python3
"""Build a deterministic human-review packet from parser candidate cases.

The packet contains file identity and a short extracted-text preview.  It never
infers layout, language, structure markers, reviewer identity, or review status;
those fields remain the reviewer's responsibility.

Usage::

    python scripts/build_parser_review_packet.py \
      --manifest /tmp/parser-candidates.json \
      --output /tmp/parser-review-packet.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.eval_parser_benchmark import validate_manifest
except ModuleNotFoundError as error:
    if error.name != "scripts":
        raise
    from eval_parser_benchmark import validate_manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _preview(text: str, limit: int) -> str:
    normalized = " ".join(text.split())
    return normalized[:limit]


def build_review_packet(cases: list[dict[str, Any]], *, preview_chars: int = 800) -> dict[str, Any]:
    """Build review metadata without changing candidate annotations."""
    if preview_chars < 0:
        raise ValueError("preview_chars must be non-negative")

    from stratum.services.pdf_to_markdown import pdf_to_markdown

    packet_cases: list[dict[str, Any]] = []
    for case in cases:
        source = Path(case["path"])
        record: dict[str, Any] = {
            "id": case["id"],
            "path": str(source),
            "source_ref": case.get("source_ref"),
            "review_status": case.get("review_status"),
            "reviewer": case.get("reviewer"),
            "layout": case.get("layout"),
            "language": case.get("language"),
            "structure_elements": case.get("structure_elements", []),
            "required_markers": case.get("required_markers", []),
        }
        if not source.is_file():
            record.update({"availability": "missing", "review_required": True})
            packet_cases.append(record)
            continue

        record.update(
            {
                "availability": "present",
                "bytes": source.stat().st_size,
                "sha256": _sha256(source),
            }
        )
        if source.suffix.lower() == ".pdf":
            extracted_path, parser_name = pdf_to_markdown(source)
            text = (
                extracted_path.read_text(encoding="utf-8", errors="ignore")
                if extracted_path.exists()
                else ""
            )
            record["parser"] = parser_name
        else:
            text = source.read_text(encoding="utf-8", errors="ignore")
            record["parser"] = "source_text"
        record.update(
            {
                "extracted_chars": len(text.strip()),
                "preview": _preview(text, preview_chars),
                "review_required": True,
            }
        )
        packet_cases.append(record)

    return {
        "schema_version": 1,
        "packet_type": "parser_human_review",
        "review_required": True,
        "annotations_unchanged": True,
        "cases": packet_cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--preview-chars", type=int, default=800)
    args = parser.parse_args()

    cases = json.loads(args.manifest.read_text(encoding="utf-8"))
    errors = validate_manifest(cases, min_cases=1)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 2
    try:
        packet = build_review_packet(cases, preview_chars=args.preview_chars)
    except ValueError as error:
        print(f"ERROR: {error}")
        return 2
    args.output.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(packet['cases'])} parser review cases to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
