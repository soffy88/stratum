"""Book Understanding 2.0 - Core Domain Models (P1-P9)."""

import hashlib
from typing import Any, List, Optional, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator


def _stable_id(prefix: str, *parts: str) -> str:
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


# ── Enums ─────────────────────────────────────────────────────────────────────


class DiscourseRole(str, Enum):
    DEFINITION = "DEFINITION"
    CLAIM = "CLAIM"
    OBSERVATION = "OBSERVATION"
    EVIDENCE = "EVIDENCE"
    EXAMPLE = "EXAMPLE"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    ASSUMPTION = "ASSUMPTION"
    HYPOTHESIS = "HYPOTHESIS"
    QUALIFICATION = "QUALIFICATION"
    EXCEPTION = "EXCEPTION"
    OBJECTION = "OBJECTION"
    REBUTTAL = "REBUTTAL"
    APPLICATION = "APPLICATION"
    CONCLUSION = "CONCLUSION"
    QUESTION = "QUESTION"


class EpistemicRole(str, Enum):
    AUTHOR_ASSERTED = "AUTHOR_ASSERTED"
    AUTHOR_HYPOTHESIZED = "AUTHOR_HYPOTHESIZED"
    QUOTED_POSITION = "QUOTED_POSITION"
    HISTORICAL_POSITION = "HISTORICAL_POSITION"
    OPPONENT_POSITION = "OPPONENT_POSITION"
    AUTHOR_REJECTED = "AUTHOR_REJECTED"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class GapType(str, Enum):
    MISSING_KU = "MISSING_KU"
    BAD_BOUNDARY = "BAD_BOUNDARY"
    MISSING_CONTEXT = "MISSING_CONTEXT"
    STANCE_ERROR = "STANCE_ERROR"
    SCOPE_ERROR = "SCOPE_ERROR"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    ARGUMENT_GAP = "ARGUMENT_GAP"
    MECHANISM_GAP = "MECHANISM_GAP"
    CONCEPT_GAP = "CONCEPT_GAP"
    CROSS_CHAPTER_GAP = "CROSS_CHAPTER_GAP"
    VISUAL_GAP = "VISUAL_GAP"
    BU_SYNTHESIS_GAP = "BU_SYNTHESIS_GAP"
    CONTRADICTION = "CONTRADICTION"
    UNRESOLVED = "UNRESOLVED"


class VerificationStatus(str, Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"


class GapStatus(str, Enum):
    OPEN = "OPEN"
    TARGETED_REREAD_REQUIRED = "TARGETED_REREAD_REQUIRED"
    REREAD_IN_PROGRESS = "REREAD_IN_PROGRESS"
    TARGETED_REREAD_DISPATCHED = "TARGETED_REREAD_DISPATCHED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"
    WONTFIX = "WONTFIX"


class LearningImportance(str, Enum):
    CORE = "CORE"
    SUPPORTING = "SUPPORTING"
    PERIPHERAL = "PERIPHERAL"


class Difficulty(str, Enum):
    EASY = "EASY"
    MEDIUM = "MEDIUM"
    HARD = "HARD"


class InteractionType(str, Enum):
    FREE_RECALL = "FREE_RECALL"
    DEFINITION = "DEFINITION"
    EXPLAIN_WHY = "EXPLAIN_WHY"
    MINIMAL_PAIR = "MINIMAL_PAIR"
    EXAMPLE = "EXAMPLE"
    NON_EXAMPLE = "NON_EXAMPLE"
    RELATION_RECONSTRUCTION = "RELATION_RECONSTRUCTION"
    ARGUMENT_RECONSTRUCTION = "ARGUMENT_RECONSTRUCTION"
    PREDICT = "PREDICT"
    COUNTERFACTUAL = "COUNTERFACTUAL"
    SOLVE = "SOLVE"
    APPLY = "APPLY"
    TEACH_BACK = "TEACH_BACK"
    TRANSFER = "TRANSFER"


class BUStatus(str, Enum):
    DRAFT = "DRAFT"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class PipelineRunState(str, Enum):
    CREATED = "CREATED"
    PERCEIVED = "PERCEIVED"
    INSPECTED = "INSPECTED"
    DEEP_READ_COMPLETE = "DEEP_READ_COMPLETE"
    CHAPTER_MODELLED = "CHAPTER_MODELLED"
    BOOK_INTEGRATED = "BOOK_INTEGRATED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    COMPRESSION_TESTED = "COMPRESSION_TESTED"
    FAILED = "FAILED"


# ── P1 / P2: Evidence & KU 2.0 ────────────────────────────────────────────────


class Scope(BaseModel):
    population: str = ""
    temporal: str = ""
    spatial: str = ""
    domain: str = ""


class KU20Extensions(BaseModel):
    discourse_role: Optional[DiscourseRole] = None
    argument_role: str = ""
    epistemic_role: Optional[EpistemicRole] = None
    speaker: str = ""
    modality: str = ""
    quantifier: str = ""
    scope: Scope = Field(default_factory=Scope)
    conditions: List[str] = Field(default_factory=list)
    qualifiers: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    mechanism_ref: str = ""
    grounding_status: str = "unverified"
    context_status: str = "unverified"


class EvidenceTrajectory(BaseModel):
    id: str
    claim_id: str
    source_pages: List[int] = Field(default_factory=list)
    evidence_regions: List[str] = Field(default_factory=list)
    extracted_facts: List[str] = Field(default_factory=list)
    ku_refs: List[str] = Field(default_factory=list)
    reasoning_steps: List[str] = Field(default_factory=list)
    final_interpretation: str = ""
    verification_status: VerificationStatus = VerificationStatus.PENDING


class VisualSemanticUnit(BaseModel):
    id: str
    type: str
    variables: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    relations: List[str] = Field(default_factory=list)
    trends: List[str] = Field(default_factory=list)
    comparisons: List[str] = Field(default_factory=list)
    textual_claims_supported: List[str] = Field(default_factory=list)
    ku_refs: List[str] = Field(default_factory=list)
    argument_refs: List[str] = Field(default_factory=list)


# ── P3: Explanation Structure ──────────────────────────────────────────────────


class Argument(BaseModel):
    id: str
    question: str
    premises: List[str] = Field(default_factory=list)
    warrants: List[str] = Field(default_factory=list)
    inference_steps: List[str] = Field(default_factory=list)
    objections: List[str] = Field(default_factory=list)
    rebuttals: List[str] = Field(default_factory=list)
    qualifiers: List[str] = Field(default_factory=list)
    conclusion: List[str] = Field(default_factory=list)
    ku_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)


class AuthorMechanism(BaseModel):
    id: str
    trigger_event: str
    actors: List[str] = Field(default_factory=list)
    variables: List[str] = Field(default_factory=list)
    inputs: List[str] = Field(default_factory=list)
    mediators: List[str] = Field(default_factory=list)
    state_changes: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    exceptions: List[str] = Field(default_factory=list)
    failure_conditions: List[str] = Field(default_factory=list)
    explicitness: str


class SituationModel(BaseModel):
    id: str
    entities: List[str] = Field(default_factory=list)
    states: List[str] = Field(default_factory=list)
    variables: List[str] = Field(default_factory=list)
    relations: List[str] = Field(default_factory=list)
    causal_links: List[str] = Field(default_factory=list)
    temporal_links: List[str] = Field(default_factory=list)
    mechanism_refs: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    boundary_conditions: List[str] = Field(default_factory=list)


# ── P4 & P5 JSON Structured Sub-Models ─────────────────────────────────────────


class EvidenceProgramItem(BaseModel):
    claim_ref: str
    evidence_refs: List[str]
    is_supported: bool


class ArgumentArchitecture(BaseModel):
    root_arguments: List[str] = Field(default_factory=list)
    supporting_arguments: List[str] = Field(default_factory=list)


class ChapterDependency(BaseModel):
    source_chapter: str
    target_chapter: str
    relation: str  # e.g. REQUIRES, DEFINES_FOR, SUPPORTS, EVIDENCES, QUALIFIES, CHALLENGES


class ChapterDependencyGraph(BaseModel):
    dependencies: List[ChapterDependency] = Field(default_factory=list)


class DiscourseArcStep(BaseModel):
    step_type: str  # Problem, Definitions, Model, Evidence, etc.
    description: str
    chapter_ref: str


class DiscourseArc(BaseModel):
    steps: List[DiscourseArcStep] = Field(default_factory=list)


class NegativeKnowledge(BaseModel):
    rejected_claims: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    open_problems: List[str] = Field(default_factory=list)
    unresolved_conflicts: List[str] = Field(default_factory=list)


class ConceptEvolutionStep(BaseModel):
    concept_ref: str
    version: int
    definition: str
    chapter_ref: str
    evolution_type: str  # REFINE, QUALIFY, REVISE


class ClaimEvolutionStep(BaseModel):
    claim_ref: str
    version: int
    statement: str
    chapter_ref: str
    evolution_type: str


# ── P4 & P5: Chapter Understanding and BU 2.0 ──────────────────────────────────


class ChapterUnderstanding(BaseModel):
    id: str
    run_id: str
    chapter_id: str
    chapter_question: str = ""
    chapter_goal: str = ""
    chapter_thesis: str = ""
    primary_role: str = ""
    secondary_roles: List[str] = Field(default_factory=list)
    concepts_introduced_refs: List[str] = Field(default_factory=list)
    concepts_redefined_refs: List[str] = Field(default_factory=list)
    major_ku_refs: List[str] = Field(default_factory=list)
    supporting_ku_refs: List[str] = Field(default_factory=list)
    arguments_refs: List[str] = Field(default_factory=list)
    mechanisms_refs: List[str] = Field(default_factory=list)
    evidence_program: List[EvidenceProgramItem] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)
    dependencies_on_prior: List[str] = Field(default_factory=list)
    promises_to_future: List[str] = Field(default_factory=list)
    # P12 §11: evidence_id -> strength in {DIRECT, DEFINITION, EXAMPLE,
    # DERIVED, MODEL_INFERENCE}. Additive with a default, so every existing
    # ChapterUnderstanding still validates.
    evidence_strengths: Dict[str, str] = Field(default_factory=dict)
    # Task C: concept label -> the definition text the book gives it. Additive
    # with a default so the concept-evolution layer can carry a real definition
    # instead of the placeholder "introduced or redefined in chX".
    concept_definitions: Dict[str, str] = Field(default_factory=dict)
    # The chapter's own reconstructed arguments (theorem -> proof -> use).
    # ``arguments_refs`` holds their ids; the objects ride along so the runner
    # can persist them to ``arguments`` and the argument analyzer can turn each
    # into a chain. Not a column of chapter_understandings.
    chapter_arguments: List[Argument] = Field(default_factory=list)


class ChapterDelta(BaseModel):
    id: str
    run_id: str
    chapter_id: str
    new_concepts_refs: List[str] = Field(default_factory=list)
    revised_concepts_refs: List[str] = Field(default_factory=list)
    new_claims_refs: List[str] = Field(default_factory=list)
    new_arguments_refs: List[str] = Field(default_factory=list)
    supports_prior_refs: List[str] = Field(default_factory=list)
    qualifies_prior_refs: List[str] = Field(default_factory=list)
    contradicts_prior_refs: List[str] = Field(default_factory=list)
    revises_prior_refs: List[str] = Field(default_factory=list)
    resolves_questions: List[str] = Field(default_factory=list)
    opens_questions: List[str] = Field(default_factory=list)


class BookUnderstandingV2(BaseModel):
    id: str
    run_id: str
    book_id: str
    substrate_id: str
    version: int = 1
    status: BUStatus = BUStatus.DRAFT
    genre: str = ""
    governing_questions: List[str] = Field(default_factory=list)
    central_theses: List[str] = Field(default_factory=list)
    sub_theses: List[str] = Field(default_factory=list)
    concept_system: Dict[str, Any] = Field(default_factory=dict)
    situation_model_ref: str = ""
    argument_architecture: ArgumentArchitecture = Field(default_factory=ArgumentArchitecture)
    chapter_dependency_graph: ChapterDependencyGraph = Field(default_factory=ChapterDependencyGraph)
    discourse_arc: DiscourseArc = Field(default_factory=DiscourseArc)
    negative_knowledge: NegativeKnowledge = Field(default_factory=NegativeKnowledge)
    concept_evolution: List[ConceptEvolutionStep] = Field(default_factory=list)
    claim_evolution: List[ClaimEvolutionStep] = Field(default_factory=list)
    resolved_questions: List[str] = Field(default_factory=list)
    unresolved_questions: List[str] = Field(default_factory=list)
    coverage_score: float = 0.0
    verification_score: float = 0.0
    # Task C: True when the governing questions / theses were derived from the
    # chapters rather than read by the model. Kept honest: a derived framing is
    # real content, but it is weaker than a model's reading, so the quality model
    # reports it as a gap rather than counting it as full book-level framing.
    framing_derived: bool = False

    # P12 §9: the ids of the reasoning artefacts persisted alongside this BU.
    # Nullable because a BU produced before P12 has none, and that should read
    # as "produced before P12" rather than as corruption.
    reasoning_graph_id: Optional[str] = None
    concept_evolution_id: Optional[str] = None
    argument_graph_id: Optional[str] = None


# ── P6: Verification ───────────────────────────────────────────────────────────


class UnderstandingGap(BaseModel):
    id: str
    run_id: str
    type: GapType
    severity: Severity
    affected_component: str = ""
    question: str
    evidence_targets: List[str] = Field(default_factory=list)
    required_action: str = ""
    status: GapStatus = GapStatus.OPEN


# ── P8 & P9: Learning ──────────────────────────────────────────────────────────


class LearningObject(BaseModel):
    id: str
    bu_id: str
    run_id: str = ""
    book_id: str = ""
    learning_goal: str
    knowledge_type: str
    importance: LearningImportance
    difficulty: Difficulty
    target_refs: List[str] = Field(default_factory=list)
    prerequisites_refs: List[str] = Field(default_factory=list)
    mastery_requirements: List[str] = Field(default_factory=list)
    assessment_modes: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)


class LearningGraphNode(BaseModel):
    learning_object_ref: str


class LearningGraphEdge(BaseModel):
    source_ref: str
    target_ref: str
    relation: str


class LearningGraph(BaseModel):
    id: str
    bu_id: str
    version: int = 1
    nodes: List[LearningGraphNode] = Field(default_factory=list)
    edges: List[LearningGraphEdge] = Field(default_factory=list)


class InteractionPayload(BaseModel):
    question: str = ""
    options: List[str] = Field(default_factory=list)
    expected_answer: str = ""


class RetrievalItem(BaseModel):
    id: str
    learning_object_id: str
    interaction_type: InteractionType
    payload: InteractionPayload = Field(default_factory=InteractionPayload)


# ── P6: Verification Artifact ──────────────────────────────────────────────────


class VerificationOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"


class VerificationArtifact(BaseModel):
    id: str
    run_id: str
    book_id: str
    status: VerificationOutcome
    checked_artifacts: List[str] = Field(default_factory=list)
    unresolved_gap_count: int
    verification_timestamp: str


# ── P3: UnderstandingFrontier (table stratum.understanding_frontiers, 054) ────


class FrontierType(str, Enum):
    CLAIM_AWAITING_EVIDENCE = "CLAIM_AWAITING_EVIDENCE"
    QUESTION_AWAITING_ANSWER = "QUESTION_AWAITING_ANSWER"
    CONCEPT_AWAITING_DEFINITION = "CONCEPT_AWAITING_DEFINITION"
    MECHANISM_AWAITING_COMPLETION = "MECHANISM_AWAITING_COMPLETION"
    OBJECTION_AWAITING_REBUTTAL = "OBJECTION_AWAITING_REBUTTAL"
    REFERENCE_AWAITING_EXPLANATION = "REFERENCE_AWAITING_EXPLANATION"
    PROMISE_AWAITING_FULFILLMENT = "PROMISE_AWAITING_FULFILLMENT"


class FrontierStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    SUPPORTED = "SUPPORTED"
    QUALIFIED = "QUALIFIED"
    REVISED = "REVISED"
    CONTRADICTED = "CONTRADICTED"
    REJECTED = "REJECTED"


class FrontierResolution(str, Enum):
    RESOLVE = "RESOLVE"
    SUPPORT = "SUPPORT"
    QUALIFY = "QUALIFY"
    REVISE = "REVISE"
    CONTRADICT = "CONTRADICT"
    REJECT = "REJECT"


class UnderstandingFrontier(BaseModel):
    id: str
    run_id: str
    type: FrontierType
    description: str = ""
    status: FrontierStatus = FrontierStatus.OPEN
    resolution_refs: List[str] = Field(default_factory=list)


# ── P4: WorkingBU (§35: BU(t+1) = Apply(BU(t), ChapterDelta(t+1))) ────────────


class WorkingBU(BaseModel):
    id: str
    run_id: str
    book_id: str = ""
    chapter_index: int = 0
    version: int = 0
    governing_questions: List[str] = Field(default_factory=list)
    central_theses: List[str] = Field(default_factory=list)
    concept_refs: List[str] = Field(default_factory=list)
    claim_refs: List[str] = Field(default_factory=list)
    argument_refs: List[str] = Field(default_factory=list)
    mechanism_refs: List[str] = Field(default_factory=list)
    qualified_claims: List[str] = Field(default_factory=list)
    revised_claims: List[str] = Field(default_factory=list)
    contradicted_claims: List[str] = Field(default_factory=list)
    open_questions: List[str] = Field(default_factory=list)
    resolved_questions: List[str] = Field(default_factory=list)
    applied_delta_refs: List[str] = Field(default_factory=list)


# ── P5: statement provenance (§§39-41) + multi-resolution (§§46-47) ───────────


class StatementProvenance(str, Enum):
    AUTHOR_EXPLICIT = "AUTHOR_EXPLICIT"
    AUTHOR_SYNTHESIZED = "AUTHOR_SYNTHESIZED"
    STRATUM_DERIVED = "STRATUM_DERIVED"


class BUStatement(BaseModel):
    id: str
    statement: str
    provenance: StatementProvenance
    source_refs: List[str] = Field(default_factory=list)
    synthesis_trace: str = ""
    derived_from_ku_refs: List[str] = Field(default_factory=list)
    argument_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    derivation_reason: str = ""
    confidence: float = 0.0


class ResolutionLevel(str, Enum):
    ROOT = "ROOT"
    BRANCH = "BRANCH"
    LEAF = "LEAF"


class ResolutionNode(BaseModel):
    node_id: str
    level: ResolutionLevel
    label: str = ""
    bu_refs: List[str] = Field(default_factory=list)
    ku_refs: List[str] = Field(default_factory=list)
    evidence_refs: List[str] = Field(default_factory=list)
    centrality: float = 0.0


class BUVerificationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    PARTIAL = "PARTIAL"
    QUALIFIED = "QUALIFIED"
    VERIFIED = "VERIFIED"


# ── P6: challenge suite objects (§§54-58, §§117-118) ──────────────────────────


class AblationVerdict(str, Enum):
    ARGUMENT_INVALID = "ARGUMENT_INVALID"
    SUPPORT_WEAKENED = "SUPPORT_WEAKENED"
    NO_MEANINGFUL_EFFECT = "NO_MEANINGFUL_EFFECT"


class AblationResult(BaseModel):
    target: str
    target_type: str = ""
    impacted_theses: List[str] = Field(default_factory=list)
    broken_arguments: List[str] = Field(default_factory=list)
    verdict: AblationVerdict = AblationVerdict.NO_MEANINGFUL_EFFECT
    detail: str = ""


class MutationType(str, Enum):
    WRONG_STANCE = "WRONG_STANCE"
    WRONG_QUANTIFIER = "WRONG_QUANTIFIER"
    MISSING_CONDITION = "MISSING_CONDITION"
    REVERSED_CAUSALITY = "REVERSED_CAUSALITY"
    WRONG_CHAPTER_RELATION = "WRONG_CHAPTER_RELATION"
    FAKE_EVIDENCE = "FAKE_EVIDENCE"
    OVERSTATED_CONCLUSION = "OVERSTATED_CONCLUSION"


class MutationCase(BaseModel):
    id: str
    mutation_type: MutationType
    target_ref: str
    original_statement: str = ""
    mutated_statement: str = ""
    expected: str = "REJECT"


class MutationVerdict(BaseModel):
    case_id: str
    rejected: bool
    reason: str = ""


class HoldoutItem(BaseModel):
    holdout_id: str
    category: str = ""
    probe_question: str = ""
    required_refs: List[str] = Field(default_factory=list)


class MinimalPairCase(BaseModel):
    id: str
    side_a: str
    side_b: str
    distinction: str = ""


# ── P7: projection contract (§§64-67, §79 uses LearningObject) ────────────────


class ExpressionProfile(BaseModel):
    purpose: str
    audience: str = ""
    duration: str = ""
    depth: str = ""
    modality: str = ""
    required_bu_facets: List[str] = Field(default_factory=list)
    required_ku_types: List[str] = Field(default_factory=list)
    evidence_policy: str = "traceable"
    compression_policy: str = "centrality"
    interaction_policy: str = "view"


class CompressionLoss(BaseModel):
    omitted_concepts: List[str] = Field(default_factory=list)
    omitted_arguments: List[str] = Field(default_factory=list)
    omitted_evidence: List[str] = Field(default_factory=list)
    omitted_boundaries: List[str] = Field(default_factory=list)
    thesis_preserved: bool = False
    mechanism_preserved: bool = False
    stance_preserved: bool = False


class ProjectedArtifact(BaseModel):
    artifact_id: str
    bu_id: str
    kind: str
    thesis: str = ""
    content_refs: List[str] = Field(default_factory=list)
    compression_loss: CompressionLoss = Field(default_factory=CompressionLoss)
    fidelity_checks: Dict[str, bool] = Field(default_factory=dict)


# ── P8: compiled path (§82) ───────────────────────────────────────────────────


class LearningPath(BaseModel):
    id: str
    bu_id: str = ""
    graph_id: str = ""
    goal: str = ""
    time_budget_min: int = 0
    ordered_lo_refs: List[str] = Field(default_factory=list)
    rationale: str = ""


# ── P9: tutor + errors (§§91-93) + mastery dimensions (§86, derived view) ──────


class TutorState(str, Enum):
    SELECT_OBJECTIVE = "SELECT_OBJECTIVE"
    DIAGNOSE = "DIAGNOSE"
    TEACH = "TEACH"
    GUIDED_EXAMPLE = "GUIDED_EXAMPLE"
    ACTIVE_RESPONSE = "ACTIVE_RESPONSE"
    JUDGE = "JUDGE"
    TRANSFER = "TRANSFER"
    REMEDIATE = "REMEDIATE"
    MASTERY = "MASTERY"
    NEXT = "NEXT"


class TutorSession(BaseModel):
    session_id: str
    bu_id: str = ""
    current_state: TutorState = TutorState.SELECT_OBJECTIVE
    objective_ref: str = ""
    history: List[str] = Field(default_factory=list)


class ErrorKind(str, Enum):
    KNOWLEDGE_STRUCTURAL = "knowledge_structural"
    UNDERSTANDING_DEVIATION = "understanding_deviation"
    APPLICATION_ERROR = "application_error"
    METACOGNITIVE = "metacognitive"


class MisconceptionCandidate(BaseModel):
    answer: str = ""
    correctness: bool = False
    confidence_before_answer: float = 0.0
    is_candidate: bool = False
    strategy: str = ""


class MasteryDimensions(BaseModel):
    """Derived assessment view only — never persisted as mastery authority.
    The sole mastery authority remains cx.learning_progress."""

    ref: str = ""
    recognition: float = 0.0
    recall: float = 0.0
    explanation: float = 0.0
    discrimination: float = 0.0
    application: float = 0.0
    transfer: float = 0.0
    stability: float = 0.0
    confidence: float = 0.0


# ── Benchmark gold (§§113-118) + baselines (§119) ─────────────────────────────


class BookGold(BaseModel):
    book_id: str
    genre: str = ""
    governing_questions: List[str] = Field(default_factory=list)
    central_theses: List[str] = Field(default_factory=list)
    critical_ku_refs: List[str] = Field(default_factory=list)
    major_arguments: List[str] = Field(default_factory=list)
    chapter_roles: Dict[str, str] = Field(default_factory=dict)
    cross_chapter_deps: List[str] = Field(default_factory=list)
    qualifications: List[str] = Field(default_factory=list)
    revisions: List[str] = Field(default_factory=list)
    mechanisms: List[str] = Field(default_factory=list)
    visual_evidence: List[str] = Field(default_factory=list)
    negative_knowledge: List[str] = Field(default_factory=list)


class ResolutionGold(BaseModel):
    book_id: str
    root: List[str] = Field(default_factory=list)
    branch: List[str] = Field(default_factory=list)
    leaf_sample: List[str] = Field(default_factory=list)


class EvidenceGold(BaseModel):
    question: str = ""
    required_pages: List[int] = Field(default_factory=list)
    required_regions: List[str] = Field(default_factory=list)
    required_facts: List[str] = Field(default_factory=list)
    required_ku: List[str] = Field(default_factory=list)
    expected_reasoning_relation: str = ""


class BaselineKind(str, Enum):
    B0_CHUNK_RAG = "B0_CHUNK_RAG"
    B1_WHOLE_CONTEXT_LLM = "B1_WHOLE_CONTEXT_LLM"
    B2_CHAPTER_SUMMARY_BOOK_SUMMARY = "B2_CHAPTER_SUMMARY_BOOK_SUMMARY"
    B3_PAGE_KU_EXTRACTION = "B3_PAGE_KU_EXTRACTION"
    B4_CURRENT_STRATUM = "B4_CURRENT_STRATUM"
    B5_BU_1_1 = "B5_BU_1_1"
    B6_BU_2_0 = "B6_BU_2_0"


class MetricScore(BaseModel):
    metric: str
    score: float = 0.0
    detail: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# P13: Book-Level Synthesis Models
# ═══════════════════════════════════════════════════════════════════════════════


class ThesisType(str, Enum):
    CORE = "CORE"
    SUPPORTING = "SUPPORTING"
    PROBLEM = "PROBLEM"
    QUESTION = "QUESTION"
    ASSUMPTION = "ASSUMPTION"
    CONCLUSION = "CONCLUSION"
    LIMITATION = "LIMITATION"


class ThesisProvenance(str, Enum):
    AUTHOR_ASSERTED = "AUTHOR_ASSERTED"
    MODEL_INFERRED = "MODEL_INFERRED"
    STRUCTURALLY_DERIVED = "STRUCTURALLY_DERIVED"


class ArgumentStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    MODEL_INFERRED = "MODEL_INFERRED"
    UNRESOLVED = "UNRESOLVED"
    CONTRADICTED = "CONTRADICTED"


class EvidenceStrengthP13(str, Enum):
    DIRECT = "DIRECT"
    DEFINITION = "DEFINITION"
    EXAMPLE = "EXAMPLE"
    DERIVED = "DERIVED"
    MODEL_INFERENCE = "MODEL_INFERENCE"


class ContradictionType(str, Enum):
    DIRECT_CONTRADICTION = "DIRECT_CONTRADICTION"
    CONTEXTUAL_DIFFERENCE = "CONTEXTUAL_DIFFERENCE"
    APPARENT_CONTRADICTION = "APPARENT_CONTRADICTION"
    UNRESOLVED = "UNRESOLVED"


class ChapterRole(str, Enum):
    FOUNDATION = "FOUNDATION"
    DEFINITION = "DEFINITION"
    DEVELOPMENT = "DEVELOPMENT"
    ARGUMENT = "ARGUMENT"
    EVIDENCE = "EVIDENCE"
    APPLICATION = "APPLICATION"
    COUNTERPOINT = "COUNTERPOINT"
    SYNTHESIS = "SYNTHESIS"
    CONCLUSION = "CONCLUSION"
    BRIDGE = "BRIDGE"


class ConceptRole(str, Enum):
    FOUNDATIONAL = "FOUNDATIONAL"
    CORE = "CORE"
    DERIVED = "DERIVED"
    BRIDGING = "BRIDGING"
    APPLICATION = "APPLICATION"
    TERMINAL = "TERMINAL"


class BookThesis(BaseModel):
    """A single thesis claim with full traceability."""

    id: str
    type: ThesisType
    statement: str
    scope: str = ""
    evidence_refs: List[str] = Field(default_factory=list)
    supporting_arguments: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED
    source_locations: List[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, round(v, 4)))


class BookThesisModel(BaseModel):
    """The complete thesis structure of the book."""

    core_thesis: Optional[BookThesis] = None
    supporting_theses: List[BookThesis] = Field(default_factory=list)
    problem_statements: List[BookThesis] = Field(default_factory=list)
    central_questions: List[BookThesis] = Field(default_factory=list)
    key_assumptions: List[BookThesis] = Field(default_factory=list)
    conclusions: List[BookThesis] = Field(default_factory=list)
    limitations: List[BookThesis] = Field(default_factory=list)

    def all_theses(self) -> List[BookThesis]:
        out = []
        if self.core_thesis:
            out.append(self.core_thesis)
        out.extend(self.supporting_theses)
        out.extend(self.problem_statements)
        out.extend(self.central_questions)
        out.extend(self.key_assumptions)
        out.extend(self.conclusions)
        out.extend(self.limitations)
        return out


class ConceptSystemEntry(BaseModel):
    """One concept in the book's concept system."""

    concept_id: str
    label: str
    definition: str
    role: ConceptRole
    prerequisites: List[str] = Field(default_factory=list)
    related_concepts: List[str] = Field(default_factory=list)
    refined_by: List[str] = Field(default_factory=list)
    applied_in: List[str] = Field(default_factory=list)
    supports: List[str] = Field(default_factory=list)
    chapter_refs: List[str] = Field(default_factory=list)
    final_role: str = ""
    confidence: float = 0.0


class BookConceptSystem(BaseModel):
    """The book's complete concept system with roles and dependencies."""

    foundational: List[ConceptSystemEntry] = Field(default_factory=list)
    core: List[ConceptSystemEntry] = Field(default_factory=list)
    derived: List[ConceptSystemEntry] = Field(default_factory=list)
    bridging: List[ConceptSystemEntry] = Field(default_factory=list)
    application: List[ConceptSystemEntry] = Field(default_factory=list)
    terminal: List[ConceptSystemEntry] = Field(default_factory=list)

    def all_concepts(self) -> List[ConceptSystemEntry]:
        out = []
        out.extend(self.foundational)
        out.extend(self.core)
        out.extend(self.derived)
        out.extend(self.bridging)
        out.extend(self.application)
        out.extend(self.terminal)
        return out

    def get_by_id(self, concept_id: str) -> Optional[ConceptSystemEntry]:
        for c in self.all_concepts():
            if c.concept_id == concept_id:
                return c
        return None


class BookArgument(BaseModel):
    """A major or sub-argument in the book's argument hierarchy."""

    id: str
    level: int  # 0=thesis, 1=major, 2=sub, etc.
    what: str
    why: str
    how: str
    evidence_refs: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    conclusion: str = ""
    status: ArgumentStatus = ArgumentStatus.MODEL_INFERRED
    confidence: float = 0.0
    source_chapters: List[str] = Field(default_factory=list)


class BookArgumentSystem(BaseModel):
    """The book's complete argument hierarchy."""

    thesis_arguments: List[BookArgument] = Field(default_factory=list)
    major_arguments: List[BookArgument] = Field(default_factory=list)
    sub_arguments: List[BookArgument] = Field(default_factory=list)

    def all_arguments(self) -> List[BookArgument]:
        out = []
        out.extend(self.thesis_arguments)
        out.extend(self.major_arguments)
        out.extend(self.sub_arguments)
        return out


class BookMechanism(BaseModel):
    """A causal/explanatory mechanism identified in the book."""

    id: str
    trigger: str
    precondition: str
    operation: str
    intermediate_state: str
    outcome: str
    evidence_refs: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED
    source_chapters: List[str] = Field(default_factory=list)


class BookMechanismSystem(BaseModel):
    """All mechanisms identified in the book."""

    mechanisms: List[BookMechanism] = Field(default_factory=list)


class EvidenceMapEntry(BaseModel):
    """One claim-evidence-argument-chapter linkage."""

    claim_id: str
    claim_statement: str
    evidence_ids: List[str] = Field(default_factory=list)
    evidence_strengths: Dict[str, EvidenceStrengthP13] = Field(default_factory=dict)
    argument_ids: List[str] = Field(default_factory=list)
    chapter_ids: List[str] = Field(default_factory=list)
    is_supported: bool = False
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class BookEvidenceMap(BaseModel):
    """Complete claim-evidence-argument-chapter map for the book."""

    entries: List[EvidenceMapEntry] = Field(default_factory=list)
    evidence_coverage: float = 0.0
    unsupported_claim_count: int = 0
    model_inference_ratio: float = 0.0
    contradiction_count: int = 0


class BookAuthorModel(BaseModel):
    """Structured model of the author's intellectual stance."""

    worldview: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    explanatory_strategy: List[str] = Field(default_factory=list)
    argument_style: List[str] = Field(default_factory=list)
    recurring_patterns: List[str] = Field(default_factory=list)
    evidence_preference: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    unresolved_positions: List[str] = Field(default_factory=list)
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class ChapterRoleAssignment(BaseModel):
    """One chapter's role(s) in the book."""

    chapter_id: str
    roles: List[ChapterRole] = Field(default_factory=list)
    evidence: str = ""
    confidence: float = 0.0


class BookChapterRoles(BaseModel):
    """All chapter role assignments."""

    assignments: List[ChapterRoleAssignment] = Field(default_factory=list)

    def get_roles(self, chapter_id: str) -> List[ChapterRole]:
        for a in self.assignments:
            if a.chapter_id == chapter_id:
                return a.roles
        return []


class ContradictionEntry(BaseModel):
    """A detected contradiction or tension."""

    id: str
    type: ContradictionType
    element_a: str  # claim_id, concept_id, or argument_id
    element_b: str
    element_type: str  # "claim", "concept", "argument"
    description: str
    classification: ContradictionType
    source_chapters: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class BookContradictions(BaseModel):
    """All detected contradictions in the book."""

    contradictions: List[ContradictionEntry] = Field(default_factory=list)


class BookSynthesis(BaseModel):
    """The final book-level synthesis."""

    id: str
    run_id: str
    book_id: str
    thesis: BookThesisModel
    problem_definition: str
    concept_system: BookConceptSystem
    argument_system: BookArgumentSystem
    mechanism_system: BookMechanismSystem
    evidence_map: BookEvidenceMap
    author_model: BookAuthorModel
    chapter_roles: BookChapterRoles
    unresolved_questions: List[str] = Field(default_factory=list)
    contradictions: BookContradictions
    limitations: List[str] = Field(default_factory=list)
    synthesis_evidence: Dict[str, List[str]] = Field(default_factory=dict)
    created_at: str = ""


# ═══════════════════════════════════════════════════════════════════════════════
# P14: Cross-Book Intelligence Models
# ═══════════════════════════════════════════════════════════════════════════════


class CrossBookConceptRelationType(str, Enum):
    """Types of relations between concepts across books."""

    SAME_CONCEPT = "SAME_CONCEPT"
    RELATED_CONCEPT = "RELATED_CONCEPT"
    SUBSUMES = "SUBSUMES"
    SPECIALIZES = "SPECIALIZES"
    ANALOGOUS = "ANALOGOUS"
    DISTINCT = "DISTINCT"
    SAME_TERM_DIFFERENT_MEANING = "SAME_TERM_DIFFERENT_MEANING"
    UNKNOWN = "UNKNOWN"


class CrossBookThesisRelationType(str, Enum):
    """Types of relations between theses across books."""

    SUPPORTS = "SUPPORTS"
    EXTENDS = "EXTENDS"
    QUALIFIES = "QUALIFIES"
    CONTRADICTS = "CONTRADICTS"
    COMPLEMENTS = "COMPLEMENTS"
    ALTERNATIVE = "ALTERNATIVE"
    ORTHOGONAL = "ORTHOGONAL"
    RELATED = "RELATED"
    UNKNOWN = "UNKNOWN"


class CrossBookClaimRelationType(str, Enum):
    """Types of relations between claims across books."""

    SAME_CLAIM = "SAME_CLAIM"
    RELATED_CLAIM = "RELATED_CLAIM"
    CONTRADICTORY_CLAIM = "CONTRADICTORY_CLAIM"
    SCOPE_SPECIFIC = "SCOPE_SPECIFIC"
    UNKNOWN = "UNKNOWN"


class CrossBookArgumentRelationType(str, Enum):
    """Types of relations between arguments across books."""

    SUPPORTS = "SUPPORTS"
    CHALLENGES = "CHALLENGES"
    EXTENDS = "EXTENDS"
    REFINES = "REFINES"
    CONTRADICTS = "CONTRADICTS"
    GENERALIZES = "GENERALIZES"
    SPECIALIZES = "SPECIALIZES"
    APPLIES = "APPLIES"
    COMPLEMENTS = "COMPLEMENTS"
    COMPLEMENTARY = "COMPLEMENTARY"
    ALTERNATIVE = "ALTERNATIVE"
    INDEPENDENT = "INDEPENDENT"
    UNKNOWN = "UNKNOWN"


class CrossBookMechanismRelationType(str, Enum):
    """Types of relations between mechanisms across books."""

    SAME = "SAME"
    VARIANT = "VARIANT"
    COMPLEMENTARY = "COMPLEMENTARY"
    COMPETING = "COMPETING"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class CrossBookEvidenceRelationType(str, Enum):
    """Types of relations between evidence across books."""

    CONVERGENT = "CONVERGENT"
    DIVERGENT = "DIVERGENT"
    INDEPENDENT = "INDEPENDENT"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT = "INSUFFICIENT"
    UNKNOWN = "UNKNOWN"


class CrossBookContradictionType(str, Enum):
    """Types of cross-book contradictions."""

    DIRECT_CONTRADICTION = "DIRECT_CONTRADICTION"
    DEFINITIONAL_CONFLICT = "DEFINITIONAL_CONFLICT"
    SCOPE_CONFLICT = "SCOPE_CONFLICT"
    ASSUMPTION_CONFLICT = "ASSUMPTION_CONFLICT"
    EMPIRICAL_CONFLICT = "EMPIRICAL_CONFLICT"
    THEORETICAL_CONFLICT = "THEORETICAL_CONFLICT"
    APPARENT_CONTRADICTION = "APPARENT_CONTRADICTION"
    UNRESOLVED = "UNRESOLVED"


class CrossBookProblemRelationType(str, Enum):
    """Types of relations between problems across books."""

    SAME_PROBLEM = "SAME_PROBLEM"
    SUBPROBLEM = "SUBPROBLEM"
    SUPERPROBLEM = "SUPERPROBLEM"
    RELATED_PROBLEM = "RELATED_PROBLEM"
    ORTHOGONAL = "ORTHOGONAL"
    UNKNOWN = "UNKNOWN"


class CrossBookArgumentTransferType(str, Enum):
    """Types of argument transfer across books."""

    THEORY_TO_APPLICATION = "THEORY_TO_APPLICATION"
    FOUNDATION_TO_EXTENSION = "FOUNDATION_TO_EXTENSION"
    CONCEPT_TO_MECHANISM = "CONCEPT_TO_MECHANISM"
    THESIS_TO_CRITIQUE = "THESIS_TO_CRITIQUE"
    UNKNOWN = "UNKNOWN"


class KnowledgeGapType(str, Enum):
    """Types of knowledge gaps detected across books."""

    UNANSWERED = "UNANSWERED"
    WEAKLY_SUPPORTED = "WEAKLY_SUPPORTED"
    CONFLICTING = "CONFLICTING"
    MISSING_BRIDGE = "MISSING_BRIDGE"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    SCOPE_GAP = "SCOPE_GAP"
    BOOK_SET_LIMIT = "BOOK_SET_LIMIT"


class AuthorRelationType(str, Enum):
    """Types of author stance relations."""

    SHARED_ASSUMPTION = "SHARED_ASSUMPTION"
    DIFFERENT_ASSUMPTION = "DIFFERENT_ASSUMPTION"
    COMPETING_FRAMEWORK = "COMPETING_FRAMEWORK"
    COMPLEMENTARY_FRAMEWORK = "COMPLEMENTARY_FRAMEWORK"
    UNKNOWN = "UNKNOWN"


class CrossBookCollection(BaseModel):
    """A named collection of independently understood books for cross-book analysis."""

    collection_id: str = ""
    name: str
    description: str
    book_ids: List[str] = Field(default_factory=list)
    created_at: str = ""
    version: int = 1

    @model_validator(mode="before")
    @classmethod
    def _generate_collection_id(cls, data):
        if isinstance(data, dict) and not data.get("collection_id"):
            book_ids = data.get("book_ids", [])
            name = data.get("name", "")
            data["collection_id"] = _stable_id("coll", *sorted(book_ids), name)
        return data

    @model_validator(mode="after")
    def _validate_book_count(self):
        if len(self.book_ids) < 2:
            raise ValueError("Collection requires at least 2 books")
        return self


class CrossBookConcept(BaseModel):
    """A concept identified across multiple books with alignment metadata."""

    concept_id: str
    label: str
    definition: str
    source_books: List[Dict[str, Any]] = Field(default_factory=list)  # book_id, concept_ref, role
    alignment_confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookConceptRelation(BaseModel):
    """A relation between two concepts from different books."""

    relation_id: str
    source_book_id: str
    source_concept_id: str
    target_book_id: str
    target_concept_id: str
    relation: CrossBookConceptRelationType
    reason: str
    evidence: List[str] = Field(default_factory=list)  # evidence_refs from both books
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookConceptEvolution(BaseModel):
    """Cross-book concept evolution chain."""

    chain_id: str
    sequence: List[Dict[str, Any]] = Field(
        default_factory=list
    )  # book_id, concept_id, evolution_type
    evolution_types: List[str] = Field(default_factory=list)  # INTRODUCES, REFINES, EXTENDS, etc.
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookThesis(BaseModel):
    """A thesis from a book in cross-book context."""

    thesis_id: str
    book_id: str
    thesis_ref: str  # ref to BookThesis.id in that book's synthesis
    statement: str
    type: str  # CORE, SUPPORTING, etc.
    confidence: float
    provenance: ThesisProvenance


class CrossBookThesisRelation(BaseModel):
    """A relation between theses from different books."""

    relation_id: str
    source_thesis: CrossBookThesis
    target_thesis: CrossBookThesis
    relation: CrossBookThesisRelationType
    reason: str
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookClaim(BaseModel):
    """A claim from a book in cross-book context."""

    claim_id: str
    book_id: str
    claim_ref: str  # ref to EvidenceMapEntry.claim_id
    statement: str
    confidence: float
    is_supported: bool


class CrossBookClaimRelation(BaseModel):
    """A relation between claims from different books."""

    relation_id: str
    source_claim: CrossBookClaim
    target_claim: CrossBookClaim
    relation: CrossBookClaimRelationType
    reason: str
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookArgument(BaseModel):
    """An argument from a book in cross-book context."""

    argument_id: str
    book_id: str
    argument_ref: str  # ref to BookArgument.id
    level: int
    what: str
    why: str
    how: str
    conclusion: str
    evidence_refs: List[str] = Field(default_factory=list)
    status: ArgumentStatus
    confidence: float


class CrossBookArgumentRelation(BaseModel):
    """A relation between arguments from different books."""

    relation_id: str
    source_argument: CrossBookArgument
    target_argument: CrossBookArgument
    relation: CrossBookArgumentRelationType
    reason: str
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookArgumentTransfer(BaseModel):
    """A transfer of argument structure from one book to another."""

    transfer_id: str
    source_book_id: str
    source_argument_id: str
    target_book_id: str
    target_argument_id: str
    transfer_type: CrossBookArgumentTransferType
    reason: str
    confidence: float = 0.0


class CrossBookMechanism(BaseModel):
    """A mechanism from a book in cross-book context."""

    mechanism_id: str
    book_id: str
    mechanism_ref: str  # ref to BookMechanism.id
    trigger: str
    precondition: str
    operation: str
    outcome: str
    confidence: float


class CrossBookMechanismRelation(BaseModel):
    """A relation between mechanisms from different books."""

    relation_id: str
    source_mechanism: CrossBookMechanism
    target_mechanism: CrossBookMechanism
    relation: CrossBookMechanismRelationType
    reason: str
    evidence: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookEvidence(BaseModel):
    """Evidence from a book in cross-book context."""

    evidence_id: str
    book_id: str
    evidence_ref: str  # ref to original evidence
    claim_id: str
    locator: str
    strength: EvidenceStrengthP13


class CrossBookEvidenceRelation(BaseModel):
    """A relation between evidence from different books."""

    relation_id: str
    source_evidence: CrossBookEvidence
    target_evidence: CrossBookEvidence
    relation: CrossBookEvidenceRelationType
    reason: str
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookContradiction(BaseModel):
    """A contradiction detected across books."""

    contradiction_id: str
    type: CrossBookContradictionType
    book_a_id: str
    element_a: str
    book_b_id: str
    element_b: str
    element_type: str  # "claim", "concept", "argument", "thesis"
    description: str
    classification: CrossBookContradictionType
    confidence: float = 0.0
    provenance: ThesisProvenance = ThesisProvenance.MODEL_INFERRED


class CrossBookProblem(BaseModel):
    """A problem identified in a book in cross-book context."""

    problem_id: str
    book_id: str
    problem_ref: str  # ref to BookThesis (type PROBLEM) or ProblemStatement
    statement: str
    scope: str
    domain: str


class CrossBookProblemRelation(BaseModel):
    """A relation between problems from different books."""

    relation_id: str
    source_problem: CrossBookProblem
    target_problem: CrossBookProblem
    relation: CrossBookProblemRelationType
    reason: str
    confidence: float = 0.0


class CrossBookAuthorRelation(BaseModel):
    """A relation between author models from different books."""

    relation_id: str
    book_a_id: str
    book_b_id: str
    relation: AuthorRelationType
    dimension: str  # assumptions, worldview, strategy, style, evidence, limitations
    reason: str
    confidence: float = 0.0


class CrossBookKnowledgeGap(BaseModel):
    """A knowledge gap detected across the book collection."""

    gap_id: str
    type: KnowledgeGapType
    description: str
    affected_books: List[str] = Field(default_factory=list)
    missing_elements: List[str] = Field(default_factory=list)
    reason: str
    confidence: float = 0.0


class CrossBookComparison(BaseModel):
    """Complete comparison between two books."""

    comparison_id: str
    book_a_id: str
    book_b_id: str
    concept_relations: List[CrossBookConceptRelation] = Field(default_factory=list)
    thesis_relations: List[CrossBookThesisRelation] = Field(default_factory=list)
    argument_relations: List[CrossBookArgumentRelation] = Field(default_factory=list)
    mechanism_relations: List[CrossBookMechanismRelation] = Field(default_factory=list)
    evidence_relations: List[CrossBookEvidenceRelation] = Field(default_factory=list)
    contradictions: List[CrossBookContradiction] = Field(default_factory=list)
    problem_relations: List[CrossBookProblemRelation] = Field(default_factory=list)
    author_relations: List[CrossBookAuthorRelation] = Field(default_factory=list)


class CrossBookSynthesis(BaseModel):
    """The final cross-book synthesis."""

    synthesis_id: str
    collection_id: str
    common_ground: List[str] = Field(default_factory=list)
    major_differences: List[str] = Field(default_factory=list)
    concept_evolution: List[CrossBookConceptEvolution] = Field(default_factory=list)
    supporting_theories: List[str] = Field(default_factory=list)
    competing_theories: List[str] = Field(default_factory=list)
    evidence_convergence: List[str] = Field(default_factory=list)
    evidence_divergence: List[str] = Field(default_factory=list)
    unresolved_conflicts: List[CrossBookContradiction] = Field(default_factory=list)
    knowledge_gaps: List[CrossBookKnowledgeGap] = Field(default_factory=list)
    higher_order_synthesis: str = ""
    traceability: Dict[str, List[str]] = Field(default_factory=dict)
    created_at: str = ""


class CrossBookUnderstanding(BaseModel):
    """The top-level cross-book understanding object."""

    understanding_id: str
    collection: CrossBookCollection
    shared_problems: List[CrossBookProblem] = Field(default_factory=list)
    concept_system: List[CrossBookConcept] = Field(default_factory=list)
    concept_relations: List[CrossBookConceptRelation] = Field(default_factory=list)
    thesis_system: List[CrossBookThesis] = Field(default_factory=list)
    thesis_relations: List[CrossBookThesisRelation] = Field(default_factory=list)
    argument_system: List[CrossBookArgument] = Field(default_factory=list)
    argument_relations: List[CrossBookArgumentRelation] = Field(default_factory=list)
    mechanism_system: List[CrossBookMechanism] = Field(default_factory=list)
    mechanism_relations: List[CrossBookMechanismRelation] = Field(default_factory=list)
    evidence_system: List[CrossBookEvidence] = Field(default_factory=list)
    evidence_relations: List[CrossBookEvidenceRelation] = Field(default_factory=list)
    contradictions: List[CrossBookContradiction] = Field(default_factory=list)
    comparisons: List[CrossBookComparison] = Field(default_factory=list)
    knowledge_gaps: List[CrossBookKnowledgeGap] = Field(default_factory=list)
    synthesis: CrossBookSynthesis
    quality: Dict[str, Any] = Field(default_factory=dict)  # Q19-Q26 scores
