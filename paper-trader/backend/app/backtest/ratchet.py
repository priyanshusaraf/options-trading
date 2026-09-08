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


class RiskDataRefusal(ValueError):
    code = "RISK_ATR_UNAVAILABLE"


def require_risk_atr(frame: pd.DataFrame) -> None:
    entries = frame["longEntry"] | frame["shortEntry"]
    atr = frame["_ratchet_atr"]
    usable = atr.gt(0) & atr.map(math.isfinite)
    if (entries & ~usable).any():
        raise RiskDataRefusal(
            "This risk policy requires a positive ATR at entry. "
            "Use enough complete price history or change the risk policy."
        )


def wilder_atr(df: pd.DataFrame, n: int, *, seed_policy: str = "first_observation") -> pd.Series:
    """ATR with an explicit seed; the historical default remains unchanged."""
    prev_close = df["close"].shift(1)
    tr = pd.concat([(df["high"] - df["low"]).abs(),
                    (df["high"] - prev_close).abs(),
                    (df["low"] - prev_close).abs()], axis=1).max(axis=1)
    if seed_policy == "first_observation":
        return tr.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    if seed_policy != "sma":
        raise ValueError("unsupported ATR seed policy")
    return _sma_seeded_rma(tr, n)


def _sma_seeded_rma(values: pd.Series, n: int) -> pd.Series:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("ATR length must be a positive whole number")
    result = pd.Series(float("nan"), index=values.index, dtype=float)
    first = values.iloc[:n].tolist()
    if len(first) < n or not all(math.isfinite(value) for value in first):
        return result
    previous = math.fsum(first) / n
    result.iloc[n - 1] = previous
    alpha = 1.0 / n
    for index in range(n, len(values)):
        current = values.iloc[index]
        if not math.isfinite(current):
            break
        previous = alpha * current + (1.0 - alpha) * previous
        result.iloc[index] = previous
    return result


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

    @classmethod
    def restore(cls, direction: str, fill_price: float, entry_atr: float, rm: dict,
                *, hw: float, stop: float) -> "RatchetState":
        """Rebuild live ratchet state from persisted fields (H2) — risk_pts is
        re-derived deterministically from entry_atr+rm; hw/stop resume where they left
        off, so a restart continues the exact same ratchet (never re-derives the stop)."""
        rs = cls(direction, fill_price, entry_atr, rm)
        rs.hw = float(hw)
        rs.stop = float(stop)
        return rs

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
