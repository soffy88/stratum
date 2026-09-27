from stratum.services.agent_contract import DEFAULT_AGENT_CONTRACT
from stratum.services.graph_query import BGraph
from stratum.services.query_intent_planner import plan_query
from stratum.services.slo import SLOTarget, evaluate, release_allowed
from stratum.services.spaced_repetition import ReviewState, review_priority
from stratum.services.wukr import calculate_wukr
from scripts.check_slo_gate import load_config


def test_query_planner_uses_three_tool_plan_for_comparison():
    plan = plan_query("比较 FSRS 和 SM-2 的区别")
    assert plan.intent == "compare"
    assert plan.tools == ("keyword_search", "semantic_search", "chunk_read")
    assert plan.max_depth == 3
    assert plan.rerank is True


def test_query_planner_keeps_lookup_small():
    plan = plan_query("注意力")
    assert plan.intent == "lookup"
    assert plan.tools == ("keyword_search", "semantic_search")
    assert plan.rerank is False


def test_agent_contract_forbids_direct_archival_write():
    DEFAULT_AGENT_CONTRACT.validate_tool("create_evidence", writes=True)
    DEFAULT_AGENT_CONTRACT.validate_tool("create_claim", writes=True)
    contract = DEFAULT_AGENT_CONTRACT.to_dict()
    assert contract["approved_write_tools"] == [
        "create_claim",
        "create_evidence",
        "create_highlight",
        "create_relation",
        "session_add_message",
    ]
    try:
        DEFAULT_AGENT_CONTRACT.validate_tool("direct_sql", writes=True)
    except PermissionError:
        pass
    else:
        raise AssertionError("direct SQL must not be an approved agent write")


def test_slo_error_budget_freezes_release_when_exhausted():
    target = SLOTarget("retrieval", "p95", 1500, 0.99)
    good = evaluate(target, 0.995)
    bad = evaluate(target, 0.98)
    assert good.passed is True
    assert bad.passed is False
    assert release_allowed([good]) is True
    assert release_allowed([bad]) is False


def test_slo_config_rejects_duplicate_or_invalid_targets(tmp_path):
    config = tmp_path / "slo.json"
    config.write_text(
        '{"targets": [{"name": "retrieval", "metric": "ratio", "threshold": 1, "objective": 0.99}, '
        '{"name": "retrieval", "metric": "ratio", "threshold": 1, "objective": 0.99}]}',
        encoding="utf-8",
    )
    try:
        load_config(config)
    except ValueError as exc:
        assert "duplicated" in str(exc)
    else:
        raise AssertionError("duplicate SLO names must be rejected")

    config.write_text(
        '{"targets": [{"name": "bad", "metric": "ratio", "threshold": -1, "objective": 1.2}]}',
        encoding="utf-8",
    )
    try:
        load_config(config)
    except ValueError as exc:
        assert "threshold" in str(exc)
    else:
        raise AssertionError("invalid SLO values must be rejected")


def test_ppr_is_seeded_and_explainable():
    graph = BGraph()
    graph.names = {1: "A", 2: "B", 3: "C"}
    graph.name_id = {"a": 1, "b": 2, "c": 3}
    graph.adj = {1: {2}, 2: {1, 3}, 3: {2}}
    result = graph.ppr("A", top_k=3, iterations=30)
    assert result["found"] is True
    seed = next(item for item in result["ranking"] if item["name"] == "A")
    assert seed["reason"] == "seed"
    assert seed["score"] > 0
    assert all(item["reason"] for item in result["ranking"])


def test_review_priority_uses_forgetting_risk_and_explicit_factors():
    priority = review_priority(ReviewState(), personal_relevance=0.8, prerequisite_importance=0.5)
    assert priority == 0.4


def test_wukr_is_auditable_ratio():
    assert calculate_wukr(10, 3) == {
        "active_users": 10,
        "useful_reuse_users": 3,
        "wukr": 0.3,
    }


def test_credit_policy_reports_post_charge_usage():
    from unittest.mock import patch

    from stratum.services.credit_meter import consume_credits

    class Cursor:
        def __init__(self, row):
            self.row = row

        def fetchone(self):
            return self.row

    class Connection:
        def execute(self, sql, params):
            if sql.startswith("SELECT credits_used"):
                return Cursor((0,))
            if sql.startswith("INSERT INTO stratum.usage_credits"):
                return Cursor((10,))
            raise AssertionError(f"unexpected SQL: {sql}")

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    with patch("stratum.db.get_conn", return_value=Connection()):
        decision = consume_credits("user-1", "free", "deep_research")

    assert decision.allowed is True
    assert decision.used == 10
    assert decision.remaining == 15


def test_graph_ppr_is_registered_in_openapi():
    from stratum.api.main import app

    assert "/graph/ppr" in app.openapi()["paths"]


def test_personal_model_exposes_read_only_learning_events():
    from stratum.api.main import app

    assert "/api/v1/personal-model/events" in app.openapi()["paths"]


def test_reader_action_contract_is_exposed_in_openapi():
    from stratum.api.main import app

    assert "/api/v1/interactions/content/{content_id}/actions" in app.openapi()["paths"]
