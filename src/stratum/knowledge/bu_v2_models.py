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
    TARGETED_REREAD_DISPATCHED = "TARGETED_REREAD_DISPATCHED"
    RECONCILED = "RECONCILED"
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

class ChapterDelta(BaseModel):
    id: str
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

# ── P6: Verification ───────────────────────────────────────────────────────────

class UnderstandingGap(BaseModel):
    id: str
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
