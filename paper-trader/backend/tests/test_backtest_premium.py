"""Synthetic-premium backtest (audit C6): Black-Scholes-on-realised-vol premium
path built OFFLINE from the underlying candles, with its own stop/target/expiry
mechanics — the thing the live engine actually trades, which the spot backtest
(app/backtest/engine.py) cannot model because option history is unavailable.
"""
from __future__ import annotations

import datetime as dt
import math
from unittest.mock import patch

import pytest

from app.backtest.premium import (
    DEFAULT_PREMIUM_PARAMS,
    RISK_FREE_RATE,
    simulate_premium,
)
from app.core.market_hours import ist_epoch
from app.engine.charges import compute_charges
from app.options.pricing import bs_price
from app.providers.base import Candle
from app.strategy.registry.base import Strategy


# ── fixtures ─────────────────────────────────────────────────────────────────

class Inst:
    key = "TEST"
    segment = "NFO"
    lot_size = 10
    strike_step = 50.0
    has_options = True


class NoOptionsInst:
    key = "TESTCASH"
    segment = "NSE_EQ"
    lot_size = 1
    strike_step = 1.0
    has_options = False


class StubFlags(Strategy):
    """Entry/exit flags at fixed row positions; no indicator columns, so the
    generic warmup-trim in simulate_premium is a no-op (matches the pattern used
    by tests/test_backtest_ratchet_overlay.py's StubRatchet)."""
    key = "stub_flags_premium"
    display_name = "StubFlagsPremium"
    default_params: dict = {}
    risk_model = None

    def __init__(self, longs=(), shorts=(), long_exits=(), short_exits=()):
        self._le, self._se = set(longs), set(shorts)
        self._lx, self._sx = set(long_exits), set(short_exits)

    def compute(self, df, **p):
        out = df.copy()
        n = len(out)
        out["longEntry"] = [i in self._le for i in range(n)]
        out["shortEntry"] = [i in self._se for i in range(n)]
        out["longExit"] = [i in self._lx for i in range(n)]
        out["shortExit"] = [i in self._sx for i in range(n)]
        return out


def _daily_ohlc_candles(bars: list[tuple[float, float, float, float]]) -> list[Candle]:
    """One bar per calendar day (bar index == day index), so T_i math is exact
    whole days. bars = [(open, high, low, close), ...]."""
    t0 = dt.date(2026, 1, 1)
    out = []
    for i, (o, h, l, c) in enumerate(bars):
        d = t0 + dt.timedelta(days=i)
        out.append(Candle(ts=dt.datetime.combine(d, dt.time(9, 15)),
                          open=o, high=h, low=l, close=c, volume=1000.0))
    return out


def _daily_flat_candles(closes: list[float]) -> list[Candle]:
    return _daily_ohlc_candles([(c, c, c, c) for c in closes])


WARMUP_DAYS = 31   # >= 22 needed for sigma availability; comfortable margin
FLAT = 100.0
HALF_SPREAD = DEFAULT_PREMIUM_PARAMS["premium_spread_pct"] / 2.0


# ── theta / decay ────────────────────────────────────────────────────────────

def test_bs_price_theta_decays_at_floor_sigma():
    """Control test: for the model's OWN floor sigma (RV clamped to 0.10, ×
    default multiplier) an ATM call strictly loses value every day as T shrinks
    — the mathematical premise the theta test below relies on."""
    K = S = 100.0
    sigma = 0.10 * DEFAULT_PREMIUM_PARAMS["iv_rv_multiplier"]
    T0 = DEFAULT_PREMIUM_PARAMS["entry_dte_days"] / 365.0
    days = int(DEFAULT_PREMIUM_PARAMS["entry_dte_days"])
    prices = [bs_price(S, K, max(T0 - k / 365.0, 0.0), RISK_FREE_RATE, sigma, "c")
             for k in range(days)]
    assert all(prices[i] > prices[i + 1] for i in range(len(prices) - 1))


def test_dead_flat_spot_decays_to_a_bounded_loss():
    """A dead-flat underlying can never help a long option: the position must
    eventually close at a LOSS (STOP_LOSS or EXPIRY, never TARGET/profitable),
    and that loss can never exceed the premium paid + total charges — a long
    option's max loss is capped at 100% of premium, which the stop (35% by
    default) makes even tighter."""
    closes = [FLAT] * (WARMUP_DAYS + 25)
    candles = _daily_flat_candles(closes)
    strat = StubFlags(longs={WARMUP_DAYS - 1})
    trades, m = simulate_premium(candles, Inst(), "day", strategy=strat, params={})
    assert len(trades) == 1
    t = trades[0]
    assert t.reason in ("STOP_LOSS", "EXPIRY")
    assert t.net_pnl < 0
    assert t.net_pnl >= -(t.entry_price * t.qty + t.charges) - 1e-6


# ── convexity / direction ────────────────────────────────────────────────────

def _uptrend_candles(daily_pct: float, n_up_days: int, base: float = FLAT) -> list[Candle]:
    bars = [(base, base, base, base)] * (WARMUP_DAYS - 1)
    close = base
    up = []
    for _ in range(n_up_days):
        prev = close
        close *= (1 + daily_pct)
        up.append((prev, max(prev, close), min(prev, close), close))
    # the FILL bar (index WARMUP_DAYS-1, i.e. right after the last flat signal
    # bar) opens at `base` so the strike locks at the flat price, then closes at
    # the first up-day's level.
    fill_bar = (base, up[0][1], base, up[0][3])
    return _daily_ohlc_candles(bars + [fill_bar] + up[1:])


def test_ce_convexity_beats_underlying_on_uptrend():
    # realistic underlying price (a ~20k index) so the ATM premium is meaningful and
    # the flat per-leg charges don't swamp a small-notional option; a ~1%/day rise then
    # shows the CE's leveraged (convex) upside net of costs vs the underlying's own move.
    candles = _uptrend_candles(daily_pct=0.01, n_up_days=10, base=20000.0)
    strat = StubFlags(longs={WARMUP_DAYS - 2})
    trades, m = simulate_premium(candles, Inst(), "day", strategy=strat, params={})
    assert len(trades) == 1
    t = trades[0]
    spot_at = {ist_epoch(c.ts): c.close for c in candles}
    spot_return = spot_at[t.exit_time] / spot_at[t.entry_time] - 1.0
    assert t.return_pct > 0
    assert t.return_pct > spot_return   # leveraged upside vs. the underlying's own move


def test_pe_stops_out_on_uptrend():
    candles = _uptrend_candles(daily_pct=0.01, n_up_days=10)
    strat = StubFlags(shorts={WARMUP_DAYS - 2})
    trades, m = simulate_premium(candles, Inst(), "day", strategy=strat, params={})
    assert len(trades) == 1
    assert trades[0].reason == "STOP_LOSS"
    assert trades[0].net_pnl < 0


# ── stop arithmetic to the paisa ─────────────────────────────────────────────

def _flat_then_wick_candles(wick_low=None, wick_high=None):
    """WARMUP_DAYS-1 flat days, a signal on the last of those, a flat FILL bar
    (locks K=100), then ONE MANAGED bar with a controlled wick (the first bar
    strictly after the fill, per the pending/next-open + canManage convention)."""
    bars = [(FLAT, FLAT, FLAT, FLAT)] * (WARMUP_DAYS + 1)  # 0 .. WARMUP_DAYS (signal + fill both flat)
    lo = wick_low if wick_low is not None else FLAT
    hi = wick_high if wick_high is not None else FLAT
    bars.append((FLAT, hi, lo, FLAT))                       # index WARMUP_DAYS+1: managed bar (wick)
    return _daily_ohlc_candles(bars)


def _entry_fill(sigma_floor_multiplier=1.0):
    """The deterministic entry premium for a signal fired on the last flat day
    (K=100, T0=entry_dte_days/365, sigma at the RV floor since the tape is
    perfectly flat -> RV==0 -> clamped to IV_FLOOR)."""
    sigma = 0.10 * DEFAULT_PREMIUM_PARAMS["iv_rv_multiplier"] * sigma_floor_multiplier
    T0 = DEFAULT_PREMIUM_PARAMS["entry_dte_days"] / 365.0
    raw = bs_price(FLAT, FLAT, T0, RISK_FREE_RATE, sigma, "c")
    return raw * (1 + HALF_SPREAD)


def test_stop_loss_fires_exactly_at_stop_times_half_spread():
    candles = _flat_then_wick_candles(wick_low=70.0)
    strat = StubFlags(longs={WARMUP_DAYS - 1})
    trades, m = simulate_premium(candles, Inst(), "day", strategy=strat, params={})
    assert len(trades) == 1
    t = trades[0]
    assert t.reason == "STOP_LOSS"
    entry_fill = _entry_fill()
    expected_stop = entry_fill * (1 - DEFAULT_PREMIUM_PARAMS["stop_loss_pct"])
    expected_exit = expected_stop * (1 - HALF_SPREAD)
    assert t.entry_price == pytest.approx(entry_fill, abs=1e-6)
    assert t.exit_price == pytest.approx(expected_exit, abs=1e-6)


def test_tie_bar_both_extremes_breach_stop_wins():
    candles = _flat_then_wick_candles(wick_low=70.0, wick_high=300.0)
    strat = StubFlags(longs={WARMUP_DAYS - 1})
    trades, m = simulate_premium(candles, Inst(), "day", strategy=strat, params={})
    assert len(trades) == 1
    t = trades[0]
    assert t.reason == "STOP_LOSS"        # not TARGET, despite the high-side breach too
    entry_fill = _entry_fill()
    expected_stop = entry_fill * (1 - DEFAULT_PREMIUM_PARAMS["stop_loss_pct"])
    assert t.exit_price == pytest.approx(expected_stop * (1 - HALF_SPREAD), abs=1e-6)


# ── expiry ───────────────────────────────────────────────────────────────────

def test_expiry_forces_exit_and_never_prices_a_non_positive_T():
    """Hold well past entry_dte_days on a flat tape with a very wide stop/target
    (so EXPIRY, not STOP_LOSS/TARGET, is what actually fires) and prove bs_price
    is never called with T <= 0 along the way — the 1-calendar-day EXPIRY floor
    must force the exit before T reaches zero."""
    closes = [FLAT] * (WARMUP_DAYS + 30)
    candles = _daily_flat_candles(closes)
    strat = StubFlags(longs={WARMUP_DAYS - 1})
    seen_Ts: list[float] = []
    real_bs_price = bs_price

    def spy(S, K, T, r, sigma, flag):
        seen_Ts.append(T)
        return real_bs_price(S, K, T, r, sigma, flag)

    with patch("app.backtest.premium.bs_price", side_effect=spy):
        trades, m = simulate_premium(
            candles, Inst(), "day", strategy=strat,
            params={"stop_loss_pct": 0.999, "target_pct": 1000.0})
    assert len(trades) == 1
    assert trades[0].reason == "EXPIRY"
    assert seen_Ts, "bs_price was never called"
    assert min(seen_Ts) > 0.0


# ── charges ──────────────────────────────────────────────────────────────────

def test_charges_net_equals_gross_minus_both_legs_hand_computed():
    candles = _flat_then_wick_candles(wick_low=70.0)
    strat = StubFlags(longs={WARMUP_DAYS - 1})
    trades, m = simulate_premium(candles, Inst(), "day", strategy=strat, params={})
    assert len(trades) == 1
    t = trades[0]
    expected_charges = (compute_charges(Inst.segment, "BUY", t.entry_price, t.qty)["total"]
                        + compute_charges(Inst.segment, "SELL", t.exit_price, t.qty)["total"])
    assert t.charges == pytest.approx(expected_charges, abs=0.01)
    assert t.net_pnl == pytest.approx(t.gross_pnl - t.charges, abs=0.01)
    assert t.gross_pnl == pytest.approx((t.exit_price - t.entry_price) * t.qty, abs=1e-6)


# ── no-options cell ──────────────────────────────────────────────────────────

def test_no_options_instrument_returns_no_trades():
    candles = _daily_flat_candles([FLAT] * (WARMUP_DAYS + 5))
    strat = StubFlags(longs={WARMUP_DAYS - 1})
    trades, m = simulate_premium(candles, NoOptionsInst(), "day", strategy=strat, params={})
    assert trades == []
    assert m.trades == 0


def test_no_options_cell_sets_premium_error_via_sweep():
    from sqlalchemy import select

    from app.backtest import sweep
    from app.core import instruments as inst_registry
    from app.db.models import BacktestResult, UniverseInstrument
    from app.db.session import SessionLocal, init_db
    from app.providers.mock import MockProvider

    init_db(reset=True)
    with SessionLocal() as s:
        s.add(UniverseInstrument(
            key="NOOPT_C6", name="No Options Test", segment="NSE", spot_exchange="NSE",
            spot_symbol="NOOPT_C6", option_name="NOOPT_C6", lot_size=1, strike_step=1.0,
            priority=999, has_options=False, source="seed", on_home=False,
            active=True, mock_spot=500.0, mock_vol=0.2))
        s.commit()
    inst_registry.load_universe()
    prov = MockProvider()
    rid = sweep.start_sweep(scope="liquid", intervals=["day"], capital=50_000,
                            instruments=["NOOPT_C6"], provider=prov)
    sweep._join()
    with SessionLocal() as s:
        row = s.scalars(select(BacktestResult).where(
            BacktestResult.run_id == rid,
            BacktestResult.instrument_key == "NOOPT_C6")).first()
    assert row is not None
    assert row.premium_trades == 0
    assert row.premium_error != ""


def test_options_cell_populates_premium_metrics_via_sweep():
    from sqlalchemy import select

    from app.backtest import sweep
    from app.db.models import BacktestResult
    from app.db.session import SessionLocal, init_db
    from app.providers.mock import MockProvider

    init_db(reset=True)
    prov = MockProvider()
    rid = sweep.start_sweep(scope="liquid", intervals=["day"], capital=50_000,
                            instruments=["NIFTY"], provider=prov)
    sweep._join()
    with SessionLocal() as s:
        row = s.scalars(select(BacktestResult).where(
            BacktestResult.run_id == rid,
            BacktestResult.instrument_key == "NIFTY")).first()
    assert row is not None
    assert row.premium_error == ""
    # NIFTY has_options=True with plenty of mock daily history -> the premium
    # engine should produce a defined (if possibly zero-trade) result, never a
    # crash swallowed into an error string.
    assert row.premium_trades >= 0


# ── cache / schema (mirrors tests/test_backtest_cache_risk_model.py's style) ──

def test_schema_version_is_7():
    from app.backtest.cache import SCHEMA_VERSION
    assert SCHEMA_VERSION == 7


def test_premium_param_changes_signature():
    from app.backtest.cache import params_signature
    a = params_signature(50_000, window="")
    b = params_signature(50_000, window="", iv_rv_multiplier=1.30)
    c = params_signature(50_000, window="", premium_spread_pct=0.05)
    d = params_signature(50_000, window="", entry_dte_days=7)
    assert len({a, b, c, d}) == 4
