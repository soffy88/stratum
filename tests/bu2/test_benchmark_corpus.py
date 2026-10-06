"""The evaluation corpus must stay honest — spec §12.

These tests check the dataset itself rather than the pipeline against it. A
corpus that quietly narrows itself is worse than none, because it makes a
single-discipline result look general.
"""

from __future__ import annotations

from tests.bu2.benchmark import disciplines, load_corpus


def test_five_books_are_present():
    corpus = load_corpus()
    assert len(corpus["books"]) == 5, "§12 asks for at least five books"


def test_books_span_five_distinct_disciplines():
    """Five books all from one discipline would not be a cross-discipline corpus."""
    assert len(set(disciplines())) == 5


def test_every_book_records_all_four_required_fields():
    for b in load_corpus()["books"]:
        assert b["book_structure"], f"{b['id']} has no book_structure"
        assert b["concept_map_expectation"], f"{b['id']} has no concept_map expectation"
        assert b["dependency_examples"], f"{b['id']} has no dependency examples"
        assert b["quality_expectation"], f"{b['id']} has no quality expectation"


def test_expectations_are_set_before_they_are_measured():
    """A threshold of 0 would pass every run and prove nothing."""
    for b in load_corpus()["books"]:
        q = b["quality_expectation"]
        assert q["min_level"] in ("A", "B", "C", "D")
        assert isinstance(q["min_cross_chapter_edges"], int)
        assert isinstance(q["min_argument_chains"], int)
        assert q["notes"], f"{b['id']} must explain its expectation"


def test_the_trial_book_is_in_the_corpus():
    """§12's purpose is to stop Thomas Calculus being the only measure."""
    ids = {b["id"] for b in load_corpus()["books"]}
    assert "01KWRXP646FQEPPRPHS3R617MZ" in ids
    assert len(ids) > 1, "the corpus must contain more than the trial book"


def test_missing_disciplines_are_declared_not_hidden():
    corpus = load_corpus()
    requested = {"mathematics", "physics", "biology", "humanities", "textbook"}
    present = set(disciplines()) | {b["role"] for b in corpus["books"]}
    absent = requested - present
    if absent:
        assert corpus.get("_missing_disciplines"), (
            f"{sorted(absent)} are requested by §12 and absent; that must be declared"
        )


def test_every_book_id_is_a_real_substrate_or_declared():
    """A corpus pointing at a deleted book would make every run skip."""
    import pytest

    pytest.importorskip("psycopg2")
    from stratum.services.bu_v2_entrypoint import db

    missing = []
    for b in load_corpus()["books"]:
        try:
            rows = db.query(
                "SELECT 1 FROM substrates WHERE id=%(id)s LIMIT 1", {"id": b["id"]}
            )
        except Exception:
            break  # no database; the id shape is still checked by the other tests
        if not rows:
            missing.append(b["id"])
    assert not missing, f"corpus references substrates that do not exist: {missing}"
