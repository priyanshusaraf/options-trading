# Backtest Ratchet Overlay + Next-Bar-Open Fills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the platform backtester the arbiter of strategy performance: add the v4 Pine ratchet risk engine (initial ATR stop → Chandelier trail → MFE-capture floor) as a strategy-declared exit overlay and switch all fills to next-bar-open, then rerun v4 on crude + the watchlist and compare old vs new.

**Architecture:** A new pure module `app/backtest/ratchet.py` holds Wilder-ATR + a per-position `RatchetState` state machine (Pine-parity math). `simulate()` in `app/backtest/engine.py` is restructured around a one-bar `pending` action queue so every decision confirmed on bar *i* fills at bar *i+1*'s open. Strategies opt into the ratchet by declaring a `risk_model` dict on their class; `expanding_z_v4` declares the Pine defaults, everything else declares nothing and keeps flags-only exits. Cache `SCHEMA_VERSION` bumps 5→6 and the signature learns about `risk_model`.

**Tech Stack:** Python 3 / pandas / SQLAlchemy / pytest (backend only; no frontend changes).

**Spec:** `docs/superpowers/specs/2026-07-06-backtest-ratchet-overlay-design.md`

## Global Constraints

- Run everything from `backend/`; use `.venv/bin/python -m pytest` (never bare pytest).
- The live engine (`app/engine/*`) must NOT be touched — this is backtest-only.
- Pine parity is the correctness standard: source of truth is `strategies/expanding-z-impulse-v4.pine` lines 196–315.
- `trend_impulse_v3` semantics change ONLY via the fill model — it must never gain a ratchet.
- Work on branch `feat/backtest-arbiter` off `main`. Commit per task; never push.
- Exit reasons are exactly: `STRATEGY_EXIT`, `RATCHET_STOP`, `OPEN_AT_END`.
- v4 Pine default risk model (exact values): `atr_length=14, initial_risk_atr=1.25, trail_start_r=1.75, trail_atr=3.0, use_mfe_capture_floor=True, capture_start_r=1.25, capture_pct=0.35`.

---

### Task 1: `Strategy.risk_model` declaration + v4 declares Pine defaults

**Files:**
- Modify: `backend/app/strategy/registry/base.py` (class attribute + docstring)
- Modify: `backend/app/strategy/registry/expanding_z_v4.py` (declare dict)
- Test: `backend/tests/test_risk_model_declaration.py` (new)

**Interfaces:**
- Produces: `Strategy.risk_model: dict | None` (class attribute, default `None`). Later tasks read it via `getattr(strat, "risk_model", None)`.

- [ ] **Step 1: Create branch**

```bash
cd /Users/priyanshusaraf/dev/options-trading/paper-trader && git checkout -b feat/backtest-arbiter
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_risk_model_declaration.py`:

```python
"""Strategies may declare a trade-management risk model for the backtester's
ratchet overlay. v4 declares its Pine defaults; the default strategy and the
base class declare nothing (flags-only exits)."""
from app.strategy.registry import get_strategy
from app.strategy.registry.base import Strategy


def test_base_class_declares_no_risk_model():
    assert Strategy.risk_model is None


def test_default_strategy_declares_no_risk_model():
    assert get_strategy(None).risk_model is None


def test_v4_declares_pine_default_risk_model():
    assert get_strategy("expanding_z_v4").risk_model == {
        "atr_length": 14, "initial_risk_atr": 1.25,
        "trail_start_r": 1.75, "trail_atr": 3.0,
        "use_mfe_capture_floor": True,
        "capture_start_r": 1.25, "capture_pct": 0.35,
    }
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_risk_model_declaration.py -v`
Expected: FAIL — `AttributeError: type object 'Strategy' has no attribute 'risk_model'`

- [ ] **Step 4: Implement**

In `backend/app/strategy/registry/base.py`, inside `class Strategy` after `default_params: dict[str, Any] = {}` (line 31), add:

```python
    # Optional trade-management declaration for the BACKTEST ratchet overlay
    # (initial ATR stop -> Chandelier trail -> MFE-capture floor). None = the
    # strategy exits on its canonical flags only. Keys (all required if set):
    # atr_length, initial_risk_atr, trail_start_r, trail_atr,
    # use_mfe_capture_floor, capture_start_r, capture_pct.
    risk_model: dict[str, Any] | None = None
```

In `backend/app/strategy/registry/expanding_z_v4.py`, inside `class ExpandingZImpulseV4` right after `default_params = {...}` (line 75), add:

```python
    # Pine risk engine defaults (expanding-z-impulse-v4.pine inputs, lines 98-104):
    # the backtest arbiter applies these; the .pine applies them natively in TV.
    risk_model = {
        "atr_length": 14, "initial_risk_atr": 1.25,
        "trail_start_r": 1.75, "trail_atr": 3.0,
        "use_mfe_capture_floor": True,
        "capture_start_r": 1.25, "capture_pct": 0.35,
    }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_risk_model_declaration.py -v`
Expected: 3 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/strategy/registry/base.py backend/app/strategy/registry/expanding_z_v4.py backend/tests/test_risk_model_declaration.py
git commit -m "feat(backtest): strategies may declare a ratchet risk_model; v4 declares Pine defaults"
```

---

### Task 2: `app/backtest/ratchet.py` — Wilder ATR + RatchetState (pure math)

**Files:**
- Create: `backend/app/backtest/ratchet.py`
- Test: `backend/tests/test_ratchet_state.py` (new)

**Interfaces:**
- Produces:
  - `wilder_atr(df: pd.DataFrame, n: int) -> pd.Series` — Wilder RMA of true range over columns `high/low/close` (same math as `expanding_z_v4._atr`).
  - `RatchetState(direction: str, fill_price: float, entry_atr: float, rm: dict)` with `.update(high, low, close, current_atr) -> None` (call once per MANAGED bar — bars after the fill bar) and `.stop_hit(close: float) -> bool` (close-confirmed) and `.stop: float`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_ratchet_state.py`:

```python
"""Pine-parity ratchet math (expanding-z-impulse-v4.pine lines 253-315):
initial ATR stop -> Chandelier after trail_start_r -> MFE floor after
capture_start_r; the stop only ever ratchets in the trade's favour and stop
hits are CLOSE-confirmed (a wick through the stop does not exit)."""
import pandas as pd
import pytest

from app.backtest.ratchet import RatchetState, wilder_atr

RM = {"atr_length": 3, "initial_risk_atr": 1.0, "trail_start_r": 2.0,
      "trail_atr": 1.0, "use_mfe_capture_floor": True,
      "capture_start_r": 1.0, "capture_pct": 0.5}


def test_initial_stop_and_inactive_layers_below_thresholds():
    s = RatchetState("LONG", 100.0, 2.0, RM)          # risk_pts = 1.0*2 = 2
    assert s.stop == pytest.approx(98.0)               # fill - risk_pts
    s.update(high=101.0, low=99.0, close=100.5, current_atr=2.0)  # MFE 1pt = 0.5R
    assert s.stop == pytest.approx(98.0)               # nothing active yet
    assert not s.stop_hit(98.01) and s.stop_hit(98.0)


def test_capture_floor_then_chandelier_activate_and_ratchet():
    s = RatchetState("LONG", 100.0, 2.0, RM)
    s.update(102.5, 100.0, 102.0, 2.0)   # MFE 2.5 = 1.25R >= capture_start_r
    # floor = fill + 0.5*2.5 = 101.25 > initial 98
    assert s.stop == pytest.approx(101.25)
    s.update(104.0, 101.5, 103.5, 2.0)   # MFE 4 = 2R >= trail_start_r
    # chandelier = 104 - 1.0*2 = 102 ; floor = 100 + 0.5*4 = 102
    assert s.stop == pytest.approx(102.0)


def test_stop_never_loosens():
    s = RatchetState("LONG", 100.0, 2.0, RM)
    s.update(104.0, 101.5, 103.5, 2.0)
    locked = s.stop
    s.update(103.0, 101.0, 101.5, 8.0)   # huge ATR -> looser chandelier candidate
    assert s.stop == pytest.approx(locked)  # ratchet only, never down


def test_close_confirmed_wick_through_stop_survives():
    s = RatchetState("LONG", 100.0, 2.0, RM)
    s.update(104.0, 101.5, 103.5, 2.0)          # stop ratchets to 102
    s.update(103.0, 95.0, 102.5, 2.0)           # LOW pierces 102, close doesn't
    assert not s.stop_hit(102.5)
    assert s.stop_hit(101.9)


def test_short_mirror():
    s = RatchetState("SHORT", 100.0, 2.0, RM)   # risk_pts 2, stop 102
    assert s.stop == pytest.approx(102.0)
    s.update(98.5, 96.0, 96.5, 2.0)             # MFE 4pts = 2R (low-water 96)
    # chandelier = 96 + 2 = 98 ; floor = 100 - 0.5*4 = 98
    assert s.stop == pytest.approx(98.0)
    assert not s.stop_hit(97.9) and s.stop_hit(98.0)


def test_capture_floor_can_be_disabled():
    rm = dict(RM, use_mfe_capture_floor=False)
    s = RatchetState("LONG", 100.0, 2.0, rm)
    s.update(102.5, 100.0, 102.0, 2.0)          # 1.25R: floor would fire, trail not yet
    assert s.stop == pytest.approx(98.0)


def test_nonfinite_current_atr_skips_chandelier_candidate():
    s = RatchetState("LONG", 100.0, 2.0, RM)
    s.update(104.0, 101.5, 103.5, float("nan"))  # trail active but ATR NaN
    # floor = 100 + 0.5*4 = 102 still applies; no NaN poisoning
    assert s.stop == pytest.approx(102.0)


def test_wilder_atr_matches_v4_port_atr():
    df = pd.DataFrame({"high": [10, 11, 12, 11, 13, 12, 14],
                       "low": [9, 10, 10, 10, 11, 11, 12],
                       "close": [9.5, 10.5, 11, 10.5, 12.5, 11.5, 13.0]})
    from app.strategy.registry.expanding_z_v4 import _atr
    expected = _atr(df["high"], df["low"], df["close"], 3)
    got = wilder_atr(df, 3)
    pd.testing.assert_series_equal(got, expected, check_names=False)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ratchet_state.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.backtest.ratchet'`

- [ ] **Step 3: Implement `backend/app/backtest/ratchet.py`**

```python
"""Pine-parity ratchet trade management for the backtester.

Port of the v4 Pine risk engine (strategies/expanding-z-impulse-v4.pine lines
196-315): initial ATR stop -> Chandelier trail once MFE >= trail_start_r ->
MFE-capture floor once MFE >= capture_start_r. The stop only ever moves in the
trade's favour, and hits are CLOSE-confirmed (Pine checks `close <= stop`, never
intrabar). Risk units are frozen at the FILL bar (pine:212 `longEntryATR := atr`);
the Chandelier uses the CURRENT bar's ATR (pine:274).

The caller (engine.simulate) drives one update() per MANAGED bar — bars strictly
after the fill bar (Pine's canManage: no entry-bar MFE credit, pine:233-241).
"""
from __future__ import annotations

import math

import pandas as pd


def wilder_atr(df: pd.DataFrame, n: int) -> pd.Series:
    """Wilder's ATR (RMA of true range) — identical math to the v4 port's _atr."""
    prev_close = df["close"].shift(1)
    tr = pd.concat([(df["high"] - df["low"]).abs(),
                    (df["high"] - prev_close).abs(),
                    (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


class RatchetState:
    """Stop state for ONE open position under a declared risk_model."""

    def __init__(self, direction: str, fill_price: float, entry_atr: float,
                 rm: dict) -> None:
        self.d = 1.0 if direction == "LONG" else -1.0
        self.fill = float(fill_price)
        self.risk_pts = float(rm["initial_risk_atr"]) * float(entry_atr)
        self.hw = self.fill                      # high-water (low-water for shorts)
        self.rm = rm
        self.stop = self.fill - self.d * self.risk_pts   # pine:215/226

    def update(self, high: float, low: float, close: float,
               current_atr: float) -> None:
        ext = high if self.d > 0 else low
        self.hw = max(self.hw, ext) if self.d > 0 else min(self.hw, ext)  # pine:238/241
        mfe_pts = (self.hw - self.fill) * self.d
        mfe_r = mfe_pts / self.risk_pts if self.risk_pts > 0 else 0.0     # pine:268
        cands = [self.fill - self.d * self.risk_pts]                       # pine:280
        if mfe_r >= float(self.rm["trail_start_r"]) and math.isfinite(current_atr):
            cands.append(self.hw - self.d * float(self.rm["trail_atr"]) * current_atr)  # pine:274/283
        if self.rm.get("use_mfe_capture_floor", True) and \
                mfe_r >= float(self.rm["capture_start_r"]):
            cands.append(self.fill + self.d * float(self.rm["capture_pct"]) * mfe_pts)  # pine:277/289
        best = max(cands) if self.d > 0 else min(cands)
        # stop only ratchets in the trade's favour (pine:295-300)
        self.stop = max(self.stop, best) if self.d > 0 else min(self.stop, best)

    def stop_hit(self, close: float) -> bool:
        """Close-confirmed (pine:305-315)."""
        return close <= self.stop if self.d > 0 else close >= self.stop
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_ratchet_state.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/backtest/ratchet.py backend/tests/test_ratchet_state.py
git commit -m "feat(backtest): Pine-parity ratchet state machine (ATR stop -> chandelier -> MFE floor)"
```

---

### Task 3: next-bar-open fill model in `simulate()` (all strategies)

**Files:**
- Modify: `backend/app/backtest/engine.py:176-219` (the trade loop) and module docstring lines 1-9
- Modify: `backend/app/backtest/metrics.py:26` (reason comment)
- Test: `backend/tests/test_backtest_fills.py` (new); fix any broken assertions in `backend/tests/test_backtest.py`

**Interfaces:**
- Consumes: nothing new (Task 4 adds the ratchet on top of this loop).
- Produces: `simulate()` fills entries/exits at next-bar open. The loop keeps local variables `pos` (dict) and `pending` (`("ENTER", direction) | ("EXIT", reason) | None`) — Task 4 slots the ratchet into this exact structure.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_backtest_fills.py`:

```python
"""Fill model: a signal confirmed on bar i fills at bar i+1's OPEN (Pine
process_orders_on_close=false parity). Applies to entries, strategy-flag exits,
and (Task 4) ratchet stops. A last-bar signal goes unfilled; a still-open
position closes OPEN_AT_END at the last close."""
import datetime as dt
from dataclasses import dataclass

import pytest

from app.backtest.engine import simulate
from app.strategy.registry.base import Strategy


@dataclass
class C:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float


def mk_candles(bars):
    """bars = list of (open, high, low, close); 15-minute spacing."""
    t0 = dt.datetime(2026, 7, 1, 9, 15)
    return [C(t0 + dt.timedelta(minutes=15 * i), *b) for i, b in enumerate(bars)]


class Inst:
    segment = "NFO"
    lot_size = 10


class StubFlags(Strategy):
    """Entry/exit flags at fixed row positions; no indicator columns."""
    key = "stub_flags"
    display_name = "Stub"
    default_params = {}

    def __init__(self, entries=(), exits=(), shorts=False):
        self._e, self._x, self._s = set(entries), set(exits), shorts

    def compute(self, df, **p):
        out = df.copy()
        n = len(out)
        out["longEntry"] = [i in self._e and not self._s for i in range(n)]
        out["shortEntry"] = [i in self._e and self._s for i in range(n)]
        out["longExit"] = [i in self._x for i in range(n)]
        out["shortExit"] = [i in self._x for i in range(n)]
        return out


FAST = {"ema_length": 1, "slope_lookback": 0}   # warmup = 1+0+2 = 3 bars

BARS = [(100, 101, 99, 100.5)] * 12             # flat tape; opens distinct below


def test_entry_and_exit_fill_at_next_bar_open():
    bars = list(BARS)
    bars[5] = (105.0, 106, 104, 105.5)   # bar 5 open — entry fill expected here
    bars[8] = (108.0, 109, 107, 108.5)   # bar 8 open — exit fill expected here
    candles = mk_candles(bars)
    strat = StubFlags(entries={4}, exits={7})
    trades, m = simulate(candles, Inst(), "15minute", strategy=strat, params=FAST)
    assert len(trades) == 1
    t = trades[0]
    assert t.entry_price == pytest.approx(105.0)      # bar 5 OPEN, not bar 4 close
    assert t.exit_price == pytest.approx(108.0)       # bar 8 OPEN, not bar 7 close
    assert t.reason == "STRATEGY_EXIT"
    assert t.bars_held == 3                            # fill bar 5 -> fill bar 8


def test_last_bar_entry_signal_goes_unfilled():
    strat = StubFlags(entries={11})
    trades, m = simulate(mk_candles(list(BARS)), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert trades == []


def test_last_bar_exit_flag_becomes_open_at_end_at_last_close():
    strat = StubFlags(entries={4}, exits={11})
    trades, m = simulate(mk_candles(list(BARS)), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert len(trades) == 1
    assert trades[0].reason == "OPEN_AT_END"
    assert trades[0].exit_price == pytest.approx(100.5)   # LAST CLOSE


def test_exit_flag_on_fill_bar_is_ignored_until_next_bar():
    # exit flag raised on the fill bar itself (bar 5) must NOT exit that bar —
    # management starts the bar AFTER the fill (Pine canManage). The flag is
    # still true on bar 6 here, so the exit confirms on 6 and fills on 7's open.
    bars = list(BARS)
    bars[7] = (103.0, 104, 102, 103.5)
    candles = mk_candles(bars)
    strat = StubFlags(entries={4}, exits={5, 6})
    trades, m = simulate(candles, Inst(), "15minute", strategy=strat, params=FAST)
    assert len(trades) == 1
    assert trades[0].exit_price == pytest.approx(103.0)   # bar 7 open
    assert trades[0].bars_held == 2


def test_short_side_fills_mirror():
    bars = list(BARS)
    bars[5] = (95.0, 96, 94, 95.5)
    candles = mk_candles(bars)
    strat = StubFlags(entries={4}, exits={8}, shorts=True)
    trades, m = simulate(candles, Inst(), "15minute", strategy=strat, params=FAST)
    assert len(trades) == 1 and trades[0].direction == "SHORT"
    assert trades[0].entry_price == pytest.approx(95.0)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_backtest_fills.py -v`
Expected: FAIL — entry/exit prices equal signal-bar closes (current behaviour), e.g. `assert 100.5 == 105.0`.

- [ ] **Step 3: Restructure the `simulate()` loop**

In `backend/app/backtest/engine.py` replace lines 176–213 (from `trades: list[BTTrade] = []` through the `OPEN_AT_END` block) with:

```python
    trades: list[BTTrade] = []
    pos = None      # dict: direction, entry_price, entry_time, entry_idx, qty, …, mae
    pending = None  # ("ENTER", "LONG"|"SHORT") | ("EXIT", reason) — fills next bar OPEN

    rows = sig.to_dict("records")
    for i, r in enumerate(rows):
        t = ist_epoch(r["date"])   # IST wall-clock -> true instant (no +5:30 shift)
        open_px = float(r["open"])
        close = float(r["close"])

        # 1) execute the PREVIOUS bar's confirmed decision at THIS bar's open
        #    (Pine parity: process_orders_on_close=false — no same-bar fills).
        if pending is not None:
            kind, arg = pending
            pending = None
            if kind == "ENTER" and pos is None:
                qty, notional, lots = _position(inst, open_px, capital)
                if qty > 0:
                    pos = {"direction": arg, "entry_price": open_px,
                           "entry_time": t, "entry_idx": i, "qty": qty,
                           "notional": notional, "lots": lots,
                           "mae_pct": 0.0}
            elif kind == "EXIT" and pos is not None:
                trades.append(_close(pos, open_px, t, i, seg, arg))
                pos = None

        if pos is not None:
            # MAE includes the fill bar (the position lives through it) …
            _update_mae(pos, r)
            # … but exit DECISIONS start the bar AFTER the fill (Pine canManage:
            # no same-bar management, pine:233-234).
            if i > pos["entry_idx"]:
                d = pos["direction"]
                if (d == "LONG" and bool(r["longExit"])) or \
                        (d == "SHORT" and bool(r["shortExit"])):
                    pending = ("EXIT", "STRATEGY_EXIT")
        elif r["longEntry"] or r["shortEntry"]:
            pending = ("ENTER", "LONG" if r["longEntry"] else "SHORT")

    # close any still-open position at the LAST AVAILABLE CANDLE (end of data,
    # not end of day) — includes a decision confirmed on the final bar, which
    # has no next open to fill at.
    if pos is not None:
        last = rows[-1]
        trades.append(_close(pos, float(last["close"]),
                             ist_epoch(last["date"]),
                             len(rows) - 1, seg, "OPEN_AT_END"))
```

- [ ] **Step 4: Update the module docstring**

Replace `engine.py` lines 6–9 (`Entries fire on the strategy's … don't map to the underlying).`) with:

```python
Entries fire on the strategy's longEntry/shortEntry flags; exits fire on its own
longExit/shortExit flags plus — when the strategy DECLARES a risk_model — the
Pine-parity ratchet overlay (initial ATR stop -> Chandelier trail -> MFE-capture
floor, close-confirmed; see app/backtest/ratchet.py). Every decision confirmed on
bar i fills at bar i+1's OPEN (Pine process_orders_on_close=false parity); the
option-premium stop/target of the LIVE engine is not modelled here (it doesn't
map to the underlying).
```

- [ ] **Step 5: Update the `BTTrade.reason` comment**

In `backend/app/backtest/metrics.py:26` change the comment to:

```python
    reason: str             # "STRATEGY_EXIT" | "RATCHET_STOP" | "OPEN_AT_END"
```

- [ ] **Step 6: Run the new tests, then the whole backtest test file**

Run: `cd backend && .venv/bin/python -m pytest tests/test_backtest_fills.py tests/test_backtest.py -v`
Expected: `test_backtest_fills.py` all PASS. In `tests/test_backtest.py`, metric-arithmetic tests (pure `BTTrade` fixtures) still PASS; any `simulate()`-based assertion that encodes signal-close fills or exact trade counts may FAIL.

- [ ] **Step 7: Fix broken assertions in `tests/test_backtest.py` (semantics, not weakening)**

Update failing assertions per the new model only: fills = next-bar open (so entry/exit price assertions move one bar), and a signal on the final bar no longer produces a trade (counts can drop by one). Do NOT loosen tolerance or delete assertions — restate the expected values under next-open fills. Then:

Run: `cd backend && .venv/bin/python -m pytest tests/test_backtest.py tests/test_backtest_fills.py -v`
Expected: ALL PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/backtest/engine.py backend/app/backtest/metrics.py backend/tests/test_backtest_fills.py backend/tests/test_backtest.py
git commit -m "feat(backtest): next-bar-open fills for all strategies (Pine parity)"
```

---

### Task 4: ratchet overlay integration in `simulate()`

**Files:**
- Modify: `backend/app/backtest/engine.py` (imports; ATR column; ratchet in the loop)
- Test: `backend/tests/test_backtest_ratchet_overlay.py` (new)

**Interfaces:**
- Consumes: `RatchetState`, `wilder_atr` from Task 2; the `pending`/`pos` loop from Task 3; `Strategy.risk_model` from Task 1.
- Produces: trades with `reason == "RATCHET_STOP"`; `_ratchet_atr` internal column.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_backtest_ratchet_overlay.py`:

```python
"""simulate() applies the ratchet overlay iff the strategy declares risk_model:
RATCHET_STOP exits fire close-confirmed and fill next-bar open; ratchet label
wins a same-bar tie with a strategy flag; zero/NaN entry ATR falls back to
flags-only for that trade; v3 (no declaration) never produces RATCHET_STOP."""
import datetime as dt
from dataclasses import dataclass

import pytest

from app.backtest.engine import simulate
from app.strategy.registry.base import Strategy


@dataclass
class C:
    ts: dt.datetime
    open: float
    high: float
    low: float
    close: float


def mk_candles(bars):
    t0 = dt.datetime(2026, 7, 1, 9, 15)
    return [C(t0 + dt.timedelta(minutes=15 * i), *b) for i, b in enumerate(bars)]


class Inst:
    segment = "NFO"
    lot_size = 10


class StubRatchet(Strategy):
    key = "stub_ratchet"
    display_name = "StubR"
    default_params = {}
    risk_model = {"atr_length": 3, "initial_risk_atr": 1.0, "trail_start_r": 99.0,
                  "trail_atr": 1.0, "use_mfe_capture_floor": False,
                  "capture_start_r": 99.0, "capture_pct": 0.5}
    # trail/floor thresholds set unreachably high -> only the INITIAL stop acts,
    # which makes expected exit bars easy to hand-compute.

    def __init__(self, entries=(), exits=()):
        self._e, self._x = set(entries), set(exits)

    def compute(self, df, **p):
        out = df.copy()
        n = len(out)
        out["longEntry"] = [i in self._e for i in range(n)]
        out["shortEntry"] = [False] * n
        out["longExit"] = [i in self._x for i in range(n)]
        out["shortExit"] = [False] * n
        return out


FAST = {"ema_length": 1, "slope_lookback": 0}

# Tape: TR is 2.0 on every bar (high-low=2, no gaps) -> Wilder ATR == 2.0 exactly.
# entry flag bar 4 -> fill bar 5 open=100 -> risk_pts = 1.0*2 = 2 -> stop 98.
FLAT = (100.0, 101.0, 99.0, 100.0)


def test_ratchet_stop_fires_close_confirmed_and_fills_next_open():
    bars = [FLAT] * 12
    bars[7] = (100.0, 100.5, 98.5, 97.9)   # close 97.9 <= stop 98 -> confirmed bar 7
    bars[8] = (97.0, 98.0, 96.0, 97.5)     # exit fills at bar 8 OPEN = 97.0
    strat = StubRatchet(entries={4})
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert len(trades) == 1
    assert trades[0].reason == "RATCHET_STOP"
    assert trades[0].entry_price == pytest.approx(100.0)
    assert trades[0].exit_price == pytest.approx(97.0)


def test_wick_through_stop_does_not_exit():
    bars = [FLAT] * 12
    bars[7] = (100.0, 100.5, 96.0, 100.0)  # low 96 pierces 98; close 100 survives
    strat = StubRatchet(entries={4})
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert len(trades) == 1 and trades[0].reason == "OPEN_AT_END"


def test_same_bar_tie_labels_ratchet_stop():
    bars = [FLAT] * 12
    bars[7] = (100.0, 100.5, 98.5, 97.9)   # stop confirms bar 7 …
    strat = StubRatchet(entries={4}, exits={7})   # … and flag also fires bar 7
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert trades[0].reason == "RATCHET_STOP"     # protective label wins the tie


def test_zero_atr_disables_ratchet_for_that_trade():
    # dead-flat tape: TR == 0 -> ATR == 0 -> ratchet disabled -> flags-only exit
    bars = [(100.0, 100.0, 100.0, 100.0)] * 12
    strat = StubRatchet(entries={4}, exits={8})
    trades, m = simulate(mk_candles(bars), Inst(), "15minute",
                         strategy=strat, params=FAST)
    assert len(trades) == 1
    assert trades[0].reason == "STRATEGY_EXIT"    # not RATCHET_STOP, no crash


def test_undeclared_strategy_never_ratchets():
    from app.strategy.registry import get_strategy
    from app.providers.mock import MockProvider
    from app.core.instruments import get_instrument
    prov = MockProvider()
    inst = get_instrument("NIFTY")
    candles = prov.get_candles(inst, "15minute", 90)
    trades, m = simulate(candles, inst, "15minute")   # default v3, no declaration
    assert all(t.reason in ("STRATEGY_EXIT", "OPEN_AT_END") for t in trades)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_backtest_ratchet_overlay.py -v`
Expected: first four tests FAIL (no `RATCHET_STOP` ever produced; positions run to `OPEN_AT_END`/`STRATEGY_EXIT`); last test PASSES already.

- [ ] **Step 3: Wire the ratchet into `simulate()`**

In `backend/app/backtest/engine.py`:

a. Add to imports (after `from app.backtest.metrics import …`):

```python
from app.backtest.ratchet import RatchetState, wilder_atr
```

b. Immediately after `sig = strat.signals(_candles_to_df(candles), **params)` (before the dropna), add:

```python
    rm = getattr(strat, "risk_model", None)
    if rm:
        # computed on the FULL frame so warmup trimming can't shift ATR values
        sig["_ratchet_atr"] = wilder_atr(sig, int(rm["atr_length"]))
```

c. In the loop from Task 3, extend the ENTER execution branch — after the `pos = {...}` assignment add:

```python
                    ratchet = None
                    if rm:
                        entry_atr = r.get("_ratchet_atr")
                        if entry_atr is not None and math.isfinite(entry_atr) \
                                and entry_atr > 0:
                            # risk units freeze at the FILL bar (pine:212)
                            ratchet = RatchetState(arg, open_px,
                                                   float(entry_atr), rm)
```

initialise `ratchet = None` next to `pos = None` before the loop, and set `ratchet = None` in the EXIT execution branch (next to `pos = None`).

d. In the managed-bar block (`if i > pos["entry_idx"]:`), insert the ratchet check BEFORE the flag check so the protective label wins ties:

```python
            if i > pos["entry_idx"]:
                d = pos["direction"]
                if ratchet is not None:
                    ratchet.update(float(r["high"]), float(r["low"]), close,
                                   float(r["_ratchet_atr"]))
                    if ratchet.stop_hit(close):
                        pending = ("EXIT", "RATCHET_STOP")
                if pending is None and (
                        (d == "LONG" and bool(r["longExit"])) or
                        (d == "SHORT" and bool(r["shortExit"]))):
                    pending = ("EXIT", "STRATEGY_EXIT")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_backtest_ratchet_overlay.py tests/test_backtest_fills.py tests/test_backtest.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/backtest/engine.py backend/tests/test_backtest_ratchet_overlay.py
git commit -m "feat(backtest): strategy-declared ratchet exit overlay (RATCHET_STOP)"
```

---

### Task 5: cache `SCHEMA_VERSION` 6 + `risk_model` in the signature

**Files:**
- Modify: `backend/app/backtest/cache.py:16-51`
- Test: `backend/tests/test_backtest_cache_risk_model.py` (new); existing cache tests (find via `grep -rl params_signature backend/tests/`) may pin `SCHEMA_VERSION` — update them.

**Interfaces:**
- Consumes: `Strategy.risk_model` (Task 1).
- Produces: `params_signature()` folding `risk_model` into non-default-strategy signatures; `SCHEMA_VERSION == 6`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_backtest_cache_risk_model.py`:

```python
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


def test_schema_version_is_6():
    assert SCHEMA_VERSION == 6


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_backtest_cache_risk_model.py -v`
Expected: FAIL — `SCHEMA_VERSION == 5`, and the two risk_model variants hash identically.

- [ ] **Step 3: Implement in `backend/app/backtest/cache.py`**

Append to the version-history comment block (after the v5 lines) and bump:

```python
# v6: fills moved to next-bar-open for ALL strategies (Pine parity) and a
#     strategy's declared risk_model (ratchet overlay) joined the signature.
#     Both change trade outcomes for every cell -> force a clean recompute.
SCHEMA_VERSION = 6
```

In `params_signature`, replace the non-default branch (the `else:` at lines 46-50) with:

```python
    else:
        ps = ",".join(f"{k}={strategy.default_params[k]}"
                      for k in sorted(strategy.default_params))
        rm = getattr(strategy, "risk_model", None)
        rs = ("none" if not rm else
              ",".join(f"{k}={rm[k]}" for k in sorted(rm)))
        raw = (f"v{SCHEMA_VERSION}|cap={capital}|win={window}"
               f"|strat={strategy.key}|params={ps}|risk={rs}")
```

Also update the docstring's back-compat paragraph (lines 39-41) to:

```python
    Back-compat note: through v5 the default strategy reproduced its historical
    signature so the owner's v3 cache stayed valid; v6's fill-model change makes
    every pre-v6 cell stale BY DESIGN, so that guarantee is intentionally reset
    at v6 (the format is kept stable from here so future v3 caches survive
    non-breaking bumps).
```

- [ ] **Step 4: Run tests + any existing cache tests**

Run: `cd backend && .venv/bin/python -m pytest tests/test_backtest_cache_risk_model.py -v && grep -rl params_signature tests/ | xargs .venv/bin/python -m pytest -v`
Expected: new tests PASS; if an existing test pins `SCHEMA_VERSION == 5` or a literal hash, update it to the v6 value (same rule as Task 3 Step 7: restate expectations, don't weaken).

- [ ] **Step 5: Commit**

```bash
git add backend/app/backtest/cache.py backend/tests/test_backtest_cache_risk_model.py
git commit -m "feat(backtest): schema v6 — next-open fills + risk_model in cache signature"
```

---

### Task 6: full-suite verification

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `cd backend && .venv/bin/python -m pytest`
Expected: ALL PASS (~530+ tests). Any failure traced to fill-model/reason/schema assumptions gets the Task 3 Step 7 treatment (restate under new semantics; never weaken).

- [ ] **Step 2: Headless proofs**

Run: `cd backend && .venv/bin/python scripts/backtest_smoke.py && .venv/bin/python scripts/dryrun.py 700`
Expected: smoke's net-of-charges invariant holds under next-open fills; dryrun's ledger invariant `cash == initial + realized − Σ(open entry_cost)` holds to the paisa (live engine untouched).

- [ ] **Step 3: Commit any test fixes**

```bash
git add -A backend/tests && git commit -m "test: restate fill-model expectations for v6 backtest semantics" || echo "nothing to fix"
```

---

### Task 7: arbiter rerun — v4 (+v3 reference) on CRUDEOILM + watchlist, old-vs-new table

**Files:** none in the repo (operational step; produces a chat report)

**Interfaces:**
- Consumes: the running backend (`:8090`, PT_PROVIDER=kite, fresh Kite token), `POST /api/backtest/sweep` (`backend/app/api/backtest_routes.py:67`, body per `SweepRequest:56-64`).

- [ ] **Step 1: Preconditions (needs the owner)**

The backend must be RESTARTED on this branch (the long-running stale process predates all of this) and Kite re-authed via **Connect Kite** (token expires ~06:00 IST). Confirm both with the owner before proceeding. Verify: `curl -s localhost:8090/api/backtest/runs | head -c 200` responds.

- [ ] **Step 2: Collect the shortlist**

```bash
sqlite3 -readonly backend/paper_trader.db "SELECT key FROM universe_instruments WHERE active=1;"
```

- [ ] **Step 3: Launch the sweep (both strategies, three intervals)**

```bash
curl -s -X POST localhost:8090/api/backtest/sweep -H 'Content-Type: application/json' -d '{
  "instruments": [<keys from Step 2, always including "CRUDEOILM">],
  "intervals": ["15minute", "30minute", "60minute"],
  "strategies": ["expanding_z_v4", "trend_impulse_v3"]
}'
```

Poll `curl -s localhost:8090/api/backtest/status` until complete (runs in a background thread; Kite calls are throttled — expect minutes, not seconds).

- [ ] **Step 4: Old-vs-new comparison**

```bash
sqlite3 -readonly backend/paper_trader.db "
SELECT n.strategy_key, n.instrument_key, n.interval,
       o.trades AS old_n, ROUND(o.profit_factor,2) AS old_pf, ROUND(o.return_pct,1) AS old_ret,
       n.trades AS new_n, ROUND(n.profit_factor,2) AS new_pf, ROUND(n.return_pct,1) AS new_ret,
       (SELECT COUNT(*) FROM json_each(n.trades_json) WHERE json_extract(value,'$.reason')='RATCHET_STOP') AS ratchet_exits
FROM backtest_results n
LEFT JOIN backtest_results o
  ON o.instrument_key=n.instrument_key AND o.interval=n.interval
 AND o.strategy_key=n.strategy_key AND o.schema_version<6
 AND o.id=(SELECT MAX(id) FROM backtest_results WHERE instrument_key=n.instrument_key
           AND interval=n.interval AND strategy_key=n.strategy_key AND schema_version<6)
WHERE n.schema_version=6
ORDER BY n.strategy_key, n.instrument_key, n.interval;"
```

- [ ] **Step 5: Report**

Present the table in chat with the verdict framing: which cells flipped sign under the ratchet, whether crude's TV riches survive real charges + honest fills, and RATCHET_STOP share of exits (a low share means the ratchet rarely binds — the edge is in the entries; a high share means the exits are the strategy).

---

## Self-review (done at write time)

- **Spec coverage:** contract → Task 1; fill model → Task 3; ratchet semantics incl. fill-bar ATR freeze, no entry-bar MFE credit, close-confirmed, `RATCHET_STOP`, tie precedence → Tasks 2+4; NaN/zero-ATR fallback → Task 2 (`test_nonfinite…`) + Task 4 (`test_zero_atr…`); cache v6 + risk hash → Task 5; tests-stay-green + smoke/dryrun → Task 6; deliverable comparison → Task 7. Known non-parities need no code.
- **Placeholders:** none — every code step shows the code; the two "fix what breaks" steps (3.7, 5.4, 6.1) state the exact rule to apply, not "handle appropriately".
- **Type consistency:** `RatchetState(direction, fill_price, entry_atr, rm)` and `.update(high, low, close, current_atr)` / `.stop_hit(close)` match between Task 2 (definition), Task 4 (call sites), and tests. `risk_model` key names identical across Tasks 1, 2, 4, 5.
