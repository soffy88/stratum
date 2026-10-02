"""P3 explanation-structure persistence tests (tables 053/054/056)."""

import pytest

import stratum.services.bu_v2_repositories as R
from stratum.knowledge.bu_v2_models import (
    Argument, AuthorMechanism, EvidenceTrajectory, LearningGraph,
    LearningGraphEdge, LearningGraphNode, SituationModel,
    UnderstandingFrontier, FrontierType,
)


def _store(monkeypatch):
    db, saved = {}, []

    def fake_insert(table, row):
        saved.append((table, dict(row)))
        db.setdefault(table, []).append(dict(row))

    def fake_read(table, rid, id_column="id"):
        for row in db.get(table, []):
            if row.get(id_column) == rid:
                return dict(row)
        return None

    def fake_query(sql, params=None):
        p = params or {}
        for table in ("arguments", "author_mechanisms", "situation_models",
                      "understanding_frontiers", "evidence_trajectory",
                      "learning_graphs"):
            if table in sql:
                rows = list(db.get(table, []))
                if "extraction_run_id" in sql:
                    # join emulation: claim rows carry extraction_run_id in test db
                    claims = {c["id"]: c for c in db.get("knowledge_claims", [])}
                    rows = [r for r in rows
                            if claims.get(r.get("claim_id"), {}).get("extraction_run_id") == p["run_id"]]
                elif "run_id" in sql and "run_id" in p:
                    rows = [r for r in rows if r.get("run_id") == p["run_id"]]
                if "claim_id" in sql and "cid" in p:
                    rows = [r for r in rows if r.get("claim_id") == p["cid"]]
                if "bu_id" in sql and "bu_id" in p:
                    rows = [r for r in rows if r.get("bu_id") == p["bu_id"]]
                if "LIMIT 1" in sql:
                    return rows[:1]
                return [dict(r) for r in rows]
        return []

    monkeypatch.setattr(R, "insert", fake_insert)
    monkeypatch.setattr(R, "read", fake_read)
    monkeypatch.setattr(R, "query", fake_query)
    return db, saved


def test_argument_roundtrip_and_run_scope(monkeypatch):
    _store(monkeypatch)
    a = Argument(id="a1", question="Why?", premises=["P1", "W"],
                 warrants=["W"], conclusion=["C"],
                 ku_refs=["k1"], evidence_refs=["e1"])
    R.ArgumentRepository.save(a, run_id="run_1")
    back = R.ArgumentRepository.get("a1")
    assert back is not None and back.premises == ["P1", "W"]
    assert back.conclusion == ["C"] and back.ku_refs == ["k1"]
    assert R.ArgumentRepository.list_for_run("run_1")[0].id == "a1"
    assert R.ArgumentRepository.list_for_run("run_2") == []
    assert R.ArgumentRepository.check_exists("run_1") is True
    assert R.ArgumentRepository.get("nope") is None
    with pytest.raises(ValueError):
        R.ArgumentRepository.save(a, run_id="")


def test_mechanism_roundtrip(monkeypatch):
    _store(monkeypatch)
    m = AuthorMechanism(id="m1", trigger_event="shock", actors=["firm"],
                        inputs=["x"], outputs=["y"], explicitness="EXPLICIT")
    R.MechanismRepository.save(m, run_id="run_1")
    back = R.MechanismRepository.get("m1")
    assert back is not None and back.trigger_event == "shock"
    assert back.explicitness == "EXPLICIT"
    assert R.MechanismRepository.check_exists("run_1") is True


def test_situation_model_roundtrip(monkeypatch):
    _store(monkeypatch)
    s = SituationModel(id="s1", entities=["firm"], causal_links=["a->b"],
                       mechanism_refs=["m1"], boundary_conditions=["short-run"])
    R.SituationModelRepository.save(s, run_id="run_1")
    back = R.SituationModelRepository.get("s1")
    assert back is not None and back.causal_links == ["a->b"]
    assert back.mechanism_refs == ["m1"]


def test_frontier_open_listing(monkeypatch):
    _store(monkeypatch)
    R.FrontierRepository.save(UnderstandingFrontier(
        id="f1", run_id="run_1", type=FrontierType.QUESTION_AWAITING_ANSWER,
        description="Why X?"))
    R.FrontierRepository.save(UnderstandingFrontier(
        id="f2", run_id="run_1", type=FrontierType.CLAIM_AWAITING_EVIDENCE,
        description="Need evidence."))
    from stratum.knowledge.bu_v2_models import FrontierStatus
    f2 = R.FrontierRepository.get("f2")
    assert f2 is not None and f2.status == FrontierStatus.OPEN
    assert {f.id for f in R.FrontierRepository.list_open_for_run("run_1")} == {"f1", "f2"}
    with pytest.raises(ValueError):
        R.FrontierRepository.save(UnderstandingFrontier(
            id="f3", run_id="", type=FrontierType.QUESTION_AWAITING_ANSWER))


def test_trajectory_roundtrip_and_claim_scope(monkeypatch):
    db, _ = _store(monkeypatch)
    db["knowledge_claims"] = [{"id": "cl1", "extraction_run_id": "run_1"}]
    t = EvidenceTrajectory(id="t1", claim_id="cl1", source_pages=[3],
                           evidence_regions=["p3-fig1"], extracted_facts=["f"],
                           ku_refs=["k1"], reasoning_steps=["r1"],
                           final_interpretation="holds")
    R.TrajectoryRepository.save(t)
    back = R.TrajectoryRepository.get("t1")
    assert back is not None and back.source_pages == [3]
    assert back.evidence_regions == ["p3-fig1"]
    assert R.TrajectoryRepository.list_for_claim("cl1")[0].id == "t1"
    assert R.TrajectoryRepository.list_for_run("run_1")[0].id == "t1"
    assert R.TrajectoryRepository.list_for_run("run_9") == []


def test_learning_graph_roundtrip(monkeypatch):
    _store(monkeypatch)
    g = LearningGraph(id="g1", bu_id="bu_1",
                      nodes=[LearningGraphNode(learning_object_ref="lo1")],
                      edges=[LearningGraphEdge(source_ref="lo1", target_ref="lo2",
                                               relation="REQUIRES")])
    R.LearningGraphRepository.save(g)
    back = R.LearningGraphRepository.get("g1")
    assert back is not None and back.nodes[0].learning_object_ref == "lo1"
    assert back.edges[0].relation == "REQUIRES"
    assert R.LearningGraphRepository.check_exists_for_bu("bu_1") is True
    assert R.LearningGraphRepository.get("nope") is None
