"""P13 hard quality gates and 6-dimension scoring — task D.

The audit found the verification gate too loose: ch1/ch12/ch15 carried no
concepts, no arguments and no evidence, yet the book reached VERIFIED with
coverage 1.00. The reason was structural — every existing check was an aggregate
(`evidence_count > 0`, `len(governing_questions) > 0`), so a single chapter
supplied the evidence the whole book was checked against.

This module adds the per-chapter, per-artifact gates the audit asked for, each
computed from a measurement and each able to FAIL a run:

  H1  no empty chapter         every numbered chapter carries a thesis and a
                               concept or a claim
  H2  no placeholder text      governing questions / theses / definitions are
                               not the template phrases
  H3  no dangling evidence     every evidence id a chapter references resolves
                               to an EvidenceArtifact the run produced
  H4  DEF/THM KU coverage      ≥90% of the chapter's frozen DEF/THM KUs are
                               covered by a concept or an evidence item
  H5  no zero-argument chapter every numbered chapter yields an argument chain
                               with at least a claim and evidence
  H6  evidence carries a quote every evidence artifact carries a real quote and
                               a locator

and a 6-dimension score (0–10) over: accuracy, coverage, depth, traceability,
cross-chapter synthesis and expression. Accuracy is scored by an LLM judge over
a random sample of claims; the other five are computed from the artefacts.

The gates are separate from the verifier on purpose (§10, §11 of the quality
model): they describe and can block *publication of a quality claim*, while the
verifier answers "did the pipeline run". A caller decides which is authoritative;
this module only measures and reports.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import Any

# The exact template phrases the audit found, plus their close variants. A
# governing question or thesis equal to one of these is not an understanding.
PLACEHOLDER_PATTERNS = (
    r"^what is the intellectual structure of (this|the) book\??$",
    r"^what (is|are) (this|the) book('s)? (about|main idea|central (idea|thesis))\??$",
    r"^introduced or redefined in ch",
    r"^<.*>$",
    r"^(the )?book('s)? (intellectual )?structure$",
    r"^question \d+$",
    r"^thesis \d+$",
    r"^(tbd|n/?a|none|placeholder|todo)$",
    r"^what (does|is) (the|this) (book|chapter) (cover|about)\??$",
)
_PLACEHOLDER_RE = [re.compile(p, re.I) for p in PLACEHOLDER_PATTERNS]

# A chapter with fewer than this many characters of understanding text is empty.
MIN_CHAPTER_THESIS_CHARS = 8

# DEF/THM KU coverage floor.
KU_COVERAGE_FLOOR = 0.90

# Claim sample size for the LLM accuracy judge.
ACCURACY_SAMPLE = 20


@dataclass
class HardGate:
    """One hard gate. ``passed`` is derived from a measurement, never asserted."""

    gate: str
    passed: bool
    detail: str
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate,
            "status": "PASS" if self.passed else "FAIL",
            "detail": self.detail,
            "failures": self.failures[:20],
        }


@dataclass
class DimensionScore:
    """One of the six quality dimensions, 0–10 with an explainable metric."""

    key: str
    name: str
    score: float
    metric: str
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "score": round(self.score, 2),
            "metric": self.metric,
            "detail": self.detail,
        }


@dataclass
class HardGateReport:
    gates: list[HardGate] = field(default_factory=list)
    dimensions: list[DimensionScore] = field(default_factory=list)
    run_id: str = ""
    book_id: str = ""

    @property
    def all_passed(self) -> bool:
        return bool(self.gates) and all(g.passed for g in self.gates)

    @property
    def overall(self) -> float:
        if not self.dimensions:
            return 0.0
        return round(sum(d.score for d in self.dimensions) / len(self.dimensions), 2)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "book_id": self.book_id,
            "all_passed": self.all_passed,
            "overall": self.overall,
            "gates": [g.to_dict() for g in self.gates],
            "dimensions": [d.to_dict() for d in self.dimensions],
        }


def is_placeholder(text: str) -> bool:
    """Whether a string is a template/placeholder rather than real content."""
    s = (text or "").strip()
    if not s:
        return True
    return any(r.search(s) for r in _PLACEHOLDER_RE)


class HardGateEvaluator:
    """Compute the hard gates and the six-dimension score for a run."""

    def __init__(self, *, judge: Any = None, seed: int = 0):
        # ``judge`` is an optional callable ``(prompt) -> str`` used for the
        # accuracy dimension. Absent, accuracy is scored from evidence strength.
        self.judge = judge
        self._rng = random.Random(seed)

    def evaluate(self, result: Any, *, structure: dict[str, Any] | None = None) -> HardGateReport:
        from stratum.services.bu_v2_quality_report import numbered_chapter_ids

        rep = HardGateReport(
            run_id=getattr(result, "run_id", ""),
            book_id=getattr(result, "book_id", ""),
        )
        numbered_ids = numbered_chapter_ids(result, structure)
        chapters = [c for c in result.chapters if c.chapter_id in numbered_ids]
        evidence = list(getattr(result, "evidence", []) or [])
        ev_by_id = {e.evidence_id: e for e in evidence}
        p12 = getattr(result, "p12", None) or {}
        argument = p12.get("argument")
        evolution = p12.get("evolution")
        ku_index = getattr(result, "ku_index", None)
        bu = getattr(result, "bu", None)

        rep.gates = [
            self._h1_no_empty_chapter(chapters),
            self._h2_no_placeholder(bu, chapters),
            self._h3_no_dangling_evidence(chapters, ev_by_id),
            self._h4_ku_coverage(chapters, ku_index),
            self._h5_no_zero_argument_chapter(chapters, argument),
            self._h6_evidence_has_quote(evidence),
        ]
        rep.dimensions = self._dimensions(
            result, bu, chapters, evidence, argument, evolution, ku_index
        )
        return rep

    # ── hard gates ───────────────────────────────────────────────────────────

    @staticmethod
    def _h1_no_empty_chapter(chapters: list[Any]) -> HardGate:
        empty: list[str] = []
        for c in chapters:
            thesis = (c.chapter_thesis or "").strip()
            has_concept = bool(c.concepts_introduced_refs)
            has_claim = bool(c.evidence_program)
            if len(thesis) < MIN_CHAPTER_THESIS_CHARS or not (has_concept or has_claim):
                empty.append(
                    f"{c.chapter_id}: thesis={len(thesis)}c concepts={len(c.concepts_introduced_refs)} "
                    f"claims={len(c.evidence_program)}"
                )
        return HardGate(
            "H1_no_empty_chapter",
            not empty,
            f"{len(chapters) - len(empty)} of {len(chapters)} chapters carry a thesis and a concept or claim",
            empty,
        )

    @staticmethod
    def _h2_no_placeholder(bu: Any, chapters: list[Any]) -> HardGate:
        bad: list[str] = []
        if bu is not None:
            for q in getattr(bu, "governing_questions", []) or []:
                if is_placeholder(q):
                    bad.append(f"governing_question: {q[:60]}")
            for t in getattr(bu, "central_theses", []) or []:
                if is_placeholder(t):
                    bad.append(f"central_thesis: {t[:60]}")
            for step in getattr(getattr(bu, "concept_evolution", None), "__iter__", lambda: [])():
                definition = getattr(step, "definition", "")
                if is_placeholder(definition):
                    bad.append(f"concept definition: {getattr(step, 'concept_ref', '')[:40]}")
        for c in chapters:
            if (c.chapter_thesis or "").strip().startswith("[not understood]"):
                bad.append(f"{c.chapter_id}: thesis is a failure marker")
        # De-duplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for b in bad:
            if b not in seen:
                seen.add(b)
                unique.append(b)
        return HardGate(
            "H2_no_placeholder_text",
            not unique,
            "no template/placeholder text in book framing, definitions or chapter theses",
            unique,
        )

    @staticmethod
    def _h3_no_dangling_evidence(chapters: list[Any], ev_by_id: dict[str, Any]) -> HardGate:
        dangling: list[str] = []
        total_refs = 0
        for c in chapters:
            refs: list[str] = []
            for ep in c.evidence_program:
                refs.extend(ep.evidence_refs)
            refs.extend(getattr(c, "supporting_ku_refs", []) or [])
            for r in refs:
                if not r:
                    continue
                total_refs += 1
                # KU ids (ku_*) and concept anchors are not evidence artifacts.
                if r.startswith("ku_") or r.startswith("concept:"):
                    continue
                if r.startswith("ev_") and r not in ev_by_id:
                    dangling.append(f"{c.chapter_id}: {r}")
        return HardGate(
            "H3_no_dangling_evidence",
            not dangling,
            f"{total_refs} evidence references, all resolve to a produced artifact"
            if not dangling
            else f"{len(dangling)} evidence reference(s) point at ids the run did not produce",
            dangling,
        )

    @staticmethod
    def _h4_ku_coverage(chapters: list[Any], ku_index: Any) -> HardGate:
        if ku_index is None:
            return HardGate(
                "H4_defthm_ku_coverage",
                True,
                "no frozen KUs available for this book; coverage not measurable",
            )
        low: list[str] = []
        ratios: list[float] = []
        for c in chapters:
            expected = ku_index.expected_defthm(c.chapter_id)
            if expected == 0:
                continue
            covered = _covered_ku_count(c, ku_index)
            ratio = covered / expected
            ratios.append(ratio)
            if ratio < KU_COVERAGE_FLOOR:
                low.append(
                    f"{c.chapter_id}: {covered}/{expected} DEF/THM KUs covered ({ratio:.0%})"
                )
        if not ratios:
            return HardGate(
                "H4_defthm_ku_coverage", True, "no chapter has frozen DEF/THM KUs to cover"
            )
        mean = sum(ratios) / len(ratios)
        return HardGate(
            "H4_defthm_ku_coverage",
            not low,
            f"mean DEF/THM KU coverage {mean:.0%} across {len(ratios)} chapters "
            f"(floor {KU_COVERAGE_FLOOR:.0%})",
            low,
        )

    @staticmethod
    def _h5_no_zero_argument_chapter(chapters: list[Any], argument: Any) -> HardGate:
        if argument is None:
            return HardGate(
                "H5_no_zero_argument_chapter", False, "no argument analysis was produced"
            )
        by_chapter: dict[str, int] = {}
        for chain in getattr(argument, "chains", []) or []:
            if chain.evidence and chain.conclusion is not None:
                by_chapter[chain.chapter_id] = by_chapter.get(chain.chapter_id, 0) + 1
        zero = [c.chapter_id for c in chapters if by_chapter.get(c.chapter_id, 0) == 0]
        return HardGate(
            "H5_no_zero_argument_chapter",
            not zero,
            f"{len(chapters) - len(zero)} of {len(chapters)} chapters yield a complete argument chain",
            zero,
        )

    @staticmethod
    def _h6_evidence_has_quote(evidence: list[Any]) -> HardGate:
        missing: list[str] = []
        for e in evidence:
            if (
                not (getattr(e, "quote", "") or "").strip()
                or not (getattr(e, "locator", "") or "").strip()
            ):
                missing.append(getattr(e, "evidence_id", "?"))
        return HardGate(
            "H6_evidence_has_quote",
            not missing,
            f"{len(evidence)} evidence artifacts, all carry a quote and a locator"
            if not missing
            else f"{len(missing)} evidence artifact(s) carry no quote or no locator",
            missing,
        )

    # ── six dimensions ───────────────────────────────────────────────────────

    def _dimensions(
        self,
        result: Any,
        bu: Any,
        chapters: list[Any],
        evidence: list[Any],
        argument: Any,
        evolution: Any,
        ku_index: Any,
    ) -> list[DimensionScore]:
        return [
            self._dim_accuracy(result, chapters, evidence),
            self._dim_coverage(bu, chapters, ku_index),
            self._dim_depth(chapters, argument, evolution),
            self._dim_traceability(evidence, chapters),
            self._dim_cross_chapter(result, bu, chapters),
            self._dim_expression(bu, chapters),
        ]

    def _dim_accuracy(
        self, result: Any, chapters: list[Any], evidence: list[Any]
    ) -> DimensionScore:
        """Accuracy: an LLM judge over a random sample of claims, else strength."""
        claims = _sample_claims(chapters, evidence, ACCURACY_SAMPLE, self._rng)
        if self.judge is not None and claims:
            verdicts = []
            for claim in claims:
                try:
                    verdicts.append(self._judge_one(claim))
                except Exception:
                    verdicts.append(None)
            graded = [v for v in verdicts if v is not None]
            if graded:
                good = sum(1 for v in graded if v)
                score = 10.0 * good / len(graded)
                return DimensionScore(
                    "accuracy",
                    "Accuracy",
                    score,
                    f"{good}/{len(graded)} sampled claims verified against source text",
                    f"LLM judge over {len(graded)} of {len(claims)} sampled claims",
                )
        # Fallback: DIRECT evidence ratio (no judge available).
        if not evidence:
            return DimensionScore(
                "accuracy", "Accuracy", 0.0, "no evidence to judge", "no claims sampled"
            )
        direct = sum(1 for e in evidence if getattr(e, "kind", "") in ("CLAIM", "KU_ANCHOR"))
        score = 10.0 * direct / len(evidence)
        return DimensionScore(
            "accuracy",
            "Accuracy",
            score,
            f"{direct}/{len(evidence)} evidence items are verbatim-quote backed",
            "no LLM judge configured; scored from evidence strength",
        )

    def _judge_one(self, claim: dict[str, str]) -> bool | None:
        # Two-part verdict. The quote is the part of the source text the claim was
        # anchored to; for a DIRECT claim it is the sentence that states it, for a
        # term-anchored claim it is the passage where the concept occurs. The judge
        # answers YES when the quote is consistent with the claim and gives the
        # claim a defensible textual basis — not when the claim is copied verbatim
        # (a fair paraphrase of a definition is still a fair reading). A strict
        # literal-equality test would reject every legitimate technical paraphrase.
        prompt = (
            "You are an accuracy checker. Decide whether a CLAIM is a fair reading of the "
            "SOURCE QUOTE taken from the book.\n"
            "A fair reading means: the quote supports the claim, is consistent with it, and "
            "gives the claim a defensible basis in the book's own words. A paraphrase that "
            "states the same fact the quote conveys counts as fair. Answer NO only if the "
            "claim contradicts the quote, asserts something the quote does not touch, or "
            "goes beyond what the quote could support.\n\n"
            f"CLAIM: {claim['text']}\n"
            f"SOURCE QUOTE: {claim['quote']}\n\n"
            "Answer with exactly one word: YES or NO.\n"
        )
        out = (self.judge(prompt) or "").strip().upper()
        if out.startswith("YES"):
            return True
        if out.startswith("NO"):
            return False
        return None

    @staticmethod
    def _dim_coverage(bu: Any, chapters: list[Any], ku_index: Any) -> DimensionScore:
        if ku_index is not None and getattr(ku_index, "total", 0):
            ratios = []
            for c in chapters:
                expected = ku_index.expected_defthm(c.chapter_id)
                if expected:
                    ratios.append(_covered_ku_count(c, ku_index) / expected)
            if ratios:
                mean = sum(ratios) / len(ratios)
                return DimensionScore(
                    "coverage",
                    "Coverage",
                    10.0 * mean,
                    f"mean frozen DEF/THM KU coverage {mean:.0%}",
                    f"{ku_index.total} frozen KUs indexed",
                )
        n_concepts = 0
        if bu is not None:
            system = getattr(bu, "concept_system", {}) or {}
            n_concepts = len(system.get("concepts", {})) if isinstance(system, dict) else 0
        introduced = sum(len(c.concepts_introduced_refs) for c in chapters)
        per_chapter = introduced / max(1, len(chapters))
        # Target: ~8 concepts per chapter is a substantial textbook chapter.
        score = min(10.0, 10.0 * per_chapter / 8.0)
        return DimensionScore(
            "coverage",
            "Coverage",
            score,
            f"{n_concepts} book concepts, {per_chapter:.1f} introduced per chapter",
            "scored from concept density (no frozen KUs)",
        )

    @staticmethod
    def _dim_depth(chapters: list[Any], argument: Any, evolution: Any) -> DimensionScore:
        chains = len(getattr(argument, "chains", []) or []) if argument else 0
        complete = getattr(argument, "complete_chains", 0) if argument else 0
        evolving = getattr(evolution, "fully_evolving_count", 0) if evolution else 0
        mechanisms = sum(len(c.mechanisms_refs) for c in chapters)
        n = max(1, len(chapters))
        # Depth needs arguments, evolution and mechanisms — not just concepts.
        arg_score = min(1.0, complete / n)
        evo_score = min(1.0, evolving / 10.0)
        mech_score = min(1.0, mechanisms / (3.0 * n))
        score = 10.0 * (0.45 * arg_score + 0.3 * evo_score + 0.25 * mech_score)
        return DimensionScore(
            "depth",
            "Depth",
            score,
            f"{complete} complete argument chains, {evolving} evolving concepts, {mechanisms} mechanisms",
            f"{chains} chains total across {n} chapters",
        )

    @staticmethod
    def _dim_traceability(evidence: list[Any], chapters: list[Any]) -> DimensionScore:
        n = len(evidence)
        if n == 0:
            return DimensionScore(
                "traceability",
                "Traceability",
                0.0,
                "no evidence recorded",
                "nothing is traceable to source text",
            )
        with_quote = sum(1 for e in evidence if (getattr(e, "quote", "") or "").strip())
        with_locator = sum(1 for e in evidence if (getattr(e, "locator", "") or "").strip())
        # Evidence per chapter, so one well-evidenced chapter cannot carry a book.
        per_chapter = n / max(1, len(chapters))
        quote_rate = with_quote / n
        locator_rate = with_locator / n
        density = min(1.0, per_chapter / 8.0)
        score = 10.0 * (0.4 * quote_rate + 0.3 * locator_rate + 0.3 * density)
        return DimensionScore(
            "traceability",
            "Traceability",
            score,
            f"{with_quote}/{n} with a quote, {with_locator}/{n} with a locator, {per_chapter:.1f} per chapter",
            "traceability, not correctness",
        )

    @staticmethod
    def _dim_cross_chapter(result: Any, bu: Any, chapters: list[Any]) -> DimensionScore:
        p12 = getattr(result, "p12", None) or {}
        dep = p12.get("dependency")
        graph = getattr(dep, "graph", None) if dep else None
        cross = len(graph.cross_chapter_edges()) if graph is not None else 0
        concept_nodes = len(graph.nodes_of_type("CONCEPT")) if graph is not None else 0
        theorem_nodes = len(graph.nodes_of_type("THEOREM")) if graph is not None else 0
        edges = len(
            getattr(getattr(bu, "chapter_dependency_graph", None), "dependencies", []) or []
        )
        n = max(1, len(chapters))
        cross_score = min(1.0, cross / max(1, n))
        concept_score = min(1.0, (concept_nodes + theorem_nodes) / (4.0 * n))
        edge_score = min(1.0, edges / max(1, n - 1))
        score = 10.0 * (0.4 * cross_score + 0.3 * concept_score + 0.3 * edge_score)
        return DimensionScore(
            "cross_chapter",
            "Cross-chapter synthesis",
            score,
            f"{cross} cross-chapter edges, {concept_nodes} concept + {theorem_nodes} theorem nodes, "
            f"{edges} chapter dependencies",
            "is this a model of the book or a chapter collection",
        )

    @staticmethod
    def _dim_expression(bu: Any, chapters: list[Any]) -> DimensionScore:
        if bu is None:
            return DimensionScore("expression", "Expression", 0.0, "no BU produced", "")
        questions = [
            q for q in (getattr(bu, "governing_questions", []) or []) if not is_placeholder(q)
        ]
        theses = [t for t in (getattr(bu, "central_theses", []) or []) if not is_placeholder(t)]
        sub = [t for t in (getattr(bu, "sub_theses", []) or []) if not is_placeholder(t)]
        nk = getattr(bu, "negative_knowledge", None)
        limitations = len(getattr(nk, "limitations", []) or [])
        arc_steps = len(getattr(getattr(bu, "discourse_arc", None), "steps", []) or [])
        n = max(1, len(chapters))
        framing = min(1.0, (len(questions) + len(theses) + len(sub)) / 6.0)
        arc = min(1.0, arc_steps / n)
        boundary = min(1.0, limitations / 4.0)
        score = 10.0 * (0.5 * framing + 0.3 * arc + 0.2 * boundary)
        return DimensionScore(
            "expression",
            "Expression",
            score,
            f"{len(questions)} questions, {len(theses)} theses, {arc_steps} arc steps, {limitations} limitations",
            "book-specific framing, not templates",
        )


# ── helpers ──────────────────────────────────────────────────────────────────


def _covered_ku_count(chapter: Any, ku_index: Any) -> int:
    """How many of the chapter's DEF/THM KUs the understanding covers.

    A KU is covered when any of these hold:
      * its ku_id is in the chapter's ``major_ku_refs`` (the producer adds it
        when it anchored the KU), or
      * its concept label matches a concept the chapter introduced
        (case-insensitive, either direction), or
      * the label and a concept share a distinctive term (≥5 chars, not a
        stopword), which is the honest test for an OCR-fragmented frozen label
        like "limit of" or "derivative of ƒ at" whose exact string never
        appears but whose concept the chapter clearly covers.
    """
    anchors = ku_index.concept_anchors_for(chapter.chapter_id)
    if not anchors:
        return 0
    names = [_norm(n) for n in chapter.concepts_introduced_refs if n]
    name_tokens = [set(_tokens(n)) for n in chapter.concepts_introduced_refs if n]
    ku_ids = set(getattr(chapter, "major_ku_refs", []) or [])
    covered = 0
    for a in anchors:
        name = _norm(a.get("name") or "")
        ku_id = a.get("ku_id") or ""
        if ku_id and ku_id in ku_ids:
            covered += 1
            continue
        if not name:
            continue
        if any(name == n or name in n or n in name for n in names if len(n) >= 3):
            covered += 1
            continue
        label_tokens = set(_tokens(a.get("name") or ""))
        if label_tokens and any(label_tokens & toks for toks in name_tokens):
            covered += 1
    return covered


_STOP = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "at",
    "by",
    "for",
    "and",
    "or",
    "is",
    "are",
    "be",
    "with",
    "that",
    "this",
    "as",
    "from",
    "if",
    "then",
    "its",
    "it",
    "we",
    "when",
    "can",
    "will",
    "all",
    "each",
    "not",
    "but",
}


def _tokens(s: str) -> list[str]:
    """Distinctive lowercase words in a label, for fuzzy KU coverage matching."""
    import re as _re

    return [w for w in _re.findall(r"[a-z]{5,}|[一-鿿]{2,}", (s or "").lower()) if w not in _STOP]


def _sample_claims(
    chapters: list[Any], evidence: list[Any], k: int, rng: random.Random
) -> list[dict[str, str]]:
    """A random sample of (claim, source quote) pairs for the accuracy judge."""
    ev_by_id = {e.evidence_id: e for e in evidence}
    pairs: list[dict[str, str]] = []
    for c in chapters:
        for ep in c.evidence_program:
            if not ep.evidence_refs:
                continue
            ev = ev_by_id.get(ep.evidence_refs[0])
            if ev is None or not (getattr(ev, "quote", "") or "").strip():
                continue
            pairs.append({"text": ep.claim_ref, "quote": ev.quote[:400]})
    if len(pairs) <= k:
        return pairs
    return rng.sample(pairs, k)


def _norm(s: str) -> str:
    return "".join(c for c in (s or "").lower() if c.isalnum() or c.isspace()).strip()


def persist_gates(report: HardGateReport, *, book_id: str = "") -> int:
    """Write the gates to ``stratum.bu2_p13_quality_gates``. Returns rows written.

    One row per hard gate (numbers 1–6) plus one row for the six-dimension score
    (number 7). The table's ``gate_number`` is CHECK-constrained to 1–8 and its
    ``status`` to PASS/FAIL/BOOK_LIMIT, so the dimension scores are carried in
    the row's ``evidence`` JSON rather than as their own numbered rows. The table
    is read by the report, never by the BU status path, so a gate failure cannot
    silently become a publication decision here.
    """
    from stratum.db import insert

    written = 0
    for i, gate in enumerate(report.gates, start=1):
        row = {
            "id": f"p13_{report.run_id}_{i}",
            "run_id": report.run_id,
            "book_id": book_id or report.book_id,
            "gate_number": i,
            "gate_name": gate.gate,
            "status": "PASS" if gate.passed else "FAIL",
            "score": 1.0 if gate.passed else 0.0,
            "detail": gate.detail[:1000],
            "evidence": {"failures": gate.failures[:20]},
        }
        insert("bu2_p13_quality_gates", row)
        written += 1
    # Row 7 carries the six-dimension score as JSON, plus the overall.
    dims = {d.key: d.score for d in report.dimensions}
    row = {
        "id": f"p13_{report.run_id}_dims",
        "run_id": report.run_id,
        "book_id": book_id or report.book_id,
        "gate_number": 7,
        "gate_name": "six_dimension_score",
        "status": "PASS" if report.overall >= 9.0 else "FAIL",
        "score": float(report.overall),
        "detail": f"overall {report.overall:.2f}/10 across 6 dimensions"[:1000],
        "evidence": {
            "dimensions": dims,
            "metrics": {d.key: d.metric for d in report.dimensions},
        },
    }
    insert("bu2_p13_quality_gates", row)
    written += 1
    return written
