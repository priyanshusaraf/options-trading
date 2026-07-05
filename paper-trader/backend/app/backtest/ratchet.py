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
