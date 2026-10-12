"""A Repository P8 — in-book annotations over frozen knowledge units.

Contract tests for migration 080 and the annotation service:
- schema: two tables, closed vocabularies, column parity, additive only
- roles: the closed set is enforced, and an unknown role is refused not coerced
- hints: three kinds only, confidence bounded, same book only, never applied
- identity: the occurrence key is content-derived and moves on every input
- quotes: verbatim spans are located, unlocatable ones are flagged not dropped
- no merge: nothing is deleted, edited, merged or renumbered
- authority: B is a receiver of hints, never a dependency
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List

import pytest


ROOT = Path(__file__).parents[2]
MIGRATIONS = ROOT / "src" / "stratum" / "db" / "pg_migrations"
MIGRATION = MIGRATIONS / "080_a_ku_inbook_annotations.sql"
PKG = ROOT / "src" / "stratum" / "knowledge" / "a_repository"

from stratum.knowledge.a_repository.ku_annotation import (  # noqa: E402
    ANNOTATION_TABLES,
    ANNOTATION_VERSION,
    DECLARED_RELATION_KINDS,
    DECLARED_ROLES,
    DEFERRED_RELATION_KINDS,
    QUOTE_STATUS_LOCATED,
    QUOTE_STATUS_UNLOCATABLE,
    RELATION_KIND_VOCABULARY,
    ROLE_VOCABULARY,
    AnnotationPrecondition,
    AnnotationService,
    AnnotationViolation,
    KURelationHint,
    KUOccurrence,
    occurrence_key,
    quote_hash,
    verify_quote,
)
from stratum.knowledge.a_repository.ku_annotation_runner import (  # noqa: E402
    PILOT_HINTS,
    PILOT_OCCURRENCES,
    build_annotation,
    dedup_hints,
    no_merge_gate,
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def _statements() -> str:
    return re.sub(r"--.*", "", _sql())


def _declared_columns(table: str) -> set:
    body = _statements().split(f"CREATE TABLE IF NOT EXISTS stratum.{table}")[1]
    start = body.index("(") + 1
    depth, out = 1, []
    for char in body[start:]:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        out.append(char)
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for char in "".join(out):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(char)
    parts.append("".join(current))
    columns = set()
    for fragment in parts:
        fragment = fragment.strip()
        if not fragment:
            continue
        head = fragment.split()[0]
        if head.upper() in {"CONSTRAINT", "UNIQUE", "CHECK", "PRIMARY", "FOREIGN", "REFERENCES"}:
            continue
        columns.add(head)
    return columns


@pytest.fixture(scope="module")
def annotated():
    return build_annotation()


# ── schema ────────────────────────────────────────────────────────────────────


def test_080_is_additive_only():
    statements = _statements()
    assert "ALTER TABLE" not in statements
    assert "DROP " not in statements
    assert "INSERT INTO" not in statements
    assert not re.search(r"^[ \t]*UPDATE\b", statements, re.MULTILINE)


def test_080_creates_exactly_two_tables():
    created = set(re.findall(r"CREATE TABLE IF NOT EXISTS stratum\.(\w+)", _statements()))
    assert created == set(ANNOTATION_TABLES)


def test_080_recreates_nothing_it_inherits():
    statements = _statements()
    for inherited in (
        "knowledge_unit",
        "ku_candidate",
        "ku_verification",
        "ku_freeze_event",
        "ku_identity",
        "ku_revision",
        "ku_review_event",
        "ku_confidence_evolution",
        "ku_relation",
        "relation_candidate",
        "reading_evidence",
        "source_version",
    ):
        assert f"CREATE TABLE IF NOT EXISTS stratum.{inherited} (" not in statements


def test_080_reaches_only_a_tables():
    named = set(re.findall(r"stratum\.(\w+)", _sql()))
    assert named <= set(ANNOTATION_TABLES) | {
        "knowledge_unit",
        "source_version",
        "reading_evidence",
    }


def test_080_never_executed_against_production():
    assert "staging database only" in _sql()


def test_every_foreign_key_restricts():
    actions = re.findall(r"DELETE (\w+)", _sql())
    assert set(actions) == {"RESTRICT"}


def test_composite_same_source_keys_are_declared():
    statements = _statements()
    for side in ("from", "to"):
        assert f"CONSTRAINT ku_relation_hint_{side}_same_source" in statements
        assert f"FOREIGN KEY ({side}_unit_id, source_version_id)" in statements
    assert statements.count("REFERENCES stratum.knowledge_unit (id, source_version_id)") == 2


def test_the_composite_key_target_is_declared_before_the_table():
    """079 measured it: declared after, PostgreSQL refuses the key.

    The index must precede the table that references it, or DDL being
    transactional means the whole migration rolls back and 080 could be
    recorded in the ledger by a wrapper that exited zero anyway.
    """
    statements = _statements()
    index = statements.index(
        "CREATE UNIQUE INDEX IF NOT EXISTS knowledge_unit_id_source_version_uniq"
    )
    table = statements.index("CREATE TABLE IF NOT EXISTS stratum.ku_relation_hint")
    assert index < table


# ── vocabularies ──────────────────────────────────────────────────────────────


def test_the_role_vocabulary_is_closed_and_seven_valued():
    assert DECLARED_ROLES == (
        "DEFINITION",
        "THEOREM",
        "EXAMPLE",
        "EXERCISE",
        "SUMMARY",
        "ASIDE",
        "OTHER",
    )
    assert ROLE_VOCABULARY == frozenset(DECLARED_ROLES)


def test_the_schema_and_the_service_declare_the_same_roles():
    block = _statements().split("CHECK (role IN (")[1].split(")")[0]
    assert set(re.findall(r"'([A-Z_]+)'", block)) == set(DECLARED_ROLES)


def test_the_hint_kind_vocabulary_is_closed_and_three_valued():
    assert DECLARED_RELATION_KINDS == ("RESTATES", "SUMMARIZES", "APPLIES")
    assert RELATION_KIND_VOCABULARY == frozenset(DECLARED_RELATION_KINDS)


def test_the_schema_and_the_service_declare_the_same_kinds():
    block = _statements().split("CHECK (kind IN (")[1].split(")")[0]
    assert set(re.findall(r"'([A-Z_]+)'", block)) == set(DECLARED_RELATION_KINDS)


def test_the_deferred_kinds_are_absent_from_the_schema():
    """Absent rather than unused: a later writer cannot smuggle DUPLICATE in."""
    statements = _statements()
    for deferred in DEFERRED_RELATION_KINDS:
        assert deferred not in statements


def test_columns_the_writer_names_are_declared():
    from stratum.knowledge.a_repository.ku_annotation import _HINT_COLUMNS, _OCCURRENCE_COLUMNS

    assert set(_OCCURRENCE_COLUMNS) <= _declared_columns("ku_occurrence")
    assert set(_HINT_COLUMNS) <= _declared_columns("ku_relation_hint")
    occurrence_fields = set(
        vars(
            KUOccurrence(
                id="", source_version_id="", unit_id="", locator="", quote_span="", role=""
            )
        )
    )
    hint_fields = set(
        vars(
            KURelationHint(
                id="", source_version_id="", kind="", from_unit_id="", to_unit_id="", confidence=0.0
            )
        )
    )
    assert set(_OCCURRENCE_COLUMNS) <= occurrence_fields
    assert set(_HINT_COLUMNS) <= hint_fields


def test_the_unlocatable_quote_flag_is_consistent_in_the_schema():
    """A row cannot sit in the review queue with a LOCATED span, or the reverse.

    Without this the two columns could disagree and a row would read as
    verified while it sat in the queue.
    """
    statements = _statements()
    assert "CHECK (quote_status IN ('LOCATED', 'UNLOCATED'))" in statements
    assert "CHECK ((quote_status = 'UNLOCATED') = review_required)" in statements


def test_confidence_is_bounded_at_both_ends():
    assert "CHECK (confidence >= 0.0 AND confidence <= 1.0)" in _statements()


# ── roles ─────────────────────────────────────────────────────────────────────


def test_every_role_the_vocabulary_names_is_accepted(annotated):
    """Each of the seven is writable, not merely declared.

    A role the enum carries but the writer refuses would be a vocabulary the
    service cannot speak, and nothing else in the suite would notice.
    """
    result = build_annotation()
    service: AnnotationService = result["service"]
    unit, evidence = PILOT_OCCURRENCES[0]["unit"], PILOT_OCCURRENCES[0]["evidence"]
    for role in DECLARED_ROLES:
        written = service.annotate_occurrence(
            unit, evidence, f"p.probe.{role}", "a forbidden span", role
        )
        assert written.occurrence.role == role


def test_an_unknown_role_is_refused_not_coerced(annotated):
    result = build_annotation()
    service: AnnotationService = result["service"]
    unit, evidence = PILOT_OCCURRENCES[0]["unit"], PILOT_OCCURRENCES[0]["evidence"]
    with pytest.raises(AnnotationPrecondition):
        service.annotate_occurrence(unit, evidence, "p.9", "a span", "CONCLUSION")


def test_a_mislabelled_role_never_becomes_other(annotated):
    """Coercing would hide a mislabelled passage inside the catch-all.

    `OTHER` is a role a reader may choose, not a value the writer falls back
    to. Asserted by writing nothing: the refusal leaves no row at all, so
    there is no row whose role quietly became OTHER.
    """
    result = build_annotation()
    service: AnnotationService = result["service"]
    before = len(result["sink"].ku_occurrences)
    unit, evidence = PILOT_OCCURRENCES[0]["unit"], PILOT_OCCURRENCES[0]["evidence"]
    with pytest.raises(AnnotationPrecondition):
        service.annotate_occurrence(unit, evidence, "p.9", "a span", "NOT_A_ROLE")
    assert len(result["sink"].ku_occurrences) == before
    assert not [o for o in result["sink"].ku_occurrences.values() if o.role == "OTHER"]


def test_the_role_breakdown_counts_every_declared_role(annotated):
    """Zero-filled: an empty role reads as zero, not as a missing key."""
    breakdown = annotated["service"].role_breakdown()
    assert set(breakdown) == set(DECLARED_ROLES)
    assert sum(breakdown.values()) == len(PILOT_OCCURRENCES)


def test_no_occurrence_carries_an_undeclared_role(annotated):
    assert annotated["service"].undeclared_roles() == []


def test_a_blank_locator_or_quote_is_refused(annotated):
    result = build_annotation()
    service: AnnotationService = result["service"]
    unit, evidence = PILOT_OCCURRENCES[0]["unit"], PILOT_OCCURRENCES[0]["evidence"]
    for locator, quote in (("", "a real span"), ("p.9", ""), ("   ", "span")):
        with pytest.raises(AnnotationPrecondition):
            service.annotate_occurrence(unit, evidence, locator, quote, "ASIDE")


# ── relation hints ────────────────────────────────────────────────────────────


def test_the_three_hint_kinds_are_all_writable(annotated):
    result = build_annotation()
    service: AnnotationService = result["service"]
    units = sorted(result["sink"].units)
    for index, kind in enumerate(DECLARED_RELATION_KINDS):
        written = service.add_relation_hint(
            units[index % len(units)],
            units[(index + 1) % len(units)],
            kind,
            0.5,
            result["hints"][0].evidence_id,
        )
        assert written.hint.kind == kind


def test_a_deferred_kind_is_refused(annotated):
    result = build_annotation()
    service: AnnotationService = result["service"]
    hint = result["hints"][0]
    for kind in DEFERRED_RELATION_KINDS:
        with pytest.raises(AnnotationPrecondition):
            service.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, kind, 0.9, hint.evidence_id
            )


def test_a_hint_must_have_one_of_the_three_units_of_this_book(annotated):
    result = build_annotation()
    service: AnnotationService = result["service"]
    hint = result["hints"][0]
    with pytest.raises(AnnotationPrecondition):
        service.add_relation_hint(
            "ku_000000000000", hint.to_unit_id, "RESTATES", 0.9, hint.evidence_id
        )


def test_a_hint_may_not_join_a_unit_to_itself(annotated):
    result = build_annotation()
    service: AnnotationService = result["service"]
    hint = result["hints"][0]
    with pytest.raises(AnnotationPrecondition):
        service.add_relation_hint(
            hint.from_unit_id, hint.from_unit_id, "RESTATES", 0.9, hint.evidence_id
        )


def test_confidence_is_bounded(annotated):
    result = build_annotation()
    service: AnnotationService = result["service"]
    hint = result["hints"][0]
    for confidence in (-0.1, 1.5, 2.0):
        with pytest.raises(AnnotationPrecondition):
            service.add_relation_hint(
                hint.from_unit_id, hint.to_unit_id, "APPLIES", confidence, hint.evidence_id
            )


def test_the_confidence_is_stored_as_a_reading_not_a_fact(annotated):
    """0 <= confidence <= 1 is a bound on a reading, not a probability.

    The value is carried on the hint and never used to move a unit, merge a
    unit or mark a unit a duplicate. Nothing in this stage reads it back
    except to report it.
    """
    assert 0.0 <= annotated["hints"][0].confidence <= 1.0
    assert annotated["service"].out_of_range_hints() == []


def test_every_hint_names_one_book_and_two_units_of_it(annotated):
    service: AnnotationService = annotated["service"]
    for hint in annotated["sink"].ku_relation_hints.values():
        left = annotated["sink"].units[hint.from_unit_id]
        right = annotated["sink"].units[hint.to_unit_id]
        assert left.source_version_id == right.source_version_id
        assert hint.source_version_id == left.source_version_id
    assert service.cross_source_hints() == []
    assert service.self_hints() == []


def test_a_hint_may_not_cross_books(annotated):
    """The writer refuses it, and the schema refuses it again."""
    result = build_annotation()
    service: AnnotationService = result["service"]
    with pytest.raises(AnnotationPrecondition):
        service.add_relation_hint(
            "ku_not_a_unit", "ku_also_not_a_unit", "RESTATES", 0.9, "ev_absent"
        )
    assert "REFERENCES stratum.knowledge_unit (id, source_version_id)" in _statements()


# ── identity and idempotency ─────────────────────────────────────────────────


def test_the_occurrence_key_moves_on_every_input():
    base = occurrence_key("sv_1", "ku_a", "p.3", "a span", "DEFINITION")
    assert base == occurrence_key("sv_1", "ku_a", "p.3", "a span", "DEFINITION")
    assert base != occurrence_key("sv_2", "ku_a", "p.3", "a span", "DEFINITION")
    assert base != occurrence_key("sv_1", "ku_b", "p.3", "a span", "DEFINITION")
    assert base != occurrence_key("sv_1", "ku_a", "p.4", "a span", "DEFINITION")
    assert base != occurrence_key("sv_1", "ku_a", "p.3", "other span", "DEFINITION")
    assert base.startswith("kao_")


def test_the_quote_hash_is_over_the_span_verbatim():
    assert quote_hash("a span") == quote_hash("a span")
    assert quote_hash("a span") != quote_hash("a span ")
    assert quote_hash("a span") != quote_hash("a  span")


def test_two_units_at_one_place_are_two_occurrences(annotated):
    """The measured case: a unit and its own revision, same page, same span.

    A key without the unit gives both the same key and the second silently
    overwrites the first, which is a merge performed by a hash collision
    rather than by a decision.
    """
    service: AnnotationService = annotated["service"]
    hammurabi = [o for o in annotated["sink"].ku_occurrences.values() if o.locator == "p.3"]
    assert len(hammurabi) == 2
    assert len({o.id for o in hammurabi}) == 2
    assert len({o.unit_id for o in hammurabi}) == 2
    assert len({o.role for o in hammurabi}) == 2
    assert service.duplicate_occurrences() == []


def test_rerunning_the_pilot_writes_nothing(annotated):
    """The same pilot again is a no-op: same keys, same count."""
    service: AnnotationService = annotated["service"]
    before = {o.id for o in annotated["sink"].ku_occurrences.values()}
    for entry in PILOT_OCCURRENCES:
        service.annotate_occurrence(
            entry["unit"], entry["evidence"], entry["locator"], entry["quote"], entry["role"]
        )
    after = {o.id for o in annotated["sink"].ku_occurrences.values()}
    assert before == after
    assert service.duplicate_occurrences() == []


def test_a_fresh_run_produces_the_same_occurrence_keys():
    first = {o.id for o in build_annotation()["occurrences"]}
    second = {o.id for o in build_annotation()["occurrences"]}
    assert first == second
    assert len(first) == len(PILOT_OCCURRENCES)


def test_the_same_passage_relabelled_is_a_new_occurrence(annotated):
    """A re-reading is a new row under a new role, not an edit of the old one.

    The occurrence hash carries the role, so this is the same passage with a
    different reading — and the first reading is still there.
    """
    result = build_annotation()
    service: AnnotationService = result["service"]
    entry = PILOT_OCCURRENCES[0]
    service.annotate_occurrence(
        entry["unit"], entry["evidence"], entry["locator"], entry["quote"], "ASIDE"
    )
    of_unit = service.occurrences_of(entry["unit"])
    assert len(of_unit) == 2
    assert {o.role for o in of_unit} == {entry["role"], "ASIDE"}
    assert service.duplicate_occurrences() == []


def test_hint_identity_is_order_independent():
    """A-hints-B and B-hints-A are one observation, not two."""
    from stratum.knowledge.a_repository.ku_annotation import hint_id

    assert hint_id("RESTATES", "ku_a", "ku_b") == hint_id("RESTATES", "ku_b", "ku_a")
    assert hint_id("RESTATES", "ku_a", "ku_b") != hint_id("SUMMARIZES", "ku_a", "ku_b")


def test_re_adding_the_same_hint_appends_nothing(annotated):
    service: AnnotationService = annotated["service"]
    before = {h.id for h in annotated["sink"].ku_relation_hints.values()}
    for entry in PILOT_HINTS:
        service.add_relation_hint(
            entry["from_unit"],
            entry["to_unit"],
            entry["kind"],
            entry["confidence"],
            entry["evidence"],
        )
    after = {h.id for h in annotated["sink"].ku_relation_hints.values()}
    assert before == after
    assert service.duplicate_hints() == []


# ── quote_span verification ──────────────────────────────────────────────────


def test_a_verbatim_span_is_located():
    """A verbatim span is found, and the offsets read the text back out.

    The offsets are asserted against the source rather than against a number
    written here: a hand-computed index is a second thing to be wrong about.
    """
    source = "信贷在古代和中世纪时期就得到了普遍应用。"
    probe = "和中世纪时期"
    status, review, span = verify_quote(probe, source)
    assert status == QUOTE_STATUS_LOCATED
    assert review is False
    assert span is not None
    assert span[1] - span[0] == len(probe)
    assert source[span[0] : span[1]] == probe


def test_an_unlocatable_span_is_reported_not_guessed():
    status, review, span = verify_quote(
        "a span that is not in the book", "the book says something else"
    )
    assert status == QUOTE_STATUS_UNLOCATABLE
    assert span is None
    assert review is True


def test_the_comparison_is_verbatim_with_no_normalisation():
    """One character of difference is not a match.

    A span that had to be normalised or fuzzed to match is a span a reader
    cannot find in the book, so none of it is tolerated: not case, not
    whitespace, not a one-character slip.
    """
    source = "the book says something else"
    for probe in (
        "THE BOOK",
        "the  book",
        "the book say something",
        "the book sayz something else",
        "the book.",
    ):
        status, _, _ = verify_quote(probe, source)
        assert status == QUOTE_STATUS_UNLOCATABLE, probe


def test_an_empty_span_is_never_located():
    for source in ("", "some text"):
        status, review, span = verify_quote("", source)
        assert status == QUOTE_STATUS_UNLOCATABLE
        assert span is None and review is True


def test_a_flagged_occurrence_is_kept_and_queued(annotated):
    """Written, flagged, and never dropped.

    The row exists, says so, and lands in the queue. Dropping it would be a
    place in the book that no longer accounts for itself.
    """
    result = build_annotation()
    service: AnnotationService = result["service"]
    unit, evidence = PILOT_OCCURRENCES[0]["unit"], PILOT_OCCURRENCES[0]["evidence"]
    written = service.annotate_occurrence(
        unit, evidence, "p.1", "a span that is not in this book", "ASIDE"
    )
    assert written.written is True
    assert written.occurrence.id in result["sink"].ku_occurrences
    assert written.occurrence.quote_status == QUOTE_STATUS_UNLOCATABLE
    assert written.occurrence.review_required is True
    assert written.occurrence.id in service.review_queue()


def test_the_review_queue_only_holds_the_flagged_rows(annotated):
    """The pilot corpus locates every quote, so its queue is empty."""
    assert annotated["service"].review_queue() == []
    assert len(annotated["service"].located_quotes()) == len(PILOT_OCCURRENCES)


def test_every_pilot_quote_is_verbatim_in_its_evidence(annotated):
    store = annotated["result"]["base"]["pipeline"].store
    for occurrence in annotated["sink"].ku_occurrences.values():
        unit = annotated["sink"].units[occurrence.unit_id]
        candidate = store.ku_candidates[unit.candidate_id]
        evidence = store.evidence[candidate.evidence_id]
        status, _, span = verify_quote(occurrence.quote_span, evidence.content_span)
        assert status == QUOTE_STATUS_LOCATED, occurrence.id
        assert span is not None
        assert occurrence.quote_status == status
        assert occurrence.review_required is False


# ── no merge, no delete, no edit ─────────────────────────────────────────────


def test_nothing_may_be_merged(annotated):
    service: AnnotationService = annotated["service"]
    occurrence = annotated["occurrences"][0]
    units = sorted(annotated["sink"].units)
    with pytest.raises(AnnotationViolation):
        service.merge_occurrences(occurrence.id, "kao_any")
    with pytest.raises(AnnotationViolation):
        service.merge_units(units[0], units[1])


def test_nothing_may_be_deleted(annotated):
    service: AnnotationService = annotated["service"]
    with pytest.raises(AnnotationViolation):
        service.delete_occurrence(annotated["occurrences"][0].id)
    with pytest.raises(AnnotationViolation):
        service.delete_hint(annotated["hints"][0].id)


def test_nothing_may_be_edited(annotated):
    service: AnnotationService = annotated["service"]
    with pytest.raises(AnnotationViolation):
        service.update_occurrence(annotated["occurrences"][0].id, role="OTHER")
    with pytest.raises(AnnotationViolation):
        service.update_unit(sorted(annotated["sink"].units)[0], statement="x")
    with pytest.raises(AnnotationViolation):
        service.renumber_unit(annotated["occurrences"][0].unit_id, id="ku_x")


def test_a_hint_may_not_be_applied(annotated):
    """Applying one would merge two occurrences from A仓, which is B仓's call.

    The reason this raises rather than no-ops: a no-op return value is
    something a caller could mistake for success.
    """
    service: AnnotationService = annotated["service"]
    with pytest.raises(AnnotationViolation, match="hint"):
        service.apply_hint(annotated["hints"][0].id)


def test_no_row_was_ever_merged_or_dropped(annotated):
    """Refusals leave no row behind, and the written count is the declared one."""
    service: AnnotationService = annotated["service"]
    with pytest.raises(AnnotationViolation):
        service.merge_occurrences(annotated["occurrences"][0].id, "kao_x")
    assert len(annotated["sink"].ku_occurrences) == len(PILOT_OCCURRENCES)
    assert len(annotated["sink"].ku_relation_hints) == len(PILOT_HINTS)
    assert len(annotated["sink"].units) == 11


def test_every_forbidden_shape_is_refused(annotated):
    """The negative gate, read rather than assumed.

    A map, so a regression names which case stopped being refused. Every
    probe goes through a write or a public method and asserts on a raise.
    """
    negative = no_merge_gate(annotated)
    assert negative, "no_merge_gate must not be empty"
    for case, refused in sorted(negative.items()):
        assert refused, case


def test_the_unit_rows_are_untouched_by_the_stage(annotated):
    """Annotating changed no unit row, field for field."""
    after = {key: dict(vars(unit)) for key, unit in sorted(annotated["sink"].units.items())}
    assert after == annotated["unit_snapshot_before"]


# ── dedup hints for B仓 ──────────────────────────────────────────────────────


def test_the_hints_are_exported_as_plain_data(annotated):
    payload = dedup_hints(annotated["service"])
    assert len(payload) == len(PILOT_HINTS)
    for hint in payload:
        assert hint["authority"] == "A_REPOSITORY"
        assert hint["kind"] in DECLARED_RELATION_KINDS
        confidence = float(hint["confidence"])
        assert 0.0 <= confidence <= 1.0
        assert isinstance(hint["applied"], bool)


def test_no_hint_claims_to_have_been_applied(annotated):
    """B is free to reject every one of them, and the payload says so.

    A payload that said `applied: true` would make a hint a decision and this
    stage a merge order. This is the gate that keeps "exposed as hints" honest,
    and it reads the payload rather than the docstring.
    """
    for hint in dedup_hints(annotated["service"]):
        assert hint["applied"] is False
        assert "merged" not in hint
        assert "duplicate_of" not in hint


def test_the_export_is_scoped_to_one_book(annotated):
    from stratum.knowledge.a_repository.ku_annotation_runner import (
        dedup_hints as runner_dedup_hints,
    )

    source = annotated["source_version_id"]
    scoped = [h for h in runner_dedup_hints(annotated["service"], source)]
    assert len(scoped) == len(PILOT_HINTS)
    assert all(h["source_version_id"] == source for h in scoped)


def test_no_hint_carries_a_semantic_judgement(annotated):
    """No banned field on the row, and no deferred kind in the payload."""
    from stratum.knowledge.a_repository.ku_annotation import (
        _HINT_COLUMNS,
    )

    banned = (
        "meaning",
        "interpretation",
        "explanation",
        "truth_score",
        "cause",
        "significance",
        "implies",
        "proves",
        "duplicate_of",
        "is_duplicate",
    )
    for column in _HINT_COLUMNS:
        assert column not in banned
    for hint in dedup_hints(annotated["service"]):
        assert hint["kind"] not in DEFERRED_RELATION_KINDS


# ── authority and gates ──────────────────────────────────────────────────────


def test_the_stage_reaches_nothing_outside_the_a_chain():
    """Structural: the service's imports are the A chain plus the stdlib."""
    source = (PKG / "ku_annotation.py").read_text(encoding="utf-8")
    code = re.sub(r'""".*?"""', "", source, flags=re.DOTALL)
    imports = set(re.findall(r"^\s*(?:from|import)\s+([\w.]+)", code, re.MULTILINE))
    assert imports <= {
        "__future__",
        "hashlib",
        "dataclasses",
        "enum",
        "typing",
        "identity",
        "persistence",
        ".identity",
        ".persistence",
    }
    assert not re.search(r"\b(bu2?|b_repo|ku_onto|concept_onto|rf\.|aii_refined)\b", code)


def test_nothing_imports_another_repository():
    from stratum.knowledge.a_repository.projection_builder import (
        artifact_drift,
        external_imports,
    )

    assert external_imports() == []
    payload = {"occurrences": [o.id for o in build_annotation()["occurrences"]], "dedup_hints": []}
    assert artifact_drift(payload) == {}


def test_every_gate_passes_and_the_verdict_reads_all_of_them(annotated):
    from stratum.knowledge.a_repository.ku_annotation_runner import gate_results
    from stratum.knowledge.a_repository.verdict import verdict

    gates = gate_results(annotated)
    assert gates, "gate_results must not be empty"
    for name, value in sorted(gates.items()):
        assert value == "PASS", f"{name}={value}"
    assert verdict(gates) == "PASS"
    assert len(gates) == 20


def test_the_runner_makes_no_ledger_read_as_pass():
    """R-2: no ledger is NOT_EXECUTED, which the verdict turns into BLOCKED."""
    from stratum.knowledge.a_repository.ku_annotation_runner import (
        schema_in_ledger,
    )

    assert schema_in_ledger(None) == "NOT_EXECUTED"
    assert schema_in_ledger(["070_a_repository_foundation.sql"]) == "FAIL"


def test_the_emitted_script_is_one_transaction_and_idempotent(annotated, tmp_path):
    from stratum.knowledge.a_repository.ku_annotation_runner import write_sql

    path = write_sql(annotated, str(tmp_path / "annotation.sql"))
    script = Path(path).read_text(encoding="utf-8")
    assert script.count("BEGIN;") == 1
    assert script.count("COMMIT;") == 1
    inserts = [line for line in script.splitlines() if line.startswith("INSERT INTO")]
    assert len(inserts) == len(PILOT_OCCURRENCES) + len(PILOT_HINTS)
    for line in inserts:
        assert "ON CONFLICT (" in line
        assert line.endswith("ON CONFLICT (id) DO NOTHING;")


def test_the_script_carries_the_occurrence_hash(annotated, tmp_path):
    """080 requires occurrence_hash NOT NULL, so the emitter must write it."""
    from stratum.knowledge.a_repository.ku_annotation_runner import write_sql

    path = write_sql(annotated, str(tmp_path / "annotation.sql"))
    script = Path(path).read_text(encoding="utf-8")
    assert "occurrence_hash" in script
    assert len(re.findall(r"kah_[a-f0-9]{16}", script)) == len(PILOT_OCCURRENCES)


def test_the_pilot_annotations_are_the_declared_ones(annotated):
    """The gates run against real rows of the real corpus."""
    assert len(annotated["occurrences"]) == len(PILOT_OCCURRENCES)
    assert len(annotated["hints"]) == len(PILOT_HINTS)
    assert len(annotated["sink"].ku_occurrences) == len(PILOT_OCCURRENCES)
    assert annotated["service"].traceability()["percent"] == 100.0


def test_the_stage_names_its_own_version(annotated):
    assert ANNOTATION_VERSION == "a-p8-v0.1"
    assert annotated["service"].traceability()["occurrences"] == len(PILOT_OCCURRENCES)
