"""P14-ALIGNMENT-002: Gold Cases for Thesis and Argument Alignment.

Gold cases cover:
- Thesis: strong SUPPORTS, strong CONTRADICTS, strong COMPLEMENTS, EXTENDS, QUALIFIES, unrelated
- Argument: SUPPORTS, CHALLENGES, COMPLEMENTS, EXTENDS, GENERALIZES, unrelated
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, BUStatus, BookSynthesis, BookThesisModel, BookThesis,
    ThesisType, ThesisProvenance, BookConceptSystem, ConceptSystemEntry,
    ConceptRole, BookArgumentSystem, BookArgument, ArgumentStatus,
    BookMechanismSystem, BookMechanism, BookEvidenceMap, EvidenceMapEntry,
    EvidenceStrengthP13, BookAuthorModel, BookChapterRoles, ChapterRoleAssignment,
    ChapterRole, BookContradictions, CrossBookThesis, CrossBookArgument,
    CrossBookThesisRelationType, CrossBookArgumentRelationType,
)
from stratum.services.bu_v2_crossbook_alignment import (
    LayeredThesisAligner, LayeredArgumentAligner, AlignmentThresholds,
)


@dataclass
class GoldCase:
    """A single gold case for alignment validation."""

    source: str
    target: str
    expected_relation: str
    minimum_confidence: float
    evidence: str


# ── Thesis Gold Cases ────────────────────────────────────────────────────────

THESIS_GOLD_CASES = [
    # 1. Strong SUPPORTS: identical theses
    GoldCase(
        source="Calculus provides tools to analyze change",
        target="Calculus provides tools to analyze change",
        expected_relation="SUPPORTS",
        minimum_confidence=0.9,
        evidence="identical statements",
    ),
    # 2. Strong CONTRADICTS: opposing statements
    GoldCase(
        source="Calculus provides tools to analyze change",
        target="Calculus does not provide tools to analyze change",
        expected_relation="CONTRADICTS",
        minimum_confidence=0.5,
        evidence="negation pattern detected",
    ),
    # 3. Strong COMPLEMENTS: different aspects of same topic
    GoldCase(
        source="Derivatives measure instantaneous change",
        target="Integrals measure accumulated change",
        expected_relation="COMPLEMENTS",
        minimum_confidence=0.4,
        evidence="different aspects of change",
    ),
    # 4. EXTENDS: problem → solution (core EXTENDS case)
    GoldCase(
        source="How do we measure rates of change?",
        target="Derivatives provide the tool",
        expected_relation="EXTENDS",
        minimum_confidence=0.3,
        evidence="problem-solution pattern",
    ),
    # 5. EXTENDS: concept → elaboration (general → specific)
    GoldCase(
        source="Calculus provides tools to analyze change",
        target="Derivatives provide tools to analyze change through limits",
        expected_relation="EXTENDS",
        minimum_confidence=0.4,
        evidence="general concept elaborated into specific method",
    ),
    # 6. EXTENDS: claim → evidence (claim → supporting evidence)
    GoldCase(
        source="Limits capture instantaneous change",
        target="The derivative is defined as the limit of the difference quotient",
        expected_relation="EXTENDS",
        minimum_confidence=0.4,
        evidence="claim extended by formal definition as evidence",
    ),
    # 7. QUALIFIES: similar but with qualification (core QUALIFIES case)
    GoldCase(
        source="Calculus is useful for physics",
        target="Calculus is useful for physics when functions are continuous",
        expected_relation="QUALIFIES",
        minimum_confidence=0.4,
        evidence="qualification pattern",
    ),
    # 8. QUALIFIES: claim → constrained claim (with condition)
    GoldCase(
        source="Continuous functions are integrable",
        target="Continuous functions on closed intervals are integrable",
        expected_relation="QUALIFIES",
        minimum_confidence=0.4,
        evidence="constraint added to scope",
    ),
    # 9. QUALIFIES: claim → qualified claim (with exception)
    GoldCase(
        source="Differentiable functions are continuous",
        target="Differentiable functions are continuous except at isolated points",
        expected_relation="QUALIFIES",
        minimum_confidence=0.4,
        evidence="exception clause qualifies the claim",
    ),
    # 10. Unrelated: completely different topics
    GoldCase(
        source="Calculus provides tools to analyze change",
        target="Markets determine prices through supply and demand",
        expected_relation="UNRELATED",
        minimum_confidence=0.0,
        evidence="no semantic overlap",
    ),
]

# ── Argument Gold Cases ──────────────────────────────────────────────────────

ARGUMENT_GOLD_CASES = [
    # 1. SUPPORTS: identical arguments
    GoldCase(
        source="Derivatives measure change",
        target="Derivatives measure change",
        expected_relation="SUPPORTS",
        minimum_confidence=0.9,
        evidence="identical arguments",
    ),
    # 2. CHALLENGES: opposing conclusions
    GoldCase(
        source="Markets are efficient",
        target="Markets are inefficient",
        expected_relation="CHALLENGES",
        minimum_confidence=0.4,
        evidence="opposing conclusions",
    ),
    # 3. COMPLEMENTS: different focus, same goal
    GoldCase(
        source="Derivatives measure change",
        target="Integrals measure accumulation",
        expected_relation="COMPLEMENTS",
        minimum_confidence=0.3,
        evidence="complementary focus",
    ),
    # 4. EXTENDS: general → specific (core EXTENDS case)
    GoldCase(
        source="Calculus analyzes change",
        target="Derivatives analyze instantaneous change",
        expected_relation="EXTENDS",
        minimum_confidence=0.3,
        evidence="general-specific pattern",
    ),
    # 5. EXTENDS: general concept → specific method (different phrasing)
    GoldCase(
        source="Calculus analyzes change using limits",
        target="Derivatives compute instantaneous rates via limits",
        expected_relation="EXTENDS",
        minimum_confidence=0.3,
        evidence="general concept elaborated into specific computational method",
    ),
    # 6. EXTENDS: claim → evidence (claim extended by evidence)
    GoldCase(
        source="The derivative captures instantaneous change",
        target="The derivative is the limit of the difference quotient as h approaches zero",
        expected_relation="EXTENDS",
        minimum_confidence=0.4,
        evidence="claim extended by formal definition as evidence",
    ),
    # 7. GENERALIZES: specific → general (core GENERALIZES case)
    GoldCase(
        source="Derivatives analyze instantaneous change",
        target="Calculus analyzes change",
        expected_relation="GENERALIZES",
        minimum_confidence=0.3,
        evidence="specific-general pattern",
    ),
    # 8. GENERALIZES: specific method → general principle (induction)
    GoldCase(
        source="The derivative of x^n is n*x^(n-1) for all n",
        target="The power rule generalizes differentiation of monomials",
        expected_relation="GENERALIZES",
        minimum_confidence=0.4,
        evidence="specific rule generalized to general principle",
    ),
    # 9. GENERALIZES: specific instance → general pattern (abstraction)
    GoldCase(
        source="The derivative of x^2 is 2x, the derivative of x^3 is 3x^2",
        target="The derivative of x^n follows the pattern n*x^(n-1)",
        expected_relation="GENERALIZES",
        minimum_confidence=0.4,
        evidence="specific instances abstracted to general pattern",
    ),
    # 10. COMPLEMENTS: different focus, same goal (core COMPLEMENTS case)
    GoldCase(
        source="Derivatives measure change",
        target="Integrals measure accumulation",
        expected_relation="COMPLEMENTS",
        minimum_confidence=0.3,
        evidence="complementary focus",
    ),
    # 11. Unrelated: completely different arguments
    GoldCase(
        source="Derivatives measure change",
        target="Markets determine prices",
        expected_relation="UNRELATED",
        minimum_confidence=0.0,
        evidence="no semantic overlap",
    ),
]


def make_thesis_book(book_id: str, theses: list[tuple[str, str]]) -> tuple[BookUnderstandingV2, BookSynthesis]:
    """Create a book with given theses for testing."""
    bu = BookUnderstandingV2(
        id=f"bu_{book_id}", run_id=f"run_{book_id}",
        book_id=book_id, substrate_id=book_id,
        version=1, status=BUStatus.VERIFIED,
    )
    synth = BookSynthesis(
        id=f"synth_{book_id}", run_id=f"run_{book_id}",
        book_id=book_id,
        problem_definition=f"Problems of {book_id}",
        thesis=BookThesisModel(
            core_thesis=BookThesis(
                id=f"thesis_{book_id}_core", type=ThesisType.CORE,
                statement=theses[0][0], scope="book", confidence=0.8,
                provenance=ThesisProvenance.AUTHOR_ASSERTED,
            ) if theses else None,
            supporting_theses=[BookThesis(
                id=f"thesis_{book_id}_sup{i}", type=ThesisType.SUPPORTING,
                statement=t[0], scope="book", confidence=0.7,
                provenance=ThesisProvenance.STRUCTURALLY_DERIVED,
            ) for i, t in enumerate(theses[1:])],
        ),
        concept_system=BookConceptSystem(),
        argument_system=BookArgumentSystem(),
        mechanism_system=BookMechanismSystem(),
        evidence_map=BookEvidenceMap(),
        author_model=BookAuthorModel(),
        chapter_roles=BookChapterRoles(),
        contradictions=BookContradictions(),
    )
    return (bu, synth)


def make_argument_book(book_id: str, arguments: list[tuple[str, str, str, str]]) -> tuple[BookUnderstandingV2, BookSynthesis]:
    """Create a book with given arguments for testing."""
    bu = BookUnderstandingV2(
        id=f"bu_{book_id}", run_id=f"run_{book_id}",
        book_id=book_id, substrate_id=book_id,
        version=1, status=BUStatus.VERIFIED,
    )
    synth = BookSynthesis(
        id=f"synth_{book_id}", run_id=f"run_{book_id}",
        book_id=book_id,
        problem_definition=f"Problems of {book_id}",
        thesis=BookThesisModel(),
        concept_system=BookConceptSystem(),
        argument_system=BookArgumentSystem(
            thesis_arguments=[BookArgument(
                id=f"arg_{book_id}_{i}", level=0,
                what=arg[0], why=arg[1], how=arg[2], conclusion=arg[3],
                evidence_refs=[f"ev_{book_id}_{i}"], status=ArgumentStatus.SUPPORTED,
                confidence=0.7, source_chapters=["ch1"],
            ) for i, arg in enumerate(arguments)],
        ),
        mechanism_system=BookMechanismSystem(),
        evidence_map=BookEvidenceMap(),
        author_model=BookAuthorModel(),
        chapter_roles=BookChapterRoles(),
        contradictions=BookContradictions(),
    )
    return (bu, synth)


def test_thesis_alignment_precision_recall():
    """Test thesis alignment precision and recall using gold cases."""
    print("=== Thesis Alignment Gold Cases ===")

    # Create books with gold case theses
    book_a_theses = [
        ("Calculus provides tools to analyze change", "CORE"),
        ("Derivatives measure instantaneous change", "SUPPORTING"),
        ("How do we measure rates of change?", "PROBLEM"),
        ("Calculus provides tools to analyze change using limits", "SUPPORTING"),
        ("Limits capture instantaneous change", "SUPPORTING"),
        ("Calculus is useful for physics", "SUPPORTING"),
        ("Continuous functions are integrable", "SUPPORTING"),
        ("Differentiable functions are continuous", "SUPPORTING"),
    ]
    book_b_theses = [
        ("Calculus provides tools to analyze change", "CORE"),
        ("Calculus does not provide tools to analyze change", "CORE"),
        ("Integrals measure accumulated change", "SUPPORTING"),
        ("Derivatives provide the tool", "SUPPORTING"),
        ("Derivatives provide tools to analyze change through limits", "SUPPORTING"),
        ("The derivative is defined as the limit of the difference quotient", "SUPPORTING"),
        ("Calculus is useful for physics when functions are continuous", "SUPPORTING"),
        ("Continuous functions on closed intervals are integrable", "SUPPORTING"),
        ("Differentiable functions are continuous except at isolated points", "SUPPORTING"),
        ("Markets determine prices through supply and demand", "CORE"),
    ]

    book_a = make_thesis_book("book_a", book_a_theses)
    book_b = make_thesis_book("book_b", book_b_theses)

    aligner = LayeredThesisAligner(AlignmentThresholds(candidate_threshold=0.2, acceptance_threshold=0.5))
    result = aligner.align([book_a, book_b])

    print(f"Candidates: {len(result.candidates)}")
    print(f"Relations: {len(result.relations)}")
    print(f"Rejected: {len(result.rejected)}")

    for rel in result.relations:
        print(f"  {rel.relation.value}: {rel.source_thesis.statement[:40]}... ~ {rel.target_thesis.statement[:40]}...")

    # Check gold cases
    gold_results = []
    for case in THESIS_GOLD_CASES:
        found = False
        for rel in result.relations:
            if (case.source in rel.source_thesis.statement and case.target in rel.target_thesis.statement) or \
               (case.target in rel.source_thesis.statement and case.source in rel.target_thesis.statement):
                found = True
                gold_results.append({
                    "case": case.expected_relation,
                    "found": True,
                    "actual": rel.relation.value,
                    "correct": rel.relation.value == case.expected_relation,
                    "confidence": rel.confidence,
                })
                break
        if not found:
            gold_results.append({
                "case": case.expected_relation,
                "found": False,
                "actual": None,
                "correct": case.expected_relation == "UNRELATED",
                "confidence": 0.0,
            })

    print("\n=== Gold Case Results ===")
    for r in gold_results:
        status = "✓" if r["correct"] else "✗"
        print(f"  {status} {r['case']}: found={r['found']}, actual={r['actual']}, confidence={r['confidence']:.2f}")

    return gold_results


def test_argument_alignment_precision_recall():
    """Test argument alignment precision and recall using gold cases."""
    print("\n=== Argument Alignment Gold Cases ===")

    # Create books with gold case arguments
    # Book A has general arguments, Book B has specific arguments
    book_a_args = [
        ("Derivatives measure change", "Because functions change", "Through limits", "Derivatives are useful"),
        ("Markets are efficient", "Because prices adjust", "Through competition", "Efficiency is achieved"),
        ("Calculus analyzes change", "Because functions change", "Through various tools", "Change is analyzed"),
        ("Calculus analyzes change using limits", "Because limits define continuity", "Through epsilon-delta", "Limits define analysis"),
        ("The derivative captures instantaneous change", "Because rates vary", "Through difference quotients", "Limit defines the derivative"),
    ]
    book_b_args = [
        ("Derivatives measure change", "Because functions change", "Through limits", "Derivatives are useful"),
        ("Markets are inefficient", "Because prices fail", "Through monopoly", "Inefficiency results"),
        ("Integrals measure accumulation", "Because quantities accumulate", "Through summation", "Integrals are useful"),
        ("Derivatives analyze instantaneous change", "Because functions change", "Through limits", "Instantaneous analysis"),
        ("The derivative of x^n is n*x^(n-1) for all n", "Because power rule applies", "Through binomial expansion", "Power rule holds"),
        ("The derivative of x^2 is 2x, the derivative of x^3 is 3x^2", "Because pattern holds", "Through binomial expansion", "Power rule generalizes"),
        ("The derivative is the limit of the difference quotient", "Because rate of change", "Through difference quotients", "Limit defines derivative"),
        ("Markets determine prices", "Because of supply and demand", "Through exchange", "Prices emerge"),
    ]

    book_a = make_argument_book("book_a", book_a_args)
    book_b = make_argument_book("book_b", book_b_args)

    aligner = LayeredArgumentAligner(AlignmentThresholds(candidate_threshold=0.15, acceptance_threshold=0.5))
    result = aligner.align([book_a, book_b])

    print(f"Candidates: {len(result.candidates)}")
    print(f"Relations: {len(result.relations)}")
    print(f"Rejected: {len(result.rejected)}")

    for rel in result.relations:
        print(f"  {rel.relation.value}: {rel.source_argument.what[:40]}... ~ {rel.target_argument.what[:40]}...")

    # Check gold cases
    gold_results = []
    for case in ARGUMENT_GOLD_CASES:
        found = False
        for rel in result.relations:
            if (case.source in rel.source_argument.what and case.target in rel.target_argument.what) or \
               (case.target in rel.source_argument.what and case.source in rel.target_argument.what):
                found = True
                gold_results.append({
                    "case": case.expected_relation,
                    "found": True,
                    "actual": rel.relation.value,
                    "correct": rel.relation.value == case.expected_relation,
                    "confidence": rel.confidence,
                })
                break
        if not found:
            gold_results.append({
                "case": case.expected_relation,
                "found": False,
                "actual": None,
                "correct": case.expected_relation == "UNRELATED",
                "confidence": 0.0,
            })

    print("\n=== Gold Case Results ===")
    for r in gold_results:
        status = "✓" if r["correct"] else "✗"
        print(f"  {status} {r['case']}: found={r['found']}, actual={r['actual']}, confidence={r['confidence']:.2f}")

    return gold_results


def test_unrelated_books_zero_false_positives():
    """Test that unrelated books produce 0 false-positive relations."""
    print("\n=== Unrelated Books Test ===")

    # Thomas Calculus vs Macroecomics (completely different domains)
    book_a = make_thesis_book("math", [("Calculus provides tools to analyze change", "CORE")])
    book_b = make_thesis_book("econ", [("Markets determine prices through supply and demand", "CORE")])

    aligner = LayeredThesisAligner(AlignmentThresholds(candidate_threshold=0.2, acceptance_threshold=0.5))
    result = aligner.align([book_a, book_b])

    print(f"Candidates: {len(result.candidates)}")
    print(f"Relations: {len(result.relations)}")
    print(f"Rejected: {len(result.rejected)}")

    # Should have 0 relations for unrelated books
    assert len(result.relations) == 0, f"Expected 0 relations for unrelated books, got {len(result.relations)}"
    print("✓ Unrelated books produce 0 false-positive relations")

    return True


if __name__ == "__main__":
    thesis_results = test_thesis_alignment_precision_recall()
    argument_results = test_argument_alignment_precision_recall()
    unrelated_result = test_unrelated_books_zero_false_positives()

    print("\n=== Summary ===")
    thesis_correct = sum(1 for r in thesis_results if r["correct"])
    argument_correct = sum(1 for r in argument_results if r["correct"])
    print(f"Thesis gold cases: {thesis_correct}/{len(thesis_results)} correct")
    print(f"Argument gold cases: {argument_correct}/{len(argument_results)} correct")
    print(f"Unrelated books test: {'PASS' if unrelated_result else 'FAIL'}")