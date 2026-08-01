"""`latest_state` must be byte-identical to `to_payload(...)["latest"]`.

The live scan called `to_payload` and kept only `["latest"]`, discarding the
candle/EMA/z-score/marker arrays it walks every bar to build — on every signal
tick, for every instrument. Profiling put it at 76% of a representative test's
runtime; on the box it is thousands of dicts built and thrown away every 2.5
seconds, on a 1 GB droplet that has OOM'd twice.

This is a hot path that decides trades, so the ONLY acceptable version of this
change is one where the engine's view is provably unchanged. `to_payload` now
delegates to `latest_state`, which makes divergence structurally impossible —
and these tests pin it anyway, because "structurally impossible" has been wrong
before.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.strategy.signals import latest_state, to_payload


def _frame(n=300, seed=0):
    from app.strategy.registry import get_strategy
    rng = np.random.default_rng(seed)
    close = pd.Series(100 + np.cumsum(rng.normal(0, 1, n)))
    df = pd.DataFrame({
        "date": pd.date_range("2026-08-03 09:15", periods=n, freq="15min"),
        "open": close, "high": close + 1, "low": close - 1, "close": close,
    })
    return get_strategy(None).signals(df)


@pytest.mark.parametrize("seed", [0, 1, 2, 3, 4])
def test_identical_to_the_payloads_latest(seed):
    """The whole contract. Any difference here is a change to what the engine
    believes, which is a change to what it trades."""
    sig = _frame(seed=seed)
    assert latest_state(sig, entry_z=1.0) == to_payload(sig, entry_z=1.0)["latest"]


def test_identical_on_a_short_frame():
    """z_prev reads the second-to-last row; a 1-row frame must not crash or
    silently differ."""
    sig = _frame(n=60).tail(1)
    assert latest_state(sig) == to_payload(sig)["latest"]


def test_both_return_none_on_an_empty_frame():
    empty = _frame(n=60).iloc[0:0]
    assert latest_state(empty) is None
    assert to_payload(empty)["latest"] is None


def test_it_does_not_build_the_chart_arrays():
    """The point of the change. If this ever starts walking every bar again the
    saving is gone and nobody would notice from behaviour alone."""
    import ast
    import inspect
    # Strip the docstring before checking: it legitimately mentions the candle
    # and marker arrays while explaining why it does NOT build them, and an
    # earlier version of this test failed on its own prose.
    tree = ast.parse(inspect.getsource(latest_state).lstrip())
    fn = tree.body[0]
    body = ast.unparse(ast.Module(body=fn.body[1:], type_ignores=[]))
    assert "iterrows" not in body, "latest_state walks every bar again"
    assert "candles" not in body


def test_the_engine_uses_the_cheap_path():
    import inspect
    from app.engine.runner import EngineRunner
    src = inspect.getsource(EngineRunner.scan_signals)
    assert "latest_state(" in src
    assert 'to_payload(sig' not in src, "the scan still builds the discarded payload"


def test_to_payload_still_serves_the_chart():
    """The expensive path still exists — the chart genuinely needs those arrays."""
    p = to_payload(_frame(), entry_z=1.0)
    assert p["candles"] and p["ema"] and p["zscore"]
    assert p["latest"] is not None
