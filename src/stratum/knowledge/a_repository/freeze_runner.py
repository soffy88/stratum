"""A Repository P1 — frozen baseline runner.

Executes the Chapter 1 ingestion chain deterministically against an
in-memory store (no DB mutation) and emits the inventory for the freeze.

Run: python -m stratum.knowledge.a_repository.freeze_runner
"""

from __future__ import annotations

import json
from typing import Dict, List

from . import pilot_corpus as C
from .ingestion import (
    AIngestionPipeline,
    InMemoryAStore,
    ReadingRun,
    deterministic_id,
)


def build_baseline() -> Dict:
    """Run the full Chapter 1 chain with deterministic IDs."""
    store = InMemoryAStore()
    p = AIngestionPipeline(store)

    # Stage 1: register
    bs_id = deterministic_id("bs", C.BOOK_ISBN, C.BOOK_TITLE)
    from .ingestion import BookSource
    bs = BookSource(
        id=bs_id,
        title=C.BOOK_TITLE,
        author=C.BOOK_AUTHOR,
        publisher=C.BOOK_PUBLISHER,
        isbn=C.BOOK_ISBN,
        language=C.BOOK_LANGUAGE,
        metadata={"edition": C.BOOK_EDITION, "translator": C.BOOK_TRANSLATOR},
    )
    store.book_sources[bs.id] = bs

    # Stage 2: snapshot (deterministic checksum; replay-safe)
    sv_id = deterministic_id("sv", C.CHECKSUM, C.FILE_VERSION)
    p.snapshot(
        book_source_id=bs.id,
        version=C.FILE_VERSION,
        file_hash=C.CHECKSUM,
        fmt=C.SOURCE_FORMAT,
        page_count=C.FULL_PAGE_COUNT,
        storage_uri=C.STORAGE_URI,
        version_id=sv_id,
    )

    # Stage 3: structure parse (no content understanding)
    structure = p.parse_structure(sv_id, C.CHAPTER, C.SECTIONS)

    # Stage 4: reading run
    run_id = deterministic_id("arr", sv_id, C.CHAPTER)
    run = ReadingRun(id=run_id, source_version_id=sv_id, status="CREATED")
    store.reading_runs[run.id] = run
    p.transition_run(run.id, "SNAPSHOTTED")
    p.transition_run(run.id, "READING")

    # Stage 5: evidence extraction (idempotent on replay)
    evidence_ids: Dict[str, str] = {}
    for item in C.EVIDENCE:
        if p.has_evidence(run.id, item["page_number"], item["content_span"]):
            continue
        ev = p.extract_evidence(
            reading_run_id=run.id,
            source_version_id=sv_id,
            page_number=item["page_number"],
            locator={
                "page": item["page_number"],
                "section": item["section"],
                "chapter": C.CHAPTER,
            },
            content_span=item["content_span"],
            extractor_version=item["extractor_version"],
            evidence_id=deterministic_id(
                "ev", run.id, str(item["page_number"]), item["content_span"]),
        )
        evidence_ids[item["key"]] = ev.id

    # Stage 6: KU candidate extraction (no dedup/merge/abstraction)
    candidate_ids: Dict[str, str] = {}
    for item in C.KU_CANDIDATES:
        ev_id = evidence_ids[item["evidence_key"]]
        if p.has_candidate(run.id, ev_id, item["source_span"]):
            continue
        kc = p.generate_candidate(
            reading_run_id=run.id,
            evidence_id=ev_id,
            content=item["content"],
            candidate_type=item["candidate_type"],
            confidence=item["confidence"],
            source_span=item["source_span"],
            candidate_id=deterministic_id(
                "kc", run.id, ev_id, item["source_span"]),
        )
        candidate_ids[item["key"]] = kc.id

    return {
        "store": store,
        "pipeline": p,
        "book_source": bs,
        "source_version_id": sv_id,
        "reading_run_id": run.id,
        "structure": structure,
        "evidence_ids": evidence_ids,
        "candidate_ids": candidate_ids,
    }


def inventory(result: Dict) -> Dict:
    p: AIngestionPipeline = result["pipeline"]
    store: InMemoryAStore = result["store"]
    run_id = result["reading_run_id"]
    return {
        "book_source": {
            "id": result["book_source"].id,
            "title": result["book_source"].title,
            "isbn": result["book_source"].isbn,
        },
        "source_version": {
            "id": result["source_version_id"],
            "checksum": C.CHECKSUM,
            "version": C.FILE_VERSION,
            "format": C.SOURCE_FORMAT,
            "page_count": C.FULL_PAGE_COUNT,
        },
        "reading_run": {
            "id": run_id,
            "status": store.reading_runs[run_id].status,
        },
        "evidence_count": p.evidence_count(run_id),
        "ku_candidate_count": p.candidate_count(run_id),
        "page_coverage": p.page_coverage(run_id, C.CHAPTER_PAGE_COUNT),
        "orphan_evidence": p.orphan_evidence(),
        "orphan_candidates": p.orphan_candidates(),
        "evidence_ids": dict(sorted(result["evidence_ids"].items())),
        "candidate_ids": dict(sorted(result["candidate_ids"].items())),
    }


def main() -> None:
    result = build_baseline()
    inv = inventory(result)
    print(json.dumps(inv, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()