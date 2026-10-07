"""Book Understanding 2.0 - Repository Boundary Interfaces.

Contract: MODEL <-> REPOSITORY <-> SQL must stay consistent.
Rules:
- No blind model_dump() inserts: every save() maps fields explicitly.
- No silent persistence: DB errors always propagate, never `except: pass`.
- check_exists() answers existence only; schema/DB errors propagate.
"""

from typing import Optional, List, Any
import json
from stratum.db import execute, insert, query, update, read
from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, ChapterUnderstanding, ChapterDelta,
    UnderstandingGap, LearningObject, RetrievalItem, PipelineRunState,
    VisualSemanticUnit, VerificationArtifact, GapStatus, VerificationOutcome,
    Argument, AuthorMechanism, SituationModel, UnderstandingFrontier,
    EvidenceTrajectory, LearningGraph, FrontierType, FrontierStatus,
    VerificationStatus,
    BookThesis, BookThesisModel, BookConceptSystem, BookArgument,
    BookMechanism, BookEvidenceMap, BookAuthorModel, BookChapterRoles,
    BookContradictions, BookSynthesis, ThesisProvenance, ThesisType,
)


def _jload(value: Any, default: Any):
    """JSONB columns come back as raw strings (psycopg2 registered with
    identity loads); tolerate str / already-parsed / NULL."""
    if value is None:
        return default
    if isinstance(value, str):
        return json.loads(value) if value else default
    return value


class PipelineRunRepository:
    """Manages the lifecycle and state transitions of BookReadingRun."""

    @staticmethod
    def get_status(run_id: str) -> Optional[PipelineRunState]:
        row = read("book_reading_run", run_id)
        if row:
            return PipelineRunState(row["status"])
        return None

    @staticmethod
    def get_run(run_id: str) -> Optional[dict]:
        return read("book_reading_run", run_id)

    @staticmethod
    def update_status(run_id: str, new_status: PipelineRunState, failure_reason: Optional[str] = None):
        changes = {"status": new_status.value, "updated_at": "now()"}
        if failure_reason:
            changes["failure_reason"] = failure_reason
        update("book_reading_run", run_id, changes)

    @staticmethod
    def check_reading_ledger_exists(run_id: str) -> bool:
        # P0 gate: full-source accounting ledger rows persisted for this run.
        res = query("SELECT 1 FROM reading_ledger WHERE run_id = %(run_id)s LIMIT 1", {"run_id": run_id})
        return len(res) > 0

    # P1 gate: inspection is durable only when at least one ledger item has
    # moved past machine parse into an inspected reading state.
    INSPECTED_LEDGER_STATUSES = ("READ", "INTERPRETED", "RECONCILED", "VERIFIED")

    @staticmethod
    def check_inspection_exists(run_id: str) -> bool:
        res = query(
            "SELECT 1 FROM reading_ledger WHERE run_id = %(run_id)s "
            "AND status IN ('READ', 'INTERPRETED', 'RECONCILED', 'VERIFIED') LIMIT 1",
            {"run_id": run_id},
        )
        return len(res) > 0

    # P2 gate: deep-read output (explanation structure) persisted for this run.
    @staticmethod
    def check_deep_read_exists(run_id: str) -> bool:
        params = {"run_id": run_id}
        for table in ("arguments", "author_mechanisms", "situation_models"):
            res = query(f"SELECT 1 FROM {table} WHERE run_id = %(run_id)s LIMIT 1", params)
            if len(res) > 0:
                return True
        return False


class VisualSemanticUnitRepository:
    @staticmethod
    def save(vsu: VisualSemanticUnit, run_id: str, substrate_id: str) -> None:
        if not run_id:
            raise ValueError("VisualSemanticUnit requires a valid run_id")
        if not substrate_id:
            raise ValueError("VisualSemanticUnit requires a valid substrate_id")
        row = {
            "id": vsu.id,
            "run_id": run_id,
            "substrate_id": substrate_id,
            "type": vsu.type,
            "variables_json": json.dumps(vsu.variables),
            "entities_json": json.dumps(vsu.entities),
            "relations_json": json.dumps(vsu.relations),
            "trends_json": json.dumps(vsu.trends),
            "comparisons_json": json.dumps(vsu.comparisons),
            "textual_claims_supported": json.dumps(vsu.textual_claims_supported),
            "ku_refs": vsu.ku_refs,
            "argument_refs": vsu.argument_refs,
        }
        insert("visual_semantic_unit", row)

    @staticmethod
    def get(vsu_id: str) -> Optional[VisualSemanticUnit]:
        row = read("visual_semantic_unit", vsu_id)
        if not row:
            return None
        return VisualSemanticUnit(
            id=row["id"],
            type=row["type"],
            variables=_jload(row.get("variables_json"), []),
            entities=_jload(row.get("entities_json"), []),
            relations=_jload(row.get("relations_json"), []),
            trends=_jload(row.get("trends_json"), []),
            comparisons=_jload(row.get("comparisons_json"), []),
            textual_claims_supported=_jload(row.get("textual_claims_supported"), []),
            ku_refs=list(row.get("ku_refs") or []),
            argument_refs=list(row.get("argument_refs") or []),
        )

    @staticmethod
    def list_for_run(run_id: str) -> List[VisualSemanticUnit]:
        rows = query(
            "SELECT * FROM visual_semantic_unit WHERE run_id = %(run_id)s ORDER BY id",
            {"run_id": run_id},
        )
        out = []
        for row in rows:
            vsu = VisualSemanticUnitRepository.get(row["id"])
            if vsu is not None:
                out.append(vsu)
        return out

    @staticmethod
    def check_exists(run_id: str) -> bool:
        res = query("SELECT 1 FROM visual_semantic_unit WHERE run_id = %(run_id)s LIMIT 1", {"run_id": run_id})
        return len(res) > 0


class ChapterUnderstandingRepository:
    @staticmethod
    def save(cu: ChapterUnderstanding) -> None:
        if not cu.run_id:
            raise ValueError("ChapterUnderstanding requires a valid run_id")
        row = {
            "id": cu.id,
            "run_id": cu.run_id,
            "chapter_id": cu.chapter_id,
            "chapter_question": cu.chapter_question,
            "chapter_goal": cu.chapter_goal,
            "chapter_thesis": cu.chapter_thesis,
            "primary_role": cu.primary_role,
            "secondary_roles_json": json.dumps(cu.secondary_roles),
            "concepts_introduced_refs": cu.concepts_introduced_refs,
            "concepts_redefined_refs": cu.concepts_redefined_refs,
            "major_ku_refs": cu.major_ku_refs,
            "supporting_ku_refs": cu.supporting_ku_refs,
            "arguments_refs": cu.arguments_refs,
            "mechanisms_refs": cu.mechanisms_refs,
            "evidence_program_json": json.dumps([ep.model_dump() for ep in cu.evidence_program]),
            "assumptions_json": json.dumps(cu.assumptions),
            "qualifications_json": json.dumps(cu.qualifications),
            "dependencies_on_prior": json.dumps(cu.dependencies_on_prior),
            "promises_to_future": json.dumps(cu.promises_to_future),
            "evidence_strengths": json.dumps(cu.evidence_strengths),
        }
        insert("chapter_understandings", row)

    @staticmethod
    def check_exists(run_id: str) -> bool:
        res = query("SELECT 1 FROM chapter_understandings WHERE run_id = %(run_id)s LIMIT 1", {"run_id": run_id})
        return len(res) > 0


class ChapterDeltaRepository:
    @staticmethod
    def save(cd: ChapterDelta) -> None:
        if not cd.run_id:
            raise ValueError("ChapterDelta requires a valid run_id")
        row = {
            "id": cd.id,
            "run_id": cd.run_id,
            "chapter_id": cd.chapter_id,
            "new_concepts_refs": cd.new_concepts_refs,
            "revised_concepts_refs": cd.revised_concepts_refs,
            "new_claims_refs": cd.new_claims_refs,
            "new_arguments_refs": cd.new_arguments_refs,
            "supports_prior_refs": cd.supports_prior_refs,
            "qualifies_prior_refs": cd.qualifies_prior_refs,
            "contradicts_prior_refs": cd.contradicts_prior_refs,
            "revises_prior_refs": cd.revises_prior_refs,
            "resolves_questions_json": json.dumps(cd.resolves_questions),
            "opens_questions_json": json.dumps(cd.opens_questions)
        }
        insert("chapter_deltas", row)

    @staticmethod
    def check_exists(run_id: str) -> bool:
        res = query("SELECT 1 FROM chapter_deltas WHERE run_id = %(run_id)s LIMIT 1", {"run_id": run_id})
        return len(res) > 0


class BookUnderstandingRepository:
    @staticmethod
    def save(bu: BookUnderstandingV2) -> None:
        if not bu.run_id:
            raise ValueError("BookUnderstandingV2 requires a valid run_id")
        if not bu.book_id:
            raise ValueError("BookUnderstandingV2 requires a valid book_id")
        if not bu.substrate_id:
            raise ValueError("BookUnderstandingV2 requires a valid substrate_id")
        row = {
            "id": bu.id,
            "run_id": bu.run_id,
            "book_id": bu.book_id,
            "substrate_id": bu.substrate_id,
            "version": bu.version,
            "status": bu.status.value,
            "genre": bu.genre,
            "governing_questions_json": json.dumps(bu.governing_questions),
            "central_theses_json": json.dumps(bu.central_theses),
            "sub_theses_json": json.dumps(bu.sub_theses),
            "concept_system_json": json.dumps(bu.concept_system),
            "situation_model_ref": bu.situation_model_ref,
            "argument_architecture_json": json.dumps(bu.argument_architecture.model_dump()),
            "chapter_dependency_graph": json.dumps(bu.chapter_dependency_graph.model_dump()),
            "discourse_arc": json.dumps(bu.discourse_arc.model_dump()),
            "negative_knowledge_json": json.dumps(bu.negative_knowledge.model_dump()),
            "concept_evolution_json": json.dumps([c.model_dump() for c in bu.concept_evolution]),
            "claim_evolution_json": json.dumps([c.model_dump() for c in bu.claim_evolution]),
            "resolved_questions_json": json.dumps(bu.resolved_questions),
            "unresolved_questions_json": json.dumps(bu.unresolved_questions),
            "coverage_score": bu.coverage_score,
            "verification_score": bu.verification_score
        }
        insert("book_understandings_v2", row)

    @staticmethod
    def get_by_run(run_id: str) -> Optional[dict]:
        """Raw canonical BU row for a run (latest version first)."""
        rows = query(
            "SELECT * FROM book_understandings_v2 WHERE run_id = %(run_id)s "
            "ORDER BY version DESC LIMIT 1",
            {"run_id": run_id},
        )
        return rows[0] if rows else None

    @staticmethod
    def check_exists(run_id: str) -> bool:
        res = query("SELECT 1 FROM book_understandings_v2 WHERE run_id = %(run_id)s LIMIT 1", {"run_id": run_id})
        return len(res) > 0


class GapTransitionError(ValueError):
    """Illegal UnderstandingGap lifecycle transition."""


# Canonical gap lifecycle. Terminal: RESOLVED / REJECTED / WONTFIX / RECONCILED.
# Legacy TARGETED_REREAD_DISPATCHED / RECONCILED / WONTFIX values stay accepted
# for already-persisted rows but are not the forward path for new gaps.
VALID_GAP_TRANSITIONS = {
    GapStatus.OPEN: frozenset({
        GapStatus.TARGETED_REREAD_REQUIRED,
        GapStatus.TARGETED_REREAD_DISPATCHED,
        GapStatus.REJECTED,
        GapStatus.WONTFIX,
    }),
    GapStatus.TARGETED_REREAD_REQUIRED: frozenset({
        GapStatus.REREAD_IN_PROGRESS,
        GapStatus.REJECTED,
        GapStatus.WONTFIX,
    }),
    GapStatus.REREAD_IN_PROGRESS: frozenset({
        GapStatus.RESOLVED,
        GapStatus.TARGETED_REREAD_REQUIRED,
        GapStatus.REJECTED,
        GapStatus.WONTFIX,
    }),
    GapStatus.TARGETED_REREAD_DISPATCHED: frozenset({
        GapStatus.REREAD_IN_PROGRESS,
        GapStatus.RESOLVED,
        GapStatus.REJECTED,
        GapStatus.WONTFIX,
    }),
    GapStatus.RESOLVED: frozenset(),
    GapStatus.REJECTED: frozenset(),
    GapStatus.WONTFIX: frozenset(),
}

# Gaps in these statuses block VERIFIED. RESOLVED / REJECTED / WONTFIX /
# RECONCILED never block.
BLOCKING_GAP_STATUSES = (
    "OPEN",
    "TARGETED_REREAD_REQUIRED",
    "REREAD_IN_PROGRESS",
    "TARGETED_REREAD_DISPATCHED",
)


class UnderstandingGapRepository:
    @staticmethod
    def save(gap: UnderstandingGap) -> None:
        if not gap.run_id:
            raise ValueError("UnderstandingGap requires a valid run_id")
        row = {
            "id": gap.id,
            "run_id": gap.run_id,
            "type": gap.type.value,
            "severity": gap.severity.value,
            "affected_component": gap.affected_component,
            "question": gap.question,
            "evidence_targets_json": json.dumps(gap.evidence_targets),
            "required_action": gap.required_action,
            "status": gap.status.value
        }
        insert("understanding_gaps", row)

    @staticmethod
    def get(gap_id: str) -> Optional[UnderstandingGap]:
        row = read("understanding_gaps", gap_id)
        if not row:
            return None
        from stratum.knowledge.bu_v2_models import GapType, Severity
        return UnderstandingGap(
            id=row["id"],
            run_id=row["run_id"],
            type=GapType(row["type"]),
            severity=Severity(row["severity"]),
            affected_component=row.get("affected_component") or "",
            question=row.get("question") or "",
            evidence_targets=_jload(row.get("evidence_targets_json"), []),
            required_action=row.get("required_action") or "",
            status=GapStatus(row["status"]),
        )

    @staticmethod
    def transition(gap_id: str, run_id: str, to_status: GapStatus) -> UnderstandingGap:
        """Enforce the canonical gap lifecycle. Illegal transitions raise
        GapTransitionError and change nothing. Scoped to the owning run."""
        gap = UnderstandingGapRepository.get(gap_id)
        if gap is None:
            raise GapTransitionError(f"Gap {gap_id} not found.")
        if gap.run_id != run_id:
            raise GapTransitionError(
                f"Gap {gap_id} belongs to run {gap.run_id}, not {run_id}."
            )
        allowed = VALID_GAP_TRANSITIONS.get(gap.status, frozenset())
        if to_status not in allowed:
            raise GapTransitionError(
                f"Illegal gap transition: {gap.status.value} -> {to_status.value}. "
                f"Allowed: {sorted(s.value for s in allowed) or ['<terminal, none>']}."
            )
        update("understanding_gaps", gap_id, {
            "status": to_status.value,
            "updated_at": "now()",
        })
        gap.status = to_status
        return gap

    @staticmethod
    def get_blocking_gaps_count(run_id: str) -> int:
        res = query(
            "SELECT count(*) as c FROM understanding_gaps WHERE run_id = %(run_id)s "
            "AND status IN ('OPEN', 'TARGETED_REREAD_REQUIRED', 'REREAD_IN_PROGRESS', 'TARGETED_REREAD_DISPATCHED')",
            {"run_id": run_id}
        )
        return res[0]["c"] if res else 0


class VerificationRepository:
    """Durable verification artifacts (stratum.verification_artifacts, 058).

    Persistence failures propagate: a failed save() raises, and check_exists()
    never disguises a DB/schema error as 'missing artifact'.
    """

    @staticmethod
    def save(va: VerificationArtifact) -> None:
        if not va.run_id:
            raise ValueError("VerificationArtifact requires a valid run_id")
        if not va.book_id:
            raise ValueError("VerificationArtifact requires a valid book_id")
        row = {
            "id": va.id,
            "run_id": va.run_id,
            "book_id": va.book_id,
            "status": va.status.value,
            "checked_artifacts_json": json.dumps(va.checked_artifacts),
            "unresolved_gap_count": va.unresolved_gap_count,
            "verification_timestamp": va.verification_timestamp
        }
        insert("verification_artifacts", row)

    @staticmethod
    def get_latest(run_id: str) -> Optional[VerificationArtifact]:
        rows = query(
            "SELECT * FROM verification_artifacts WHERE run_id = %(run_id)s "
            "ORDER BY created_at DESC LIMIT 1",
            {"run_id": run_id},
        )
        if not rows:
            return None
        row = rows[0]
        return VerificationArtifact(
            id=row["id"],
            run_id=row["run_id"],
            book_id=row["book_id"],
            status=VerificationOutcome(row["status"]),
            checked_artifacts=_jload(row.get("checked_artifacts_json"), []),
            unresolved_gap_count=int(row.get("unresolved_gap_count") or 0),
            verification_timestamp=str(row.get("verification_timestamp") or ""),
        )

    @staticmethod
    def check_exists(run_id: str) -> bool:
        res = query("SELECT 1 FROM verification_artifacts WHERE run_id = %(run_id)s LIMIT 1", {"run_id": run_id})
        return len(res) > 0


class LearningObjectRepository:
    """Learning projection only. LearningObjects are derived from the canonical
    BU and are never a mastery authority (see AUTHORITY_MAP.md)."""

    @staticmethod
    def save(lo: LearningObject) -> None:
        if not lo.run_id:
            raise ValueError("LearningObject requires a valid run_id for provenance")
        if not lo.book_id:
            raise ValueError("LearningObject requires a valid book_id for provenance")
        row = {
            "id": lo.id,
            "bu_id": lo.bu_id,
            "run_id": lo.run_id,
            "book_id": lo.book_id,
            "learning_goal": lo.learning_goal,
            "knowledge_type": lo.knowledge_type,
            "importance": lo.importance.value,
            "difficulty": lo.difficulty.value,
            "target_refs": lo.target_refs,
            "prerequisites_refs": lo.prerequisites_refs,
            "mastery_requirements_json": json.dumps(lo.mastery_requirements),
            "assessment_modes_json": json.dumps(lo.assessment_modes),
            "source_refs": lo.source_refs
        }
        insert("learning_objects", row)

    @staticmethod
    def check_exists_for_bu(bu_id: str) -> bool:
        res = query("SELECT 1 FROM learning_objects WHERE bu_id = %(bu_id)s LIMIT 1", {"bu_id": bu_id})
        return len(res) > 0

    @staticmethod
    def list_for_bu(bu_id: str) -> List[dict]:
        return query("SELECT * FROM learning_objects WHERE bu_id = %(bu_id)s ORDER BY id", {"bu_id": bu_id})


class RetrievalItemRepository:
    @staticmethod
    def save(ri: RetrievalItem) -> None:
        row = {
            "id": ri.id,
            "learning_object_id": ri.learning_object_id,
            "interaction_type": ri.interaction_type.value,
            "payload_json": json.dumps(ri.payload.model_dump())
        }
        insert("retrieval_items", row)

    @staticmethod
    def check_exists_for_learning_object(learning_object_id: str) -> bool:
        res = query(
            "SELECT 1 FROM retrieval_items WHERE learning_object_id = %(lo_id)s LIMIT 1",
            {"lo_id": learning_object_id},
        )
        return len(res) > 0

    @staticmethod
    def list_for_learning_object(learning_object_id: str) -> List[dict]:
        return query(
            "SELECT * FROM retrieval_items WHERE learning_object_id = %(lo_id)s ORDER BY id",
            {"lo_id": learning_object_id},
        )


# ── P3: Explanation Structure repositories (tables 054 / 053) ─────────────────
# Tables already exist; these classes close the MODEL <-> REPOSITORY <-> SQL
# loop with explicit mappings (no blind model_dump inserts, no silent errors).

class ArgumentRepository:
    @staticmethod
    def save(arg: Argument, run_id: str) -> None:
        if not run_id:
            raise ValueError("Argument requires a valid run_id")
        row = {
            "id": arg.id,
            "run_id": run_id,
            "question": arg.question,
            "premises_json": json.dumps(arg.premises),
            "warrants_json": json.dumps(arg.warrants),
            "inference_steps_json": json.dumps(arg.inference_steps),
            "objections_json": json.dumps(arg.objections),
            "rebuttals_json": json.dumps(arg.rebuttals),
            "qualifiers_json": json.dumps(arg.qualifiers),
            "conclusion": json.dumps(arg.conclusion),
            "ku_refs": arg.ku_refs,
            "evidence_refs": arg.evidence_refs,
        }
        insert("arguments", row)

    @staticmethod
    def get(argument_id: str) -> Optional[Argument]:
        row = read("arguments", argument_id)
        if not row:
            return None
        return Argument(
            id=row["id"],
            question=row.get("question") or "",
            premises=_jload(row.get("premises_json"), []),
            warrants=_jload(row.get("warrants_json"), []),
            inference_steps=_jload(row.get("inference_steps_json"), []),
            objections=_jload(row.get("objections_json"), []),
            rebuttals=_jload(row.get("rebuttals_json"), []),
            qualifiers=_jload(row.get("qualifiers_json"), []),
            conclusion=_jload(row.get("conclusion"), []),
            ku_refs=list(row.get("ku_refs") or []),
            evidence_refs=list(row.get("evidence_refs") or []),
        )

    @staticmethod
    def list_for_run(run_id: str) -> List[Argument]:
        rows = query("SELECT * FROM arguments WHERE run_id = %(run_id)s ORDER BY id",
                     {"run_id": run_id})
        return [a for a in (ArgumentRepository.get(r["id"]) for r in rows) if a is not None]

    @staticmethod
    def check_exists(run_id: str) -> bool:
        res = query("SELECT 1 FROM arguments WHERE run_id = %(run_id)s LIMIT 1",
                    {"run_id": run_id})
        return len(res) > 0


class MechanismRepository:
    @staticmethod
    def save(mech: AuthorMechanism, run_id: str) -> None:
        if not run_id:
            raise ValueError("AuthorMechanism requires a valid run_id")
        row = {
            "id": mech.id,
            "run_id": run_id,
            "trigger_event": mech.trigger_event,
            "actors_json": json.dumps(mech.actors),
            "variables_json": json.dumps(mech.variables),
            "inputs_json": json.dumps(mech.inputs),
            "mediators_json": json.dumps(mech.mediators),
            "state_changes_json": json.dumps(mech.state_changes),
            "outputs_json": json.dumps(mech.outputs),
            "conditions_json": json.dumps(mech.conditions),
            "exceptions_json": json.dumps(mech.exceptions),
            "failure_conditions_json": json.dumps(mech.failure_conditions),
            "ku_refs": [],
            "evidence_refs": [],
            "explicitness": mech.explicitness,
        }
        insert("author_mechanisms", row)

    @staticmethod
    def get(mechanism_id: str) -> Optional[AuthorMechanism]:
        row = read("author_mechanisms", mechanism_id)
        if not row:
            return None
        return AuthorMechanism(
            id=row["id"],
            trigger_event=row.get("trigger_event") or "",
            actors=_jload(row.get("actors_json"), []),
            variables=_jload(row.get("variables_json"), []),
            inputs=_jload(row.get("inputs_json"), []),
            mediators=_jload(row.get("mediators_json"), []),
            state_changes=_jload(row.get("state_changes_json"), []),
            outputs=_jload(row.get("outputs_json"), []),
            conditions=_jload(row.get("conditions_json"), []),
            exceptions=_jload(row.get("exceptions_json"), []),
            failure_conditions=_jload(row.get("failure_conditions_json"), []),
            explicitness=row.get("explicitness") or "",
        )

    @staticmethod
    def list_for_run(run_id: str) -> List[AuthorMechanism]:
        rows = query("SELECT * FROM author_mechanisms WHERE run_id = %(run_id)s ORDER BY id",
                     {"run_id": run_id})
        return [m for m in (MechanismRepository.get(r["id"]) for r in rows) if m is not None]

    @staticmethod
    def check_exists(run_id: str) -> bool:
        res = query("SELECT 1 FROM author_mechanisms WHERE run_id = %(run_id)s LIMIT 1",
                    {"run_id": run_id})
        return len(res) > 0


class SituationModelRepository:
    @staticmethod
    def save(sm: SituationModel, run_id: str) -> None:
        if not run_id:
            raise ValueError("SituationModel requires a valid run_id")
        row = {
            "id": sm.id,
            "run_id": run_id,
            "entities_json": json.dumps(sm.entities),
            "states_json": json.dumps(sm.states),
            "variables_json": json.dumps(sm.variables),
            "relations_json": json.dumps(sm.relations),
            "causal_links_json": json.dumps(sm.causal_links),
            "temporal_links_json": json.dumps(sm.temporal_links),
            "mechanism_refs": sm.mechanism_refs,
            "constraints_json": json.dumps(sm.constraints),
            "boundary_conditions_json": json.dumps(sm.boundary_conditions),
        }
        insert("situation_models", row)

    @staticmethod
    def get(situation_id: str) -> Optional[SituationModel]:
        row = read("situation_models", situation_id)
        if not row:
            return None
        return SituationModel(
            id=row["id"],
            entities=_jload(row.get("entities_json"), []),
            states=_jload(row.get("states_json"), []),
            variables=_jload(row.get("variables_json"), []),
            relations=_jload(row.get("relations_json"), []),
            causal_links=_jload(row.get("causal_links_json"), []),
            temporal_links=_jload(row.get("temporal_links_json"), []),
            mechanism_refs=list(row.get("mechanism_refs") or []),
            constraints=_jload(row.get("constraints_json"), []),
            boundary_conditions=_jload(row.get("boundary_conditions_json"), []),
        )

    @staticmethod
    def list_for_run(run_id: str) -> List[SituationModel]:
        rows = query("SELECT * FROM situation_models WHERE run_id = %(run_id)s ORDER BY id",
                     {"run_id": run_id})
        return [s for s in (SituationModelRepository.get(r["id"]) for r in rows) if s is not None]


class FrontierRepository:
    @staticmethod
    def save(fr: UnderstandingFrontier) -> None:
        if not fr.run_id:
            raise ValueError("UnderstandingFrontier requires a valid run_id")
        row = {
            "id": fr.id,
            "run_id": fr.run_id,
            "type": fr.type.value,
            "description": fr.description,
            "status": fr.status.value,
            "resolution_refs": fr.resolution_refs,
        }
        insert("understanding_frontiers", row)

    @staticmethod
    def get(frontier_id: str) -> Optional[UnderstandingFrontier]:
        row = read("understanding_frontiers", frontier_id)
        if not row:
            return None
        return UnderstandingFrontier(
            id=row["id"],
            run_id=row["run_id"],
            type=FrontierType(row["type"]),
            description=row.get("description") or "",
            status=FrontierStatus(row["status"]),
            resolution_refs=list(row.get("resolution_refs") or []),
        )

    @staticmethod
    def list_open_for_run(run_id: str) -> List[UnderstandingFrontier]:
        rows = query(
            "SELECT * FROM understanding_frontiers WHERE run_id = %(run_id)s "
            "AND status = 'OPEN' ORDER BY id",
            {"run_id": run_id})
        return [f for f in (FrontierRepository.get(r["id"]) for r in rows) if f is not None]


class TrajectoryRepository:
    @staticmethod
    def save(traj: EvidenceTrajectory) -> None:
        row = {
            "id": traj.id,
            "claim_id": traj.claim_id,
            "source_pages": json.dumps(traj.source_pages),
            "evidence_regions": json.dumps(traj.evidence_regions),
            "extracted_facts": json.dumps(traj.extracted_facts),
            "ku_refs": traj.ku_refs,
            "reasoning_steps": json.dumps(traj.reasoning_steps),
            "final_interpretation": traj.final_interpretation,
            "verification_status": traj.verification_status.value,
        }
        insert("evidence_trajectory", row)

    @staticmethod
    def get(trajectory_id: str) -> Optional[EvidenceTrajectory]:
        row = read("evidence_trajectory", trajectory_id)
        if not row:
            return None
        return EvidenceTrajectory(
            id=row["id"],
            claim_id=row.get("claim_id") or "",
            source_pages=_jload(row.get("source_pages"), []),
            evidence_regions=_jload(row.get("evidence_regions"), []),
            extracted_facts=_jload(row.get("extracted_facts"), []),
            ku_refs=list(row.get("ku_refs") or []),
            reasoning_steps=_jload(row.get("reasoning_steps"), []),
            final_interpretation=row.get("final_interpretation") or "",
            verification_status=VerificationStatus(row.get("verification_status") or "PENDING"),
        )

    @staticmethod
    def list_for_claim(claim_id: str) -> List[EvidenceTrajectory]:
        rows = query("SELECT * FROM evidence_trajectory WHERE claim_id = %(cid)s ORDER BY id",
                     {"cid": claim_id})
        return [t for t in (TrajectoryRepository.get(r["id"]) for r in rows) if t is not None]

    @staticmethod
    def list_for_run(run_id: str) -> List[EvidenceTrajectory]:
        """Run scoping via knowledge_claims.extraction_run_id (053) — trajectories
        reference claims, claims carry the extraction run. No new table."""
        rows = query(
            "SELECT t.* FROM evidence_trajectory t "
            "JOIN knowledge_claims k ON k.id = t.claim_id "
            "WHERE k.extraction_run_id = %(run_id)s ORDER BY t.id",
            {"run_id": run_id})
        return [t for t in (TrajectoryRepository.get(r["id"]) for r in rows) if t is not None]


class LearningGraphRepository:
    @staticmethod
    def save(graph: LearningGraph) -> None:
        row = {
            "id": graph.id,
            "bu_id": graph.bu_id,
            "version": graph.version,
            "nodes_json": json.dumps([n.model_dump() for n in graph.nodes]),
            "edges_json": json.dumps([e.model_dump() for e in graph.edges]),
        }
        insert("learning_graphs", row)

    @staticmethod
    def get(graph_id: str) -> Optional[LearningGraph]:
        from stratum.knowledge.bu_v2_models import LearningGraphNode, LearningGraphEdge
        row = read("learning_graphs", graph_id)
        if not row:
            return None
        return LearningGraph(
            id=row["id"],
            bu_id=row.get("bu_id") or "",
            version=int(row.get("version") or 1),
            nodes=[LearningGraphNode(**n) for n in _jload(row.get("nodes_json"), [])],
            edges=[LearningGraphEdge(**e) for e in _jload(row.get("edges_json"), [])],
        )

    @staticmethod
    def check_exists_for_bu(bu_id: str) -> bool:
        res = query("SELECT 1 FROM learning_graphs WHERE bu_id = %(bu_id)s LIMIT 1",
                    {"bu_id": bu_id})
        return len(res) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# P13: Book-Level Synthesis Repositories
# ═══════════════════════════════════════════════════════════════════════════════

class BookThesisRepository:
    @staticmethod
    def save(thesis: BookThesis) -> None:
        if not thesis.id:
            raise ValueError("BookThesis requires id")
        row = {
            "id": thesis.id,
            "run_id": getattr(thesis, "run_id", ""),
            "book_id": getattr(thesis, "book_id", ""),
            "thesis_type": thesis.type.value,
            "statement": thesis.statement,
            "scope": thesis.scope,
            "evidence_refs": thesis.evidence_refs,
            "supporting_arguments": thesis.supporting_arguments,
            "confidence": thesis.confidence,
            "provenance": thesis.provenance.value,
            "source_locations": thesis.source_locations,
        }
        insert("book_theses", row)

    @staticmethod
    def list_for_run(run_id: str) -> list[BookThesis]:
        rows = query("SELECT * FROM book_theses WHERE run_id = %(run_id)s ORDER BY created_at",
                     {"run_id": run_id})
        return [BookThesis(
            id=r["id"],
            type=ThesisType(r["thesis_type"]),
            statement=r["statement"],
            scope=r.get("scope") or "",
            evidence_refs=list(r.get("evidence_refs") or []),
            supporting_arguments=list(r.get("supporting_arguments") or []),
            confidence=float(r.get("confidence") or 0.0),
            provenance=ThesisProvenance(r.get("provenance") or "MODEL_INFERRED"),
            source_locations=list(r.get("source_locations") or []),
        ) for r in rows]


class BookConceptSystemRepository:
    @staticmethod
    def save(entry: BookConceptSystem) -> None:
        # Not used directly; bulk save via BookSynthesisRepository
        pass


class BookArgumentRepository:
    @staticmethod
    def save(arg: BookArgument) -> None:
        if not arg.id:
            raise ValueError("BookArgument requires id")
        row = {
            "id": arg.id,
            "run_id": getattr(arg, "run_id", ""),
            "book_id": getattr(arg, "book_id", ""),
            "level": arg.level,
            "what": arg.what,
            "why": arg.why,
            "how": arg.how,
            "evidence_refs": arg.evidence_refs,
            "depends_on": arg.depends_on,
            "conclusion": arg.conclusion,
            "status": arg.status.value,
            "confidence": arg.confidence,
            "source_chapters": arg.source_chapters,
        }
        insert("book_arguments", row)


class BookMechanismRepository:
    @staticmethod
    def save(mech: BookMechanism) -> None:
        if not mech.id:
            raise ValueError("BookMechanism requires id")
        row = {
            "id": mech.id,
            "run_id": getattr(mech, "run_id", ""),
            "book_id": getattr(mech, "book_id", ""),
            "trigger": mech.trigger,
            "precondition": mech.precondition,
            "operation": mech.operation,
            "intermediate_state": mech.intermediate_state,
            "outcome": mech.outcome,
            "evidence_refs": mech.evidence_refs,
            "confidence": mech.confidence,
            "provenance": mech.provenance.value,
            "source_chapters": mech.source_chapters,
        }
        insert("book_mechanisms", row)


class BookEvidenceMapRepository:
    @staticmethod
    def save(entry: BookEvidenceMap, run_id: str, book_id: str) -> None:
        if not run_id or not book_id:
            raise ValueError("BookEvidenceMap requires run_id and book_id")
        row = {
            "id": _stable_id("emap", run_id, book_id),
            "run_id": run_id,
            "book_id": book_id,
            "evidence_coverage": entry.evidence_coverage,
            "unsupported_claim_count": entry.unsupported_claim_count,
            "model_inference_ratio": entry.model_inference_ratio,
            "contradiction_count": entry.contradiction_count,
        }
        insert("book_evidence_map_summary", row)


class BookAuthorModelRepository:
    @staticmethod
    def save(model: BookAuthorModel, run_id: str, book_id: str) -> None:
        if not run_id or not book_id:
            raise ValueError("BookAuthorModel requires run_id and book_id")
        row = {
            "run_id": run_id,
            "book_id": book_id,
            "worldview": model.worldview,
            "assumptions": model.assumptions,
            "explanatory_strategy": model.explanatory_strategy,
            "argument_style": model.argument_style,
            "recurring_patterns": model.recurring_patterns,
            "evidence_preference": model.evidence_preference,
            "limitations": model.limitations,
            "unresolved_positions": model.unresolved_positions,
            "provenance": model.provenance.value,
        }
        insert("book_author_models", row)


class BookChapterRolesRepository:
    @staticmethod
    def save(assignment: BookChapterRoles, run_id: str, book_id: str) -> None:
        for a in assignment.assignments:
            row = {
                "id": _stable_id("crole", run_id, a.chapter_id),
                "run_id": run_id,
                "book_id": book_id,
                "chapter_id": a.chapter_id,
                "roles": [r.value for r in a.roles],
                "evidence": a.evidence,
                "confidence": a.confidence,
            }
            insert("book_chapter_roles", row)


class BookContradictionsRepository:
    @staticmethod
    def save(contra: BookContradictions, run_id: str, book_id: str) -> None:
        for c in contra.contradictions:
            row = {
                "id": c.id,
                "run_id": run_id,
                "book_id": book_id,
                "contradiction_type": c.type.value,
                "element_a": c.element_a,
                "element_b": c.element_b,
                "element_type": c.element_type,
                "description": c.description,
                "classification": c.classification.value,
                "source_chapters": c.source_chapters,
                "confidence": c.confidence,
            }
            insert("book_contradictions", row)


class BookSynthesisRepository:
    @staticmethod
    def save(synthesis: BookSynthesis) -> None:
        if not synthesis.id or not synthesis.run_id or not synthesis.book_id:
            raise ValueError("BookSynthesis requires id, run_id, book_id")
        row = {
            "id": synthesis.id,
            "run_id": synthesis.run_id,
            "book_id": synthesis.book_id,
            "thesis": synthesis.thesis.model_dump(),
            "problem_definition": synthesis.problem_definition,
            "concept_system": synthesis.concept_system.model_dump(),
            "argument_system": synthesis.argument_system.model_dump(),
            "mechanism_system": synthesis.mechanism_system.model_dump(),
            "evidence_map": synthesis.evidence_map.model_dump(),
            "author_model": synthesis.author_model.model_dump(),
            "chapter_roles": synthesis.chapter_roles.model_dump(),
            "unresolved_questions": synthesis.unresolved_questions,
            "contradictions": synthesis.contradictions.model_dump(),
            "limitations": synthesis.limitations,
            "synthesis_evidence": synthesis.synthesis_evidence,
        }
        insert("book_syntheses", row)

    @staticmethod
    def get_by_run(run_id: str) -> Optional[BookSynthesis]:
        row = read("book_syntheses", run_id)
        if not row:
            return None
        return BookSynthesis(**row)

    @staticmethod
    def check_exists(run_id: str) -> bool:
        res = query("SELECT 1 FROM book_syntheses WHERE run_id = %(run_id)s LIMIT 1", {"run_id": run_id})
        return len(res) > 0


class BookSynthesisExpressionRepository:
    @staticmethod
    def save(expr: Any, run_id: str, book_id: str, synthesis_id: str) -> None:
        if not run_id or not book_id or not synthesis_id:
            raise ValueError("BookSynthesisExpression requires run_id, book_id, synthesis_id")
        row = {
            "id": _stable_id("expr", run_id),
            "run_id": run_id,
            "book_id": book_id,
            "synthesis_id": synthesis_id,
            "executive_summary": getattr(expr, "executive_summary", ""),
            "full_explanation": getattr(expr, "full_explanation", ""),
            "concept_map": getattr(expr, "concept_map", ""),
            "argument_map": getattr(expr, "argument_map", ""),
            "chapter_by_chapter": getattr(expr, "chapter_by_chapter", ""),
            "author_position": getattr(expr, "author_position", ""),
            "limitations": getattr(expr, "limitations", ""),
            "unresolved_questions": getattr(expr, "unresolved_questions", ""),
        }
        insert("book_synthesis_expressions", row)


class P13QualityGateRepository:
    @staticmethod
    def save(gate_num: int, gate_name: str, status: str, run_id: str, book_id: str,
             score: float = None, detail: str = "", evidence: dict = None) -> None:
        if not run_id or not book_id:
            raise ValueError("Quality gate requires run_id and book_id")
        row = {
            "id": _stable_id("gate", run_id, str(gate_num)),
            "run_id": run_id,
            "book_id": book_id,
            "gate_number": gate_num,
            "gate_name": gate_name,
            "status": status,
            "score": score,
            "detail": detail,
            "evidence": evidence or {},
        }
        insert("bu2_p13_quality_gates", row)


def _stable_id(prefix: str, *parts: str) -> str:
    import hashlib
    raw = "|".join(p for p in parts if p)
    return f"{prefix}_{hashlib.sha256(raw.encode()).hexdigest()[:12]}"
