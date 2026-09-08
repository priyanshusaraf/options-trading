"""The registry is the seam the whole multi-strategy platform hangs off, so two
things are pinned here: (1) the registry's `trend_impulse_v3` produces output
BYTE-IDENTICAL to the legacy `compute_signals` (no behaviour change when we route
the engine/backtest/chart through the registry), and (2) every registered strategy
honours the canonical four-column contract on real-shaped data."""
import numpy as np
import pandas as pd
import pytest

from app.strategy.signals import compute_signals
from app.strategy.registry import (
    get_strategy, all_strategies, strategy_keys, DEFAULT_STRATEGY_KEY)
from app.strategy.registry.base import CANONICAL_COLUMNS


def _synthetic(n: int = 400) -> pd.DataFrame:
    """Deterministic OHLC: a drifting sine so EMA slope and z-score both swing
    through entries and exits. Fixed seed → stable golden comparison."""
    rng = np.random.default_rng(42)
    t = np.arange(n)
    base = 1000.0 + 60.0 * np.sin(t / 18.0) + 0.4 * t
    noise = rng.normal(0, 4.0, n)
    close = base + noise
    high = close + np.abs(rng.normal(0, 3.0, n))
    low = close - np.abs(rng.normal(0, 3.0, n))
    open_ = close + rng.normal(0, 2.0, n)
    dates = pd.date_range("2024-01-01 09:15", periods=n, freq="15min")
    return pd.DataFrame({"date": dates, "open": open_, "high": high,
                         "low": low, "close": close})


def test_default_key_is_v3():
    assert DEFAULT_STRATEGY_KEY == "trend_impulse_v3"
    assert get_strategy(None).key == "trend_impulse_v3"
    # Fail-SAFE fallback, retained for the legacy per-instrument path only. The
    # fail-CLOSED counterpart (`resolve_strategy`, which raises `StrategyNotFound`) and
    # the content-hash version are pinned in tests/test_strategy_identity.py.
    assert get_strategy("does_not_exist").key == "trend_impulse_v3"


def test_v3_registered_and_listed():
    keys = strategy_keys()
    assert "trend_impulse_v3" in keys
    assert all(s.display_name for s in all_strategies())  # every strategy is labelled


def test_v3_registry_matches_legacy_compute_signals_byte_for_byte():
    df = _synthetic()
    legacy = compute_signals(df, ema_length=50, z_length=50, entry_z=1.0, slope_lookback=5)
    viareg = get_strategy("trend_impulse_v3").signals(
        df, ema_length=50, z_length=50, entry_z=1.0, slope_lookback=5)
    # canonical signal columns identical
    for col in CANONICAL_COLUMNS:
        assert (legacy[col].fillna(False) == viareg[col].fillna(False)).all(), col
    # key indicator columns identical too (chart payload depends on these)
    for col in ("ema", "z", "slope"):
        pd.testing.assert_series_equal(legacy[col], viareg[col], check_names=False)


def test_v3_defaults_applied_when_no_overrides():
    df = _synthetic()
    explicit = get_strategy("trend_impulse_v3").signals(
        df, ema_length=50, z_length=50, entry_z=1.0, slope_lookback=5)
    defaulted = get_strategy("trend_impulse_v3").signals(df)  # uses default_params
    for col in CANONICAL_COLUMNS:
        assert (explicit[col].fillna(False) == defaulted[col].fillna(False)).all(), col


def test_every_strategy_emits_canonical_columns():
    df = _synthetic()
    for strat in all_strategies():
        out = strat.signals(df)
        for col in CANONICAL_COLUMNS:
            assert col in out.columns, f"{strat.key} missing {col}"
            assert out[col].dropna().isin([True, False]).all(), f"{strat.key}:{col} not boolean"


def test_original_v3_v2_preset_matches_source_and_prefix():
    from app.ir.library import REGISTRY
    from app.ir.original_strategy_presets import instantiate_preset
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.ir.validity import ValidityState

    document = instantiate_preset("trend_impulse_v3", "v3-parity")
    resolved = resolve_v2(document, REGISTRY)
    frame = _synthetic().set_index("date")
    expected = compute_signals(frame)
    actual = evaluate_v2(resolved, {"frame": dict(frame.items())}, REGISTRY)
    prefix = evaluate_v2(resolved, {"frame": dict(frame.iloc[:180].items())}, REGISTRY)
    for name in CANONICAL_COLUMNS:
        assert all(cell.state is ValidityState.VALID for cell in actual[name]), name
        assert [cell.value for cell in actual[name]] == expected[name].tolist(), name
        assert actual[name].iloc[:180].tolist() == prefix[name].tolist()
    flat = frame.copy()
    flat.loc[:, "close"] = 1000.0
    result = evaluate_v2(resolved, {"frame": dict(flat.items())}, REGISTRY)
    assert all(cell.value is False for series in result.values() for cell in series)
    broken = frame.copy()
    broken.iloc[100, broken.columns.get_loc("close")] = np.nan
    result = evaluate_v2(resolved, {"frame": dict(broken.items())}, REGISTRY)
    assert all(series.iloc[100].state is not ValidityState.VALID for series in result.values())


def test_original_v3_primitives_independent_recurrence_and_refusals():
    import math
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir.validity import ValidityState, invalid, valid

    close = _synthetic(80).set_index("date")["close"]
    numeric = pd.Series([valid(float(value)) for value in close], index=close.index)
    ema = p._ema({"length": 7}, {"source": numeric})["value"]
    std = p._rolling_stddev({"length": 7}, {"source": numeric})["value"]
    mean = float(close.iloc[0])
    for i, price in enumerate(close):
        if i:
            mean = 0.25 * price + 0.75 * mean
        assert ema.iloc[i].value == pytest.approx(mean, abs=1e-10)
        if i < 6:
            assert std.iloc[i].state is ValidityState.INSUFFICIENT_HISTORY
        else:
            values = close.iloc[i-6:i+1].tolist()
            avg = sum(values) / 7
            expected = math.sqrt(sum((value - avg) ** 2 for value in values) / 7)
            assert std.iloc[i].value == pytest.approx(expected, abs=1e-10)
    states = [ValidityState.INSUFFICIENT_HISTORY, ValidityState.MATHEMATICALLY_UNDEFINED,
              ValidityState.MISSING, ValidityState.STALE, ValidityState.PROVIDER_UNAVAILABLE]
    source = pd.Series([invalid(state) for state in states],
                       index=pd.date_range("2024-01-01", periods=len(states)))
    fallback = p._fallback({"source": source}, 0.0)["value"]
    assert [cell.value for cell in fallback.iloc[:2]] == [0.0, 0.0]
    assert fallback.iloc[2:].tolist() == source.iloc[2:].tolist()
    equal = pd.Series([valid(1.0), valid(2.0)], index=source.index[:2])
    threshold = pd.Series([valid(1.0), valid(1.0)], index=equal.index)
    assert [cell.value for cell in p._binary("lt", {"left": equal, "right": threshold})["value"]] == [False, False]


def _original_preset_registry():
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir.original_strategy_presets import V2_COMPONENTS
    from app.ir.registry import PlatformRegistry
    return PlatformRegistry(
        components={}, bodies={}, registrations={},
        v2_types={(ref["type_id"], 2): {**ref, "shapes": ["series"],
                   "runtime_representation": "indexed values"}
                  for ref in (p.FLOAT, p.BOOLEAN, p.MARKET_FRAME)},
        v2_components={**p.V2_COMPONENTS, **V2_COMPONENTS},
        v2_implementations=p.V2_IMPLEMENTATIONS, node_contracts=p.NODE_CONTRACTS,
        data_requirement_declarations=p.DATA_REQUIREMENTS, contract_bindings=p.CONTRACT_BINDINGS,
    )


def test_original_v4_pine_signals_match_independent_atr_and_corrected_source(monkeypatch):
    from app.ir.original_strategy_presets import instantiate_preset
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.ir.validity import ValidityState
    from app.strategy.registry import expanding_z_v4 as source

    def pine_rma(values, length):
        result = [np.nan] * len(values)
        if len(values) >= length:
            result[length-1] = sum(values.iloc[:length]) / length
        for i in range(length, len(values)):
            result[i] = (values.iloc[i] + (length-1) * result[i-1]) / length
        return pd.Series(result, index=values.index)

    monkeypatch.setattr(source, "_rma", pine_rma)
    monkeypatch.setattr(source, "_crossover", lambda a, b: (a.shift(1) <= b.shift(1)) & (a > b))
    registry = _original_preset_registry()
    document = instantiate_preset("expanding_z_v4", "v4-parity")
    resolved = resolve_v2(document, registry)
    frame = _synthetic().set_index("date")
    expected = source.ExpandingZImpulseV4().compute(frame)
    actual = evaluate_v2(resolved, {"frame": dict(frame.items())}, registry)
    prefix = evaluate_v2(resolved, {"frame": dict(frame.iloc[:180].items())}, registry)
    for name in CANONICAL_COLUMNS:
        assert all(cell.state is ValidityState.VALID for cell in actual[name]), name
        assert [cell.value for cell in actual[name]] == expected[name].tolist(), name
        assert actual[name].iloc[:180].tolist() == prefix[name].tolist()
    document["nodes"][0]["parameters"].update({"require_expansion": False,
        "allow_reexpansion": False, "use_absz_contraction_exit": True,
        "exit_on_drift_flip": False, "exit_on_ema_cross": False})
    expected = source.ExpandingZImpulseV4().compute(frame, **document["nodes"][0]["parameters"])
    actual = evaluate_v2(resolve_v2(document, registry), {"frame": dict(frame.items())}, registry)
    for name in CANONICAL_COLUMNS:
        assert [cell.value for cell in actual[name]] == expected[name].tolist(), name


def test_original_v4_intrinsics_have_distinct_seed_rank_and_equality():
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir.validity import valid
    index = pd.date_range("2024-01-01", periods=5)
    values = pd.Series([valid(value) for value in [1., 2., 6., 3., 5.]], index=index)
    atr = p._rma({"length": 3}, {"source": values})["value"]
    assert [cell.value for cell in atr] == pytest.approx([None, None, 3., 3., 11/3], nan_ok=True)
    rank = p._nearest_rank({"length": 3, "percentile": 65.}, {"source": values})["value"]
    assert [cell.value for cell in rank] == [None, None, 2., 3., 5.]
    a = pd.Series([valid(1.), valid(2.)], index=index[:2])
    b = pd.Series([valid(1.), valid(1.)], index=index[:2])
    assert p._binary("le", {"left": a, "right": b})["value"].iloc[0].value is True
    assert p._binary("lt", {"left": a, "right": b})["value"].iloc[0].value is False


def test_original_primitive_missing_history_never_becomes_legacy_zero():
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir.validity import ValidityState, invalid, valid
    index = pd.date_range("2024-01-01", periods=6)
    for state in (ValidityState.MISSING, ValidityState.STALE, ValidityState.PROVIDER_UNAVAILABLE):
        values = pd.Series([valid(1.), valid(2.), invalid(state), valid(4.), valid(5.), valid(6.)], index=index)
        for kernel in (p._ema, p._rma):
            result = kernel({"length": 2}, {"source": values})["value"]
            assert all(cell.state is state for cell in result.iloc[2:])
        result = p._rolling_stddev({"length": 3}, {"source": values})["value"]
        assert all(cell.state is state for cell in result.iloc[2:5])
        fallback = p._fallback({"source": result}, 0.)["value"]
        assert all(cell.state is state for cell in fallback.iloc[2:5])
        assert result.iloc[5].state is ValidityState.VALID


def test_original_primitive_input_validation_and_alignment():
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir.validity import ValidityState, invalid, valid
    index = pd.date_range("2024-01-01", periods=3)
    values = pd.Series([valid(1.), valid(2.), valid(3.)], index=index)
    with pytest.raises(p.OriginalStrategyPrimitiveError):
        p._series({"source": [1., 2.]}, "source")
    with pytest.raises(p.OriginalStrategyPrimitiveError):
        p._numeric(1.)
    with pytest.raises(p.OriginalStrategyPrimitiveError):
        p._binary("gt", {"left": values, "right": values.iloc[:2]})
    for length in (True, 0, 4097, 1.5):
        with pytest.raises(p.OriginalStrategyPrimitiveError):
            p._length({"length": length})
    for value in (True, np.nan, "1"):
        with pytest.raises(p.OriginalStrategyPrimitiveError):
            p._value({"value": value}, {"alignment": values})
    for pct in (True, -1, 101, np.nan, "50"):
        with pytest.raises(p.OriginalStrategyPrimitiveError):
            p._nearest_rank({"length": 2, "percentile": pct}, {"source": values})
    with pytest.raises(p.OriginalStrategyPrimitiveError):
        p._optional_condition({"enabled": 1, "otherwise": False}, {"source": values})
    for frame in (None, {}, {"close": [1, 2]}):
        with pytest.raises(p.OriginalStrategyPrimitiveError):
            p._close({}, {"frame": frame})
    raw = pd.Series([True, np.nan, invalid(ValidityState.STALE)], index=index)
    assert [cell.state for cell in p._close({}, {"frame": {"close": raw}})["value"]] == [
        ValidityState.MISSING, ValidityState.MISSING, ValidityState.STALE]
    zero = pd.Series([valid(0.)] * 3, index=index)
    result = p._binary("divide", {"left": values, "right": zero})["value"]
    assert all(cell.state is ValidityState.MATHEMATICALLY_UNDEFINED for cell in result)
    assert p._lag({"length": 5}, {"source": values})["value"].size == 3


def test_original_sources_and_templates_reject_wrong_contexts():
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir.original_strategy_presets import instantiate_preset, preset_summaries
    from app.ir.validity import ValidityState, invalid, valid
    index = pd.date_range("2024-01-01", periods=3)
    values = pd.Series([valid(1.), invalid(ValidityState.PROVIDER_UNAVAILABLE), valid(3.)], index=index)
    rank = p._nearest_rank({"length": 2, "percentile": 100.}, {"source": values})["value"]
    assert all(cell.state is ValidityState.PROVIDER_UNAVAILABLE for cell in rank.iloc[1:])
    frame = {"close": values, "high": values, "low": values}
    tr = p._true_range({"frame": frame})["value"]
    assert all(cell.state is ValidityState.PROVIDER_UNAVAILABLE for cell in tr.iloc[1:])
    for context in ({}, {"bound_contract": None}):
        with pytest.raises(p.OriginalStrategyPrimitiveError):
            p._check_context("close", context)
    with pytest.raises(ValueError):
        p._source_binding("close")({"unexpected": 1}, {})
    with pytest.raises(KeyError):
        instantiate_preset("unknown", "copy")
    assert instantiate_preset("trend_impulse_v3", "copy", "Renamed")["metadata"]["name"] == "Renamed"
    assert all(row["provenance"]["source_sha256"] for row in preset_summaries())


def test_original_arithmetic_truth_table_and_fallback_boundaries():
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir.validity import ValidityState, invalid, valid
    index = pd.date_range("2024-01-01", periods=3)
    left = pd.Series([valid(1.), valid(2.), valid(3.)], index=index)
    right = pd.Series([valid(2.), valid(2.), valid(2.)], index=index)
    expected = {"subtract": [-1., 0., 1.], "divide": [.5, 1., 1.5],
                "multiply": [2., 4., 6.], "maximum": [2., 2., 3.],
                "gt": [False, False, True], "lt": [True, False, False],
                "le": [True, True, False]}
    for operation, result in expected.items():
        actual = p._binary(operation, {"left": left, "right": right})["value"]
        assert [cell.value for cell in actual] == result
    a = pd.Series([valid(False), valid(True), valid(True)], index=index)
    b = pd.Series([valid(False), valid(False), valid(True)], index=index)
    assert [cell.value for cell in p._binary("and", {"left": a, "right": b})["value"]] == [False, False, True]
    assert [cell.value for cell in p._binary("or", {"left": a, "right": b})["value"]] == [False, True, True]
    source = pd.Series([valid(-1.), invalid(ValidityState.MISSING), valid(2.)], index=index)
    assert p._abs({}, {"source": source})["value"].tolist() == [valid(1.), invalid(ValidityState.MISSING), valid(2.)]
    fallback = p._fallback_value({"left": source, "right": right})["value"]
    assert fallback.tolist() == source.tolist()
    assert p._lag({"length": 1}, {"source": left})["value"].tolist() == [
        invalid(ValidityState.INSUFFICIENT_HISTORY), valid(1.), valid(2.)]
    assert p._optional_condition({"enabled": True, "otherwise": False}, {"source": a})["value"].tolist() == a.tolist()
    assert [cell.value for cell in p._optional_condition({"enabled": False, "otherwise": True}, {"source": a})["value"]] == [True] * 3


def test_original_market_fields_reject_wrapped_non_price_values():
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir.validity import ValidityState, invalid, valid
    for value in (valid(True), valid((1., 2.)), True, np.nan):
        assert p._price_cell(value).state is ValidityState.MISSING
    assert p._price_cell(valid(12.)).value == 12.
    assert p._price_cell(invalid(ValidityState.STALE)).state is ValidityState.STALE


@pytest.mark.parametrize("preset", ["trend_impulse_v3", "expanding_z_v4"])
def test_original_presets_explicit_directional_adapter_preserves_signals(preset):
    from app.ir.hashing import content_address
    from app.ir.original_strategy_presets import instantiate_preset
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from research.evaluation.phase5_runtime import ResearchRunResult, _stable_value
    from research.strategy.v2_runtime_strategy import (
        DIRECTIONAL_ADAPTER_POLICY_ADDRESS, V2RuntimeStrategy, V2SignalAdapterRefusal,
    )

    registry = _original_preset_registry()
    document = instantiate_preset(preset, "adapter-original")
    frame = _synthetic().set_index("date")
    frame.index = frame.index.tz_localize("Asia/Kolkata")
    outputs = evaluate_v2(resolve_v2(document, registry), {"frame": dict(frame.items())}, registry)
    batch = _stable_value(outputs)
    result_document = {"schema": "phase5-research-run-result/1", "status": "COMPLETED",
        "output_digest": content_address({"schema": "incremental-output/1", "outputs": batch})}
    address = content_address(result_document)
    result = ResearchRunResult({**result_document, "result_address": address}, address, batch, batch)
    with pytest.raises(V2SignalAdapterRefusal, match="simultaneous"):
        V2RuntimeStrategy(document, result, frame.index)
    adapter = V2RuntimeStrategy(document, result, frame.index,
                                policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS)
    actual = adapter.signals(frame)
    assert any(actual.longEntry & actual.shortExit)
    for name in CANONICAL_COLUMNS:
        assert actual[name].tolist() == [cell.value for cell in outputs[name]]
    assert adapter.risk_model is None  # Signal preservation alone does not supply V4 stops.


# Historical full-session gaps are distinct from an opening jump.
def _gap_binding(*, timeframe=86400):
    from app.ir import hashing
    from app.ir.first_party import historical_daily_gaps as g
    from app.ir.first_party.analytical_v2 import contracts
    def address(value):
        return hashing.content_address({"gap_test": value})
    ports = {}
    for port, fields in g._FIELDS.items():
        fact = {"schema": "canonical-input-binding/1", "owner_id": "org.gap",
            "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
            "dataset_manifest_address": address("manifest"), "market_truth_address": address("market-truth"),
            "provider_product_address": address("provider-product"), "provider_contract_address": address("provider-contract"),
            "canonical_instrument_address": address("instrument"), "timeframe": timeframe,
            "fields": list(fields), "freshness": {"maximum_age_seconds": 86400},
            "depth": {"kind": "NONE", "levels": None}, "session": "INSTRUMENT_CALENDAR",
            "alignment": {"kind": "EXACT", "maximum_skew_seconds": 0}, "derived_local": port == "session",
            "instrument": {"role": "primary" if port == "frame" else "session", "type": "PHYSICAL"}}
        ports[port] = {"source": {"scope": "graph_input", "port_id": port}, "binding": fact,
                       "binding_address": hashing.content_address(fact)}
    context = {"schema": "node-input-binding/1", "owner_id": "org.gap",
        "dataset_context_address": address("dataset"), "evaluation_context_address": address("evaluation"),
        "context_address": hashing.content_address(ports), "ports": ports}
    return contracts.materialize_node_contract(g.NODE_CONTRACTS[g.KEY], g.CONTRACT_BINDINGS[g.KEY], {}, context)


def _gap_rows(prices=None):
    # (high, low, close). Day2 creates [100,104]; Day6 reaches proximal only.
    prices = prices or [(100., 96., 99.), (108., 104., 106.), (112., 107., 111.),
                        (113., 108., 110.), (111., 106., 107.), (108., 104., 105.),
                        (107., 103., 106.), (106., 99., 101.), (109., 103., 108.)]
    result = []
    for i, (high, low, close) in enumerate(prices):
        day = pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=i)
        end = day + pd.Timedelta(hours=10)
        result.append((end, {"frame": {"high": high, "low": low, "close": close},
            "session": {"session_id": f"SYNTHETIC:{i}", "session_open_at": day + pd.Timedelta(hours=4),
                        "session_close_at": end}}))
    return result


def _gap_inputs(rows):
    index = pd.DatetimeIndex([time for time, _ in rows])
    return {port: {field: pd.Series([row[port][field] for _, row in rows], index=index)
                   for field in rows[0][1][port]} for port in ("frame", "session")}


def test_historical_daily_gap_completed_geometry_partial_fill_restart_and_idempotence():
    import dataclasses
    from app.ir import node_contracts
    from app.ir.first_party import historical_daily_gaps as g
    rows, bound = _gap_rows(), _gap_binding()
    state = g.GapState(bound)
    state.step(rows[0][1], event_time=rows[0][0])
    with pytest.raises(node_contracts.NodeContractRefusal, match="GAP_COMPLETE_SESSION_REQUIRED"):
        state.step(rows[1][1], event_time=rows[1][0] - pd.Timedelta(hours=1))
    assert state.zones == ()
    state.step(rows[1][1], event_time=rows[1][0])
    original = state.zones[0]
    assert (original.lower, original.upper, original.status) == (100., 104., "OPEN")
    with pytest.raises(dataclasses.FrozenInstanceError):
        original.upper = 105.
    for time, row in rows[2:6]:
        state.step(row, event_time=time)
    assert state.zones[0].status == "PARTIAL"
    assert state.zones[0].touched_at == rows[5][0].isoformat()
    saved = state.snapshot()
    restored = g.GapState.restore(bound, saved, expected_payload_address=saved["payload_address"])
    repeated = restored.step(rows[5][1], event_time=rows[5][0])
    for _ in range(100):
        assert restored.step(rows[5][1], event_time=rows[5][0]) == repeated
    assert restored.snapshot() == saved
    for time, row in rows[6:]:
        assert restored.step(row, event_time=time) == state.step(row, event_time=time)
    assert restored.snapshot() == state.snapshot()
    assert (state.zones[0].lower, state.zones[0].upper, state.zones[0].status) == (100., 104., "FILLED")
    assert state.zones[0].zone_id == original.zone_id
    assert state.zones[0].filled_at == rows[7][0].isoformat()
    assert state.zones[0].touched_at == rows[5][0].isoformat()
    assert len({zone.zone_id for zone in state.zones}) == len(state.zones)


def test_historical_daily_gap_opening_jump_is_not_full_range_gap_and_mirror_is_exact():
    from app.ir.first_party import historical_daily_gaps as g
    rows = _gap_rows([(100., 95., 99.), (110., 99., 105.), (96., 93., 94.)])
    state = g.GapState(_gap_binding())
    for time, row in rows[:2]:
        state.step(row, event_time=time)
    assert not state.zones  # hypothetical open105 above prior close99 is not enough
    session = {"session_id": "equal", "session_close_at": rows[1][0].isoformat()}
    assert g._new_zone({"high": 100., "low": 95.}, {"low": 100., "high": 105.}, session) is None
    assert g._new_zone({"high": 100., "low": 95.}, {"low": 90., "high": 95.}, session) is None
    output = state.step(rows[2][1], event_time=rows[2][0])
    zone = state.zones[0]
    assert (zone.direction, zone.lower, zone.upper) == ("BEARISH", 96., 99.)
    assert output["bearish_proximal"].value == 96.
    assert output["bearish_distal"].value == 99.
    partial = g._observe_zone(zone, {"high": 96., "low": 93.}, "2026-01-04T10:00:00+00:00")
    assert partial.status == "PARTIAL"
    assert g._observe_zone(partial, {"high": 99., "low": 93.}, "2026-01-05T10:00:00+00:00").status == "FILLED"


def test_historical_daily_gap_deterministic_selection_and_historical_invalidity():
    import dataclasses
    from app.ir.first_party import historical_daily_gaps as g
    from app.ir.validity import ValidityState, invalid
    state = g.GapState(_gap_binding())
    rows = _gap_rows()
    for time, row in rows[:2]:
        state.step(row, event_time=time)
    first = state.zones[0]
    newer = g._new_zone({"high": 100., "low": 95.}, {"low": 104., "high": 108.},
                        {"session_id": "later", "session_close_at": "2026-01-03T10:00:00+00:00"})
    assert g._nearest((newer, first), "BULLISH", 108.) == first
    assert g._nearest((first, newer), "BULLISH", 108.) == first
    closer = g._new_zone({"high": 104., "low": 95.}, {"low": 105., "high": 108.},
                        {"session_id": "closer", "session_close_at": "2026-01-03T10:00:00+00:00"})
    assert g._nearest((first, closer), "BULLISH", 108.) == closer
    rows[2][1]["frame"]["low"] = invalid(ValidityState.STALE)
    output = state.step(rows[2][1], event_time=rows[2][0])
    assert all(cell.state is ValidityState.STALE for cell in output.values())
    assert state.zones == (first,)
    assert all(cell.state is ValidityState.STALE for cell in state.step(rows[3][1], event_time=rows[3][0]).values())
    saved = state.snapshot()
    restored = g.GapState.restore(state.bound_contract, saved, expected_payload_address=saved["payload_address"])
    assert restored.snapshot() == saved


def test_historical_daily_gap_refuses_conflicts_wrong_resolution_and_restore_tampering(monkeypatch):
    from app.ir import node_contracts
    from app.ir.first_party import historical_daily_gaps as g
    bound, rows = _gap_binding(), _gap_rows()
    state = g.GapState(bound)
    for time, row in rows[:2]:
        state.step(row, event_time=time)
    with pytest.raises(node_contracts.NodeContractRefusal, match="GAP_DUPLICATE_EVENT_CONFLICT"):
        state.step({**rows[1][1], "frame": {"high": 109., "low": 104., "close": 106.}}, event_time=rows[1][0])
    with pytest.raises(node_contracts.NodeContractRefusal, match="GAP_EVENT_ORDER"):
        state.step(rows[0][1], event_time=rows[0][0])
    with pytest.raises(ValueError, match="registered binding refused its exact inputs"):
        _gap_binding(timeframe=900)
    saved = node_contracts._plain(state.snapshot())
    address = saved["payload_address"]
    wrong_count = {**saved, "count": saved["count"] + 1}
    with pytest.raises(node_contracts.NodeContractRefusal, match="GAP_STATE_IDENTITY"):
        g.GapState.restore(bound, wrong_count, expected_payload_address=address)
    with pytest.raises(node_contracts.NodeContractRefusal, match="GAP_STATE_IDENTITY"):
        g.GapState.restore(bound, saved, expected_payload_address="sha256:" + "a" * 64)
    saved["zones"][0]["upper"] = 105.
    with pytest.raises(node_contracts.NodeContractRefusal, match="GAP_STATE_IDENTITY"):
        g.GapState.restore(bound, saved, expected_payload_address=address)
    monkeypatch.setattr(g, "MAX_ZONES", 1)
    extra = _gap_rows([(120., 115., 118.)])[0][1]
    extra["session"] = rows[2][1]["session"]
    before = state.snapshot()
    with pytest.raises(node_contracts.NodeContractRefusal, match="GAP_REGISTRY_CAPACITY_EXCEEDED"):
        state.step(extra, event_time=rows[2][0])
    assert state.snapshot() == before


def test_historical_daily_gap_batch_matches_prefix_and_future_mutation():
    from app.ir.first_party import historical_daily_gaps as g
    rows, bound = _gap_rows(), _gap_binding()
    inputs = _gap_inputs(rows)
    full = g.evaluate({}, inputs, evaluation_context={"bound_contract": bound})
    for end in range(1, len(rows) + 1):
        prefix = g.evaluate({}, _gap_inputs(rows[:end]), evaluation_context={"bound_contract": bound})
        for port in full:
            assert prefix[port].tolist() == full[port].iloc[:end].tolist()
    rows[-1][1]["frame"] = {"high": 140., "low": 130., "close": 135.}
    future = g.evaluate({}, _gap_inputs(rows), evaluation_context={"bound_contract": bound})
    for port in full:
        assert future[port].iloc[:-1].tolist() == full[port].iloc[:-1].tolist()


def _gap_graph():
    from app.ir import node_contracts
    from app.ir.first_party import historical_daily_gaps as g
    ports = node_contracts._plain(g.V2_COMPONENTS[g.KEY]["ports"])
    inputs = [port for port in ports if port["direction"] == "input"]
    outputs = [port for port in ports if port["direction"] == "output"]
    def edge(identifier, source, destination):
        return {"edge_id": identifier, "source": source, "target": destination, "binding": {"kind": "single"}}
    edges = [edge(f"input.{port['port_id']}", {"scope": "graph_input", "port_id": port["port_id"]},
                  {"scope": "node", "node_id": "gaps", "port_id": port["port_id"]}) for port in inputs]
    edges += [edge(f"output.{port['port_id']}", {"scope": "node", "node_id": "gaps", "port_id": port["port_id"]},
                   {"scope": "graph_output", "port_id": port["port_id"]}) for port in outputs]
    return {"format_version": 2, "strategy_id": "synthetic.full_daily_gap", "strategy_version": 1,
            "metadata": {"metadata_version": 1, "name": "Full daily gap regression", "description": "Synthetic analytical gap outputs", "tags": []},
            "graph_inputs": inputs, "graph_outputs": outputs,
            "nodes": [{"node_id": "gaps", "component": {"component_id": g.KEY[0], "component_version": g.KEY[1]}, "parameters": {}}],
            "edges": edges}


def test_historical_daily_gap_registered_graph_save_load_and_independent_prefix_runtime():
    import json
    from app.ir import hashing
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.ir.streaming_reference import evaluate_v2_prefix_stream
    from app.ir.first_party import historical_daily_gaps as g
    document = _gap_graph()
    assert g.KEY in REGISTRY.v2_components
    saved = json.loads(json.dumps(document))
    assert hashing.content_address(saved) == hashing.content_address(document)
    graph = resolve_v2(saved, REGISTRY)
    bound, inputs = _gap_binding(), _gap_inputs(_gap_rows())
    context = lambda node, values: {"bound_contract": bound}
    batch = evaluate_v2(graph, inputs, REGISTRY, evaluation_context_resolver=context)
    prefix = evaluate_v2_prefix_stream(graph, inputs, REGISTRY, evaluation_context_resolver=context)
    for port in batch:
        assert batch[port].tolist() == prefix[port].tolist()
    assert batch["bullish_proximal"].iloc[1].value == 104.
    assert batch["bullish_formed_at"].iloc[1].value == inputs["frame"]["close"].index[1].timestamp()


def _gap_eligibility_graph():
    from app.ir.first_party import original_strategy_primitives as p
    from app.ir import node_contracts
    from app.ir.original_strategy_presets import _edge
    graph = _gap_graph()
    for name in ("price", "atr", "stop", "confirmed", "cooldown", "additions"):
        kind = p.FLOAT if name in ("price", "atr", "stop") else p.BOOLEAN
        graph["graph_inputs"].append(p._port(name, "input", kind))
    def source(name):
        if name.startswith("$"):
            return "$input", name[1:]
        if name == "gap":
            return "gaps", "bullish_proximal"
        if name == "open_gap":
            return "gaps", "bullish_still_open"
        return name, "value"
    def node(name, operation, left, right=None, **parameters):
        graph["nodes"].append({"node_id": name, "component": {"component_id": "strategy_math." + operation,
                               "component_version": 1}, "parameters": parameters})
        for port, origin in (("alignment", left),) if operation == "value" else (("left", left), ("right", right)):
            identifier, output = source(origin)
            graph["edges"].append(_edge(name + "." + port, identifier, output, name, port))
    node("distance", "subtract", "$price", "gap")
    node("distance_atr", "divide", "distance", "$atr")
    node("stop_distance", "subtract", "$stop", "$price")
    node("reward_risk", "divide", "distance", "stop_distance")
    node("half", "value", "distance", value=.5)
    node("two", "value", "distance", value=2.)
    node("near_enough", "le", "distance_atr", "two")
    node("far_enough", "le", "half", "distance_atr")
    node("reward_enough", "le", "two", "reward_risk")
    node("distance_ok", "and", "near_enough", "far_enough")
    node("price_ok", "and", "distance_ok", "reward_enough")
    node("trend_ok", "and", "$confirmed", "open_gap")
    node("policy_ok", "and", "$cooldown", "$additions")
    node("conditions_ok", "and", "price_ok", "trend_ok")
    node("eligible", "and", "conditions_ok", "policy_ok")
    for name, kind in (("distance_atr", p.FLOAT), ("reward_risk", p.FLOAT), ("eligible", p.BOOLEAN)):
        graph["graph_outputs"].append(p._port(name, "output", kind))
        graph["edges"].append(_edge("output." + name, name, "value", "$output", name))
    return graph


def _gap_synthetic_eligibility():
    from app.ir.library import REGISTRY
    from app.ir.resolve import resolve_v2
    from app.ir.runtime import evaluate_v2
    from app.ir.validity import valid, invalid, ValidityState
    rows, bound = _gap_rows(), _gap_binding()
    inputs = _gap_inputs(rows)
    index = inputs["frame"]["close"].index
    frozen = {
        "price": [row["frame"]["close"] for _, row in rows],
        "atr": [None, None, 2., 2., 2., 2., 2., 2., 2.],
        "stop": [110., 110., 112., 111., 108.25, 108.25, 108.25, 108.25, 108.25],
        "confirmed": [False, False, False, True, True, True, False, False, False],
        "cooldown": [True, True, True, True, True, False, False, False, False],
        "additions": [True, True, True, True, True, False, False, False, False],
    }
    for name, cells in frozen.items():
        inputs[name] = pd.Series([invalid(ValidityState.INSUFFICIENT_HISTORY) if value is None else valid(value)
                                 for value in cells], index=index)
    graph = resolve_v2(_gap_eligibility_graph(), REGISTRY)
    actual = evaluate_v2(graph, inputs, REGISTRY,
        evaluation_context_resolver=lambda node, values: {"bound_contract": bound} if node.node_id == "gaps" else None)
    return rows, frozen, actual


def test_historical_daily_gap_007_frozen_eligibility_and_target_delta_oracle():
    from app.ir.validity import entry_authorized, ValidityState
    from app.ir.hashing import content_address
    from app.execution.target_position import TargetPositionRequest, PendingQuantityEvidence, derive_target_delta
    rows, frozen, actual = _gap_synthetic_eligibility()
    assert actual["distance_atr"].iloc[2].value == 3.5
    assert actual["distance_atr"].iloc[3].value == 3.0
    assert actual["distance_atr"].iloc[4].value == 1.5
    assert actual["reward_risk"].iloc[4].value == 2.4
    assert actual["eligible"].iloc[0].state is ValidityState.INSUFFICIENT_HISTORY
    assert [entry_authorized(cell) for cell in actual["eligible"]] == [False, False, False, False, True, False, False, False, False]
    # These are the frozen target oracle, not graph-generated orders. The current
    # four-boolean strategy adapter cannot publish independently owned tranches.
    core = [0, 0, -1, -1, -1, -1, 0, 0, 0]
    overlay = [0, 0, 0, 0, -3, 0, 0, 0, 0]
    aggregate = [a + b for a, b in zip(core, overlay, strict=True)]
    assert aggregate == [0, 0, -1, -1, -4, -1, 0, 0, 0]
    owned_gap = (actual["bullish_formed_at"].iloc[4].value,
                 actual["bullish_proximal"].iloc[4].value, actual["bullish_distal"].iloc[4].value)
    assert owned_gap == (rows[1][0].timestamp(), 104., 100.)
    assert rows[5][1]["frame"]["low"] <= owned_gap[1]  # close105 remains above target104
    assert core[5] == -1 and overlay[5] == 0
    address = content_address({"synthetic-target-oracle": 1})
    def request(index):
        return TargetPositionRequest(request_id=f"gap-oracle-{index}", owner_id="org.gap", broker_account_id="paper.gap",
            book="paper", deployment_id=1, strategy_key="ir.synthetic.gap", strategy_version="1",
            admission_address=address, graph_address=address, attribution_state="VERIFIED_GRAPH",
            canonical_instrument_key="SYNTHETIC", product_address=address, target_quantity=aggregate[index],
            purpose="TARGET_ADJUSTMENT", decision_at=rows[index][0].to_pydatetime())
    deltas = [derive_target_delta(request(i), held_quantity=aggregate[i - 1]).requested_delta for i in (2, 4, 5, 6)]
    assert deltas == [-1, -3, 3, 1]
    pending = PendingQuantityEvidence(evidence_id="pending-overlay", owner_id="org.gap", broker_account_id="paper.gap",
        book="paper", canonical_instrument_key="SYNTHETIC", product_address=address, signed_remaining_quantity=-3,
        state="ACKNOWLEDGED", uncertain=False, source_address=address)
    for _ in range(100):
        assert derive_target_delta(request(4), held_quantity=-4).requested_delta == 0
        assert derive_target_delta(request(4), held_quantity=-1, pending=(pending,)).requested_delta == 0
    assert derive_target_delta(request(5), held_quantity=-4).risk_reducing is True
    assert derive_target_delta(request(6), held_quantity=-1).risk_reducing is True


def test_historical_daily_gap_binding_refuses_cross_instrument_calendar_and_extra_parameters():
    from app.ir import node_contracts
    from app.ir.first_party import historical_daily_gaps as g
    context = node_contracts._plain(_gap_binding().document["input_binding"])
    with pytest.raises(ValueError, match="no parameters"):
        g._binding({"invented": True}, context)
    changes = {"derived_local": False, "instrument": {"role": "other", "type": "PHYSICAL"},
               "canonical_instrument_address": "sha256:" + "a" * 64,
               "market_truth_address": "sha256:" + "b" * 64}
    for field, value in changes.items():
        changed = node_contracts._plain(context)
        changed["ports"]["session"]["binding"][field] = value
        with pytest.raises(ValueError, match="canonical price instrument"):
            g._binding({}, changed)


def test_historical_gap_later_evaluation_uses_session_close_for_overlap():
    from app.ir.first_party import historical_daily_gaps as g
    from app.ir import node_contracts
    rows = _gap_rows()
    state = g.GapState(_gap_binding())
    state.step(rows[0][1], event_time=rows[0][0] + pd.Timedelta(hours=20))
    output = state.step(rows[1][1], event_time=rows[1][0] + pd.Timedelta(hours=20))
    assert output["bullish_proximal"].value == 104.
    assert state.zones[0].formed_at == rows[1][0].isoformat()
    rows[2][1]["session"]["session_open_at"] = rows[1][0]
    with pytest.raises(node_contracts.NodeContractRefusal, match="GAP_SESSION_OVERLAP"):
        state.step(rows[2][1], event_time=rows[2][0] + pd.Timedelta(hours=20))
