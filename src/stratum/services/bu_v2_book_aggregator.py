"""CPU-only book aggregator — P13-RUNTIME-QUALIFICATION-001 §9, §15, §22-§23.

Aggregates chunk-level understanding into chapter understanding,
then runs P13 book-level components in staged execution.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2,
    BUStatus,
    ChapterDelta,
    ChapterUnderstanding,
    EvidenceProgramItem,
)
from stratum.services.bu_v2_book_integrator import BookIntegrator, IntegrationInput
from stratum.services.bu_v2_chunk_planner import SemanticChunk, ChunkPlan
from stratum.services.bu_v2_cpu_provider import CPUModelProvider
from stratum.services.bu_v2_intermediate_store import BU2IntermediateStore
from stratum.services.bu_v2_producer import (
    Chapter,
    ChapterContext,
    ChapterRole,
    ChapterUnderstandingProducer,
    EvidenceArtifact,
    classify_role,
)
from stratum.services.bu_v2_provider import ModelProvider
from stratum.services.bu_v2_reasoning_graph import BookReasoningGraph
from stratum.services.bu_v2_verifier import BUVerifier


@dataclass
class ChunkUnderstanding:
    """Understanding extracted from one chunk."""

    chunk_id: str
    chapter_id: str
    concepts: list[dict] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    mechanisms: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    uncertainties: list[str] = field(default_factory=list)
    terminology: list[dict] = field(default_factory=list)
    raw_response: str = ""


@dataclass
class ChapterSynthesisResult:
    """Complete chapter understanding after aggregating chunks."""

    chapter_id: str
    chapter_understanding: ChapterUnderstanding | None
    chunk_understandings: list[ChunkUnderstanding]
    delta: ChapterDelta | None
    evidence: list[EvidenceArtifact]
    synthesis_calls: int = 0
    chunk_calls: int = 0
    errors: list[str] = field(default_factory=list)


class BU2BookAggregator:
    """Aggregates chunks → chapters → book, runs P13 components."""

    def __init__(
        self,
        provider: ModelProvider,
        *,
        chunk_planner: "BU2ChunkPlanner",
        intermediate_store: BU2IntermediateStore,
        max_chunk_calls: int = 10,
        max_synthesis_calls: int = 2,
        max_retry: int = 1,
    ):
        self.provider = provider
        self.chunk_planner = chunk_planner
        self.store = intermediate_store
        self.max_chunk_calls = max_chunk_calls
        self.max_synthesis_calls = max_synthesis_calls
        self.max_retry = max_retry

        # Reuse existing P10/P11 components
        self.chapter_producer = ChapterUnderstandingProducer(provider=provider)
        self.book_integrator = BookIntegrator(provider=provider)
        self.verifier = BUVerifier()

    def _hash(self, *parts: str) -> str:
        raw = "|".join(p for p in parts if p)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ── Stage A: Chunk-level understanding ──

    def process_chunk(
        self,
        chunk: SemanticChunk,
        run_id: str,
        book_id: str,
        prior_chapter_ids: list[str],
        book_title: str,
        chapter_number: int,
        chapter_total: int,
    ) -> ChunkUnderstanding:
        """Process one chunk with bounded LLM call — §8."""

        input_hash = self._hash(
            run_id, chunk.chapter_id, chunk.chunk_id, "chunk_understanding", chunk.text
        )

        # Check checkpoint
        if self.store.is_chunk_completed(
            run_id, chunk.chapter_id, chunk.chunk_id, "chunk_understanding", input_hash
        ):
            checkpoint = self.store.load_chunk_checkpoint(
                run_id, chunk.chapter_id, chunk.chunk_id, "chunk_understanding"
            )
            return ChunkUnderstanding(**checkpoint.output_data)

        # Build context
        context = ChapterContext(
            book_title=book_title,
            chapter_number=chapter_number,
            chapter_total=chapter_total,
            previous_chapter_titles=prior_chapter_ids[-3:],
            previous_concepts=[],
            following_expectations=f"chunk {chunk.sequence} of chapter {chunk.chapter_id}",
            position_ratio=round(chunk.sequence / max(1, len(prior_chapter_ids) + 1), 3),
        )

        # Create chapter-like object for producer
        chapter_obj = Chapter(
            chapter_id=chunk.chunk_id,
            number=chunk.sequence,
            title=f"{chunk.chapter_id} chunk {chunk.sequence}",
            text=chunk.text,
            start=chunk.start_offset,
            end=chunk.end_offset,
            context=context,
            role=ChapterRole.CONCEPT_BUILDING,
        )

        # Generate understanding for this chunk
        # Use a reduced schema for chunk-level extraction
        schema = self._chunk_schema_hint()
        prompt = (
            f"{context.render()}\n\n"
            f"CHUNK: {chunk.chunk_id}\n"
            f"SECTION CONTEXT: {chunk.section_context}\n\n"
            f"CHUNK TEXT:\n{chunk.text}\n\n"
            f"Extract concepts, claims, mechanisms, evidence, uncertainties, terminology.\n"
            f"Respond with exactly this JSON shape:\n{schema}"
        )

        _SYSTEM = "You extract textbook structure from a chapter chunk. Output ONLY JSON."

        for attempt in range(self.max_retry + 1):
            try:
                resp = self.provider.complete(
                    prompt,
                    system=_SYSTEM,
                    json_mode=True,
                    max_tokens=800,
                    temperature=0.0,
                )
                data = resp.json()
                if not isinstance(data, dict):
                    raise ValueError(f"Expected dict, got {type(data)}")
                break
            except Exception as e:
                if attempt == self.max_retry:
                    raise
                time.sleep(1)

        # Parse into ChunkUnderstanding
        cu = ChunkUnderstanding(
            chunk_id=chunk.chunk_id,
            chapter_id=chunk.chapter_id,
            concepts=_as_list(data.get("concepts")),
            claims=_as_list(data.get("claims")),
            mechanisms=_as_list(data.get("mechanisms")),
            evidence=_as_list(data.get("evidence")),
            uncertainties=_as_list(data.get("uncertainties")),
            terminology=_as_list(data.get("terminology")),
            raw_response=resp.text,
        )

        # Save checkpoint
        self.store.save_chunk_checkpoint(
            run_id,
            chunk.chapter_id,
            chunk.chunk_id,
            "chunk_understanding",
            input_hash,
            cu.__dict__,
            success=True,
        )

        return cu

    def _chunk_schema_hint(self) -> str:
        return (
            '{"concepts":[{"name":"<term>","definition":"<one sentence>"}],'
            '"claims":[{"text":"<assertion>","quote":"<exact phrase from text>"}],'
            '"mechanisms":[{"cause":"<cause>","process":"<steps>","conditions":"<when>"}],'
            '"evidence":[{"claim":"<claim>","locator":"<char:N>","strength":"<DIRECT|INFERRED|TERM_ANCHOR>"}],'
            '"uncertainties":["<what is unclear>"],'
            '"terminology":[{"term":"<word>","meaning":"<definition>"}]}'
        )

    # ── Stage B: Chapter synthesis from chunks ──

    def synthesize_chapter(
        self,
        chapter_plan: ChunkPlan,
        chunk_understandings: list[ChunkUnderstanding],
        run_id: str,
        book_id: str,
        prior_chapter_ids: list[str],
        book_title: str,
        chapter_number: int,
        chapter_total: int,
        chapter_text: str,
        chapter_title: str,
    ) -> ChapterSynthesisResult:
        """Synthesize chapter understanding from chunk understandings — §9."""

        chapter_id = chapter_plan.chapter_id
        errors = []

        # Check chapter checkpoint
        cp = self.store.load_chapter_checkpoint(run_id, chapter_id)
        if cp and cp.success and cp.chapter_synthesis:
            # Reconstruct from checkpoint
            cu = ChapterUnderstanding(**cp.chapter_synthesis)
            return ChapterSynthesisResult(
                chapter_id=chapter_id,
                chapter_understanding=cu,
                chunk_understandings=chunk_understandings,
                delta=None,  # Will be regenerated if needed
                evidence=[],
                synthesis_calls=0,
                chunk_calls=len(chunk_understandings),
            )

        # Aggregate chunk understandings
        merged = self._merge_chunk_understandings(chunk_understandings, chapter_id)

        # Build full chapter object for synthesis
        context = ChapterContext(
            book_title=book_title,
            chapter_number=chapter_number,
            chapter_total=chapter_total,
            previous_chapter_titles=prior_chapter_ids[-3:],
            previous_concepts=[],
            following_expectations=f"chapter synthesis for {chapter_id}",
            position_ratio=round(chapter_number / chapter_total, 3) if chapter_total else 0,
        )

        chapter_obj = Chapter(
            chapter_id=chapter_id,
            number=chapter_number,
            title=chapter_title,
            text=chapter_text,
            context=context,
            role=classify_role(
                Chapter(
                    chapter_id=chapter_id,
                    number=chapter_number,
                    title=chapter_title,
                    text=chapter_text,
                )
            ),
        )

        # Single bounded chapter synthesis call
        for attempt in range(self.max_synthesis_calls):
            try:
                cu, delta, evidence = self.chapter_producer.produce(
                    chapter_obj,
                    run_id=run_id,
                    book_id=book_id,
                    prior_chapter_ids=prior_chapter_ids,
                )
                # Merge with chunk-extracted facts
                cu = self._merge_with_chunk_facts(cu, merged)
                break
            except Exception as e:
                errors.append(f"synthesis attempt {attempt + 1}: {e}")
                if attempt == self.max_synthesis_calls - 1:
                    # Failed — create minimal understanding
                    cu = ChapterUnderstanding(
                        id=f"cu_{run_id}_{chapter_id}",
                        run_id=run_id,
                        chapter_id=chapter_id,
                        chapter_thesis=f"[synthesis failed] {errors[-1]}",
                        primary_role="UNDERSTANDING_FAILED",
                        qualifications=errors,
                    )
                    delta = ChapterDelta(
                        id=f"cd_{run_id}_{chapter_id}",
                        run_id=run_id,
                        chapter_id=chapter_id,
                    )
                    evidence = []
                else:
                    time.sleep(1)

        # Save chapter checkpoint
        self.store.save_chapter_checkpoint(
            run_id,
            chapter_id,
            chunks_completed=[c.chunk_id for c in chapter_plan.chunks],
            chunk_understandings=[c.__dict__ for c in chunk_understandings],
            chapter_synthesis=cu.__dict__ if cu else None,
            completed=cu is not None and cu.primary_role != "UNDERSTANDING_FAILED",
            error="; ".join(errors) if errors else None,
        )

        return ChapterSynthesisResult(
            chapter_id=chapter_id,
            chapter_understanding=cu,
            chunk_understandings=chunk_understandings,
            delta=delta,
            evidence=evidence,
            synthesis_calls=attempt + 1 if "attempt" in locals() else 0,
            chunk_calls=len(chunk_understandings),
            errors=errors,
        )

    def _merge_chunk_understandings(
        self, understandings: list[ChunkUnderstanding], chapter_id: str
    ) -> dict[str, Any]:
        """Deterministically merge chunk understandings — §9."""
        merged = {
            "concepts": [],
            "claims": [],
            "mechanisms": [],
            "evidence": [],
            "uncertainties": [],
            "terminology": [],
        }

        seen_concepts = set()
        seen_claims = set()

        for cu in understandings:
            # Concepts
            for c in cu.concepts:
                name = c.get("name", "").strip()
                if name and name not in seen_concepts:
                    seen_concepts.add(name)
                    merged["concepts"].append(c)

            # Claims
            for cl in cu.claims:
                text = cl.get("text", "").strip()
                if text and text not in seen_claims:
                    seen_claims.add(text)
                    merged["claims"].append(cl)

            # Mechanisms
            merged["mechanisms"].extend(cu.mechanisms)
            merged["evidence"].extend(cu.evidence)
            merged["uncertainties"].extend(cu.uncertainties)
            merged["terminology"].extend(cu.terminology)

        return merged

    def _merge_with_chunk_facts(
        self, cu: ChapterUnderstanding, merged: dict[str, Any]
    ) -> ChapterUnderstanding:
        """Enhance chapter understanding with chunk-extracted facts."""
        if not cu:
            return cu

        # Merge concepts
        existing_concepts = set(cu.concepts_introduced_refs)
        for c in merged["concepts"]:
            name = c.get("name", "")
            if name and name not in existing_concepts:
                cu.concepts_introduced_refs.append(name)

        return cu

    # ── Stage C: Book-level P13 components ──

    def build_book_understanding(
        self,
        run_id: str,
        book_id: str,
        substrate_id: str,
        chapter_results: list[ChapterSynthesisResult],
        version: int = 1,
    ) -> BookUnderstandingV2:
        """Integrate chapter understandings into book understanding."""

        chapters = [r.chapter_understanding for r in chapter_results if r.chapter_understanding]
        deltas = [r.delta for r in chapter_results if r.delta]

        # Evidence by chapter
        evidence_by_chapter = {}
        for r in chapter_results:
            for ev in r.evidence:
                evidence_by_chapter.setdefault(ev.chapter_id, []).append(ev.evidence_id)

        integration_input = IntegrationInput(
            run_id=run_id,
            book_id=book_id,
            substrate_id=substrate_id,
            chapters=chapters,
            deltas=deltas,
            evidence_by_chapter=evidence_by_chapter,
            genre="",
        )

        bu = self.book_integrator.integrate(integration_input, version=version)
        return bu

    def run_p13_components(
        self,
        bu: BookUnderstandingV2,
        chapters: list[ChapterUnderstanding],
        run_id: str,
        book_id: str,
    ) -> dict[str, Any]:
        """Run all P13 book-level components in staged order — §15."""
        from stratum.services.bu_v2_argument_analyzer import ArgumentAnalyzer
        from stratum.services.bu_v2_concept_evolution import ConceptEvolutionBuilder
        from stratum.services.bu_v2_dependency_builder import DependencyBuilder
        from stratum.services.bu_v2_deep_quality import DeepQualityEvaluator
        from stratum.services.bu_v2_quality_report import numbered_chapter_ids

        # Build P12 components first
        dependency = DependencyBuilder().build(chapters, run_id=run_id, book_id=book_id)
        evolution = ConceptEvolutionBuilder().build(chapters, run_id=run_id, book_id=book_id)
        argument = ArgumentAnalyzer().analyze(
            chapters,
            run_id=run_id,
            book_id=book_id,
            evidence_by_chapter=self._evidence_by_chapter(chapters),
        )

        numbered_ids = numbered_chapter_ids(
            type("obj", (object,), {"chapters": chapters, "structure": None})(),
            None,
        )
        numbered = [c for c in chapters if c.chapter_id in numbered_ids]

        deep = DeepQualityEvaluator().evaluate(
            book_id=book_id,
            run_id=run_id,
            graph=dependency.graph,
            evolution=evolution,
            argument=argument,
            chapter_count=len(numbered),
            pipeline_status=bu.status.value if bu.status else "UNKNOWN",
        )

        # Now P13 components
        from stratum.services.bu_v2_thesis_analyzer import ThesisAnalyzer
        from stratum.services.bu_v2_concept_system import ConceptSystemBuilder
        from stratum.services.bu_v2_argument_system import ArgumentSystemBuilder
        from stratum.services.bu_v2_mechanism_analyzer import MechanismAnalyzer
        from stratum.services.bu_v2_evidence_map import EvidenceMapBuilder
        from stratum.services.bu_v2_chapter_roles import ChapterRoleAnalyzer
        from stratum.services.bu_v2_contradiction_detector import ContradictionDetector

        thesis_analyzer = ThesisAnalyzer()
        concept_builder = ConceptSystemBuilder()
        argument_builder = ArgumentSystemBuilder()
        mechanism_analyzer = MechanismAnalyzer()
        evidence_builder = EvidenceMapBuilder()
        chapter_roles = ChapterRoleAnalyzer()
        contradiction_detector = ContradictionDetector()

        thesis_analysis = thesis_analyzer.analyze(bu, chapters, dependency.graph)
        concept_analysis = concept_builder.build(bu, chapters, evolution, dependency.graph)
        argument_analysis_result = argument_builder.build(
            bu, chapters, thesis_analysis.model, argument, dependency.graph
        )
        mechanism_analysis = mechanism_analyzer.analyze(bu, chapters, dependency.graph)
        evidence_analysis = evidence_builder.build(bu, chapters, argument, dependency.graph)
        chapter_roles_analysis = chapter_roles.analyze(bu, chapters, None)
        contradiction_analysis = contradiction_detector.detect(
            bu,
            chapters,
            thesis_analysis.model,
            concept_analysis.system,
            argument_analysis_result.system,
            dependency.graph,
        )

        return {
            "thesis": thesis_analysis,
            "concepts": concept_analysis,
            "arguments": argument_analysis_result,
            "mechanisms": mechanism_analysis,
            "evidence": evidence_analysis,
            "chapter_roles": chapter_roles_analysis,
            "contradictions": contradiction_analysis,
            "dependency": dependency,
            "evolution": evolution,
            "argument_graph": argument,
            "deep_quality": deep,
        }

    def _evidence_by_chapter(self, chapters: list[ChapterUnderstanding]) -> dict[str, list[str]]:
        out = {}
        for cu in chapters:
            out[cu.chapter_id] = []
            for ep in cu.evidence_program:
                out[cu.chapter_id].extend(ep.evidence_refs)
        return out


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]
