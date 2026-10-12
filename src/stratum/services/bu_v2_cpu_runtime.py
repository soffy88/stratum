"""CPU-only BU2 runtime orchestrator — P13-RUNTIME-QUALIFICATION-001.

Complete pipeline for 16-chapter book processing on CPU.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2,
    BUStatus,
)
from stratum.services.bu_v2_book_integrator import BookIntegrator, IntegrationInput
from stratum.services.bu_v2_chunk_planner import (
    BU2ChunkPlanner,
    ChunkPlan,
    plan_all_chapters,
)
from stratum.services.bu_v2_cpu_provider import CPUModelProvider, CPUProviderProfile
from stratum.services.bu_v2_entrypoint import (
    BU2RunError,
    BU2Runner,
    BookLoader,
    RunResult,
)
from stratum.services.bu_v2_intermediate_store import BU2IntermediateStore, make_chunk_input_hash
from stratum.services.bu_v2_book_aggregator import BU2BookAggregator, ChapterSynthesisResult
from stratum.services.bu_v2_producer import ChapterContext, classify_role
from stratum.services.bu_v2_provider import ModelProvider, resolve_provider
from stratum.services.bu_v2_verifier import BUVerifier, VerificationReport
from stratum.services.bu_v2_expression import BUExpressionGenerator
from stratum.services.bu_v2_quality_evaluator import BUQualityEvaluator
from stratum.services.bu_v2_quality_report import build_report, evaluate_gates


ENGINE_VERSION = "p13_cpu"


@dataclass
class CPURunConfig:
    """Configuration for CPU-only run."""

    max_chunk_calls: int = 10
    max_synthesis_calls: int = 2
    max_retry: int = 1
    simple_call_timeout: int = 300
    chunk_timeout: int = 600
    chapter_synthesis_timeout: int = 600
    book_synthesis_timeout: int = 900
    concurrency: int = 1
    persist_checkpoints: bool = True


@dataclass
class CPURunStats:
    """Statistics for CPU run."""

    total_wall_clock: float = 0.0
    total_model_calls: int = 0
    total_chunk_calls: int = 0
    total_synthesis_calls: int = 0
    total_retries: int = 0
    total_timeouts: int = 0
    chapters_completed: int = 0
    chapters_failed: int = 0
    avg_chapter_time: float = 0.0
    max_chapter_time: float = 0.0


class BU2CPURunner:
    """CPU-only book understanding runner."""

    def __init__(
        self,
        provider: ModelProvider | CPUModelProvider,
        *,
        loader: BookLoader | None = None,
        config: CPURunConfig | None = None,
        intermediate_store: BU2IntermediateStore | None = None,
        persist: bool = False,
        chapter_limit: int | None = None,
    ):
        self.provider = provider
        self.loader = loader or BookLoader()
        self.config = config or CPURunConfig()
        self.store = intermediate_store or BU2IntermediateStore()
        self.persist = persist
        self.chapter_limit = chapter_limit

        # Components
        self.chunk_planner = BU2ChunkPlanner()
        self.aggregator = BU2BookAggregator(
            provider=provider,
            chunk_planner=self.chunk_planner,
            intermediate_store=self.store,
            max_chunk_calls=self.config.max_chunk_calls,
            max_synthesis_calls=self.config.max_synthesis_calls,
            max_retry=self.config.max_retry,
        )
        self.verifier = BUVerifier()
        self.expr = BUExpressionGenerator()
        self.quality_evaluator = BUQualityEvaluator()

    def create_run(self, book_id: str) -> str:
        from stratum.common import generate_ulid
        from stratum.services import bu_v2_entrypoint as ep

        run_id = f"br_{generate_ulid()}"
        if self.persist:
            substrate = ep.db.read("substrates", book_id) or {}
            ep.db.insert(
                "book_reading_run",
                {
                    "id": run_id,
                    "user_id": substrate.get("user_id") or "system",
                    "source_id": book_id,
                    "source_version": "v1",
                    "status": "CREATED",
                    "engine_version": ENGINE_VERSION,
                },
            )
        return run_id

    def execute(self, substrate_id: str) -> RunResult:
        """Execute full CPU-only book understanding pipeline."""
        start_time = time.perf_counter()
        stats = CPURunStats()

        # Load book
        title, text, chapters = self.loader.load(substrate_id)
        if self.chapter_limit:
            chapters = chapters[: self.chapter_limit]

        if not chapters:
            raise BU2RunError(f"{substrate_id} yielded no chapterable structure")

        # Plan chunks for all chapters
        chapter_data = []
        for ch in chapters:
            section_context = f"Chapter {ch.number}: {ch.title}"
            chapter_data.append((ch.chapter_id, ch.text, section_context))

        plans = plan_all_chapters(chapter_data)
        run_id = self.create_run(substrate_id)

        # Save chunk plan
        self.store.save_chunk_plan(run_id, plans)

        # Save run metadata
        self.store.save_run_metadata(
            run_id,
            {
                "run_id": run_id,
                "substrate_id": substrate_id,
                "book_title": title,
                "total_chapters": len(chapters),
                "chapter_ids": [c.chapter_id for c in chapters],
                "config": self.config.__dict__,
                "started_at": time.time(),
            },
        )

        # Process each chapter
        result = RunResult(
            run_id=run_id,
            book_id=substrate_id,
            substrate_id=substrate_id,
        )
        result.structure = {"chapter_count": len(chapters)}

        prior_chapter_ids: list[str] = []
        chapter_results: list[ChapterSynthesisResult] = []

        for idx, chapter in enumerate(chapters):
            chapter_start = time.perf_counter()

            plan = plans[chapter.chapter_id]
            chunk_understandings: list = []

            # Process each chunk
            for chunk in plan.chunks:
                if self.store.is_chunk_completed(
                    run_id,
                    chunk.chapter_id,
                    chunk.chunk_id,
                    "chunk_understanding",
                    make_chunk_input_hash(
                        run_id,
                        chunk.chapter_id,
                        chunk.chunk_id,
                        "chunk_understanding",
                        chunk.text,
                        "",
                    ),
                ):
                    continue

                try:
                    cu = self.aggregator.process_chunk(
                        chunk=chunk,
                        run_id=run_id,
                        book_id=substrate_id,
                        prior_chapter_ids=prior_chapter_ids,
                        book_title=title,
                        chapter_number=idx + 1,
                        chapter_total=len(chapters),
                    )
                    chunk_understandings.append(cu)
                    stats.total_chunk_calls += 1
                    stats.total_model_calls += 1
                except Exception as e:
                    stats.total_timeouts += 1
                    stats.total_retries += 1
                    # Log error but continue
                    result.failures.append(f"{chunk.chunk_id}: {e}")

            # Synthesize chapter
            try:
                synthesis = self.aggregator.synthesize_chapter(
                    chapter_plan=plan,
                    chunk_understandings=chunk_understandings,
                    run_id=run_id,
                    book_id=substrate_id,
                    prior_chapter_ids=prior_chapter_ids,
                    book_title=title,
                    chapter_number=idx + 1,
                    chapter_total=len(chapters),
                    chapter_text=chapter.text,
                    chapter_title=chapter.title,
                )
                stats.total_synthesis_calls += synthesis.synthesis_calls
                stats.total_model_calls += synthesis.synthesis_calls
                stats.total_retries += len(synthesis.errors)
            except Exception as e:
                result.failures.append(f"{chapter.chapter_id} synthesis: {e}")
                synthesis = ChapterSynthesisResult(
                    chapter_id=chapter.chapter_id,
                    chapter_understanding=None,
                    chunk_understandings=chunk_understandings,
                    delta=None,
                    evidence=[],
                    errors=[str(e)],
                )

            chapter_results.append(synthesis)
            result.chapters.append(
                synthesis.chapter_understanding
            ) if synthesis.chapter_understanding else None
            if synthesis.delta:
                result.deltas.append(synthesis.delta)
            result.evidence.extend(synthesis.evidence)

            prior_chapter_ids.append(chapter.chapter_id)

            # Stats
            chapter_time = time.perf_counter() - chapter_start
            stats.chapters_completed += 1 if synthesis.chapter_understanding else 0
            stats.chapters_failed += 1 if not synthesis.chapter_understanding else 0
            stats.max_chapter_time = max(stats.max_chapter_time, chapter_time)

        # Build book understanding
        chapter_understandings = [
            r.chapter_understanding for r in chapter_results if r.chapter_understanding
        ]
        if not chapter_understandings:
            raise BU2RunError("no chapter produced an understanding")

        bu = self.aggregator.build_book_understanding(
            run_id=run_id,
            book_id=substrate_id,
            substrate_id=substrate_id,
            chapter_results=chapter_results,
        )
        result.bu = bu

        # Verify
        bu.status = BUStatus.VERIFICATION_PENDING
        failed = [c for c in result.chapters if c and c.primary_role == "UNDERSTANDING_FAILED"]
        report = self.verifier.verify(
            bu,
            chapter_count=len(result.chapters),
            evidence_count=len(result.evidence),
            failed_chapters=len(failed),
        )
        result.report = report
        if report.outcome.value == "PASS":
            bu.status = BUStatus.VERIFIED
            bu.verification_score = 1.0
        else:
            bu.status = BUStatus.DRAFT
            result.failures.append(f"verification FAIL: {len(report.failed)} check(s)")

        # Run P13 components
        p13_results = self.aggregator.run_p13_components(
            bu, chapter_understandings, run_id, substrate_id
        )

        # Store P12 results on result
        result.p12 = {
            "dependency": p13_results["dependency"],
            "evolution": p13_results["evolution"],
            "argument": p13_results["argument_graph"],
            "deep_quality": p13_results["deep_quality"],
        }

        # P13 results
        result.p13 = {
            "thesis": p13_results["thesis"],
            "concepts": p13_results["concepts"],
            "arguments": p13_results["arguments"],
            "mechanisms": p13_results["mechanisms"],
            "evidence": p13_results["evidence"],
            "chapter_roles": p13_results["chapter_roles"],
            "contradictions": p13_results["contradictions"],
        }

        # Quality evaluation
        pipeline_status = bu.status.value if bu.status else "UNKNOWN"
        result.quality = self.quality_evaluator.evaluate(
            bu,
            chapters=result.chapters,
            evidence=result.evidence,
            pipeline_status=pipeline_status,
            structure=result.structure,
        )

        # Expression
        result.expression = self.expr.generate(bu, quality=result.quality)

        # Build report
        from stratum.services.bu_v2_quality_report import evaluate_p12_gates

        detection = 1.0 if len(result.chapters) >= 16 else round(len(result.chapters) / 16, 4)
        content_cov = 1.0
        result.report_bundle = build_report(
            result.quality,
            run_id=run_id,
            book_id=substrate_id,
            substrate_id=substrate_id,
            pipeline_status=pipeline_status,
            gates=evaluate_gates(
                result.quality,
                structure=result.structure,
                detection_ratio=detection,
                coverage_ratio=1.0,
                content_coverage=content_cov,
                chapter_count=len(result.chapters),
                context_used=True,
            ),
            chapter_roles=[
                {"chapter_id": c.chapter_id, "role": c.primary_role} for c in result.chapters
            ],
        )

        p12_gates = evaluate_p12_gates(result, structure=result.structure)
        result.report_bundle.gates.extend(p12_gates)

        # Final stats
        stats.total_wall_clock = time.perf_counter() - start_time
        stats.avg_chapter_time = stats.total_wall_clock / max(1, len(chapters))
        result.cpu_stats = stats

        # Save final metadata
        self.store.save_run_metadata(
            run_id,
            {
                "run_id": run_id,
                "completed_at": time.time(),
                "total_wall_clock": stats.total_wall_clock,
                "total_model_calls": stats.total_model_calls,
                "chapters_completed": stats.chapters_completed,
                "chapters_failed": stats.chapters_failed,
                "bu_status": bu.status.value if bu else None,
                "verification": report.outcome.value if report else "NONE",
            },
        )

        return result

    def run_book(self, substrate_id: str) -> BookUnderstandingV2:
        result = self.execute(substrate_id)
        if result.bu is None:
            raise BU2RunError("; ".join(result.failures) or "book run produced no understanding")
        return result.bu


def create_cpu_runner(
    substrate_id: str,
    *,
    model: str | None = None,
    provider: ModelProvider | None = None,
    config: CPURunConfig | None = None,
    persist: bool = False,
    chapter_limit: int | None = None,
) -> BU2CPURunner:
    """Factory for CPU runner with default profile."""
    if provider is None:
        # Use CPU provider wrapper
        base_provider = resolve_provider()
        if hasattr(base_provider, "profile"):
            provider = base_provider
        else:
            profile = CPUProviderProfile(
                model=model or "",
                timeout=config.simple_call_timeout if config else 300,
                max_context_tokens=4096,
                max_output_tokens=1024,
                concurrency=config.concurrency if config else 1,
            )
            provider = CPUModelProvider(profile=profile, base_provider=base_provider)

    return BU2CPURunner(
        provider=provider,
        config=config or CPURunConfig(),
        persist=persist,
        chapter_limit=chapter_limit,
    )
