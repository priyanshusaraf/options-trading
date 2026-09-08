from __future__ import annotations

from collections.abc import Sequence
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from app.backtest.metrics import BTTrade
from app.ir.hashing import canonical_json, content_address
from research.data.store import StaticDataSource, materialize
from research.domain.models import ExperimentSpec
from research.evaluation import kernels
from research.domain.base import init_research_db, make_engine, make_sessionmaker
from research.domain.models import ExperimentRun, Hypothesis, ResearchProgram
from research.evidence import (
    MAX_EVIDENCE_BYTES,
    EvidenceRejected,
    decode_terminal_evidence,
    encode_terminal_evidence,
)
from research.robustness.integration import (
    AVAILABLE,
    NOT_REQUESTED,
    UNAVAILABLE,
    RobustnessEvidenceRejected,
    build_stationary_bootstrap_evidence,
    encode_terminal_evidence_with_robustness_fallback,
    reconstruct_robustness_projection,
    stationary_bootstrap_recipe_binding,
)
from research.robustness.monte_carlo import BOUNDS


SETTINGS = {
    "enabled": True,
    "iterations": 100,
    "restart_probability_ppm": 250_000,
}


def _trades(values):
    return tuple(SimpleNamespace(net_pnl=value) for value in values)


def _bt_trade(net_pnl: float, stamp: int) -> BTTrade:
    return BTTrade(
        direction="LONG", entry_time=stamp, entry_price=100.0,
        exit_time=stamp + 1, exit_price=101.0, qty=1,
        gross_pnl=net_pnl + 1.0, charges=1.0, net_pnl=net_pnl,
        reason="STRATEGY_EXIT", bars_held=1,
    )


def _persist_available_run(engine, *, owner_id="restart-owner") -> tuple[int, str]:
    init_research_db(engine)
    Session = make_sessionmaker(engine)
    stored = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=_trades(tuple(range(1, 21))),
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )
    with Session() as session:
        program = ResearchProgram(owner_id=owner_id, name="Restart", thesis="")
        session.add(program)
        session.flush()
        hypothesis = Hypothesis(
            owner_id=owner_id, program_id=program.id, statement="Evidence restarts"
        )
        session.add(hypothesis)
        session.flush()
        spec = ExperimentSpec(
            owner_id=owner_id, id="a" * 32, hypothesis_id=hypothesis.id,
            recipe_json="{}", git_commit="test", qualifier_version="q",
            optimizer_version="o", validator_version="v", scoring_version="s",
            rng_seed=7,
        )
        session.add(spec)
        session.flush()
        run = ExperimentRun(
            owner_id=owner_id, spec_id=spec.id, status="completed", decision="archive",
            checkpoint_json=encode_terminal_evidence({
                "spec_id": spec.id,
                "run": {"id": 1, "status": "completed", "decision": "archive"},
                "provenance": {},
                "results": {"robustness": stored},
            }),
        )
        session.add(run)
        session.commit()
        return run.id, stored["method"]["address"]


def test_recipe_binding_is_closed_and_contains_the_accepted_method_identity():
    binding = stationary_bootstrap_recipe_binding(SETTINGS)

    assert binding == {
        "stationary_bootstrap": {
            "enabled": True,
            "iterations": 100,
            "restart_probability_ppm": 250_000,
            "method": {
                "schema": "strategy-os-stationary-trade-bootstrap/1",
                "algorithm_version": "stationary-circular-geometric-blocks/1",
                "prng_version": "splitmix64/1",
                "bounds": dict(BOUNDS),
            },
        }
    }
    with pytest.raises(RobustnessEvidenceRejected):
        stationary_bootstrap_recipe_binding({**SETTINGS, "unknown": 1})


def test_available_evidence_uses_ordered_signed_money_authority_and_reconstructs():
    values = (1.005, -2.005, 0.0, -0.0) * 5
    stored = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=_trades(values),
        starting_capital=50_000.005,
        seed=7,
        instrument_count=1,
    )

    assert stored["state"] == AVAILABLE
    payload = stored["method"]["canonical_payload"].encode("utf-8")
    method = json.loads(payload)
    assert method["input"] == {
        "trade_net_pnl_paise": [101, -201, 0, 0] * 5,
        "starting_capital_paise": 5_000_001,
        "seed": 7,
        "iterations": 100,
        "restart_probability_ppm": 250_000,
    }
    assert stored["method"]["address"] == content_address(method)

    projected = reconstruct_robustness_projection(stored)
    assert projected == {
        "schema": "strategy-os-run-robustness/1",
        "state": AVAILABLE,
        "method_address": stored["method"]["address"],
        "method": method,
    }


def test_not_requested_and_unavailable_states_never_substitute_an_input_series():
    assert build_stationary_bootstrap_evidence(
        None,
        locked_oos_trades=_trades((1,) * 20),
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    ) == {"schema": "strategy-os-run-robustness/1", "state": NOT_REQUESTED}

    disabled = stationary_bootstrap_recipe_binding({**SETTINGS, "enabled": False})
    assert build_stationary_bootstrap_evidence(
        disabled,
        locked_oos_trades=_trades((1,) * 20),
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )["state"] == NOT_REQUESTED

    insufficient = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=_trades((1,) * 19),
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )
    assert insufficient == {
        "schema": "strategy-os-run-robustness/1",
        "state": UNAVAILABLE,
        "reason_code": "INSUFFICIENT_LOCKED_OOS_TRADES",
    }

    ambiguous = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=_trades((1,) * 20),
        starting_capital=50_000,
        seed=7,
        instrument_count=2,
    )
    assert ambiguous["reason_code"] == "MULTI_INSTRUMENT_AMBIGUITY"

    absent = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=None,
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )
    assert absent["reason_code"] == "LOCKED_OOS_TRADES_UNAVAILABLE"


@pytest.mark.parametrize("invalid", [True, False, "1.0", object()])
def test_boolean_and_non_real_trade_pnl_are_typed_unavailable_not_money(invalid):
    result = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=_trades((invalid,) + (1.0,) * 19),
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )
    assert result == {
        "schema": "strategy-os-run-robustness/1",
        "state": UNAVAILABLE,
        "reason_code": "STATIONARY_BOOTSTRAP_METHOD_REFUSED",
    }


def test_oversized_locked_oos_sequence_is_refused_before_iteration():
    class Oversized(Sequence):
        def __len__(self):
            return BOUNDS["maximum_trades"] + 1

        def __getitem__(self, _index):
            raise AssertionError("oversized OOS sequence must not be materialized")

        def __iter__(self):
            raise AssertionError("oversized OOS sequence must not be iterated")

    result = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=Oversized(),
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )
    assert result["state"] == UNAVAILABLE
    assert result["reason_code"] == "STATIONARY_BOOTSTRAP_METHOD_REFUSED"


def test_reconstruction_refuses_readdressed_semantically_forged_method_bytes():
    stored = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=_trades(tuple(range(1, 21))),
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )
    forged = json.loads(stored["method"]["canonical_payload"])
    forged["distributions"]["terminal_pnl_paise"][0] += 1
    stored["method"]["canonical_payload"] = canonical_json(forged)
    stored["method"]["address"] = content_address(forged)

    with pytest.raises(RobustnessEvidenceRejected):
        reconstruct_robustness_projection(stored)


def test_available_evidence_survives_sqlite_reopen_and_fresh_process(tmp_path):
    database = tmp_path / "restart-research.db"
    engine = make_engine(str(database))
    run_id, expected_address = _persist_available_run(engine)
    engine.dispose()

    reopened = make_engine(str(database))
    Session = make_sessionmaker(reopened)
    with Session() as session:
        run = session.get(ExperimentRun, run_id)
        assert run.owner_id == "restart-owner"
        stored = decode_terminal_evidence(run.checkpoint_json)["results"]["robustness"]
        assert reconstruct_robustness_projection(stored)["method_address"] == expected_address
    reopened.dispose()

    script = """
import sys
from research.domain.base import make_engine, make_sessionmaker
from research.domain.models import ExperimentRun
from research.evidence import decode_terminal_evidence
from research.robustness.integration import reconstruct_robustness_projection
engine = make_engine(sys.argv[1])
Session = make_sessionmaker(engine)
with Session() as session:
    run = session.get(ExperimentRun, int(sys.argv[2]))
    assert run.owner_id == 'restart-owner'
    stored = decode_terminal_evidence(run.checkpoint_json)['results']['robustness']
    print(reconstruct_robustness_projection(stored)['method_address'])
engine.dispose()
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(database), str(run_id)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
    )
    assert completed.stdout.strip() == expected_address


def test_available_evidence_round_trips_postgresql_when_disposable_harness_exists(
    pg_sandbox,
):
    engine = pg_sandbox.research_engine
    run_id, expected_address = _persist_available_run(engine, owner_id="postgres-owner")
    engine.dispose()
    reopened = make_engine(pg_sandbox.research_url)
    Session = make_sessionmaker(reopened)
    with Session() as session:
        run = session.get(ExperimentRun, run_id)
        assert run.owner_id == "postgres-owner"
        stored = decode_terminal_evidence(run.checkpoint_json)["results"]["robustness"]
        assert reconstruct_robustness_projection(stored)["method_address"] == expected_address
    reopened.dispose()


def test_terminal_size_refusal_drops_the_complete_distribution_not_the_base_result(
    monkeypatch,
):
    from research.robustness import integration

    evidence = {
        "results": {
            "robustness": build_stationary_bootstrap_evidence(
                stationary_bootstrap_recipe_binding(SETTINGS),
                locked_oos_trades=_trades(tuple(range(1, 21))),
                starting_capital=50_000,
                seed=7,
                instrument_count=1,
            ),
            "base": {"accepted": True},
        }
    }
    calls = []

    def bounded_encoder(document):
        calls.append(document)
        if document["results"]["robustness"]["state"] == AVAILABLE:
            raise EvidenceRejected("terminal evidence exceeds the persisted size limit")
        return canonical_json(document)

    monkeypatch.setattr(integration, "encode_terminal_evidence", bounded_encoder)
    encoded = encode_terminal_evidence_with_robustness_fallback(evidence)
    persisted = json.loads(encoded)

    assert len(calls) == 2
    assert persisted["results"]["base"] == {"accepted": True}
    assert persisted["results"]["robustness"] == {
        "schema": "strategy-os-run-robustness/1",
        "state": UNAVAILABLE,
        "reason_code": "TERMINAL_EVIDENCE_SIZE_REFUSED",
    }


def test_actual_terminal_envelope_ceiling_is_hard_and_complete_distribution_falls_back():
    robustness = build_stationary_bootstrap_evidence(
        stationary_bootstrap_recipe_binding(SETTINGS),
        locked_oos_trades=_trades(tuple(range(1, 21))),
        starting_capital=50_000,
        seed=7,
        instrument_count=1,
    )

    def evidence(padding):
        return {"results": {"base": {"accepted": True}, "padding": padding,
                            "robustness": robustness}}

    empty_size = len(encode_terminal_evidence(evidence("")).encode("utf-8"))
    exact_padding = "x" * (MAX_EVIDENCE_BYTES - empty_size)
    assert len(encode_terminal_evidence(evidence(exact_padding)).encode("utf-8")) == (
        MAX_EVIDENCE_BYTES
    )
    assert len(encode_terminal_evidence(evidence(exact_padding[:-1])).encode("utf-8")) == (
        MAX_EVIDENCE_BYTES - 1
    )
    above = evidence(exact_padding + "x")
    with pytest.raises(EvidenceRejected, match="persisted size limit"):
        encode_terminal_evidence(above)

    encoded = encode_terminal_evidence_with_robustness_fallback(above)
    persisted = decode_terminal_evidence(encoded)
    assert persisted["results"]["base"] == {"accepted": True}
    assert persisted["results"]["robustness"]["state"] == UNAVAILABLE
    assert persisted["results"]["robustness"]["reason_code"] == (
        "TERMINAL_EVIDENCE_SIZE_REFUSED"
    )


def test_optional_settings_change_spec_identity_while_absence_preserves_legacy_recipe(
    research_session, inst_factory, candles_factory,
):
    from research.orchestrator.run import run_experiment

    instrument = inst_factory("AAA")
    dataset = materialize(
        StaticDataSource({("AAA", "day"): candles_factory(100)}), instrument, "day"
    )
    strategy = kernels.get_strategy("trend_impulse_v3")
    shared = dict(
        owner_id="robustness-identity-owner",
        program_name="Robustness identity",
        hypothesis_statement="Settings are immutable inputs",
        strategy=strategy,
        datasets=[(instrument, dataset)],
        git_commit="robustness-test",
        min_trades=10_000,
        n_folds=2,
    )

    legacy = run_experiment(research_session, **shared)
    first = run_experiment(research_session, robustness=SETTINGS, **shared)
    second = run_experiment(
        research_session,
        robustness={**SETTINGS, "restart_probability_ppm": 300_000},
        **shared,
    )

    assert len({legacy["spec_id"], first["spec_id"], second["spec_id"]}) == 3
    legacy_recipe = json.loads(research_session.get(
        ExperimentSpec, (shared["owner_id"], legacy["spec_id"])
    ).recipe_json)
    assert "robustness" not in legacy_recipe
    assert json.loads(research_session.get(
        ExperimentSpec, (shared["owner_id"], first["spec_id"])
    ).recipe_json)["robustness"] == stationary_bootstrap_recipe_binding(SETTINGS)


@pytest.mark.parametrize("optimized", [False, True])
def test_orchestrator_passes_only_ordered_pooled_locked_oos_trades_to_robustness(
    research_session, inst_factory, candles_factory, monkeypatch, optimized,
):
    import research.orchestrator.run as orchestrator

    instrument = inst_factory("AAA")
    dataset = materialize(
        StaticDataSource({("AAA", "day"): candles_factory(80)}), instrument, "day"
    )
    strategy = kernels.get_strategy("trend_impulse_v3")
    oos = tuple(_bt_trade(value, index * 2) for index, value in enumerate(
        (1.01, -2.01, 3.01, -4.01) * 5
    ))
    metrics = kernels.compute_metrics(list(oos), 50_000.0)
    qualification = SimpleNamespace(
        instrument_key="AAA", qualified=True, trades=999,
        reason="qualification series must not be reused", metrics=metrics,
    )
    folds = [
        SimpleNamespace(fold_index=0, trades=list(oos[:10])),
        SimpleNamespace(fold_index=1, trades=list(oos[10:])),
    ]
    failed_gates = {"test_gate": {"passed": False, "value": 20}}
    visualizations = []
    monkeypatch.setattr(orchestrator, "qualify_instrument", lambda *_a, **_k: qualification)
    monkeypatch.setattr(
        orchestrator, "build_visualization_projection",
        lambda **kwargs: visualizations.append(kwargs) or {"state": "test"},
    )
    if optimized:
        selected_params = {**strategy.default_params, "entry_z": 9.0}
        monkeypatch.setattr(orchestrator, "optimize", lambda *_a, **_k: SimpleNamespace(
            trials=[], per_fold_oos=[list(oos[:10]), list(oos[10:])],
            oos_trades=list(oos), oos_metrics=metrics, n_trials=1,
            var_sr=0.0, perf_matrix=[], selected_params=selected_params,
            final_trials=[],
        ))
    monkeypatch.setattr(orchestrator, "validate", lambda *_a, **_k: SimpleNamespace(
        wf=SimpleNamespace(folds=folds), gates=failed_gates,
        passed=False,
    ))
    captured = {}

    def capture(binding, **kwargs):
        captured.update(kwargs)
        captured["binding"] = binding
        return {"schema": "strategy-os-run-robustness/1", "state": NOT_REQUESTED}

    monkeypatch.setattr(orchestrator, "build_stationary_bootstrap_evidence", capture)
    orchestrator.run_experiment(
        research_session,
        owner_id=f"oos-trace-{optimized}",
        program_name="OOS trace",
        hypothesis_statement="Only locked OOS enters robustness",
        strategy=strategy,
        datasets=[(instrument, dataset)],
        git_commit="robustness-test",
        min_trades=1,
        n_folds=2,
        optimize_search=optimized,
        seed=7,
        robustness=SETTINGS,
    )

    assert captured["locked_oos_trades"] == oos
    assert captured["locked_oos_trades"] is not qualification
    assert captured["starting_capital"] == 50_000.0
    assert captured["seed"] == 7
    assert captured["instrument_count"] == 1
    assert captured["binding"] == stationary_bootstrap_recipe_binding(SETTINGS)
    if optimized:
        assert visualizations[-1]["recipe"]["params"] == selected_params
