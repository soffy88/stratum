"""Benchmark the canonical omodul/oprim PDF parser over 30 real PDFs.

The production HTTP smoke covers persistence.  This benchmark measures the
canonical parser stage across the full corpus without writing synthetic rows
to PostgreSQL: fragments and anchors are derived in memory from the parser's
own markdown output, then the production projection is checked separately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "experiments/02-batch/samples/pdf"
BOOKS_DIR = Path("/data/soffy/books")
SAMPLES = [
    SAMPLE_DIR / name
    for name in (
        "S1-chinese-novel-history.pdf",
        "S2-marchenko-pastur-1998.pdf",
        "S3-real-analysis-notes.pdf",
        "S4-attention-is-all-you-need.pdf",
        "S5-pride-and-prejudice.pdf",
    )
]


def select_documents() -> list[Path]:
    selected = [path for path in SAMPLES if path.is_file() and path.stat().st_size > 0]
    seen = {path.resolve() for path in selected}
    candidates = sorted(
        (
            path
            for path in BOOKS_DIR.rglob("*.pdf")
            if path.is_file() and path.stat().st_size > 10_240 and path.resolve() not in seen
        ),
        key=lambda path: (path.stat().st_size, str(path)),
    )
    selected.extend(candidates[: max(0, 30 - len(selected))])
    if len(selected) != 30:
        raise RuntimeError(f"expected 30 real PDFs, selected {len(selected)}")
    return selected


def _parse(path: Path) -> tuple[str, int, int, float]:
    from omodul.process_inbox_substrate import _stage_parse
    from oprim.document_structure_extractor import document_structure_extractor

    started = time.perf_counter()
    parsed = _stage_parse(path, "application/pdf")
    pages = getattr(parsed, "pages", [])
    content = "\n\n".join(getattr(page, "text", "") or "" for page in pages).strip()
    structure = document_structure_extractor(parsed_doc=parsed)
    return content, len(pages), len(structure.headings), time.perf_counter() - started


def _fragment_metrics(content: str) -> dict:
    from oprim import structural_chunk

    raw = structural_chunk(text=content, min_chars=500, max_chars=2000) or []
    def locate(text: str) -> tuple[int, int, str]:
        start = content.find(text)
        status = "exact"
        if start < 0:
            compact_content = re.sub(r"\s+", " ", content)
            compact_text = re.sub(r"\s+", " ", text).strip()
            offset = compact_content.find(compact_text)
            if offset >= 0:
                start = min(len(content), int(offset * len(content) / max(len(compact_content), 1)))
                status = "normalized"
        if start < 0:
            prefix = text[:80]
            start = content.find(prefix)
            status = "approx" if start >= 0 else "unresolved"
        return start, start + len(text) if start >= 0 else -1, status

    fragments = []
    for item in raw:
        text = item.get("content", "") if isinstance(item, dict) else str(item)
        if not text or not text.strip():
            continue
        start, end, status = locate(text)
        fragments.append(
            {
                "text": text,
                "start_pos": start,
                "end_pos": min(len(content), end) if end >= 0 else -1,
                "anchor_status": status,
                "traceable": status == "exact",
                "resolvable": status != "unresolved",
            }
        )
    starts = [item["start_pos"] for item in fragments]
    valid = [
        item
        for item in fragments
        if item["resolvable"] and 0 <= item["start_pos"] < item["end_pos"] <= len(content)
    ]
    return {
        "fragment_count": len(fragments),
        "anchor_count": len(valid),
        "ordering_valid": [item["start_pos"] for item in valid] == sorted(item["start_pos"] for item in valid)
        and len(valid) == len(fragments),
        "quote_fidelity": sum(item["traceable"] for item in fragments) / len(fragments) if fragments else 0.0,
        "fragments": fragments,
    }


def main(output: Path) -> int:
    documents = select_documents()
    records = []
    for index, path in enumerate(documents, 1):
        record = {
            "case_id": f"parser-{index:02d}",
            "filename": str(path),
            "format": "pdf",
            "language": "zh" if re.search(r"[\u3400-\u9fff]", path.name) else "en/mixed",
        }
        try:
            content, pages, headings, elapsed = _parse(path)
            metrics = _fragment_metrics(content)
            record.update(
                {
                    "parse_success": True,
                    "pages": pages,
                    "headings": headings,
                    "content_chars": len(content),
                    "content_nonempty": bool(content),
                    "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "elapsed_sec": round(elapsed, 3),
                    "fragments": metrics["fragment_count"],
                    "anchors": metrics["anchor_count"],
                    "ordering_valid": metrics["ordering_valid"],
                    "quote_fidelity": metrics["quote_fidelity"],
                    "table_candidate": bool(re.search(r"(?:^|\n)\s*\|.+\|", content)),
                    "code_candidate": "```" in content or bool(re.search(r"\n\s{4}\S", content)),
                }
            )
        except Exception as exc:
            record.update({"parse_success": False, "exception": f"{type(exc).__name__}: {exc}"})
        records.append(record)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    first = documents[0]
    try:
        first_a = _parse(first)[0]
        first_b = _parse(first)[0]
        hash_stability = {
            "pass": hashlib.sha256(first_a.encode()).hexdigest() == hashlib.sha256(first_b.encode()).hexdigest(),
            "first_sha256": hashlib.sha256(first_a.encode()).hexdigest(),
            "second_sha256": hashlib.sha256(first_b.encode()).hexdigest(),
        }
    except Exception as exc:
        hash_stability = {"pass": False, "exception": f"{type(exc).__name__}: {exc}"}

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "benchmark": "AII FINAL PRODUCT QUALITY CLOSURE parser stage",
                "entrypoint": "omodul.process_inbox_substrate._stage_parse -> oprim.file_parser_pdf",
                "documents_total": len(records),
                "records": records,
                "hash_stability": hash_stability,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    raise SystemExit(main(parser.parse_args().output))
