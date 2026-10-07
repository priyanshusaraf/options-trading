"""Session-Gap Carry — hold the MCX contract only across the hours MCX is SHUT.

Idea (self-derived from the 2019-2026 MCX-proxy research): MCX closes at
23:30/23:55 IST but COMEX/NYMEX keep trading through the US afternoon and the
Asian morning. The MCX "overnight gap" (session close -> next session open) has
carried a persistent positive drift in gold (USD gold, entry at the open of the
last session bar → next open: +3.3 bps/night 2019-23, t≈2.6; +7.7 bps 2024-26,
t≈2.6; positive in every calendar year) while gold's IN-session MCX hours were
flat-to-negative in 2021-2023 and 2026. Crude shows a similar but weaker gap
drift. The strategy therefore owns the gap, not the session.

Layers (each a param so its contribution can be measured):
  0. carry every night (bare): enter near the close, exit at the next open.
  1. trend filter: carry only when close > EMA(trend_hours) on this timeframe —
     gold's gap averaged ~+4 bps IS / ~+12 bps OOS above its 100-hour EMA vs
     ~+2 bps below it.
  2. day filter: carry only when the session so far is up by >= min_day_ret bps
     (strong closes carried better OOS; weak in-sample — off by default).
  3. direction: "long" (default; the drift is one-sided) or "trend" (short the
     gap below the EMA — tested, see the research note).
Timing: the entry flag fires on the bar `entry_bars_before_close` bars before
the session's last bar (so the engine fills at the next bar's open, inside the
session); the exit flag fires on the session's LAST bar, so the engine fills at
the NEXT session's first open. The session close comes from the exchange
schedule (MCX: 23:30 IST under US daylight time, else 23:55) — `session_close`
can pin it (IST minutes) for data sets that stop earlier.

Costs decide the contract: a round trip is ~8.8 bps of charges on GOLDPETAL
(Zerodha's 0.03% brokerage never reaches its ₹20 cap on a 1 g lot) but ~2.1 bps
on GOLDM (100 g). A few bps of nightly drift only survives the charge stack on
the larger contracts — see the research note for the per-contract results.

Regime: any regime — it is a structural (clock) effect, not a trend or a
reversion signal. It complements the intraday strategies, which are flat
overnight.
"""
from __future__ import annotations

import pandas as pd

from app.strategy.ta import atr, bar_minutes, bars_to_session_close, ema, session_key

from .base import Strategy


class SessionGapCarry(Strategy):
    key = "session_gap_carry"
    display_name = "Session-Gap Carry (MCX overnight)"
    default_params = {
        "direction": "long",            # long | trend
        "trend_hours": 100.0,           # EMA length in HOURS (converted to bars); 0 = off
        "min_day_ret": None,            # bps the session must be up (None = off)
        "entry_bars_before_close": 2,   # signal bar index from the close (fill one bar later)
        "session_close": None,          # IST minutes; None = MCX schedule (23:30 / 23:55)
    }
    session_flat = False
    warmup_columns = ("atr",)

    def compute(self, df: pd.DataFrame, direction: str = "long", trend_hours: float = 100.0,
                min_day_ret: float | None = None, entry_bars_before_close: int = 2,
                session_close: int | None = None) -> pd.DataFrame:
        out = df.copy()
        c = out["close"]
        tf = bar_minutes(out)
        to_close = bars_to_session_close(out, session_close)
        k = max(1, int(entry_bars_before_close))
        signal_bar = to_close == k
        last_bar = to_close == 0

        if trend_hours and trend_hours > 0:
            n = max(2, int(round(float(trend_hours) * 60.0 / tf)))
            e = ema(c, n)
            up, dn = c > e, c < e
        else:
            e = pd.Series(float("nan"), index=out.index)
            up = pd.Series(True, index=out.index)
            dn = pd.Series(False, index=out.index)

        long_ok = up
        short_ok = dn if direction == "trend" else pd.Series(False, index=out.index)
        if min_day_ret is not None:
            key = session_key(out)
            day_open = out["open"].groupby(key).transform("first")
            day_ret = (c / day_open - 1.0) * 1e4
            long_ok = long_ok & (day_ret >= float(min_day_ret))
            short_ok = short_ok & (day_ret <= -float(min_day_ret))

        out["atr"] = atr(out, 14)
        out["trendEma"] = e
        out["barsToClose"] = to_close
        out["longEntry"] = (signal_bar & long_ok).fillna(False).astype(bool)
        out["shortEntry"] = (signal_bar & short_ok).fillna(False).astype(bool)
        # exit decision on the session's last bar -> fills at the next session open
        out["longExit"] = last_bar.astype(bool)
        out["shortExit"] = last_bar.astype(bool)
        return out


STRATEGY = SessionGapCarry()
