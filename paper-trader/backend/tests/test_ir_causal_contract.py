from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pandas as pd
import pytest
import math

from app.ir.causal import (
    BlockCausalDisposition,
    BoundTerm,
    CausalContract,
    CausalDeclarationError,
    HistoryBound,
    RecursiveStateContract,
    causal_contract,
)
from app.ir.kernels import KernelDeclarationError, kernel_spec


@dataclass(frozen=True)
class _State:
    value: float = 0.0


def _initializer(params):
    return _State(float(params.get("seed", 0.0)))


def _encoder(state):
    return {"value": state.value}


def _update(state, params, inputs, context):
    return _State(state.value + float(inputs["close"]))


def _step(state, params, inputs, context):
    return {"out": state.value}


def _recursive_state():
    return RecursiveStateContract(
        initializer=_initializer,
        state_type=_State,
        state_encoder=_encoder,
        update=_update,
        step=_step,
    )


def test_causal_contract_rejects_future_or_hidden_dependencies():
    with pytest.raises(CausalDeclarationError, match="output_delay_bars"):
        causal_contract(
            node_input_sockets=("close",),
            history=HistoryBound("bounded"),
            output_delay_bars=-1,
        )
    with pytest.raises(CausalDeclarationError, match="context_inputs"):
        causal_contract(
            node_input_sockets=("close",),
            context_inputs=("wall_clock",),
            history=HistoryBound("bounded"),
        )


def test_parameter_history_is_exact_and_closed():
    bound = HistoryBound(
        "bounded",
        constant=1,
        terms=(BoundTerm("length"), BoundTerm("lookback")),
    )
    assert bound.bars({"length": 50, "lookback": 5}) == 56
    with pytest.raises(CausalDeclarationError, match="undeclared"):
        bound.bars({"length": 50})
    with pytest.raises(CausalDeclarationError, match="integers"):
        bound.bars({"length": True, "lookback": 5})


def test_recursive_mode_requires_a_complete_state_contract():
    with pytest.raises(CausalDeclarationError, match="recursive_state"):
        causal_contract(
            node_input_sockets=("close",),
            history=HistoryBound("causal_recursive"),
        )

    contract = causal_contract(
        node_input_sockets=("close",),
        history=HistoryBound("causal_recursive"),
        recursive_state=_recursive_state(),
    )
    state = contract.recursive_state.initializer({"seed": 2.0})
    next_state = contract.recursive_state.update(
        state, {"seed": 2.0}, {"close": 3.0}, {}
    )
    assert type(next_state) is _State
    assert contract.recursive_state.state_encoder(next_state) == {"value": 5.0}
    assert contract.recursive_state.step(
        next_state, {"seed": 2.0}, {"close": 3.0}, {}
    ) == {"out": 5.0}
    assert contract.recursive_state.initialize({"seed": 2.0}) == _State(2.0)
    assert contract.recursive_state.advance(
        state, {"seed": 2.0}, {"close": 3.0}, {}
    ) == _State(5.0)
    assert contract.recursive_state.encode(next_state) == {"value": 5.0}


def test_recursive_contract_checks_exact_state_and_closed_json_behavior():
    bad_initial = RecursiveStateContract(
        initializer=lambda params: object(),
        state_type=_State,
        state_encoder=_encoder,
        update=_update,
        step=_step,
    )
    with pytest.raises(CausalDeclarationError, match="exact state_type"):
        bad_initial.initialize({})

    bad_encoder = RecursiveStateContract(
        initializer=_initializer,
        state_type=_State,
        state_encoder=lambda state: {"bad": object()},
        update=_update,
        step=_step,
    )
    with pytest.raises(CausalDeclarationError, match="closed JSON"):
        bad_encoder.encode(_State())

    for value in (float("nan"), float("inf"), float("-inf")):
        def encode_nonfinite(state):
            return {"bad": value}

        nonfinite = RecursiveStateContract(
            initializer=_initializer,
            state_type=_State,
            state_encoder=encode_nonfinite,
            update=_update,
            step=_step,
        )
        with pytest.raises(CausalDeclarationError, match="closed JSON"):
            nonfinite.encode(_State())


def test_bounded_mode_refuses_recursive_state():
    with pytest.raises(CausalDeclarationError, match="bounded"):
        causal_contract(
            node_input_sockets=("close",),
            history=HistoryBound("bounded"),
            recursive_state=_recursive_state(),
        )


def test_direct_contract_construction_cannot_bypass_closed_validation():
    with pytest.raises(CausalDeclarationError, match="context_inputs"):
        CausalContract(("close",), ("wall_clock",), HistoryBound("bounded"))
    with pytest.raises(CausalDeclarationError, match="output_delay_bars"):
        CausalContract(("close",), (), HistoryBound("bounded"), -1)
    with pytest.raises(CausalDeclarationError, match="recursive_state"):
        CausalContract(("close",), (), HistoryBound("causal_recursive"))
    with pytest.raises(CausalDeclarationError, match="bounded"):
        CausalContract(
            ("close",), (), HistoryBound("bounded"), recursive_state=_recursive_state()
        )

    assert CausalContract(("close",)).history == HistoryBound("bounded")
    with pytest.raises(CausalDeclarationError, match="input_bar"):
        CausalContract(("close",), input_bar="forming")
    with pytest.raises(CausalDeclarationError, match="purity"):
        CausalContract(("close",), purity="wall_clock")


@pytest.mark.parametrize("fake", [{}, "causal", object()])
def test_kernel_registry_seam_rejects_fake_causal_metadata(fake):
    with pytest.raises(KernelDeclarationError, match="causal"):
        kernel_spec(causal=fake)


def test_dispositions_are_closed_and_truthful():
    bounded = causal_contract(
        node_input_sockets=("close",), history=HistoryBound("bounded")
    )
    admitted = BlockCausalDisposition.admitted(bounded, dependencies=(_step,))
    quarantined = BlockCausalDisposition.quarantined("parity evidence unavailable")

    assert admitted.status == "admitted"
    assert admitted.contract is bounded
    assert admitted.dependencies == (_step,)
    assert quarantined.status == "quarantined"
    assert quarantined.contract is None
    with pytest.raises(CausalDeclarationError):
        BlockCausalDisposition("admitted", None, None, ())
    with pytest.raises(CausalDeclarationError):
        BlockCausalDisposition("admitted", object(), None, ())
    with pytest.raises(CausalDeclarationError):
        BlockCausalDisposition("admitted", bounded, None, [_step])


def test_generated_block_manifest_is_exhaustive_and_app_owned():
    from app.ir.contributors.generated_blocks import (
        BLOCKS,
        BLOCK_COMPONENTS,
        BLOCK_DEPENDENCIES,
        BLOCK_REGISTRATIONS,
        CAUSAL_MANIFEST,
    )
    from research.strategy.builder import blocks as research_blocks

    assert research_blocks.BLOCKS is BLOCKS
    assert set(CAUSAL_MANIFEST) == set(BLOCKS)
    assert set(BLOCK_DEPENDENCIES) == set(BLOCKS)
    admitted = {
        name for name, disposition in CAUSAL_MANIFEST.items()
        if disposition.status == "admitted"
    }
    assert set(BLOCK_REGISTRATIONS) == {
        BLOCK_COMPONENTS[name].body_ref for name in admitted
    }
    for name, spec in BLOCKS.items():
        disposition = CAUSAL_MANIFEST[name]
        assert spec.history is not None
        if disposition.status == "admitted":
            assert disposition.contract.node_input_sockets == spec.inputs
            expected_context = ("bar_timestamp",) if spec.needs_clock else ()
            assert disposition.contract.context_inputs == expected_context
    assert BLOCKS["body_frac_gt"].warmup(BLOCKS["body_frac_gt"].sample_args) == 0
    assert BLOCKS["body_frac_gt"].history == HistoryBound("bounded", constant=1)


def test_existing_expanding_z_kernels_have_closed_causal_contracts():
    from app.ir.strategies.expanding_z import KERNELS

    assert KERNELS
    assert all(spec.causal is not None for spec in KERNELS.values())
    recursive = [spec.causal for spec in KERNELS.values()
                 if spec.causal.history.mode == "causal_recursive"]
    assert recursive
    assert all(contract.recursive_state is not None for contract in recursive)


@pytest.mark.parametrize("name,input_socket", [("EMA", "source"), ("WILDER", "in")])
def test_expanding_z_recursive_ewm_matches_vector_across_interior_nan(name, input_socket):
    from app.ir.strategies import expanding_z

    component = getattr(expanding_z, name)
    ref = component["body"]["ref"]
    contract = expanding_z.KERNELS[ref].causal.recursive_state
    params = {"length": 3}
    values = [1.0, float("nan"), 3.0, 4.0]
    state = contract.initialize(params)
    actual = []
    for value in values:
        inputs = {input_socket: value}
        state = contract.advance(state, params, inputs, {})
        actual.append(contract.output(state, params, inputs, {})["out"])
    index = pd.RangeIndex(len(values))
    vector = expanding_z.IMPLEMENTATIONS[ref](
        params, {input_socket: pd.Series(values, index=index)}, {}
    )["out"]
    for got, want in zip(actual, vector.tolist()):
        assert got is None if pd.isna(want) else got == pytest.approx(want)


def test_research_regime_uses_the_app_owned_implementation():
    from app.ir.contributors import generated_blocks
    from research import regime

    assert regime.label_regimes is generated_blocks.label_regimes
    assert regime.efficiency_ratio is generated_blocks.efficiency_ratio
    assert regime.atr_pct is generated_blocks.atr_pct
    assert regime.REGIMES is generated_blocks.REGIMES


def _recursive_frame():
    idx = pd.date_range("2026-01-01 09:15", periods=280, freq="15min", tz="Asia/Kolkata")
    close = pd.Series(
        [1000 + math.sin(i / 8) * 13 + math.sin(i / 31) * 27 for i in range(len(idx))],
        index=idx,
    )
    return pd.DataFrame({
        "open": close.shift(1).fillna(close.iloc[0]),
        "high": close + 2 + pd.Series(range(len(idx)), index=idx) % 4,
        "low": close - 2 - pd.Series(range(len(idx)), index=idx) % 3,
        "close": close,
        "volume": 1000.0,
    }, index=idx)


def _step_block(name, frame, args=None):
    from app.ir.contributors.generated_blocks import BLOCKS, CAUSAL_MANIFEST

    spec = BLOCKS[name]
    disposition = CAUSAL_MANIFEST[name]
    assert disposition.status == "admitted", name
    contract = disposition.contract
    params = dict(zip((key for key, _ in spec.params), args or spec.sample_args))
    state = contract.recursive_state.initialize(params)
    values = []
    for timestamp, row in frame.iterrows():
        inputs = {field: row[field] for field in spec.inputs}
        context = {"bar_timestamp": timestamp} if spec.needs_clock else {}
        state = contract.recursive_state.advance(state, params, inputs, context)
        contract.recursive_state.encode(state)
        values.append(contract.recursive_state.output(state, params, inputs, context)["out"])
    return pd.Series(values, index=frame.index, dtype=bool)


@pytest.mark.parametrize("name", [
    "ema_slope_up", "ema_slope_down", "price_above_ema", "price_below_ema",
    "zscore_gt", "zscore_lt", "zscore_cross_up", "zscore_cross_down",
    "atr_pct_lt", "range_atr_lt", "still_expanding_z",
    "opening_range_break_up", "opening_range_break_down", "regime_is",
])
def test_recursive_block_transition_stream_matches_vector(name):
    from app.ir.contributors.generated_blocks import BLOCKS

    frame = _recursive_frame()
    spec = BLOCKS[name]
    vector_frame = frame.assign(date=frame.index) if spec.needs_clock else frame
    assert _step_block(name, frame).equals(
        spec.fn(vector_frame, *spec.sample_args)), name


@pytest.mark.parametrize("name", ["rsi_gt", "rsi_lt"])
@pytest.mark.parametrize("source", range(4))
@pytest.mark.parametrize("smooth", range(4))
def test_rsi_transition_stream_matches_every_source_and_smoothing(name, source, smooth):
    from app.ir.contributors.generated_blocks import BLOCKS

    frame = _recursive_frame()
    spec = BLOCKS[name]
    args = (14, spec.sample_args[1], source, smooth)
    assert _step_block(name, frame, args).equals(spec.fn(frame, *args))


def test_opening_range_transition_resets_on_recorded_session_date():
    frame = _recursive_frame().iloc[:12].copy()
    second = frame.copy()
    second.index = second.index + pd.Timedelta(days=1)
    joined = pd.concat([frame, second])
    for name in ("opening_range_break_up", "opening_range_break_down"):
        assert _step_block(name, joined).equals(
            __import__("app.ir.contributors.generated_blocks", fromlist=["BLOCKS"])
            .BLOCKS[name].fn(joined.assign(date=joined.index), 4, 0.1)
        )


@pytest.mark.parametrize("name", [
    "ema_slope_up", "price_above_ema", "zscore_gt", "atr_pct_lt",
    "rsi_gt", "opening_range_break_up", "regime_is",
])
def test_recursive_transitions_match_vector_through_nan_prefix(name):
    from app.ir.contributors.generated_blocks import BLOCKS

    frame = _recursive_frame().iloc[:80].copy()
    frame.loc[frame.index[:3], ["open", "high", "low", "close"]] = float("nan")
    spec = BLOCKS[name]
    vector_frame = frame.assign(date=frame.index) if spec.needs_clock else frame
    assert _step_block(name, frame).equals(spec.fn(vector_frame, *spec.sample_args)), name


@pytest.mark.parametrize("name,args", [
    ("price_above_ema", (5,)),
    ("atr_pct_lt", (5, 5.0)),
    ("rsi_gt", (5, 55.0, 0, 1)),
    ("rsi_gt", (5, 55.0, 0, 2)),
])
def test_recursive_ewm_families_match_vector_across_interior_nan(name, args):
    from app.ir.contributors.generated_blocks import BLOCKS

    frame = _recursive_frame().iloc[:30].copy()
    frame.loc[frame.index[5], ["open", "high", "low", "close"]] = float("nan")
    spec = BLOCKS[name]
    assert _step_block(name, frame, args).equals(spec.fn(frame, *args)), name


def test_rsi_numeric_state_matches_vector_after_missing_gap():
    from app.ir.contributors.generated_blocks import CAUSAL_MANIFEST, _rsi

    frame = _recursive_frame().iloc[:20].copy()
    frame.loc[frame.index[5], "close"] = float("nan")
    params = {"length": 5, "thr": 55.0, "source": 0, "smooth": 2}
    state_contract = CAUSAL_MANIFEST["rsi_gt"].contract.recursive_state
    state = state_contract.initialize(params)
    actual = []
    for _, row in frame.iterrows():
        inputs = {name: row[name] for name in ("open", "high", "low", "close")}
        state = state_contract.advance(state, params, inputs, {})
        actual.append(state.rsi)
    expected = _rsi(frame, 5, 0, 2)
    for got, want in zip(actual, expected):
        assert got is None if pd.isna(want) else got == pytest.approx(want)


def test_rsi_ema_missing_gap_regression_exposes_decision_threshold():
    from app.ir.contributors.generated_blocks import BLOCKS

    close = [101.4947, 96.5036, 95.3410, 98.5964, 98.7303,
             float("nan"), 98.3974, 99.8457]
    idx = pd.date_range("2026-01-01", periods=len(close), freq="min", tz="UTC")
    series = pd.Series(close, index=idx)
    frame = pd.DataFrame({"open": series, "high": series, "low": series,
                          "close": series, "volume": 1.0}, index=idx)
    args = (5, 55.0, 0, 1)
    actual = _step_block("rsi_gt", frame, args)
    expected = BLOCKS["rsi_gt"].fn(frame, *args)
    assert actual.equals(expected)
    assert bool(actual.iloc[-1]) is True


def test_atr_transition_uses_each_available_true_range_candidate():
    from app.ir.contributors.generated_blocks import BLOCKS

    for missing in ("high", "low"):
        frame = _recursive_frame().iloc[:30].copy()
        frame.loc[frame.index[7], missing] = float("nan")
        spec = BLOCKS["atr_pct_lt"]
        assert _step_block("atr_pct_lt", frame, (5, 5.0)).equals(
            spec.fn(frame, 5, 5.0))


def test_atr_does_not_carry_previous_close_across_a_missing_bar():
    from app.ir.contributors.generated_blocks import BLOCKS

    idx = pd.date_range("2026-01-01", periods=4, freq="min", tz="UTC")
    frame = pd.DataFrame({
        "high": [101.0, 101.0, float("nan"), 200.0],
        "low": [99.0, 99.0, float("nan"), 190.0],
        "close": [100.0, 100.0, float("nan"), 195.0],
    }, index=idx)
    actual = _step_block("atr_pct_lt", frame, (2, 10.0))
    expected = BLOCKS["atr_pct_lt"].fn(frame, 2, 10.0)
    assert actual.equals(expected)
    assert bool(actual.iloc[-1]) is True
    assert bool(_step_block("atr_pct_lt", frame, (2, 4.0)).iloc[-1]) is False
    assert bool(_step_block("range_atr_lt", frame, (2, 1.3)).iloc[-1]) is True


def test_wilder_rsi_gap_numeric_and_decision_regression():
    from app.ir.contributors.generated_blocks import BLOCKS, CAUSAL_MANIFEST, _rsi

    close = [100.304717, 99.264733, 100.015184, 100.955749,
             float("nan"), 97.702534, 97.830375, 97.514132]
    idx = pd.date_range("2026-01-01", periods=len(close), freq="min", tz="UTC")
    series = pd.Series(close, index=idx)
    frame = pd.DataFrame({"open": series, "high": series, "low": series,
                          "close": series}, index=idx)
    params = {"length": 2, "thr": 83.0, "source": 0, "smooth": 2}
    contract = CAUSAL_MANIFEST["rsi_gt"].contract.recursive_state
    state = contract.initialize(params)
    numeric = []
    decisions = []
    for _, row in frame.iterrows():
        inputs = {name: row[name] for name in ("open", "high", "low", "close")}
        state = contract.advance(state, params, inputs, {})
        numeric.append(state.rsi)
        decisions.append(contract.output(state, params, inputs, {})["out"])
    expected = _rsi(frame, 2, 0, 2)
    for got, want in zip(numeric, expected):
        assert got is None if pd.isna(want) else got == pytest.approx(want)
    assert decisions == BLOCKS["rsi_gt"].fn(frame, 2, 83.0, 0, 2).tolist()


def test_regime_transition_matches_vector_across_partial_ohlc_gap():
    from app.ir.contributors.generated_blocks import BLOCKS

    frame = _recursive_frame()
    frame.loc[frame.index[75], "high"] = float("nan")
    frame.loc[frame.index[151], "low"] = float("nan")
    actual = _step_block("regime_is", frame)
    expected = BLOCKS["regime_is"].fn(frame, *BLOCKS["regime_is"].sample_args)
    assert actual.equals(expected)


@pytest.mark.parametrize(
    "index",
    [pd.RangeIndex(2), pd.date_range("2026-01-01", periods=2, freq="min")],
)
def test_timestamp_context_requires_recorded_timezone_aware_datetimes(index):
    from app.ir.runtime import EvaluationError, _timestamp_context

    contract = causal_contract(
        node_input_sockets=("close",),
        context_inputs=("bar_timestamp",),
        history=HistoryBound("bounded"),
    )
    graph = SimpleNamespace(nodes=(SimpleNamespace(causal=contract),))
    with pytest.raises(EvaluationError, match="timezone-aware DatetimeIndex"):
        _timestamp_context(graph, {"close": pd.Series([1.0, 2.0], index=index)})
