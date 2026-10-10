"""P14: Cross-Book Intelligence Entrypoint.

Orchestrates the complete cross-book intelligence pipeline.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2,
    BookSynthesis,
    CrossBookCollection,
    CrossBookUnderstanding,
)
from stratum.services.bu_v2_crossbook_collection import BU2CrossBookCollectionManager
from stratum.services.bu_v2_crossbook_concepts import BU2CrossBookConceptAligner
from stratum.services.bu_v2_crossbook_thesis import BU2CrossBookThesisComparator
from stratum.services.bu_v2_crossbook_arguments import BU2CrossBookArgumentComparator
from stratum.services.bu_v2_crossbook_mechanisms import BU2CrossBookMechanismComparator
from stratum.services.bu_v2_crossbook_evidence import BU2CrossBookEvidenceComparator
from stratum.services.bu_v2_crossbook_contradictions import BU2CrossBookContradictionDetector
from stratum.services.bu_v2_crossbook_problems import BU2CrossBookProblemAligner
from stratum.services.bu_v2_crossbook_gaps import BU2CrossBookGapDetector
from stratum.services.bu_v2_crossbook_synthesis import BU2CrossBookSynthesisBuilder
from stratum.services.bu_v2_crossbook_query import BU2CrossBookQueryBuilder
from stratum.services.bu_v2_crossbook_expression import BU2CrossBookExpressionGenerator


ENGINE_VERSION = "p14"


@dataclass
class P14RunResult:
    """Result of a P14 cross-book run."""

    run_id: str
    collection: CrossBookCollection
    understanding: CrossBookUnderstanding | None = None
    expression: Any = None
    persisted: bool = False
    failures: list[str] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


class BU2P14Runner:
    """P14 Cross-Book Intelligence Runner."""

    def __init__(
        self,
        *,
        db_read_func=None,
        persist: bool = False,
        user_id: str = "",
        use_db: bool | None = None,
    ):
        self.persist = persist
        self.user_id = user_id
        # Without an injected reader the runner loads from the database
        # (BU2 + P13 synthesis per book); tests inject books directly.
        self.use_db = (db_read_func is None) if use_db is None else use_db
        self.notes: list[str] = []
        self.collection_manager = BU2CrossBookCollectionManager(db_read_func=db_read_func)
        self.concept_aligner = BU2CrossBookConceptAligner()
        self.thesis_comparator = BU2CrossBookThesisComparator()
        self.argument_comparator = BU2CrossBookArgumentComparator()
        self.mechanism_comparator = BU2CrossBookMechanismComparator()
        self.evidence_comparator = BU2CrossBookEvidenceComparator()
        self.contradiction_detector = BU2CrossBookContradictionDetector()
        self.problem_aligner = BU2CrossBookProblemAligner()
        self.gap_detector = BU2CrossBookGapDetector()
        self.synthesis_builder = BU2CrossBookSynthesisBuilder()
        self.query_builder = BU2CrossBookQueryBuilder
        self.expr_generator = BU2CrossBookExpressionGenerator()

    def create_run(self, collection_id: str) -> str:
        """Create a new P14 run."""
        from stratum.common import generate_ulid

        run_id = f"cb_{generate_ulid()}"
        if self.persist:
            # Would persist to DB here
            pass
        return run_id

    def execute(
        self,
        collection: CrossBookCollection,
        books: list[tuple[BookUnderstandingV2, BookSynthesis]] | None = None,
    ) -> P14RunResult:
        """Execute the full P14 cross-book intelligence pipeline.

        Args:
            collection: CrossBookCollection defining the book set
            books: Optional pre-loaded (BU, Synthesis) pairs. If None, loads from DB.

        Returns:
            P14RunResult with the complete CrossBookUnderstanding
        """
        start_time = time.perf_counter()
        stats: dict[str, Any] = {"stages": {}}
        failures = []

        run_id = self.create_run(collection.collection_id)

        # Load books if not provided
        if books is None and self.use_db and not self.collection_manager.db_read:
            from stratum.services.bu_v2_p14_loader import load_book_pair

            books = []
            if len(set(collection.book_ids)) < len(collection.book_ids):
                failures.append("Collection lists the same book more than once")
            for book_id in dict.fromkeys(collection.book_ids):
                try:
                    bu, synth, note = load_book_pair(book_id, persist=self.persist)
                except Exception as exc:  # surface, never hide, DB/model errors
                    bu, synth, note = None, None, f"Book {book_id}: load failed: {exc}"
                self.notes.append(note)
                if bu and synth:
                    books.append((bu, synth))
                else:
                    failures.append(note)
            stats["load_notes"] = list(self.notes)
        elif books is None:
            books = []
            for book_id in collection.book_ids:
                bu = self.collection_manager._get_book_understanding(book_id)
                synth = self.collection_manager._get_book_synthesis(book_id)
                if bu and synth:
                    books.append((bu, synth))
                else:
                    failures.append(f"Book {book_id}: missing BU or Synthesis")

            # Validate collection only when loading from DB
            validation = self.collection_manager.validate_collection(collection)
            if not validation.valid:
                failures.extend(validation.errors)

        if len(books) < 2:
            failures.append("Need at least 2 valid books for cross-book analysis")

        if failures:
            return P14RunResult(
                run_id=run_id,
                collection=collection,
                persisted=False,
                failures=failures,
                stats=stats,
            )

        # Stage 1: Concept Alignment
        stage_start = time.perf_counter()
        concept_result = self.concept_aligner.align(books)
        stats["stages"]["concept_alignment"] = time.perf_counter() - stage_start

        # Stage 2: Thesis Comparison
        stage_start = time.perf_counter()
        thesis_result = self.thesis_comparator.compare(books)
        stats["stages"]["thesis_comparison"] = time.perf_counter() - stage_start

        # Stage 3: Argument Comparison
        stage_start = time.perf_counter()
        argument_result = self.argument_comparator.compare(books)
        stats["stages"]["argument_comparison"] = time.perf_counter() - stage_start

        # Stage 4: Mechanism Comparison
        stage_start = time.perf_counter()
        mechanism_result = self.mechanism_comparator.compare(books)
        stats["stages"]["mechanism_comparison"] = time.perf_counter() - stage_start

        # Stage 5: Evidence Comparison
        stage_start = time.perf_counter()
        evidence_result = self.evidence_comparator.compare(books)
        stats["stages"]["evidence_comparison"] = time.perf_counter() - stage_start

        # Stage 6: Contradiction Detection
        stage_start = time.perf_counter()
        contradiction_result = self.contradiction_detector.detect(books)
        stats["stages"]["contradiction_detection"] = time.perf_counter() - stage_start

        # Stage 7: Problem Alignment
        stage_start = time.perf_counter()
        problem_result = self.problem_aligner.align(books)
        stats["stages"]["problem_alignment"] = time.perf_counter() - stage_start

        # Stage 8: Knowledge Gap Detection
        stage_start = time.perf_counter()
        gap_result = self.gap_detector.detect(books)
        stats["stages"]["gap_detection"] = time.perf_counter() - stage_start

        # Stage 9: Synthesis
        stage_start = time.perf_counter()
        understanding = self.synthesis_builder.build(
            collection=collection,
            books=books,
            concept_result=concept_result,
            thesis_result=thesis_result,
            argument_result=argument_result,
            mechanism_result=mechanism_result,
            evidence_result=evidence_result,
            contradiction_result=contradiction_result,
            problem_result=problem_result,
            gap_result=gap_result,
            comparison_results=[],  # Built inside synthesis_builder
        )
        stats["stages"]["synthesis"] = time.perf_counter() - stage_start

        # Generate expression
        expression = self.expr_generator.generate(understanding)

        stats["total_wall_clock"] = time.perf_counter() - start_time
        stats["books_processed"] = len(books)
        stats["concept_relations"] = len(concept_result.concept_relations)
        stats["thesis_relations"] = len(thesis_result.thesis_relations)
        stats["argument_relations"] = len(argument_result.argument_relations)
        stats["mechanism_relations"] = len(mechanism_result.mechanism_relations)
        stats["evidence_relations"] = len(evidence_result.evidence_relations)
        stats["contradictions"] = len(contradiction_result.contradictions)
        stats["knowledge_gaps"] = len(gap_result.knowledge_gaps)

        persisted = False
        if self.persist:
            from stratum.services.bu_v2_p14_loader import save_collection, save_understanding

            if self.user_id:
                save_collection(collection, self.user_id)
            save_understanding(understanding)
            persisted = True

        return P14RunResult(
            run_id=run_id,
            collection=collection,
            understanding=understanding,
            expression=expression,
            persisted=persisted,
            failures=failures,
            stats=stats,
        )


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m stratum.services.bu_v2_crossbook_entrypoint <collection_json>"""
    import argparse

    parser = argparse.ArgumentParser(
        prog="bu2-p14", description="Run P14 cross-book intelligence on a collection"
    )
    parser.add_argument("collection", nargs="?", help="JSON file with collection definition")
    parser.add_argument(
        "--books", nargs="+", default=None, help="substrate ids, instead of a JSON file"
    )
    parser.add_argument("--name", default="", help="collection name when using --books")
    parser.add_argument("--user-id", default="", help="owner for the persisted collection")
    parser.add_argument("--persist", action="store_true", help="write to database")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    args = parser.parse_args(argv)

    if args.books:
        collection_data = {
            "name": args.name or "P14 " + " + ".join(args.books),
            "description": "CLI collection",
            "book_ids": args.books,
        }
    elif args.collection:
        with open(args.collection) as f:
            collection_data = json.load(f)
    else:
        parser.error("give a collection JSON file or --books")

    from stratum.services.bu_v2_p14_loader import collection_from_row

    collection = collection_from_row(collection_data)

    user_id = args.user_id
    if args.persist and not user_id:
        from stratum.db import query

        rows = (
            query(
                "SELECT user_id FROM stratum.substrates WHERE id = %(b)s LIMIT 1",
                {"b": collection.book_ids[0]},
            )
            if collection.book_ids
            else []
        )
        user_id = rows[0]["user_id"] if rows else ""

    runner = BU2P14Runner(persist=args.persist, user_id=user_id)
    result = runner.execute(collection)

    if args.json:
        print(
            json.dumps(
                {
                    "run_id": result.run_id,
                    "collection_id": result.collection.collection_id,
                    "books_processed": result.stats.get("books_processed", 0),
                    "concept_relations": result.stats.get("concept_relations", 0),
                    "thesis_relations": result.stats.get("thesis_relations", 0),
                    "argument_relations": result.stats.get("argument_relations", 0),
                    "mechanism_relations": result.stats.get("mechanism_relations", 0),
                    "evidence_relations": result.stats.get("evidence_relations", 0),
                    "contradictions": result.stats.get("contradictions", 0),
                    "knowledge_gaps": result.stats.get("knowledge_gaps", 0),
                    "failures": result.failures,
                    "persisted": result.persisted,
                    "stats": result.stats,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        if result.expression:
            print(result.expression.render())
        print(f"\nrun_id={result.run_id}")
        print(f"books={result.stats.get('books_processed', 0)}")
        print(f"concept_relations={result.stats.get('concept_relations', 0)}")
        print(f"thesis_relations={result.stats.get('thesis_relations', 0)}")
        print(f"argument_relations={result.stats.get('argument_relations', 0)}")
        print(f"contradictions={result.stats.get('contradictions', 0)}")
        print(f"knowledge_gaps={result.stats.get('knowledge_gaps', 0)}")
        print(f"wall_clock={result.stats.get('total_wall_clock', 0):.2f}s")
        for f in result.failures:
            print(f"  ! {f}")

    return 0 if result.understanding else 1


if __name__ == "__main__":
    raise SystemExit(main())
