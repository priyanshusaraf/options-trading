"""Critical Composition-to-IR lowering checks.

Each test pins a stated failure hypothesis from the Phase 3 Task 5 brief.
"""
from __future__ import annotations

import math
import pathlib
from types import SimpleNamespace

import pandas as pd
import pytest

from app.ir.hashing import canonical_json
from app.ir.library import REGISTRY
import research.strategy.builder.composition_ir as lowering
from research.strategy.builder.composition_ir import CompositionLoweringError, composition_to_ir
from research.strategy.builder.grammar import BlockRef, Clause, Composition
from research.strategy.builder.ir_strategy import IRGraphStrategy
from research.strategy.builder.load import build_strategy


_SPEC = {
    "key": "gen_composition_ir_v1",
    "longEntry": {"all": ["ema_slope_up(50,5)", "zscore_cross_up(50,1.0)"]},
    "shortEntry": {"all": ["ema_slope_down(50,5)", "zscore_cross_down(50,1.0)"]},
    "longExit": {"any": ["zscore_lt(50,0.0)", "ema_slope_down(50,5)"]},
    "shortExit": {"any": ["zscore_gt(50,0.0)", "ema_slope_up(50,5)"]},
}

_MIXED_SPEC = {
    "key": "gen_composition_ir_mixed_v1",
    "longEntry": {"all": ["rsi_gt(14,60.0,3,2)", "volume_surge(20,2.0)"]},
    "shortEntry": {"all": ["opening_range_break_down(3,0.25)"]},
    "longExit": {"any": ["body_frac_gt(0.5)"]},
    "shortExit": {"any": ["gap_down_pct(0.5)"]},
}


def _frame(n: int = 640) -> pd.DataFrame:
    index = pd.date_range("2026-01-01 09:15", periods=n, freq="15min", tz="Asia/Kolkata")
    close = pd.Series(
        [100.0 + 0.15 * i + 6.0 * math.sin(i / 9.0) for i in range(n)], index=index)
    return pd.DataFrame({
        "date": index,
        "open": close.shift(1).fillna(close.iloc[0]),
        "high": close + 0.9,
        "low": close - 0.9,
        "close": close,
    }, index=index)


def test_same_composition_lowers_to_identical_canonical_graph_bytes() -> None:
    """Hypothesis 1: logically equal compositions can mint different graph identities."""
    composition = Composition.from_dict(_SPEC)
    first = composition_to_ir(composition, identifier="generated.example")
    second = composition_to_ir(
        Composition.from_dict(composition.to_dict()), identifier="generated.example")
    assert canonical_json(first) == canonical_json(second)


def test_lowered_graph_matches_legacy_composition_decisions() -> None:
    """Hypothesis 2: lowered graph outputs can drift from the composition evaluator."""
    composition = Composition.from_dict(_SPEC)
    frame = _frame()
    legacy = build_strategy(composition).signals(frame)
    graph = composition_to_ir(composition, identifier="generated.example")
    lowered = IRGraphStrategy(graph, (REGISTRY.library, REGISTRY.implementations)).signals(frame)
    pd.testing.assert_frame_equal(
        lowered[["longEntry", "shortEntry", "longExit", "shortExit"]],
        legacy[["longEntry", "shortEntry", "longExit", "shortExit"]],
    )


def test_lowering_preserves_overrides_input_union_and_canonical_clause_order() -> None:
    """Hypothesis 3: an override, required bar input, or clause ordering is lost."""
    graph = composition_to_ir(Composition.from_dict(_MIXED_SPEC), identifier="generated.example")
    assert [item["identifier"] for item in graph["interface"] if item["item"] == "socket"] == [
        "open", "high", "low", "close", "volume", "longEntry", "shortEntry", "longExit", "shortExit"
    ]
    assert [node["instance_id"] for node in graph["nodes"] if node["instance_id"].startswith("c")] == [
        "c0_b0", "c0_b1", "c0_and1", "c1_b0", "c2_b0", "c3_b0",
    ]
    assert next(node for node in graph["nodes"] if node["instance_id"] == "c0_b0")["overrides"] == {
        "length": 14, "thr": 60.0, "source": 3, "smooth": 2
    }
    assert next(node for node in graph["nodes"] if node["instance_id"] == "c0_b1")["overrides"] == {
        "length": 20, "mult": 2.0
    }
    assert next(node for node in graph["nodes"] if node["instance_id"] == "c1_b0")["overrides"] == {
        "bars": 3, "buffer_pct": 0.25
    }


def test_lowering_refuses_empty_clause_even_if_a_composition_is_forged() -> None:
    """Hypothesis 4: an empty clause is accepted outside grammar parsing."""
    good = Composition.from_dict(_SPEC)
    forged = Composition(
        key=good.key,
        long_entry=Clause("all", ()),
        short_entry=good.short_entry,
        long_exit=good.long_exit,
        short_exit=good.short_exit,
    )
    with pytest.raises(CompositionLoweringError, match="empty"):
        composition_to_ir(forged, identifier="generated.example")


@pytest.mark.parametrize("identifier", ("logic.and", "logic.or"))
def test_lowering_refuses_a_missing_registered_logic_component(monkeypatch, identifier: str) -> None:
    """Hypothesis 4: a missing registered boolean combiner falls back to local code."""
    body_ref = REGISTRY.library.components[(identifier, 1)]["body"]["ref"]
    monkeypatch.setattr(
        lowering,
        "REGISTRY",
        SimpleNamespace(
            library=REGISTRY.library,
            registrations={key: value for key, value in REGISTRY.registrations.items()
                           if key != body_ref},
        ),
    )
    with pytest.raises(CompositionLoweringError, match="no executable registration"):
        lowering.composition_to_ir(Composition.from_dict(_SPEC), identifier="generated.example")


def test_lowering_refuses_an_unsupported_block_before_it_emits_a_graph() -> None:
    """Hypothesis 4: a bypass can lower an unsupported block outside grammar parsing."""
    good = Composition.from_dict(_SPEC)
    forged = Composition(
        key=good.key,
        long_entry=Clause("all", (BlockRef("not_registered", ()),)),
        short_entry=good.short_entry,
        long_exit=good.long_exit,
        short_exit=good.short_exit,
    )
    with pytest.raises(CompositionLoweringError, match="unknown block"):
        composition_to_ir(forged, identifier="generated.example")


def test_lowering_refuses_forged_block_argument_arity_before_binding() -> None:
    """Hypothesis 3: forged refs can silently drop an argument during parameter binding."""
    good = Composition.from_dict(_SPEC)
    forged = Composition(
        key=good.key,
        long_entry=Clause("all", (BlockRef("ema_slope_up", (50,)),)),
        short_entry=good.short_entry,
        long_exit=good.long_exit,
        short_exit=good.short_exit,
    )
    with pytest.raises(CompositionLoweringError, match="expects 2 arguments"):
        composition_to_ir(forged, identifier="generated.example")


def test_lowering_refuses_a_known_block_without_its_registered_kernel(monkeypatch) -> None:
    """Hypothesis 4: a library component exists but its executable registration is absent."""
    body_ref = REGISTRY.library.components[("block.ema_slope_up", 1)]["body"]["ref"]
    monkeypatch.setattr(
        lowering,
        "REGISTRY",
        SimpleNamespace(
            library=REGISTRY.library,
            registrations={key: value for key, value in REGISTRY.registrations.items()
                           if key != body_ref},
        ),
    )
    with pytest.raises(CompositionLoweringError, match="no executable registration"):
        lowering.composition_to_ir(Composition.from_dict(_SPEC), identifier="generated.example")


def test_generated_authority_uses_app_registry_not_legacy_python_or_a_local_library() -> None:
    """Hypotheses 5/6: generated research can bypass admitted app-owned IR authority."""
    root = pathlib.Path(__file__).resolve().parents[1]
    generated = (root / "research/orchestrator/generate.py").read_text()
    lowerer = (root / "research/strategy/builder/composition_ir.py").read_text()
    assert "from app.ir.library import REGISTRY" in generated
    assert "from app.ir.library import REGISTRY" in lowerer
    assert "build_strategy" not in generated
