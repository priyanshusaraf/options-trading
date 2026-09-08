from __future__ import annotations

import ast
import copy
from pathlib import Path
from types import MappingProxyType

import pandas as pd
import pytest

from app.ir.hashing import content_address
from app.ir.validity import NumericValue, ValidityState, invalid, valid
from research.evaluation.phase5_runtime import ResearchRunResult
from research.strategy.v2_runtime_strategy import (
    ADAPTER_POLICY_ADDRESS,
    ADAPTER_POLICY_DOCUMENT,
    DIRECTIONAL_ADAPTER_POLICY_ADDRESS,
    DIRECTIONAL_ADAPTER_POLICY_DOCUMENT,
    risk_policy_document,
    V2RuntimeStrategy,
    V2SignalAdapterRefusal,
)
from research.orchestrator.v2_operation import _BarOpenPositionProjectionStrategy


ROLES = {
    "research_long_entry": "longEntry",
    "research_short_entry": "shortEntry",
    "research_long_exit": "longExit",
    "research_short_exit": "shortExit",
}


def _index(periods: int = 4) -> pd.DatetimeIndex:
    return pd.date_range("2026-01-05 09:15", periods=periods, freq="min", tz="Asia/Kolkata")


def _descriptor(role: str, port_id: str, **changes) -> dict:
    descriptor = {
        "port_id": port_id,
        "direction": "output",
        "semantic_flow": "value",
        "semantic_role": role,
        "type_ref": {"type_id": "analytical.boolean", "type_version": 2},
        "shape": "series",
    }
    descriptor.update(changes)
    return descriptor


def _document(descriptors: list[dict]) -> MappingProxyType:
    return MappingProxyType({
        "format_version": 2,
        "strategy_id": "arbitrary.strategy",
        "strategy_version": 7,
        "graph_outputs": tuple(MappingProxyType(item) for item in descriptors),
    })


def _stable(value):
    if isinstance(value, NumericValue):
        return {
            "schema": "numeric-value/1",
            "state": value.state.value,
            "value": value.value,
            "causes": [cause.value for cause in value.causes],
        }
    return value


def _result(outputs: dict[str, tuple[pd.DatetimeIndex, list[object]]], *, status="COMPLETED"):
    if status == "CANCELLED":
        batch = {}
        output_digest = None
    else:
        batch = {
            port: {
                "schema": "pandas-series/1",
                "index": [item.isoformat() for item in index],
                "values": [_stable(item) for item in values],
            }
            for port, (index, values) in outputs.items()
        }
        output_digest = content_address({
            "schema": "incremental-output/1", "outputs": batch,
        })
    document = {"schema": "phase5-research-run-result/1", "status": status,
                "output_digest": output_digest}
    result_address = content_address(document)
    document["result_address"] = result_address
    return ResearchRunResult(
        MappingProxyType(document), result_address,
        MappingProxyType(batch), MappingProxyType(copy.deepcopy(batch)),
    )


def _adapter(role_cells: dict[str, list[object]], *, descriptors=None, indexes=None,
             policy_address=ADAPTER_POLICY_ADDRESS, risk_policy="none", **exit_kwargs):
    ports = {role: f"opaque-port-{number}" for number, role in enumerate(role_cells)}
    descriptors = descriptors or [_descriptor(role, ports[role]) for role in role_cells]
    indexes = indexes or {role: _index(len(cells)) for role, cells in role_cells.items()}
    outputs = {
        ports[role]: (indexes[role], cells) for role, cells in role_cells.items()
    }
    return V2RuntimeStrategy(_document(descriptors), _result(outputs),
                             _index(len(next(iter(role_cells.values())))),
                             policy_address=policy_address, risk_policy=risk_policy, **exit_kwargs)


class _WarmupAdapter:
    key = "v2.warmup.probe"
    display_name = "warmup probe"
    risk_model = None
    adapter_address = "sha256:" + "a" * 64
    adapter_policy_address = ADAPTER_POLICY_ADDRESS

    def __init__(self, declared_warmup: int):
        self.declared_warmup = declared_warmup

    def signals(self, frame):
        result = frame.copy(deep=True)
        valid_from = self.declared_warmup
        for column in ("longEntry", "shortEntry", "longExit", "shortExit"):
            result[column] = [index >= valid_from for index in range(len(result))]
        return result


def _projected_warmup_strategy(native: int, baseline: int):
    availability = pd.date_range(
        "2026-01-05 09:16", periods=8, freq="min", tz="Asia/Kolkata",
    )
    bar_open = availability - pd.Timedelta(minutes=1)
    manifest = "sha256:" + "b" * 64
    position_map = content_address({
        "schema": "bar-open-position-map/1",
        "dataset_manifest_address": manifest,
        "availability_index": [item.isoformat() for item in availability],
        "bar_open_index": [item.isoformat() for item in bar_open],
    })
    return _BarOpenPositionProjectionStrategy(
        _WarmupAdapter(native), manifest_address=manifest,
        availability_index=availability, bar_open_index=bar_open,
        position_map_address=position_map, declared_warmup=baseline,
    ), pd.DataFrame({"date": bar_open, "close": range(8)})


def _fold_signature(frame, folds=2):
    size = len(frame) // folds
    return tuple((frame.iloc[index * size]["date"],
                  frame.iloc[len(frame) - 1 if index == folds - 1
                             else (index + 1) * size - 1]["date"])
                 for index in range(folds))


def test_candidate_warmup_is_conservatively_bound_to_authored_baseline():
    from app.backtest.engine import trim_warmup

    baseline_warmup = 3
    high, frame = _projected_warmup_strategy(5, baseline_warmup)
    low, _ = _projected_warmup_strategy(1, baseline_warmup)
    high_signals = high.signals(frame)
    low_signals = low.signals(frame)
    high_trimmed = trim_warmup(high_signals, high).reset_index(drop=True)
    low_trimmed = trim_warmup(low_signals, low).reset_index(drop=True)

    assert not high_signals.loc[:4, "longEntry"].any()
    assert low_signals.loc[1:2, "longEntry"].all()
    assert not low_trimmed["date"].isin(low_signals.loc[1:2, "date"]).any()
    assert _fold_signature(high_trimmed) == _fold_signature(low_trimmed)

    native_high, _ = _projected_warmup_strategy(5, 5)
    native_low, _ = _projected_warmup_strategy(1, 1)
    assert _fold_signature(trim_warmup(native_high.signals(frame), native_high)) \
        != _fold_signature(trim_warmup(native_low.signals(frame), native_low))


@pytest.mark.parametrize(
    ("role_cells", "expected"),
    [
        (
            {"research_long_entry": [valid(False), valid(True), valid(False), valid(False)],
             "research_long_exit": [valid(False), valid(False), valid(True), valid(False)]},
            {"longEntry": [False, True, False, False],
             "shortEntry": [False] * 4, "longExit": [False, False, True, False],
             "shortExit": [False] * 4},
        ),
        (
            {"research_short_entry": [valid(False), valid(True), valid(False), valid(False)],
             "research_short_exit": [valid(False), valid(False), valid(True), valid(False)]},
            {"longEntry": [False] * 4,
             "shortEntry": [False, True, False, False], "longExit": [False] * 4,
             "shortExit": [False, False, True, False]},
        ),
        (
            {"research_long_entry": [valid(True), valid(False), valid(False), valid(False)],
             "research_short_entry": [valid(False), valid(True), valid(False), valid(False)],
             "research_long_exit": [valid(False), valid(False), valid(True), valid(False)],
             "research_short_exit": [valid(False), valid(False), valid(False), valid(True)]},
            {"longEntry": [True, False, False, False],
             "shortEntry": [False, True, False, False],
             "longExit": [False, False, True, False],
             "shortExit": [False, False, False, True]},
        ),
    ],
)
def test_accepts_exact_role_sets_with_arbitrary_port_ids(role_cells, expected):
    adapter = _adapter(role_cells)
    frame = pd.DataFrame({"date": _index(), "close": [1.0, 2.0, 3.0, 4.0]})

    actual = adapter.signals(frame)

    assert actual[list(expected)].to_dict("list") == expected
    assert adapter.declared_warmup == 0
    assert adapter.risk_model is None
    assert adapter.adapter_policy_address == ADAPTER_POLICY_ADDRESS
    assert adapter.adapter_policy_document == ADAPTER_POLICY_DOCUMENT


def test_output_reorder_and_port_rename_stay_role_driven():
    cells = {
        "research_long_entry": [valid(False), valid(True), valid(False), valid(False)],
        "research_long_exit": [valid(False), valid(False), valid(True), valid(False)],
    }
    descriptors = [_descriptor("research_long_exit", "renamed-z"),
                   _descriptor("research_long_entry", "renamed-a")]
    result = _result({
        "renamed-a": (_index(), cells["research_long_entry"]),
        "renamed-z": (_index(), cells["research_long_exit"]),
    })
    adapter = V2RuntimeStrategy(_document(descriptors), result, _index())

    actual = adapter.signals(pd.DataFrame(index=_index()))

    assert actual["longEntry"].tolist() == [False, True, False, False]
    assert actual["longExit"].tolist() == [False, False, True, False]
    assert dict(adapter.role_to_port) == {
        "research_long_entry": "renamed-a", "research_long_exit": "renamed-z",
    }


@pytest.mark.parametrize(
    "roles",
    [[], ["research_long_entry"], ["research_long_exit"],
     ["research_long_entry", "research_short_entry"],
     ["research_long_entry", "research_long_exit", "research_short_entry"],
     ["research_long_entry", "research_long_exit", "hold"],
     ["research_long_entry", "research_long_exit", "research_diagnostic"]],
)
def test_refuses_every_wrong_extra_or_incomplete_role_set(roles):
    descriptors = [_descriptor(role, f"p{number}") for number, role in enumerate(roles)]
    outputs = {f"p{number}": (_index(), [valid(False)] * 4)
               for number, _role in enumerate(roles)}

    with pytest.raises(V2SignalAdapterRefusal, match="role set"):
        V2RuntimeStrategy(_document(descriptors), _result(outputs), _index())


def test_refuses_duplicate_role_even_when_the_set_looks_supported():
    descriptors = [_descriptor("research_long_entry", "p1"),
                   _descriptor("research_long_entry", "p2"),
                   _descriptor("research_long_exit", "p3")]
    outputs = {port: (_index(), [valid(False)] * 4) for port in ("p1", "p2", "p3")}

    with pytest.raises(V2SignalAdapterRefusal, match="unique"):
        V2RuntimeStrategy(_document(descriptors), _result(outputs), _index())


def test_refuses_duplicate_output_port_lookup():
    descriptors = [_descriptor("research_long_entry", "shared"),
                   _descriptor("research_long_exit", "shared")]
    with pytest.raises(V2SignalAdapterRefusal, match="port_ids must be unique"):
        V2RuntimeStrategy(_document(descriptors), _result({
            "shared": (_index(), [valid(False)] * 4),
        }), _index())


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"direction": "input"}, "direction"),
        ({"semantic_flow": "condition"}, "semantic_flow"),
        ({"type_ref": {"type_id": "analytical.float64", "type_version": 2}}, "type_ref"),
        ({"type_ref": {"type_id": "analytical.boolean", "type_version": 1}}, "type_ref"),
        ({"shape": "scalar"}, "shape"),
        ({"shape": "event_stream"}, "shape"),
        ({"type_ref": {"type_id": "monitoring.condition", "type_version": 1}}, "type_ref"),
        ({"type_ref": {"type_id": "execution.intent", "type_version": 1}}, "type_ref"),
    ],
)
def test_refuses_descriptor_semantic_type_version_flow_and_shape(changes, match):
    descriptors = [_descriptor("research_long_entry", "entry", **changes),
                   _descriptor("research_long_exit", "exit")]
    outputs = {port: (_index(), [valid(False)] * 4) for port in ("entry", "exit")}

    with pytest.raises(V2SignalAdapterRefusal, match=match):
        V2RuntimeStrategy(_document(descriptors), _result(outputs), _index())


def test_refuses_missing_or_extra_runtime_output_port():
    descriptors = [_descriptor("research_long_entry", "entry"),
                   _descriptor("research_long_exit", "exit")]
    with pytest.raises(V2SignalAdapterRefusal, match="output ports"):
        V2RuntimeStrategy(_document(descriptors), _result({
            "entry": (_index(), [valid(False)] * 4),
        }), _index())
    with pytest.raises(V2SignalAdapterRefusal, match="output ports"):
        V2RuntimeStrategy(_document(descriptors), _result({
            "entry": (_index(), [valid(False)] * 4),
            "exit": (_index(), [valid(False)] * 4),
            "diagnostic": (_index(), [valid(False)] * 4),
        }), _index())


@pytest.mark.parametrize(
    "bad_index",
    [
        pd.date_range("2026-01-05", periods=4, freq="min"),
        pd.DatetimeIndex([_index()[0], _index()[1], _index()[1], _index()[3]]),
        _index()[::-1],
        pd.date_range("2026-01-05 09:16", periods=4, freq="min", tz="Asia/Kolkata"),
    ],
)
def test_refuses_naive_duplicate_descending_or_mismatched_output_indexes(bad_index):
    roles = {"research_long_entry": [valid(False)] * 4,
             "research_long_exit": [valid(False)] * 4}
    with pytest.raises(V2SignalAdapterRefusal, match="index"):
        _adapter(roles, indexes={role: bad_index for role in roles})


def test_refuses_mismatched_role_indexes():
    roles = {"research_long_entry": [valid(False)] * 4,
             "research_long_exit": [valid(False)] * 4}
    indexes = {"research_long_entry": _index(),
               "research_long_exit": _index().tz_convert("UTC")}
    with pytest.raises(V2SignalAdapterRefusal, match="index"):
        _adapter(roles, indexes=indexes)


def test_equal_and_unequal_role_warmups_use_maximum_and_suppress_all_flags():
    ih = invalid(ValidityState.INSUFFICIENT_HISTORY)
    adapter = _adapter({
        "research_long_entry": [ih, valid(True), valid(True), valid(False)],
        "research_long_exit": [ih, ih, valid(False), valid(True)],
    })
    equal = _adapter({
        "research_long_entry": [ih, valid(False), valid(True), valid(False)],
        "research_long_exit": [ih, valid(False), valid(False), valid(True)],
    })

    actual = adapter.signals(pd.DataFrame(index=_index()))

    assert adapter.declared_warmup == 2
    assert actual["longEntry"].tolist() == [False, False, True, False]
    assert actual["longExit"].tolist() == [False, False, False, True]
    assert equal.declared_warmup == 1


@pytest.mark.parametrize("state", [state for state in ValidityState
                                    if state not in {ValidityState.VALID,
                                                     ValidityState.INSUFFICIENT_HISTORY}])
def test_refuses_wrong_invalid_state_before_settlement(state):
    with pytest.raises(V2SignalAdapterRefusal, match="INSUFFICIENT_HISTORY"):
        _adapter({"research_long_entry": [invalid(state), valid(False), valid(False), valid(False)],
                  "research_long_exit": [valid(False)] * 4})


@pytest.mark.parametrize("state", [state for state in ValidityState
                                    if state is not ValidityState.VALID])
def test_refuses_any_invalidity_after_a_role_settles(state):
    with pytest.raises(V2SignalAdapterRefusal, match="after settlement"):
        _adapter({
            "research_long_entry": [valid(False), invalid(state),
                                    valid(False), valid(False)],
            "research_long_exit": [valid(False)] * 4,
        })


@pytest.mark.parametrize("cell", [valid(1), valid(0), valid(1.0), valid((True,))])
def test_refuses_non_bool_valid_cells(cell):
    with pytest.raises(V2SignalAdapterRefusal, match="exact bool"):
        _adapter({"research_long_entry": [cell] + [valid(False)] * 3,
                  "research_long_exit": [valid(False)] * 4})


def test_refuses_raw_bool_series_and_non_series_runtime_output():
    descriptors = [_descriptor("research_long_entry", "entry"),
                   _descriptor("research_long_exit", "exit")]
    with pytest.raises(V2SignalAdapterRefusal, match="NumericValue"):
        V2RuntimeStrategy(_document(descriptors), _result({
            "entry": (_index(), [False] * 4), "exit": (_index(), [False] * 4),
        }), _index())
    result = _result({"entry": (_index(), [valid(False)] * 4),
                      "exit": (_index(), [valid(False)] * 4)})
    bad_batch = dict(result.batch_output_document)
    bad_batch["entry"] = _stable(valid(False))
    digest = content_address({"schema": "incremental-output/1", "outputs": bad_batch})
    document = {"status": "COMPLETED", "output_digest": digest}
    address = content_address(document)
    document["result_address"] = address
    malformed = ResearchRunResult(document, address, bad_batch, copy.deepcopy(bad_batch))
    with pytest.raises(V2SignalAdapterRefusal, match="pandas Series"):
        V2RuntimeStrategy(_document(descriptors), malformed, _index())


def test_refuses_more_than_one_true_flag_per_settled_bar():
    with pytest.raises(V2SignalAdapterRefusal, match="simultaneous"):
        _adapter({
            "research_long_entry": [valid(False), valid(True), valid(False), valid(False)],
            "research_short_entry": [valid(False), valid(False), valid(False), valid(False)],
            "research_long_exit": [valid(False), valid(True), valid(False), valid(False)],
            "research_short_exit": [valid(False)] * 4,
        })


def test_all_false_is_hold_and_repeated_signals_are_defensive_copies():
    source = pd.DataFrame({"date": _index(), "close": [1.0, 2.0, 3.0, 4.0]})
    before = source.copy(deep=True)
    adapter = _adapter({"research_long_entry": [valid(False)] * 4,
                        "research_long_exit": [valid(False)] * 4})

    first = adapter.signals(source)
    first.loc[0, "longEntry"] = True
    second = adapter.signals(source)

    pd.testing.assert_frame_equal(source, before)
    assert not second[list(ROLES.values())].to_numpy().any()
    assert first is not second
    assert all(dtype == bool for dtype in second[list(ROLES.values())].dtypes)


def test_constructor_and_repeated_signals_do_not_mutate_document_or_result():
    descriptors = [_descriptor("research_long_entry", "entry"),
                   _descriptor("research_long_exit", "exit")]
    document = _document(descriptors)
    result = _result({"entry": (_index(), [valid(False)] * 4),
                      "exit": (_index(), [valid(False)] * 4)})
    document_before = repr(document)
    result_before = repr(result)
    adapter = V2RuntimeStrategy(document, result, _index())

    adapter.signals(pd.DataFrame(index=_index()))
    adapter.signals(pd.DataFrame(index=_index()))

    assert repr(document) == document_before
    assert repr(result) == result_before


def test_refuses_parameter_overrides_and_input_index_substitution():
    adapter = _adapter({"research_long_entry": [valid(False)] * 4,
                        "research_long_exit": [valid(False)] * 4})
    with pytest.raises(V2SignalAdapterRefusal, match="parameter overrides"):
        adapter.signals(pd.DataFrame(index=_index()), threshold=1)
    with pytest.raises(V2SignalAdapterRefusal, match="parameter overrides"):
        adapter.compute(pd.DataFrame(index=_index()), threshold=1)
    with pytest.raises(V2SignalAdapterRefusal, match="verified event index"):
        adapter.signals(pd.DataFrame(index=_index().tz_convert("UTC")))


def test_accepts_only_completed_research_run_result():
    descriptors = [_descriptor("research_long_entry", "entry"),
                   _descriptor("research_long_exit", "exit")]
    with pytest.raises(V2SignalAdapterRefusal, match="ResearchRunResult"):
        V2RuntimeStrategy(_document(descriptors), object(), _index())
    with pytest.raises(V2SignalAdapterRefusal, match="COMPLETED"):
        V2RuntimeStrategy(_document(descriptors), _result({}, status="CANCELLED"), _index())


def test_policy_document_has_the_reviewed_content_address():
    assert ADAPTER_POLICY_ADDRESS == "sha256:e35daffd61c1bacb3b51a4384cafaac71f7637b029a541189060a1d6ff7e0ca1"
    assert content_address(ADAPTER_POLICY_DOCUMENT) == ADAPTER_POLICY_ADDRESS
    with pytest.raises(TypeError, match="immutable"):
        ADAPTER_POLICY_DOCUMENT["algorithm_version"] = 2


def test_adapter_has_no_forbidden_boundary_imports():
    path = Path(__file__).parents[1] / "research" / "strategy" / "v2_runtime_strategy.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = ("provider", "broker", "runner", "ledger", "database", "sqlalchemy",
                 "v2_lifecycle", "evaluation.walkforward", "backtest.engine",
                 "research.pipeline", "research.domain.operations")
    assert not [name for name in imported if any(token in name for token in forbidden)]


@pytest.mark.parametrize("flags, accepted", [
    ("0000", True), ("0001", True), ("0010", True), ("0011", True),
    ("0100", True), ("0101", False), ("0110", True), ("0111", False),
    ("1000", True), ("1001", True), ("1010", False), ("1011", False),
    ("1100", False), ("1101", False), ("1110", False), ("1111", False),
])
def test_directional_policy_preserves_opposite_exits_and_refuses_conflicts(flags, accepted):
    cells = {role: [valid(bit == "1")] for role, bit in zip(ROLES, flags, strict=True)}
    if not accepted:
        with pytest.raises(V2SignalAdapterRefusal, match="conflicting directional"):
            _adapter(cells, policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS)
        return
    adapter = _adapter(cells, policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS)
    observed = adapter.signals(pd.DataFrame({"date": _index(1)}))
    assert [bool(observed[column].iloc[0]) for column in ROLES.values()] == [bit == "1" for bit in flags]
    assert adapter.adapter_policy_address == DIRECTIONAL_ADAPTER_POLICY_ADDRESS
    assert adapter.provenance_document["adapter_policy_document"] == DIRECTIONAL_ADAPTER_POLICY_DOCUMENT


def test_directional_policy_is_explicit_and_changes_adapter_identity():
    cells = {role: [valid(role == "research_long_entry")] for role in ROLES}
    legacy = _adapter(cells)
    directional = _adapter(cells, policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS)
    assert legacy.adapter_policy_address == ADAPTER_POLICY_ADDRESS
    assert directional.adapter_address != legacy.adapter_address
    assert content_address(DIRECTIONAL_ADAPTER_POLICY_DOCUMENT) == DIRECTIONAL_ADAPTER_POLICY_ADDRESS
    with pytest.raises(V2SignalAdapterRefusal, match="unsupported"):
        _adapter(cells, policy_address="sha256:" + "0" * 64)
    cells["research_short_exit"] = [valid(True)]
    with pytest.raises(V2SignalAdapterRefusal, match="simultaneous"):
        _adapter(cells)



def test_explicit_pine_risk_overlay_is_pinned_and_warms_up():
    cells = {role: [valid(False)] * 16 for role in ROLES}
    cells["research_long_entry"][0] = valid(True)
    cells["research_long_entry"][14] = valid(True)
    adapter = _adapter(cells, policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS, risk_policy="pine-v4-ratchet/1")
    assert adapter.risk_model == risk_policy_document("pine-v4-ratchet/1")["risk_model"]
    assert adapter.risk_atr_seed_policy == "sma"
    assert adapter.declared_warmup == 13
    frame = adapter.signals(pd.DataFrame({"date": _index(16)}))
    assert not bool(frame.longEntry.iloc[0])
    assert bool(frame.longEntry.iloc[14])
    assert adapter.provenance_document["risk_policy_address"] == content_address(adapter.risk_policy_document)
    with pytest.raises(TypeError):
        adapter.risk_model["atr_length"] = 1
    short = {role: [valid(False)] * 4 for role in ROLES}
    with pytest.raises(V2SignalAdapterRefusal, match="more completed bars"):
        _adapter(short, policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS, risk_policy="pine-v4-ratchet/1")
    with pytest.raises(V2SignalAdapterRefusal, match="directional"):
        _adapter(short, risk_policy="pine-v4-ratchet/1")
    with pytest.raises(V2SignalAdapterRefusal, match="unsupported"):
        risk_policy_document("unknown")


def test_reversal_policy_has_distinct_identity_and_preserves_legacy_overlay():
    cells = {role: [valid(False)] * 16 for role in ROLES}
    legacy = _adapter(cells, policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS,
                      risk_policy="pine-v4-ratchet/1")
    reversal = _adapter(cells, policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS,
                        risk_policy="pine-v4-reversal/1")
    assert legacy.replay_policy is None
    assert reversal.replay_policy == "pine-reversal-fixed-unit/1"
    assert reversal.risk_model == legacy.risk_model
    assert reversal.declared_warmup == legacy.declared_warmup == 13
    assert reversal.risk_policy_address != legacy.risk_policy_address
    assert reversal.adapter_address != legacy.adapter_address
    assert dict(legacy.risk_policy_document) == {
        "schema": "v2-research-risk-policy/1", "policy_id": "pine-v4-ratchet/1",
        "risk_model": {"atr_length": 14, "initial_risk_atr": 1.25,
                       "trail_start_r": 1.75, "trail_atr": 3.0,
                       "use_mfe_capture_floor": True, "capture_start_r": 1.25,
                       "capture_pct": 0.35},
        "atr_seed_policy": "sma", "management": "close-confirmed-after-fill/1",
        "warmup": "require-atr-seed-before-entries/1",
    }


def test_percentage_exit_policy_is_frozen_and_changes_adapter_identity_only_when_active():
    cells = {"research_long_entry": [valid(True), valid(False), valid(False), valid(False)],
             "research_long_exit": [valid(False)] * 4}
    default = _adapter(cells)
    disabled = _adapter(cells, stop_loss_pct=0, take_profit_pct=0)
    protected = _adapter(cells, stop_loss_pct=.01, take_profit_pct=.02)
    assert default.adapter_address == disabled.adapter_address
    assert default.protective_band_document is None
    assert "protective_band_document" not in default.provenance_document
    assert protected.adapter_address != default.adapter_address
    assert protected.provenance_document["protective_band_document"] == {
        "schema": "research-percentage-exit-policy/1", "stop_loss_pct": .01,
        "take_profit_pct": .02, "basis": "slipped-entry-fill",
        "trigger": "completed-close-after-entry-bar", "fill": "next-bar-open-adverse-slippage",
        "intrabar": "not-evaluated", "precedence": "stop-target-ratchet-strategy"}
    with pytest.raises(TypeError, match="immutable"):
        protected.protective_band_document["stop_loss_pct"] = .2


@pytest.mark.parametrize("document", [None, {"format_version": 1}])
def test_research_signal_columns_require_v2_document_without_a_run_wrapper(document):
    from research.strategy.v2_runtime_strategy import research_signal_columns
    with pytest.raises(V2SignalAdapterRefusal, match="V2 document"):
        research_signal_columns(document, {}, _index(),
            policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS, risk_policy="none")


def test_research_signal_columns_accept_evaluated_series_and_detach_flag_values():
    from research.strategy.v2_runtime_strategy import research_signal_columns
    descriptors = [_descriptor(role, port) for role, port in ROLES.items()]
    index = _index()
    outputs = {port: pd.Series([valid(False), valid(False), valid(port == "longEntry"),
                               valid(port == "longExit")], index=index, dtype=object)
               for port in ROLES.values()}
    roles, columns, warmup = research_signal_columns(_document(descriptors), outputs, index,
        policy_address=DIRECTIONAL_ADAPTER_POLICY_ADDRESS, risk_policy="none")
    assert roles == ROLES and warmup == 0
    assert columns["longEntry"] == [False, False, True, False]
    assert columns["longExit"] == [False, False, False, True]
    outputs["longEntry"].iloc[2] = valid(False)
    assert columns["longEntry"][2] is True
