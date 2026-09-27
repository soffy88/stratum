from scripts.apply_personal_model_migration import validate_report
from scripts.plan_personal_model_migration import build_plan, parameterized_sql


def test_personal_model_plan_requires_explicit_user_and_object_mappings():
    snapshot = {
        "learning_progress": [
            {
                "point_id": 55,
                "profile_id": 12,
                "mastery_score": 0.7,
                "grade": "learning",
                "attempts": [{"passed": False}],
            }
        ],
        "positional_knowledge_units": [{"ku_id": "ku-1", "natural_text": "作者的主张"}],
        "decision_cases": [{"case_id": 7, "lesson": "可复用边界"}],
        "learning_stuck": [{"stuck_id": 9}],
    }
    manifest = {
        "profile_users": {"12": "user-1"},
        "learning_progress": {"55": {"object_type": "concept", "object_id": "concept-1"}},
        "positional_beliefs": {
            "ku-1": {"user_id": "user-1", "claim_id": "claim-1", "stance": "agree"}
        },
        "decision_context_links": {
            "7": {
                "user_id": "user-1",
                "object_type": "claim",
                "object_id": "claim-1",
                "context_type": "project",
                "context_id": "project-1",
            }
        },
    }

    report = build_plan(snapshot, manifest, "batch-test")

    assert report["status"] == "blocked"
    assert report["summary"] == {
        "candidates": 4,
        "blocked": 1,
        "personal_states": 1,
        "beliefs": 1,
        "context_links": 1,
        "learning_events": 1,
    }
    assert report["blocked"][0]["reason"] == "no_canonical_personal_model_object_mapping"
    assert all(candidate["status"] == "candidate" for candidate in report["candidates"])

    statements = [parameterized_sql(candidate) for candidate in report["candidates"]]
    assert len(statements) == 4
    assert all("personal_model_import_ledger" in item["ledger"]["sql"] for item in statements)
    assert validate_report(report) == []


def test_personal_model_plan_blocks_profile_owner_conflicts_without_writes():
    snapshot = {
        "learning_progress": [{"point_id": 1, "profile_id": 2, "attempts": []}],
    }
    manifest = {
        "profile_users": {"2": "user-a"},
        "learning_progress": {
            "1": {"user_id": "user-b", "object_type": "concept", "object_id": "c-1"}
        },
    }

    report = build_plan(snapshot, manifest, "batch-conflict")

    assert report["candidates"] == []
    assert report["blocked"][0]["reason"] == "profile_user_mapping_conflict"


def test_apply_guard_rejects_tampered_payload_hash():
    report = {
        "batch_id": "batch-tampered",
        "candidates": [
            {
                "id": "import-1",
                "batch_id": "batch-tampered",
                "source_database": "aii_context",
                "source_table": "cx.learning_progress",
                "source_id": "1",
                "target_table": "stratum.personal_states",
                "payload_hash": "wrong",
                "payload_json": {"id": "state-1"},
            }
        ],
    }
    assert any("payload_hash mismatch" in error for error in validate_report(report))
