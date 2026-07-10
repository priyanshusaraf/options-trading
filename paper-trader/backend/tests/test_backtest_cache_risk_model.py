"""v6 cache: fill model changed for every strategy (forced recompute) and a
declared risk_model is part of a strategy's signature — changing a ratchet
knob can never silently reuse stale cells."""
from types import SimpleNamespace

from app.backtest.cache import SCHEMA_VERSION, params_signature

RM = {"atr_length": 14, "initial_risk_atr": 1.25, "trail_start_r": 1.75,
      "trail_atr": 3.0, "use_mfe_capture_floor": True,
      "capture_start_r": 1.25, "capture_pct": 0.35}


def _strat(rm):
    return SimpleNamespace(key="expanding_z_v4",
                           default_params={"ema_length": 50}, risk_model=rm)


def test_schema_version_is_7():
    # bumped for the synthetic-premium backtest (audit C6) — see cache.py's v7 note
    assert SCHEMA_VERSION == 7


def test_risk_model_changes_signature():
    a = params_signature(50_000, window="", strategy=_strat(RM))
    b = params_signature(50_000, window="", strategy=_strat(dict(RM, trail_atr=4.0)))
    c = params_signature(50_000, window="", strategy=_strat(None))
    assert a != b and a != c and b != c


def test_default_strategy_signature_still_stable_shape():
    # v3/None path must not blow up and must differ from a v4 signature
    d = params_signature(50_000, window="90d")
    v4 = params_signature(50_000, window="90d", strategy=_strat(RM))
    assert d != v4 and len(d) == 32
