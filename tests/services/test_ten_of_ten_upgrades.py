"""Deterministic checks for the directly executable 10/10 upgrade slices."""

from datetime import datetime, timezone


def test_fsrs_review_has_canonical_state_and_retention_control():
    from stratum.services.spaced_repetition import ReviewState, schedule_review

    now = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)
    low, low_due = schedule_review(ReviewState(), "easy", now, desired_retention=0.7)
    high, high_due = schedule_review(ReviewState(), "easy", now, desired_retention=0.95)

    assert low.stability is not None
    assert low.difficulty is not None
    assert low.last_review == now
    assert high_due <= low_due
    assert high.interval_days <= low.interval_days


def test_highlight_locator_uses_w3c_selectors_and_stable_quote_hash():
    from stratum.api.routers.highlights import _quote_hash, _w3c_locator

    text = "A claim worth citing."
    locator = _w3c_locator("sub-1", text, {"start": 10, "end": 30}, None)

    assert locator["source"] == "substrate://sub-1"
    assert locator["selector"][0] == {"type": "TextQuoteSelector", "exact": text}
    assert locator["selector"][1] == {
        "type": "TextPositionSelector",
        "start": 10,
        "end": 30,
    }
    assert _quote_hash(text) == _quote_hash(f"  {text}  ")
    assert len(_quote_hash(text)) == 64


def test_architecture_gate_is_green():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[2] / "scripts" / "check_architecture.py"
    spec = importlib.util.spec_from_file_location("check_architecture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert module.check() == []


def test_aii_migration_prefixes_are_unique_after_library_renumbering():
    from pathlib import Path

    migration_dir = Path(__file__).parents[2] / "aii" / "migrations"
    assert (migration_dir / "0013_library_catalog.sql").is_file()
    assert not (migration_dir / "0009_library_catalog.sql").exists()
    assert (migration_dir / "0009_bu_skill_embedding.sql").is_file()
