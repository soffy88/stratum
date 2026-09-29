"""Book Understanding 2.0 - Repository Boundary Interfaces."""

from typing import Optional
from stratum.db import execute, insert, query, update, read
from stratum.knowledge.bu_v2_models import (
    BookUnderstandingV2, ChapterUnderstanding, ChapterDelta,
    UnderstandingGap, LearningObject, RetrievalItem, PipelineRunState
)

class PipelineRunRepository:
    """Manages the lifecycle and state transitions of BookReadingRun."""
    
    @staticmethod
    def get_status(run_id: str) -> Optional[PipelineRunState]:
        row = read("book_reading_run", run_id)
        if row:
            return PipelineRunState(row["status"])
        return None
        
    @staticmethod
    def update_status(run_id: str, new_status: PipelineRunState, failure_reason: Optional[str] = None):
        changes = {"status": new_status.value, "updated_at": "now()"}
        if failure_reason:
            changes["failure_reason"] = failure_reason
        update("book_reading_run", run_id, changes)

class ChapterUnderstandingRepository:
    @staticmethod
    def save(cu: ChapterUnderstanding) -> None:
        row = cu.model_dump()
        # JSON serialize specific fields for DB
        import json
        row["secondary_roles_json"] = json.dumps(row.pop("secondary_roles"))
        row["evidence_program_json"] = json.dumps(row.pop("evidence_program"))
        row["assumptions_json"] = json.dumps(row.pop("assumptions"))
        row["qualifications_json"] = json.dumps(row.pop("qualifications"))
        row["dependencies_on_prior"] = json.dumps(row.pop("dependencies_on_prior"))
        row["promises_to_future"] = json.dumps(row.pop("promises_to_future"))
        insert("chapter_understandings", row)

class ChapterDeltaRepository:
    @staticmethod
    def save(cd: ChapterDelta) -> None:
        row = cd.model_dump()
        import json
        row["resolves_questions_json"] = json.dumps(row.pop("resolves_questions"))
        row["opens_questions_json"] = json.dumps(row.pop("opens_questions"))
        insert("chapter_deltas", row)

class BookUnderstandingRepository:
    @staticmethod
    def save(bu: BookUnderstandingV2) -> None:
        row = bu.model_dump()
        import json
        row["status"] = row["status"].value
        row["governing_questions_json"] = json.dumps(row.pop("governing_questions"))
        row["central_theses_json"] = json.dumps(row.pop("central_theses"))
        row["sub_theses_json"] = json.dumps(row.pop("sub_theses"))
        row["concept_system_json"] = json.dumps(row.pop("concept_system"))
        row["argument_architecture_json"] = json.dumps(row.pop("argument_architecture"))
        row["chapter_dependency_graph"] = json.dumps(row.pop("chapter_dependency_graph"))
        row["discourse_arc"] = json.dumps(row.pop("discourse_arc"))
        row["negative_knowledge_json"] = json.dumps(row.pop("negative_knowledge"))
        row["concept_evolution_json"] = json.dumps(row.pop("concept_evolution"))
        row["claim_evolution_json"] = json.dumps(row.pop("claim_evolution"))
        row["resolved_questions_json"] = json.dumps(row.pop("resolved_questions"))
        row["unresolved_questions_json"] = json.dumps(row.pop("unresolved_questions"))
        insert("book_understandings_v2", row)

class UnderstandingGapRepository:
    @staticmethod
    def save(gap: UnderstandingGap) -> None:
        row = gap.model_dump()
        import json
        row["type"] = row["type"].value
        row["severity"] = row["severity"].value
        row["status"] = row["status"].value
        row["evidence_targets_json"] = json.dumps(row.pop("evidence_targets"))
        insert("understanding_gaps", row)

class LearningObjectRepository:
    @staticmethod
    def save(lo: LearningObject) -> None:
        row = lo.model_dump()
        import json
        row["importance"] = row["importance"].value
        row["difficulty"] = row["difficulty"].value
        row["mastery_requirements_json"] = json.dumps(row.pop("mastery_requirements"))
        row["assessment_modes_json"] = json.dumps(row.pop("assessment_modes"))
        insert("learning_objects", row)

class RetrievalItemRepository:
    @staticmethod
    def save(ri: RetrievalItem) -> None:
        row = ri.model_dump()
        import json
        row["interaction_type"] = row["interaction_type"].value
        row["payload_json"] = json.dumps(row.pop("payload"))
        insert("retrieval_items", row)
