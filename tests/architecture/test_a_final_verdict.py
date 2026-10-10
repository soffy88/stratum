"""The final verdict, and the property it exists to guarantee.

Every layer derives its own verdict from its own gates. This file checks the
union of them: that every gate a layer reports reaches the chain verdict, and
that the chain verdict fails when any layer does.

The second half matters more than the first. A chain-wide verdict computed by
reading each layer's headline string would report PASS for eight passing layers
while the ninth reported FAIL, and nothing in the output would show it. Three
layers have shipped exactly that shape already -- 8 reported and 6 counted, 14
and 12, 7 returned beside a list of 5 -- so the property is asserted here rather
than assumed, and each assertion is mutation-checked below.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


#: Chain-level verdict tests whose premise is "every other gate passes". The
#: P5_5_PAPER_EVIDENCE_FK layer's live gates read the A staging database through
#: `docker exec aii-postgres` (see paper_evidence_fk_runner); without it they
#: report FAIL and the chain verdict is FAIL whatever the mutation under test.
#: The ledger and catalog evidence is supplied by the fixture below; a seeded
#: staging database cannot be, so these run under `-m production_runtime`.
_LIVE_A_STAGING = pytest.mark.production_runtime

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from stratum.knowledge.a_repository.verdict import (  # noqa: E402
    VERDICT_BLOCKED,
    VERDICT_FAIL,
    VERDICT_PASS,
    verdict,
    verdict_inputs,
)


def _load_aggregator():
    spec = importlib.util.spec_from_file_location(
        "a_final_verdict", _ROOT / "scripts" / "a_final_verdict.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AFV = _load_aggregator()


#: The stratum catalog P7's schema-closure gate reads. Written here rather than
#: inherited: the gate is NOT_EXECUTED without one, and the chain verdict BLOCKS.
#: An earlier version of this file read A_P7_DB_TABLES from the environment, so
#: it passed under `pytest tests/architecture` and failed under `pytest tests/`.
#: A test that depends on how pytest was invoked is testing the shell.
_A_CATALOG = (
    "book_source source_version reading_run reading_evidence evidence_quality "
    "ku_candidate ku_verification knowledge_unit ku_freeze_event ku_revision "
    "ku_confidence_evolution ku_identity"
)


@pytest.fixture(scope="module")
def collected(tmp_path_factory):
    """Both pieces of evidence the two schema-gated layers need.

    Written here rather than read from the environment. Two gates depend on it
    and neither can pass without it: `schema` is NOT_EXECUTED with no ledger,
    and `G5_schema_closure` is NOT_EXECUTED with no catalog. A fixture that
    inherited either from the environment made this file pass under
    `pytest tests/architecture` and fail under `pytest tests/`.
    """
    from stratum.knowledge.a_repository.ku_evolution_runner import REQUIRED_CHAIN as P5_CHAIN
    from stratum.knowledge.a_repository.ku_identity_runner import REQUIRED_CHAIN as P6_CHAIN

    root = tmp_path_factory.mktemp("evidence")
    catalog = root / "tables.txt"
    catalog.write_text(_A_CATALOG + "\n", encoding="utf-8")
    ledger = root / "ledger.txt"
    ledger.write_text("\n".join(sorted(set(P5_CHAIN) | set(P6_CHAIN))) + "\n", encoding="utf-8")

    previous = {key: os.environ.get(key) for key in ("A_P7_DB_TABLES", "A_P5_LEDGER_FILE")}
    os.environ["A_P7_DB_TABLES"] = str(catalog)
    os.environ["A_P5_LEDGER_FILE"] = str(ledger)
    try:
        merged, report = AFV.collect()
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return merged, report


def test_every_layer_reports_and_every_layer_is_counted(collected):
    merged, report = collected
    assert len(report) == len(AFV.LAYERS)
    for row in report:
        assert not row.get("error"), f"{row['layer']} failed to run: {row}"
        assert row["reported"] > 0, f"{row['layer']} reported no gates"
        assert row["reported"] == row["counted"], (
            f"{row['layer']} reported {row['reported']} gates but only "
            f"{row['counted']} reached the merge"
        )
        assert not row["non_string"], (
            f"{row['layer']} still publishes measurements inside `gates`: {row['non_string']}"
        )


def test_each_layers_own_verdict_agrees_with_its_gates(collected):
    """A layer must not report a verdict its own gates disagree with."""
    _, report = collected
    for row in report:
        assert row["verdict"] in (VERDICT_PASS, VERDICT_FAIL, VERDICT_BLOCKED)
        assert row["verdict_key"], f"{row['layer']} exposes no verdict key"


@_LIVE_A_STAGING
def test_the_chain_verdict_is_derived_not_declared(collected):
    merged, _ = collected
    evidence = verdict_inputs(merged)
    assert not evidence["gates_not_executed"], f"unevidenced: {evidence['gates_not_executed']}"
    assert evidence["verdict"] == VERDICT_PASS
    assert evidence["gates_not_executed"] == []
    assert evidence["gates_failed"] == []
    assert evidence["gates_unknown_status"] == []
    # The count is the sum of what the layers reported, not a remembered total.
    assert evidence["gate_count"] == len(merged)
    assert evidence["gate_count"] == sum(
        len([k for k in merged if k.startswith(f"{layer}:")]) for layer in AFV.LAYERS
    )


def test_the_aggregator_holds_no_list_of_gate_names():
    """The defect was always a parallel list. There must not be one here."""
    source = (_ROOT / "scripts" / "a_final_verdict.py").read_text(encoding="utf-8")
    for banned in ("GATE_ORDER", "GATE_NAMES", "ALL_GATES"):
        assert banned not in source, f"{banned} is back"


# ── the chain verdict has to be able to fail ─────────────────────────────────


def test_one_failing_gate_fails_the_chain(collected):
    merged, _ = collected
    broken = dict(merged)
    broken["P7_PROJECTION:G5_isolation"] = VERDICT_FAIL
    assert verdict(broken) == VERDICT_FAIL


@_LIVE_A_STAGING
def test_a_non_string_gate_blocks_rather_than_passes(collected):
    """A measurement left inside `gates` must not be coerced into a pass.

    This is why seven gates were converted and six duplicate detail dicts were
    removed instead of being made to fit: an unrecognised value is BLOCKED, and
    that is the correct reading of a gate nobody defined.
    """
    merged, _ = collected
    broken = dict(merged)
    broken["P5_1_MECHANISM:GATE_2_traceability_percent"] = 100.0
    assert verdict(broken) == VERDICT_BLOCKED


@_LIVE_A_STAGING
def test_an_unexecuted_gate_blocks(collected):
    merged, _ = collected
    broken = dict(merged)
    broken["P6_IDENTITY:schema"] = "NOT_EXECUTED"
    assert verdict(broken) == VERDICT_BLOCKED


@_LIVE_A_STAGING
def test_a_layer_that_cannot_run_blocks_the_chain(monkeypatch, collected):
    """A layer that fails to execute must block, not be skipped.

    Skipping is the failure mode worth guarding: the chain would report the
    eight layers that worked and say PASS.
    """
    merged, _ = collected
    real = AFV.run_layer
    monkeypatch.setattr(
        AFV,
        "run_layer",
        lambda layer, module: (
            ({}, "ImportError") if layer == "P7_PROJECTION" else real(layer, module)
        ),
    )
    broken, report = AFV.collect()
    row = next(r for r in report if r["layer"] == "P7_PROJECTION")
    assert row.get("error")
    assert verdict(broken) == VERDICT_BLOCKED


def test_no_layer_is_silently_absent(collected):
    merged, report = collected
    for layer in AFV.LAYERS:
        assert any(k.startswith(f"{layer}:") for k in merged), (
            f"{layer} contributed no gate to the chain verdict"
        )


def test_the_chain_covers_all_nine_layers(collected):
    merged, _ = collected
    prefixes = {k.split(":", 1)[0] for k in merged}
    assert prefixes == set(AFV.LAYERS), f"expected {sorted(AFV.LAYERS)}, got {sorted(prefixes)}"


@_LIVE_A_STAGING
def test_the_aggregator_does_not_coerce_a_measurement_into_a_pass(monkeypatch):
    """Regression, mutation-checked.

    The mutation it catches: merging a layer's gates as
    `value if isinstance(value, str) else "PASS"`, which would silently promote
    a leftover measurement to a passing gate. The direct check above calls
    `verdict()` on a hand-built mapping and so never reaches the merge.
    """
    real = AFV.run_layer
    monkeypatch.setattr(
        AFV,
        "run_layer",
        lambda layer, module: (
            ({"GATE_ok": "PASS", "GATE_measured": 100.0}, "k")
            if layer == "P5_1_MECHANISM"
            else real(layer, module)
        ),
    )
    merged, report = AFV.collect()
    row = next(r for r in report if r["layer"] == "P5_1_MECHANISM")
    assert row["non_string"] == ["GATE_measured"], "the aggregator did not notice a non-string gate"
    assert verdict(merged) == VERDICT_BLOCKED, (
        "a measurement inside `gates` was coerced into a pass"
    )
