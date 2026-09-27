import pytest
from pydantic import ValidationError


def test_inferred_personal_state_requires_provenance():
    from stratum.api.routers.personal_model import PersonalStateUpsert

    with pytest.raises(ValidationError):
        PersonalStateUpsert(
            object_type="concept",
            object_id="concept-1",
            source="inferred",
        )

    state = PersonalStateUpsert(
        object_type="concept",
        object_id="concept-1",
        relevance=0.8,
        source="inferred",
        source_event_id="run-1",
    )
    assert state.relevance == 0.8


def test_belief_and_context_link_use_explicit_source_contract():
    from stratum.api.routers.personal_model import BeliefUpsert, ContextLinkUpsert

    belief = BeliefUpsert(claim_id="claim-1", stance="disagree", rationale="Not supported")
    link = ContextLinkUpsert(
        object_type="claim",
        object_id="claim-1",
        context_type="project",
        context_id="project-1",
    )
    assert belief.source == "user"
    assert link.weight == 1.0


def test_personal_state_upsert_is_idempotent_by_object_key():
    from stratum.services.personal_model import upsert_personal_state

    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Connection:
        def __init__(self):
            self.inserts = []

        def execute(self, sql, params):
            if sql.startswith("INSERT INTO stratum.personal_states"):
                self.inserts.append(params)
                return Cursor(None)
            if sql.startswith("SELECT id FROM stratum.personal_states"):
                return Cursor(("01STATE",))
            raise AssertionError(sql)

    conn = Connection()
    first = upsert_personal_state(
        conn,
        "user-1",
        object_type="evidence",
        object_id="evidence-1",
        mastery=0.0,
        interest=0.0,
        certainty=1.0,
        relevance=1.0,
        source="explicit",
        source_event_id="highlight-1",
    )
    second = upsert_personal_state(
        conn,
        "user-1",
        object_type="evidence",
        object_id="evidence-1",
        mastery=0.2,
        interest=0.4,
        certainty=0.8,
        relevance=1.0,
        source="explicit",
        source_event_id="highlight-2",
    )
    assert first == second == "01STATE"
    assert len(conn.inserts) == 2
    assert conn.inserts[1][3] == "evidence-1"


def test_personalized_score_is_bounded_and_zero_signal_is_neutral():
    from stratum.services.personal_model import personalized_score

    assert personalized_score(0.42) == 0.42
    assert personalized_score(0.42, relevance=1.0, interest=1.0, certainty=1.0) == 0.57
    assert personalized_score(0.99, relevance=1.0, interest=1.0, certainty=1.0) == 1.0


def test_learning_event_is_insert_only_service_operation():
    from unittest.mock import patch

    from stratum.services.personal_model import record_learning_event

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, params):
            self.sql = sql
            self.params = params

    conn = Connection()
    with patch("stratum.db.get_conn", return_value=conn):
        event_id = record_learning_event(
            "user-1",
            object_type="flashcard",
            object_id="card-1",
            event_type="flashcard_reviewed",
            result={"rating": "good"},
            source="learn",
        )

    assert event_id
    assert conn.sql.startswith("INSERT INTO stratum.learning_events")
    assert conn.params[1:5] == ("user-1", "flashcard", "card-1", "flashcard_reviewed")


def test_personal_model_event_row_decodes_json_result():
    from stratum.api.routers.personal_model import _event_row

    row = _event_row(
        ("event-1", "flashcard", "card-1", "review", '{"rating":"good"}', "learn", "t", "t")
    )
    assert row["result"] == {"rating": "good"}


def test_evidence_state_projects_to_source_substrate_signal():
    from unittest.mock import patch

    from stratum.services.personal_model import personal_signals

    class Cursor:
        def __init__(self, rows):
            self.rows = rows

        def fetchall(self):
            return self.rows

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def execute(self, sql, params):
            if "JOIN stratum.evidence" in sql:
                return Cursor([("substrate-1", 1.0, 0.2, 1.0)])
            return Cursor([("evidence", "evidence-1", 1.0, 0.2, 1.0)])

    with patch("stratum.db.get_conn", return_value=Connection()):
        signals = personal_signals("user-1")

    assert signals[("evidence", "evidence-1")]["relevance"] == 1.0
    assert signals[("substrate", "substrate-1")]["certainty"] == 1.0


def test_reader_semantic_actions_require_text():
    from stratum.api.routers.interactions import ReaderAction

    ReaderAction(action="important")
    with pytest.raises(ValidationError):
        ReaderAction(action="question")
    with pytest.raises(ValidationError):
        ReaderAction(action="contradict", note=" ")
