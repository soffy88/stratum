"""Book Understanding 2.0 - Core Domain Models (P1-P9)."""

from typing import Any, List, Optional, Dict
from enum import Enum
from pydantic import BaseModel, Field, field_validator

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
    relation: str # e.g. REQUIRES, DEFINES_FOR, SUPPORTS, EVIDENCES, QUALIFIES, CHALLENGES

class ChapterDependencyGraph(BaseModel):
    dependencies: List[ChapterDependency] = Field(default_factory=list)

class DiscourseArcStep(BaseModel):
    step_type: str # Problem, Definitions, Model, Evidence, etc.
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
    evolution_type: str # REFINE, QUALIFY, REVISE

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
