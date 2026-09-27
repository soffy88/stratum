from scripts.apply_legacy_knowledge_merge import validate_report
from scripts.plan_legacy_knowledge_merge import build_plan, normalize_label


def test_normalization_is_conservative_for_symbolic_names():
    assert normalize_label("Marginal-cost") == "marginal cost"
    assert normalize_label("C++") != normalize_label("C")


def test_legacy_merge_plan_groups_exact_keys_but_never_auto_merges():
    snapshot = {
        "concepts": [
            {
                "source_table": "aii.concept_onto",
                "source_id": "12",
                "name": "Marginal Cost",
                "type": "concept",
                "domain": "economics",
            },
            {
                "source_table": "rf.refined_concept",
                "source_id": "44",
                "name": "marginal-cost",
                "type": "concept",
                "domain": "economics",
            },
        ],
        "relations": [
            {
                "source_table": "aii.edge_onto",
                "source_id": "9",
                "source_ref": "aii.concept_onto:12",
                "target_ref": "rf.refined_concept:44",
                "relation_type": "prerequisite_of",
            }
        ],
    }

    report = build_plan(snapshot, "merge-test")

    assert report["status"] == "needs_manual_review"
    assert report["summary"] == {
        "concept_groups": 1,
        "relation_groups": 1,
        "candidates": 3,
        "blocked": 0,
        "needs_manual_review": 3,
        "approved": 0,
    }
    assert all(item["review_status"] == "needs_manual_review" for item in report["candidates"])


def test_legacy_merge_plan_records_missing_relation_endpoints_as_blocked():
    snapshot = {
        "concepts": [{"source_table": "aii.concept_onto", "source_id": "1", "name": "A"}],
        "relations": [
            {
                "source_table": "aii.edge_onto",
                "source_id": "2",
                "source_ref": "aii.concept_onto:1",
                "target_ref": "rf.refined_concept:404",
                "relation_type": "causes",
            }
        ],
    }

    report = build_plan(snapshot, "merge-blocked")

    assert report["status"] == "blocked"
    assert report["candidates"]
    assert report["blocked"][0]["reason"] == "relation_endpoint_not_in_concept_snapshot"


def test_approved_merge_requires_canonical_identity_and_relation_endpoints():
    snapshot = {
        "concepts": [
            {"source_table": "aii.concept_onto", "source_id": "1", "name": "A"},
            {"source_table": "rf.refined_concept", "source_id": "2", "name": "B"},
        ],
        "relations": [
            {
                "source_table": "aii.edge_onto",
                "source_id": "3",
                "source_ref": "aii.concept_onto:1",
                "target_ref": "rf.refined_concept:2",
                "relation_type": "causes",
            }
        ],
    }
    draft = build_plan(snapshot, "merge-approved")
    concept_groups = {
        group["normalized_key"][0]: group["group_id"] for group in draft["concept_groups"]
    }
    relation_group = draft["relation_groups"][0]["group_id"]
    approvals = {
        "concept_groups": {
            group_id: {"decision": "merge", "target_id": f"canon-{name}", "user_id": "user-1"}
            for name, group_id in concept_groups.items()
        },
        "relation_groups": {
            relation_group: {
                "decision": "merge",
                "target_id": "relation-1",
                "user_id": "user-1",
                "source_concept_id": "canon-a",
                "target_concept_id": "canon-b",
            }
        },
    }

    report = build_plan(snapshot, "merge-approved", approvals)

    assert report["status"] == "ready_for_apply"
    assert report["summary"]["approved"] == 3
    assert validate_report(report) == []
